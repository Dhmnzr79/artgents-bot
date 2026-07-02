"""Single flash turn planner (full-context roadmap stage 4)."""

from __future__ import annotations

import json
from typing import Any

from config import TURN_PLANNER_LLM_MODEL
from contracts.turn_plan import TurnPlan
from core.pricebook_loader import list_pricebook_service_ids, load_pricebook_service
from core.service_selector_llm import build_compact_service_catalog
from logging_setup import get_logger, log_json, log_llm_error, log_llm_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create
from session import format_dialog_context_for_understanding, recent_dialog_history

logger = get_logger(__name__)

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


def _validate_plan(
    raw: dict[str, Any],
    *,
    allowed_service_ids: frozenset[str],
    allowed_brand_groups: frozenset[str],
    allowed_brands: frozenset[str],
) -> TurnPlan | None:
    plan = TurnPlan.model_validate(raw)
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
