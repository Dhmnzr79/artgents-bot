"""Single flash turn planner (full-context roadmap stage 4)."""

from __future__ import annotations

import json
from typing import Any

from config import TURN_PLANNER_LLM_MODEL
from contracts.planner_attempt import PlannerAttempt, turn_frame_has_invalid_or_missing
from contracts.turn_plan import TurnPlan
from core.pricebook_loader import list_pricebook_service_ids, load_pricebook_service
from core.service_selector_llm import build_compact_service_catalog
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.topic_taxonomy import load_client_topic_taxonomy
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_client, chat_completions_create
from session import format_dialog_context_for_understanding, recent_dialog_history

logger = get_logger(__name__)

_TURN_PLANNER_MAX_COMPLETION_TOKENS = 700

_PATIENT_SCOPE_PROMPT = (
    "patient_scope: верни компактный объект ровно с четырьмя ключами extent, jaw, stage, modifiers. "
    "extent: unknown | one_tooth | few_teeth | full_arch; jaw: unknown | upper | lower | both; "
    "stage: unknown | natural_tooth_present | extraction_context | implant_placed; modifiers: [] или [reported_bone_deficit]. "
    "Всегда верни все четыре ключа. Извлекай только явно сообщённые признаки текущего сообщения; "
    "если признак не сообщён — unknown или [], не угадывай. История может помочь понять referent, "
    "но не переноси старое scope-значение без явного упоминания в текущем сообщении. "
    "patient_situation верни отдельно по legacy enum. Patient scope не выбирает service, protocol, "
    "price unit, document, evidence или diagnosis; urgency и pain не входят в patient scope. "
    "reported_bone_deficit означает сообщённый контекст, не клиническое подтверждение. "
    "Не добавляй другие ключи внутрь patient_scope.\n"
)

_SYSTEM = (
    "Ты единый планировщик одного хода диалога для стоматологического чата. "
    "Ты НЕ отвечаешь пациенту и НЕ называешь цены. Ты только возвращаешь JSON-план.\n"
    "Поля JSON строго такие: route, aspects, service_id, followup_of, needs_clarify, "
    "patient_situation, patient_scope, brand_filter, topic, topic_confidence.\n"
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
    + _PATIENT_SCOPE_PROMPT
    + "brand_filter: null или объект {brand_group, brand}; только если пациент ЯВНО назвал бренд "
    "или группу (Nobel, Impro, корейские, немецкие). НЕ выводи brand_filter из «дешевле», "
    "«подешевле», «бюджет», «доступные» — это не бренд.\n"
    "topic: одна предметная область из списка разрешённых topics в user-сообщении или null. "
    "Не aspect, не subtopic, не service_id и не doc_id.\n"
    "topic_confidence: число 0..1; при topic=null обязательно 0.0. "
    "Если область неоднозначна — topic=null, topic_confidence=0.0; не угадывай.\n"
    "Не добавляй query_rewrite и любые другие поля. Верни только JSON без markdown."
)


def _planner_completion_controls() -> dict[str, Any]:
    controls: dict[str, Any] = {
        "max_completion_tokens": _TURN_PLANNER_MAX_COMPLETION_TOKENS,
    }
    if "qwen" in TURN_PLANNER_LLM_MODEL.lower():
        controls["extra_body"] = {"enable_thinking": False}
    return controls


def _planner_chat_completions_create(**kwargs: Any):
    """Keep Qwen controls model-aware when the planner model is overridden."""
    model = str(kwargs.get("model") or "").lower()
    if "qwen" in model:
        return chat_completions_create(**kwargs)
    return chat_client.chat.completions.create(**kwargs)



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


def _topics_prompt_block(allowed_topics: frozenset[str]) -> str:
    if allowed_topics:
        return (
            "Разрешенные topics (предметные области):\n"
            f"{', '.join(sorted(allowed_topics))}.\n\n"
        )
    return (
        "Разрешенные topics для этого client pack сейчас недоступны. "
        "Верни topic=null и topic_confidence=0.0.\n\n"
    )


