"""Request-scoped flags for lead-context content turns (pause / interrupt)."""
from __future__ import annotations

from contextvars import ContextVar

_provider_question_var: ContextVar[str | None] = ContextVar(
    "lead_provider_question_turn", default=None
)


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


def bind_lead_provider_question(text: str) -> None:
    safe = (text or "").strip()
    if not safe:
        return
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["lead_provider_question"] = safe
    except Exception:
        pass
    _provider_question_var.set(safe)


def take_lead_provider_question() -> str | None:
    q: str | None = None
    try:
        from flask import has_request_context, request

        if has_request_context():
            raw = request.ctx.pop("lead_provider_question", None)
            if raw:
                q = str(raw).strip() or None
    except Exception:
        pass
    if not q:
        try:
            q = _provider_question_var.get()
        except LookupError:
            q = None
    _provider_question_var.set(None)
    return q


def clear_lead_provider_question_turn() -> None:
    _provider_question_var.set(None)
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx.pop("lead_provider_question", None)
    except Exception:
        pass
