"""Deterministic lead active-turn classifier (intent before slot)."""
from __future__ import annotations

from contracts.lead_turn import LeadContentHint, LeadTurnDecision
from core.lead_turn_llm import classify_lead_turn_gray_zone
from lead_interrupt import (
    LEAD_CANCEL_REF,
    LEAD_PAUSE_REF,
    LEAD_RESUME_REF,
    detect_lead_interrupt,
    is_ambiguous_short_reply,
    parse_lead_cancel,
    parse_lead_defer,
    parse_lead_meta_pause,
)
from core.booking_date_defer import should_defer_booking_date_confirmation
from name_gate import accept_lead_name
from policy import PRICE_CONCERN_RE, contacts_intent, price_intent
from session import extract_phone, normalize_phone

_CONTENT_HINT_TO_INTERRUPT: dict[str, str] = {
    "price": "price",
    "contacts": "contacts",
    "pain": "generic",
    "generic": "generic",
}


def interrupt_kind_for_content_hint(hint: LeadContentHint | None) -> str:
    if not hint:
        return "generic"
    return _CONTENT_HINT_TO_INTERRUPT.get(hint, "generic")


def _resume_step(st: dict) -> str:
    return (st.get("lead_intent") or "collecting_name").strip()


def _classify_content(q: str, *, resume_step: str) -> LeadTurnDecision | None:
    kind = detect_lead_interrupt(q, resume_step=resume_step)
    if not kind:
        return None
    hint: LeadContentHint
    if kind == "price":
        hint = "price"
    elif kind == "contacts":
        hint = "contacts"
    elif kind == "pain":
        hint = "pain"
    else:
        hint = "generic"
    return LeadTurnDecision(kind="content", content_hint=hint, confidence=1.0)


def _classify_slot(q: str, *, resume_step: str) -> LeadTurnDecision | None:
    step = (resume_step or "").strip()
    if step == "collecting_phone":
        phone = extract_phone(q) or normalize_phone(q)
        if phone:
            return LeadTurnDecision(kind="slot", slot_value=phone, confidence=1.0)
        return None
    if step in {"collecting_name", "confirming_name"}:
        name = accept_lead_name(q)
        if name:
            return LeadTurnDecision(kind="slot", slot_value=name, confidence=1.0)
    return None


def classify_lead_active_turn(
    q: str,
    *,
    ref: str = "",
    st: dict,
    sid: str | None = None,
    client_id: str | None = None,
) -> LeadTurnDecision:
    """
    Classify user turn during LEAD_ACTIVE (not LEAD_PAUSED resume ref-only paths).

    Order: ref/meta → cancel/defer/pause → content → slot → gray LLM → unclear.
    """
    s = (q or "").strip()
    r = (ref or "").strip()
    step = _resume_step(st)

    if r == LEAD_CANCEL_REF or parse_lead_cancel(s):
        return LeadTurnDecision(kind="meta_cancel", confidence=1.0)
    if r == LEAD_PAUSE_REF or parse_lead_meta_pause(s):
        return LeadTurnDecision(kind="meta_pause", confidence=1.0)
    if r == LEAD_RESUME_REF:
        return LeadTurnDecision(kind="meta_resume", confidence=1.0)

    if parse_lead_defer(s) or (PRICE_CONCERN_RE.search(s) and not price_intent(s)):
        return LeadTurnDecision(kind="defer", confidence=0.85)

    if should_defer_booking_date_confirmation(q=s, client_id=client_id, resume_step=step, sid=sid):
        return LeadTurnDecision(kind="booking_date", confidence=1.0)

    content = _classify_content(s, resume_step=step)
    if content is not None:
        return content

    slot = _classify_slot(s, resume_step=step)
    if slot is not None:
        return slot

    gray = classify_lead_turn_gray_zone(
        s,
        lead_step=step,
        client_id=client_id,
        sid=sid,
    )
    if gray is not None:
        return gray

    if is_ambiguous_short_reply(s):
        return LeadTurnDecision(kind="unclear", confidence=0.4)

    if s and step in {"collecting_name", "confirming_name", "collecting_phone"}:
        if step == "collecting_phone" and not extract_phone(s):
            return LeadTurnDecision(kind="unclear", confidence=0.5)
        if step in {"collecting_name", "confirming_name"} and not accept_lead_name(s):
            if contacts_intent(s) or price_intent(s):
                return LeadTurnDecision(kind="unclear", confidence=0.3)
            return LeadTurnDecision(kind="unclear", confidence=0.55)

    return LeadTurnDecision(kind="unclear", confidence=0.3)
