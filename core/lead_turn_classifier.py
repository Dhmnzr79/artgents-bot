"""Deterministic lead active-turn classifier (intent before slot)."""
from __future__ import annotations

from contracts.lead_turn import LeadContentHint, LeadTurnDecision
from lead_interrupt import (
    LEAD_CANCEL_REF,
    LEAD_PAUSE_REF,
    LEAD_RESUME_REF,
    parse_lead_cancel,
    parse_lead_defer,
    parse_lead_meta_pause,
)
from core.booking_date_defer import should_defer_booking_date_confirmation
from core.lead_phone_input import parse_unambiguous_lead_phone
from name_gate import accept_lead_name
from policy import PRICE_CONCERN_RE, price_intent

_PII_SLOT_STEPS = frozenset({"collecting_name", "collecting_phone"})


def interrupt_kind_for_content_hint(hint: LeadContentHint | None) -> str:
    _CONTENT_HINT_TO_INTERRUPT = {
        "price": "price",
        "contacts": "contacts",
        "pain": "generic",
        "generic": "generic",
    }
    if not hint:
        return "generic"
    return _CONTENT_HINT_TO_INTERRUPT.get(hint, "generic")


def _resume_step(st: dict) -> str:
    return (st.get("lead_intent") or "collecting_name").strip()


def _classify_slot(q: str, *, resume_step: str) -> LeadTurnDecision | None:
    step = (resume_step or "").strip()
    if step == "collecting_phone":
        phone = parse_unambiguous_lead_phone(q)
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

    collecting_name / collecting_phone: no content heuristics and no gray LLM.
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

    slot = _classify_slot(s, resume_step=step)
    if slot is not None:
        return slot

    if step in _PII_SLOT_STEPS:
        if s:
            return LeadTurnDecision(kind="pending_interrupt", confidence=0.9)
        return LeadTurnDecision(kind="unclear", confidence=0.4)

    from lead_interrupt import detect_lead_interrupt

    kind = detect_lead_interrupt(s, resume_step=step)
    if kind:
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

    return LeadTurnDecision(kind="unclear", confidence=0.3)