def _resolve_allowed_topics(client_id: str | None, *, sid: str | None) -> frozenset[str]:
    try:
        return load_client_topic_taxonomy(client_id)
    except Exception:
        log_json(
            logger,
            "turn_plan_topic_sanitized",
            client_id=client_id,
            sid=sid,
            reason="topic_taxonomy_unavailable",
        )
        return frozenset()


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


def _not_available_attempt() -> PlannerAttempt:
    return PlannerAttempt(frame=None, status="not_available")


def _log_turn_planner_failure(
    error: Exception,
    *,
    client_id: str | None,
    sid: str | None,
) -> None:
    log_llm_error(
        logger,
        call_type="turn_planner_plan",
        err=str(error),
        model=TURN_PLANNER_LLM_MODEL,
    )
    log_json(
        logger,
        "turn_planner_failed",
        client_id=client_id,
        sid=sid,
        err=str(error)[:300],
    )


def plan_turn_attempt(
    q: str,
    sid: str | None,
    client_id: str | None,
) -> PlannerAttempt:
    """Run one planner call and build native TurnFrame only (C2b)."""
    msg = (q or "").strip()
    if not msg:
        return _not_available_attempt()
    rows = build_compact_service_catalog(client_id)
    if not rows:
        return _not_available_attempt()
    allowed_ids = frozenset(r["service_id"] for r in rows)
    allowed_groups, allowed_brands = _allowed_pricebook_filters(client_id)
    allowed_topics = _resolve_allowed_topics(client_id, sid=sid)
    hist = recent_dialog_history(sid) if sid else ""
    brand_hint = ""
    if allowed_groups or allowed_brands:
        brand_hint = (
            "Разрешенные brand_group: "
            f"{', '.join(sorted(allowed_groups)) or 'нет'}.\n"
            "Разрешенные brand: "
            f"{', '.join(sorted(allowed_brands)) or 'нет'}.\n\n"
        )
    topics_hint = _topics_prompt_block(allowed_topics)
    user_content = (
        f"Каталог услуг:\n{_catalog_lines(rows)}\n\n"
        f"{brand_hint}"
        f"{topics_hint}"
        f"{format_dialog_context_for_understanding(hist)}"
        f"Вопрос пациента:\n{msg[:900]}"
    )
    try:
        resp = _planner_chat_completions_create(
            model=TURN_PLANNER_LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            **_planner_completion_controls(),
        )
        log_llm_usage(logger, resp, call_type="turn_planner_plan", model=TURN_PLANNER_LLM_MODEL)
        raw_text = (resp.choices[0].message.content or "").strip()
        obj = json.loads(raw_text)
        if not isinstance(obj, dict):
            raise ValueError("turn_plan_not_object")
    except Exception as error:
        _log_turn_planner_failure(error, client_id=client_id, sid=sid)
        return _not_available_attempt()

    frame = None
    build_degraded = False
    try:
        frame = build_turn_frame_from_raw(
            obj,
            allowed_topics=allowed_topics,
            allowed_service_ids=allowed_ids,
        )
    except Exception:
        frame = None
        build_degraded = True
        try:
            log_json(
                logger,
                "turn_planner_frame_degraded",
                client_id=client_id,
                sid=sid,
                reason="turn_frame_build_failed",
            )
        except Exception:
            pass

    if build_degraded:
        return PlannerAttempt(frame=None, status="degraded")
    if frame is None:
        raise AssertionError("frame_missing_without_degraded")
    status = "partial" if turn_frame_has_invalid_or_missing(frame) else "ok"
    log_json(
        logger,
        "turn_planner_llm",
        client_id=client_id,
        sid=sid,
        route=frame.intent,
        aspects=frame.aspects,
        service_id=frame.service_id,
        followup_of=frame.followup_of,
        needs_clarify=frame.needs_clarification,
        topic=frame.topic,
    )
    return PlannerAttempt(frame=frame, status=status)
