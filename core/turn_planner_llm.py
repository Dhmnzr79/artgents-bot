"""Single flash turn planner (full-context roadmap stage 4)."""

from __future__ import annotations

import json
from typing import Any

from config import TURN_PLANNER_LLM_MODEL
from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.turn_plan import TurnPlan
from contracts.answer_plan import AspectKind
from core.pricebook_loader import list_pricebook_service_ids, load_pricebook_service
from core.service_selector_llm import build_compact_service_catalog, _read_service_catalog
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create
from session import format_dialog_context_for_understanding, recent_dialog_history

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
    "aspects: подмножество price, payment, warranty, pain, included, duration, comparison, stages, overview.\n"
    "service_id: id услуги текущего хода из каталога или null.\n"
    "followup_of: service_id предыдущего фокуса, только если текущий вопрос продолжает его; иначе null. "
    "Для продолжения «а сколько стоит?» после All-on-4 верни followup_of=all_on_4 и service_id=all_on_4. "
    "Для смены темы «а виниры сколько?» после All-on-4 верни followup_of=null и service_id=veneers.\n"
    "needs_clarify: true только когда без уточнения нельзя выбрать безопасный маршрут.\n"
    "patient_situation: один enum kind ситуации пациента или null.\n"
    "brand_filter: null или объект {brand_group, brand}; используй только явно запрошенный бренд/группу.\n"
    "Не добавляй query_rewrite и любые другие поля. Верни только JSON без markdown."
)


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
) -> TurnPlan | None:
    plan = TurnPlan.model_validate(raw)
    plan = plan.model_copy(update={"aspects": order_plan_aspects(list(plan.aspects))})
    for field in ("service_id", "followup_of"):
        value = str(getattr(plan, field) or "").strip()
        if value and value not in allowed_service_ids:
            raise ValueError(f"turn_plan_{field}_not_in_catalog")
    if plan.brand_filter is not None:
        group = str(plan.brand_filter.brand_group or "").strip().lower()
        brand = str(plan.brand_filter.brand or "").strip().lower()
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
        )
        if plan is None:
            raise ValueError("turn_plan_invalid")
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
