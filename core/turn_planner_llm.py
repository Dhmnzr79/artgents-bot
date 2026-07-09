"""Single flash turn planner (full-context roadmap stage 4)."""

from __future__ import annotations

import json
from typing import Any

from config import CLARIFY_STATE_ON, TURN_PLANNER_LLM_MODEL
from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.turn_plan import TurnPlan
from contracts.answer_plan import AspectKind
from core.pricebook_loader import list_pricebook_service_ids, load_pricebook_service
from core.service_selector_llm import build_compact_service_catalog, _read_service_catalog
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create
from session import format_dialog_context_for_understanding, get_pending_clarify, recent_dialog_history

logger = get_logger(__name__)

_ASPECT_PRIORITY: tuple[AspectKind, ...] = (
    "price",
    "payment",
    "included",
    "warranty",
    "pain",
    "duration",
    "comparison",
    "stages",
    "overview",
)

_SYSTEM = (
    "Ты единый планировщик одного хода диалога для стоматологического чата. "
    "Ты НЕ отвечаешь пациенту и НЕ называешь цены. Ты только возвращаешь JSON-план.\n"
    "Поля JSON строго такие: route, aspects, service_id, followup_of, needs_clarify, "
    "patient_situation, brand_filter.\n"
    "route: content | price_lookup | price_concern | unknown.\n"
    "aspects: подмножество price, payment, warranty, pain, included, duration, comparison, stages, overview. "
    "comparison — когда пациент сравнивает варианты или спрашивает «X вместо Y», "
    "«X — это то же, что Y?», «чем X отличается от Y».\n"
    "service_id: id услуги текущего хода из каталога или null. "
    "Для размытых ценовых вопросов про имплантацию без названного протокола "
    "(«сколько стоит имплантация», «сколько стоит имплантация зуба», «поставить имплант») "
    "верни service_id=null — пациенту покажут обзор протоколов, не решай протокол за него. "
    "Конкретную услугу возвращай, когда она названа (all-on-4, классическая, виниры) "
    "или однозначна из контекста диалога.\n"
    "followup_of: service_id предыдущего фокуса, только если текущий вопрос продолжает его; иначе null. "
    "Для продолжения «а сколько стоит?» после All-on-4 верни followup_of=all_on_4 и service_id=all_on_4. "
    "Для смены темы «а виниры сколько?» после All-on-4 верни followup_of=null и service_id=veneers.\n"
    "needs_clarify: true только когда вопрос одинаково подходит к НЕСКОЛЬКИМ услугам каталога "
    "с разными ценами, контекст диалога не помогает выбрать, и пациент сам легко ответил бы, "
    "какая из них его — тогда верни service_id=null и needs_clarify=true. "
    "Пример: «сколько стоит коронка» без контекста — это и коронка на свой зуб, и коронка на имплант "
    "(разные услуги и цены) → service_id=null, needs_clarify=true. "
    "НЕ ставь needs_clarify, если различие определяет врач (диагноз, состояние кости) "
    "или если в диалоге уже ясно, о чём речь.\n"
    "patient_situation: один enum kind ситуации пациента или null.\n"
    "brand_filter: null или объект {brand_group, brand}; только если пациент ЯВНО назвал бренд "
    "или группу (Nobel, Impro, корейские, немецкие). НЕ выводи brand_filter из «дешевле», "
    "«подешевле», «бюджет», «доступные» — это не бренд.\n"
    "Не добавляй query_rewrite и любые другие поля. Верни только JSON без markdown."
)


def _implantation_tagged_service_ids(client_id: str | None) -> frozenset[str]:
    """Pricebook services tagged 'implantation' (data-driven protocol group)."""
    out: set[str] = set()
    for service_id in list_pricebook_service_ids(client_id):
        entry = load_pricebook_service(client_id, service_id)
        if not entry:
            continue
        tags = [str(t or "").strip().lower() for t in (entry.tags or [])]
        if "implantation" in tags:
            out.add(service_id)
    return frozenset(out)


def _session_focus_service_id(sid: str | None) -> str | None:
    """Текущий фокус диалога из сессии (last_subject с age-гардом) — детерминированное
    подтверждение контекста, не зависящее от того, заполнила ли модель followup_of."""
    if not (sid or "").strip():
        return None
    try:
        from core.dialog_focus import _focus_from_last_subject
        from session import mem_get

        focus, _age = _focus_from_last_subject(mem_get(sid))
        if focus:
            return str(focus.get("service_id") or "").strip() or None
    except Exception:
        return None
    return None


