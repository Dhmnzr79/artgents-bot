"""Deterministic answer slot assembly from service md frontmatter (stage 2)."""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from config import TRIGGERS_COMPILED
from contracts.answer_slots import AnswerSlotKind, AnswerSlotsTelemetry
from core.marketing_loader import load_marketing_config
from core.routing_loader import THRESHOLDS
from query_selector import commercial_info_query

_PROMO_QUERY_RE = re.compile(r"(акци\w*|скидк\w*|промо|спецпредлож\w*)", re.I | re.U)


def doc_meta_has_consult_value(meta: dict | None, *, h3_id: str | None = None) -> bool:
    """When true, consult_nudge LLM prompt is suppressed for this chunk."""
    m = meta if isinstance(meta, dict) else {}
    if str(m.get("consult_value") or "").strip():
        return True
    h3 = str(h3_id or "").strip().lower()
    if not h3:
        return False
    overrides = m.get("h3_overrides") or {}
    if isinstance(overrides, dict):
        entry = overrides.get(h3) or {}
        if isinstance(entry, dict) and str(entry.get("consult_value") or "").strip():
            return True
    return False


def _promo_active(promo: dict | None) -> bool:
    if not isinstance(promo, dict):
        return False
    text = str(promo.get("text") or "").strip()
    if not text:
        return False
    until = promo.get("active_until")
    if not until:
        return True
    try:
        end = date.fromisoformat(str(until).strip()[:10])
        return date.today() <= end
    except ValueError:
        return True


def _effective_slot_fields(meta: dict, h3_id: str | None) -> dict[str, Any]:
    """Doc-level slots with optional h3 override (override wins per field)."""
    clinic_note = str(meta.get("clinic_note") or "").strip() or None
    consult_value = str(meta.get("consult_value") or "").strip() or None
    promo_note = meta.get("promo_note") if isinstance(meta.get("promo_note"), dict) else None

    h3 = str(h3_id or "").strip().lower()
    overrides = meta.get("h3_overrides") or {}
    if h3 and isinstance(overrides, dict):
        entry = overrides.get(h3) or {}
        if isinstance(entry, dict):
            if str(entry.get("clinic_note") or "").strip():
                clinic_note = str(entry.get("clinic_note") or "").strip()
            if str(entry.get("consult_value") or "").strip():
                consult_value = str(entry.get("consult_value") or "").strip()
            if isinstance(entry.get("promo_note"), dict):
                promo_note = entry.get("promo_note")

    return {
        "clinic_note": clinic_note,
        "consult_value": consult_value,
        "promo_note": promo_note if _promo_active(promo_note) else None,
    }


def is_commercial_intent(q: str, route: str | None) -> bool:
    r = (route or "").strip().lower()
    if r == "price_lookup":
        return True
    return commercial_info_query(q) or bool(_PROMO_QUERY_RE.search(q or ""))


def is_promo_blocked(
    *,
    q: str,
    route: str | None,
    meta: dict,
    lead_context: bool,
) -> bool:
    if lead_context:
        return True
    r = (route or "").strip().lower()
    if r in {"price_concern", "lead_flow", "booking_flow"}:
        return True
    doc_id = str(meta.get("doc_id") or "").lower()
    if "__faq__pain" in doc_id or "contraindication" in doc_id:
        return True
    sub = str(meta.get("subtopic") or "").lower()
    if sub in {"pain", "contraindications"}:
        return True
    text = q or ""
    if TRIGGERS_COMPILED["fear_pain"].search(text) or TRIGGERS_COMPILED["safety"].search(text):
        return True
    return False


def _slot_on_cooldown(
    *,
    topic_state: dict,
    slot_key: AnswerSlotKind,
    cooldown_turns: int,
) -> bool:
    slots_last = topic_state.get("slots_last_turn") or {}
    if not isinstance(slots_last, dict):
        return False
    last = slots_last.get(slot_key)
    if last is None:
        return False
    current = int(topic_state.get("doc_turn_count") or 0)
    next_turn = current + 1
    return (next_turn - int(last)) < cooldown_turns


def _marketing_text_limit(meta: dict) -> int:
    cid = meta.get("client_id") if isinstance(meta, dict) else None
    return load_marketing_config(cid).limits.max_text_ingredients


def _slot_priority(kind: AnswerSlotKind) -> int:
    # Promo is already gated to commercial turns, so it wins when eligible.
    return {"promo_note": 0, "consult_value": 1, "clinic_note": 2}.get(kind, 99)


def assemble_answer_slots(
    *,
    meta: dict,
    h3_id: str | None,
    q: str,
    route: str | None,
    topic_state: dict,
    lead_context: bool,
) -> tuple[str, AnswerSlotsTelemetry]:
    """Return append text (paragraphs) and telemetry for meta.answer_slots."""
    cfg = THRESHOLDS.answer_slots
    fields = _effective_slot_fields(meta, h3_id)
    telemetry = AnswerSlotsTelemetry()
    candidates: list[tuple[int, AnswerSlotKind, str]] = []

    if doc_meta_has_consult_value(meta, h3_id=h3_id):
        telemetry.suppressed["consult_nudge"] = "consult_value_in_doc"

    slot_specs: list[tuple[AnswerSlotKind, str | None, int]] = [
        ("clinic_note", fields.get("clinic_note"), cfg.clinic_note_max_chars),
        ("consult_value", fields.get("consult_value"), cfg.consult_value_max_chars),
    ]

    promo_raw = fields.get("promo_note")
    promo_text = str(promo_raw.get("text") or "").strip() if isinstance(promo_raw, dict) else ""
    if promo_text:
        if is_promo_blocked(q=q, route=route, meta=meta, lead_context=lead_context):
            telemetry.suppressed["promo_note"] = "blocked_intent_or_topic"
        elif not is_commercial_intent(q, route):
            telemetry.suppressed["promo_note"] = "not_commercial_intent"
        else:
            slot_specs.append(("promo_note", promo_text, cfg.promo_note_max_chars))

    for kind, raw_text, max_chars in slot_specs:
        text = str(raw_text or "").strip()
        if not text:
            continue
        if _slot_on_cooldown(
            topic_state=topic_state,
            slot_key=kind,
            cooldown_turns=cfg.cooldown_turns,
        ):
            telemetry.skipped_cooldown.append(kind)
            continue
        if len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        candidates.append((len(candidates), kind, text))

    limit = _marketing_text_limit(meta)
    selected = sorted(candidates, key=lambda item: (_slot_priority(item[1]), item[0]))[:limit]
    selected_indexes = {idx for idx, _, _ in selected}
    paragraphs: list[str] = []
    for idx, kind, text in candidates:
        if idx not in selected_indexes:
            telemetry.suppressed[kind] = "text_ingredient_limit"
            continue
        paragraphs.append(text)
        telemetry.appended.append(kind)

    return ("\n\n".join(paragraphs), telemetry)


def merge_deterministic_appends(
    *,
    slots_text: str,
    generator_append_text: str | None,
) -> str:
    parts = [p.strip() for p in (slots_text, generator_append_text or "") if (p or "").strip()]
    return "\n\n".join(parts)
