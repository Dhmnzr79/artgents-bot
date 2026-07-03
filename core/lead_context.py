"""Request-scoped flags for lead-context content turns (pause / interrupt)."""
from __future__ import annotations


def bind_lead_context_turn(
    *,
    interrupt_no_topic: bool = True,
    interrupt_kind: str | None = None,
) -> None:
    try:
        from flask import has_request_context, request
    except Exception:
        return
    if not has_request_context():
        return
    request.ctx["lead_context_turn"] = True
    if interrupt_no_topic:
        request.ctx["lead_interrupt_no_topic"] = True
    if interrupt_kind:
        request.ctx["lead_interrupt_kind"] = str(interrupt_kind).strip() or None


def lead_interrupt_no_topic() -> bool:
    try:
        from flask import has_request_context, request
    except Exception:
        return False
    if not has_request_context():
        return False
    return bool(request.ctx.get("lead_interrupt_no_topic"))


def lead_interrupt_kind() -> str | None:
    try:
        from flask import has_request_context, request
    except Exception:
        return None
    if not has_request_context():
        return None
    raw = request.ctx.get("lead_interrupt_kind")
    return str(raw).strip() if raw else None