def _apply_focus_followup_enrichment(plan: TurnPlan, *, q: str, sid: str | None) -> TurnPlan:
    """Детерминированное разрешение смутного follow-up («кто делает?», «а сколько
    стоит?») по фокусу сессии, когда модель не заполнила service_id/followup_of.
    Зеркало protocol-guard: гард понижает недоказанное, обогащение поднимает
    доказанное кодом (last_subject + age-гард + боевой детектор attribute_followup)."""
    if plan.service_id or plan.followup_of:
        return plan
    focus = _session_focus_service_id(sid)
    if not focus:
        return plan
    from core.attribute_followup import is_vague_attribute_followup_any

    if not is_vague_attribute_followup_any(q):
        return plan
    log_json(
        logger,
        "turn_plan_focus_followup_enriched",
        sid=sid,
        service_id=focus,
    )
    return plan.model_copy(update={"service_id": focus, "followup_of": focus})


def _apply_protocol_choice_guard(
    plan: TurnPlan, *, q: str, client_id: str | None, sid: str | None = None
) -> TurnPlan:
    """Не решать имплант-протокол за пациента (детерминированно, поверх LLM).

    Услуга имплант-группы в плане остаётся только если пациент сам назвал
    протокол, продолжает предыдущий фокус (followup_of от модели ИЛИ фокус
    сессии — детерминированный) или речь про коронку на уже установленный
    имплант. Иначе service_id → None: пациент получит обзор вариантов /
    ответ из базы, а не навязанный протокол.
    """
    svc = str(plan.service_id or "").strip()
    if not svc or plan.followup_of:
        return plan
    if svc == (_session_focus_service_id(sid) or ""):
        return plan
    if svc not in _implantation_tagged_service_ids(client_id):
        return plan
    from core.patient_scope_cues import (
        CROWN_ON_IMPLANT_RX,
        EXISTING_IMPLANT_RX,
        query_names_specific_implant_protocol,
    )

    text = (q or "").strip()
    if query_names_specific_implant_protocol(text):
        return plan
    if EXISTING_IMPLANT_RX.search(text) or CROWN_ON_IMPLANT_RX.search(text):
        return plan
    # Выбор из вариантов, предложенных ботом (pending clarify) — сильнейшее
    # доказательство контекста: пациент явно ткнул/назвал вариант.
    try:
        from session import get_pending_clarify

        pending = get_pending_clarify(sid) if (sid or "").strip() else None
        if isinstance(pending, dict) and svc in {
            str(x or "").strip() for x in (pending.get("option_service_ids") or [])
        }:
            return plan
    except Exception:
        pass
    log_json(
        logger,
        "turn_plan_service_downgraded",
        client_id=client_id,
        service_id=svc,
        reason="implant_protocol_not_named",
    )
    return plan.model_copy(update={"service_id": None})


def _allowed_pricebook_filters(client_id: str | None) -> tuple[frozenset[str], frozenset[str]]:
    groups: set[str] = set()
    brands: set[str] = set()
    for service_id in list_pricebook_service_ids(client_id):
        entry = load_pricebook_service(client_id, service_id)
        if not entry:
            continue
        for variant in entry.variants:
            group = str(variant.brand_group or "").strip().lower()
            brand = str(variant.brand or "").strip().lower()
            if group:
                groups.add(group)
            if brand:
                brands.add(brand)
    return frozenset(groups), frozenset(brands)


def _catalog_lines(rows: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for row in rows:
        sid = row["service_id"]
        title = row["title"]
        about = row["about"]
        suffix = f" — {about}" if about and about != title else ""
        lines.append(f"- {sid}: {title}{suffix}")
    return "\n".join(lines)


def _pending_clarify_prompt_block(
    *,
    sid: str | None,
    client_id: str | None,
) -> str:
    if not CLARIFY_STATE_ON or not (sid or "").strip():
        return ""
    pending = get_pending_clarify(str(sid))
    if not isinstance(pending, dict):
        return ""
    question = str(pending.get("question") or "").strip()
    option_ids = [
        str(x or "").strip()
        for x in list(pending.get("option_service_ids") or [])
        if str(x or "").strip()
    ]
    if not question or not option_ids:
        return ""
    from core.clarify_state import (
        TURN_PLANNER_PENDING_CLARIFY_INSTRUCTION,
        pending_options_line,
    )

    options = pending_options_line(client_id=client_id, option_service_ids=option_ids)
    if not options:
        return ""
    return (
        TURN_PLANNER_PENDING_CLARIFY_INSTRUCTION.format(
            question=json.dumps(question, ensure_ascii=False),
            options=options,
        )
        + "\n\n"
    )


def order_plan_aspects(aspects: list[AspectKind]) -> list[AspectKind]:
    uniq: list[AspectKind] = []
    for aspect in _ASPECT_PRIORITY:
        if aspect in aspects and aspect not in uniq:
            uniq.append(aspect)
    for aspect in aspects:
        if aspect not in uniq:
            uniq.append(aspect)
    return uniq


def _validate_plan(
    raw: dict[str, Any],
    *,
    allowed_service_ids: frozenset[str],
    allowed_brand_groups: frozenset[str],
    allowed_brands: frozenset[str],
    client_id: str | None = None,
) -> TurnPlan | None:
    plan = TurnPlan.model_validate(raw)
    plan = plan.model_copy(update={"aspects": order_plan_aspects(list(plan.aspects))})
    for field in ("service_id", "followup_of"):
        value = str(getattr(plan, field) or "").strip()
        if value and value not in allowed_service_ids:
            raise ValueError(f"turn_plan_{field}_not_in_catalog")
    if plan.brand_filter is not None:
        group = str(plan.brand_filter.brand_group or "").strip().lower()
        brand_raw = str(plan.brand_filter.brand or "").strip()
        brand = brand_raw.lower()
        if brand_raw:
            from core.price_offers import canonical_brand_name

            canon = canonical_brand_name(brand_raw, client_id=client_id)
            if canon:
                brand_raw = canon
                brand = canon.strip().lower()
                plan = plan.model_copy(
                    update={
                        "brand_filter": plan.brand_filter.model_copy(update={"brand": canon}),
                    }
                )
        if group and group not in allowed_brand_groups:
            raise ValueError("turn_plan_brand_group_not_in_pricebook")
        if brand and brand not in allowed_brands:
            raise ValueError("turn_plan_brand_not_in_pricebook")
    return plan


def _service_topic_for_plan(client_id: str | None, service_id: str | None) -> str:
    sid = (service_id or "").strip()
    if not sid:
        return "unknown"
    catalog = _read_service_catalog(client_id)
    entry = catalog.get(sid) if isinstance(catalog, dict) else None
    ref = ""
    if isinstance(entry, dict):
        ref = str(entry.get("md_entry_ref") or entry.get("price_ref") or "").strip().lower()
    if ref.startswith("implantation__") or sid in {
        "classic",
        "one_stage",
        "all_on_4",
        "all_on_6",
        "zygomatic_implants",
        "pterygoid_implants",
        "sinus_lift",
        "implant_supported_prosthetics",
    }:
        return "implantation"
    if ref.startswith("prosthetics__") or sid in {
        "veneers",
        "zirconia_crowns",
        "removable_dentures",
        "clasp_dentures",
        "temporary_teeth",
    }:
        return "prosthetics"
    if ref.startswith("clinic__"):
        return "clinic"
    if ref.startswith("doctors__"):
        return "doctors"
    return "unknown"


def _query_mode_for_plan(plan: TurnPlan) -> str:
    aspects = set(plan.aspects or [])
    if "comparison" in aspects:
        return "comparison"
    if "stages" in aspects:
        return "process"
    if aspects == {"overview"}:
        return "overview"
    return "specific"


def turn_plan_to_decision_frame(plan: TurnPlan, *, client_id: str | None) -> DecisionFrame:
    """Materialize a resolver-compatible frame so downstream guards stay unchanged."""
    service_id = str(plan.service_id or "").strip() or None
    topic = _service_topic_for_plan(client_id, service_id)
    service_conf = 0.9 if service_id else 0.0
    topic_conf = 0.85 if topic != "unknown" else 0.0
    return DecisionFrame(
        route_intent=plan.route,
        service_topic=topic,  # type: ignore[arg-type]
        service_id=service_id,
        query_mode=_query_mode_for_plan(plan),  # type: ignore[arg-type]
        confidence=DecisionFrameConfidence(
            intent=0.9 if plan.route != "unknown" else 0.0,
            topic=topic_conf,
            service=service_conf,
            query_mode=0.85,
        ),
        needs_clarification=bool(plan.needs_clarify),
    )


def publish_turn_plan(plan: TurnPlan) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            request.ctx["turn_plan"] = plan.model_dump()
            request.ctx["turn_planner_used"] = True
            request.ctx["turn_plan_route"] = plan.route
            request.ctx["turn_plan_aspects"] = list(plan.aspects)
            request.ctx["turn_plan_service_id"] = plan.service_id
            request.ctx["turn_plan_followup_of"] = plan.followup_of
            request.ctx["turn_plan_needs_clarify"] = plan.needs_clarify
            request.ctx["turn_plan_patient_situation"] = plan.patient_situation
            if plan.brand_filter is not None:
                request.ctx["turn_plan_brand_filter"] = plan.brand_filter.model_dump()
    except Exception:
        pass


def turn_plan_from_ctx() -> TurnPlan | None:
    try:
        from flask import has_request_context, request

        if not has_request_context() or not isinstance(getattr(request, "ctx", None), dict):
            return None
        raw = request.ctx.get("turn_plan")
        if not isinstance(raw, dict):
            return None
        return TurnPlan.model_validate(raw)
    except Exception:
        return None


def turn_plan_brand_filter_from_ctx() -> tuple[str | None, str | None]:
    plan = turn_plan_from_ctx()
    if plan is None or plan.brand_filter is None:
        return None, None
    brand = str(plan.brand_filter.brand or "").strip() or None
    brand_group = str(plan.brand_filter.brand_group or "").strip().lower() or None
    return brand, brand_group


def plan_turn(q: str, sid: str | None, client_id: str | None) -> TurnPlan | None:
    """Plan one turn with one flash LLM call. Returns None for fail-open."""
    msg = (q or "").strip()
    if not msg:
        return None
    rows = build_compact_service_catalog(client_id)
    if not rows:
        return None
    allowed_ids = frozenset(r["service_id"] for r in rows)
    allowed_groups, allowed_brands = _allowed_pricebook_filters(client_id)
    hist = recent_dialog_history(sid) if sid else ""
    brand_hint = ""
    if allowed_groups or allowed_brands:
        brand_hint = (
            "Разрешенные brand_group: "
            f"{', '.join(sorted(allowed_groups)) or 'нет'}.\n"
            "Разрешенные brand: "
            f"{', '.join(sorted(allowed_brands)) or 'нет'}.\n\n"
        )
    user_content = (
        f"Каталог услуг:\n{_catalog_lines(rows)}\n\n"
        f"{brand_hint}"
        f"{format_dialog_context_for_understanding(hist)}"
        f"{_pending_clarify_prompt_block(sid=sid, client_id=client_id)}"
        f"Вопрос пациента:\n{msg[:900]}"
    )
    try:
        resp = chat_completions_create(
            model=TURN_PLANNER_LLM_MODEL,
            temperature=0,
            max_completion_tokens=300,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        log_llm_usage(logger, resp, call_type="turn_planner_plan", model=TURN_PLANNER_LLM_MODEL)
        raw_text = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw_text)
        if not isinstance(obj, dict):
            raise ValueError("turn_plan_not_object")
        plan = _validate_plan(
            obj,
            allowed_service_ids=allowed_ids,
            allowed_brand_groups=allowed_groups,
            allowed_brands=allowed_brands,
            client_id=client_id,
        )
        if plan is None:
            raise ValueError("turn_plan_invalid")
        plan = _apply_protocol_choice_guard(plan, q=msg, client_id=client_id, sid=sid)
        plan = _apply_focus_followup_enrichment(plan, q=msg, sid=sid)
        log_json(
            logger,
            "turn_planner_llm",
            client_id=client_id,
            sid=sid,
            route=plan.route,
            aspects=plan.aspects,
            service_id=plan.service_id,
            followup_of=plan.followup_of,
            needs_clarify=plan.needs_clarify,
            patient_situation=plan.patient_situation,
            brand_filter=plan.brand_filter.model_dump() if plan.brand_filter else None,
        )
        return plan
    except Exception as e:
        log_llm_error(
            logger,
            call_type="turn_planner_plan",
            err=str(e),
            model=TURN_PLANNER_LLM_MODEL,
        )
        log_json(
            logger,
            "turn_planner_failed",
            client_id=client_id,
            sid=sid,
            err=str(e)[:300],
        )
        return None
