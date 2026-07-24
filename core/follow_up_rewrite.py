"""Follow-up rewrite: short attribute replies + session focus → retrieval query."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from core.client_config_loader import _pack_path
from core.routing_loader import THRESHOLDS
from core.service_followup import is_short_attribute_followup, normalize_service_id
from core.target_runtime_session import (
    clear_target_service_focus,
    focus_dict_from_session_state,
    read_age_guarded_service_focus,
)

_PAYMENT_RE = re.compile(r"\b(рассроч|оплат|кредит|цен)\w*\b", re.I | re.U)
_WARRANTY_RE = re.compile(r"\bгарант\w*\b", re.I | re.U)
_PAIN_RE = re.compile(
    r"\b(больно|болит|боль|анестез|обезбол|безболезнен)\w*\b",
    re.I | re.U,
)
_CONTACTS_RE = re.compile(
    r"\b(адрес|контакт|телефон|график|расписан|как\s+доехать|где\s+наход)\w*\b",
    re.I | re.U,
)
_DURATION_RE = re.compile(
    r"\b(долго|длительн|сколько\s+времени|по\s+времени|срок|сроки|месяц|недел)\w*\b",
    re.I | re.U,
)
_INCLUDED_RE = re.compile(
    r"\b(под\s+ключ|что\s+входит|входит\s+в|не\s+входит|включено|состав)\b",
    re.I | re.U,
)
_DIALOG_FOCUS_REWRITE_ATTRS = frozenset(
    {"duration", "pain", "warranty", "payment", "included", "general"}
)


@dataclass(frozen=True)
class FollowUpTurnContext:
    follow_up_mode: bool
    rewritten_query: str
    focus: dict[str, str]
    service_focus_age: int


def follow_up_ctx_to_dict(ctx: FollowUpTurnContext) -> dict[str, Any]:
    return {
        "follow_up_mode": ctx.follow_up_mode,
        "rewritten_query": ctx.rewritten_query,
        "focus": dict(ctx.focus),
        "service_focus_age": ctx.service_focus_age,
    }


def follow_up_ctx_from_dict(raw: dict[str, Any] | None) -> FollowUpTurnContext | None:
    if not isinstance(raw, dict) or not raw.get("follow_up_mode"):
        return None
    focus = raw.get("focus")
    if not isinstance(focus, dict) or not str(focus.get("service_id") or "").strip():
        return None
    rewritten = str(raw.get("rewritten_query") or "").strip()
    if not rewritten:
        return None
    return FollowUpTurnContext(
        follow_up_mode=True,
        rewritten_query=rewritten,
        focus={
            "service_id": str(focus.get("service_id") or "").strip(),
            "topic": str(focus.get("topic") or "").strip(),
            "label": str(focus.get("label") or focus.get("service_id") or "").strip(),
            "last_route": str(focus.get("last_route") or "").strip(),
        },
        service_focus_age=int(raw.get("service_focus_age") or 0),
    )


def _read_catalog(client_id: str | None) -> dict[str, Any]:
    if not client_id:
        return {}
    path = _pack_path(client_id, "service_catalog.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def catalog_service_label(client_id: str | None, service_id: str | None) -> str | None:
    sid = normalize_service_id(service_id)
    if not sid:
        return None
    entry = _read_catalog(client_id).get(sid)
    if isinstance(entry, dict):
        title = str(entry.get("title") or "").strip()
        if title:
            return title
    return sid.replace("_", " ")


def _service_id_from_doc_id(doc_id: str | None) -> str | None:
    raw = (doc_id or "").strip().removesuffix(".md")
    if not raw:
        return None
    parts = raw.split("__")
    if len(parts) >= 3 and parts[1] == "service":
        return normalize_service_id(parts[2])
    return None


def _topic_from_doc_id(doc_id: str | None) -> str | None:
    raw = (doc_id or "").strip().removesuffix(".md")
    if not raw:
        return None
    head = raw.split("__", 1)[0].strip().lower()
    return head or None


def resolve_focus_from_turn(
    *,
    client_id: str | None,
    doc_id: str | None,
    matched_service_id: str | None,
    route: str | None,
    meta: dict[str, Any] | None,
) -> dict[str, str] | None:
    meta = meta if isinstance(meta, dict) else {}
    svc_id = normalize_service_id(matched_service_id) or _service_id_from_doc_id(doc_id)
    if not svc_id:
        return None
    topic = str(meta.get("topic") or _topic_from_doc_id(doc_id) or "unknown").strip().lower()
    label = catalog_service_label(client_id, svc_id) or str(meta.get("title") or svc_id).strip()
    if not label:
        label = svc_id
    return {
        "service_id": svc_id,
        "topic": topic,
        "label": label,
        "last_route": str(route or "").strip(),
    }


def is_explicit_topic_change(q: str, focus: dict[str, str], *, client_id: str | None) -> bool:
    from query_selector import match_service_from_catalog

    match = match_service_from_catalog(q, client_id=client_id)
    if not match.get("is_confident"):
        return False
    new_sid = normalize_service_id(str(match.get("matched_service_id") or ""))
    old_sid = normalize_service_id(str(focus.get("service_id") or ""))
    return bool(new_sid and old_sid and new_sid != old_sid)


def rewrite_follow_up_query(q: str, focus: dict[str, str]) -> str:
    label = str(focus.get("label") or focus.get("service_id") or "услугу").strip()
    q0 = (q or "").strip()
    low = q0.lower()
    if _WARRANTY_RE.search(low):
        return f"гарантия на {label}"
    if _PAIN_RE.search(low):
        return f"больно ли {label}"
    if _PAYMENT_RE.search(low):
        return f"оплата и рассрочка {label}"
    if _INCLUDED_RE.search(low):
        return f"что входит в {label}"
    if _CONTACTS_RE.search(low):
        return "контакты и адрес клиники"
    if _DURATION_RE.search(low):
        return f"сроки и длительность {label}"
    cleaned = q0.rstrip("?.! ").strip()
    if cleaned:
        return f"{cleaned} {label}"
    return label


def _dialog_focus_for_follow_up(
    q: str,
    *,
    st: dict[str, Any],
    client_id: str | None,
) -> tuple[dict[str, str], int] | None:
    try:
        from core.dialog_focus import dialog_focus_from_ctx

        focus_decision = dialog_focus_from_ctx()
    except Exception:
        return None
    if focus_decision is None:
        return None
    if focus_decision.attribute not in _DIALOG_FOCUS_REWRITE_ATTRS:
        return None
    if focus_decision.attribute == "general" and not str(
        focus_decision.query_rewrite or ""
    ).strip():
        return None
    if focus_decision.explicit_topic_change:
        return None
    service_id = normalize_service_id(
        focus_decision.resolved_service_id or focus_decision.focus_service_id
    )
    if not service_id:
        return None
    age = (
        int(focus_decision.focus_turn_age)
        if isinstance(focus_decision.focus_turn_age, int)
        else None
    )
    if age is None:
        snap = read_age_guarded_service_focus(st)
        if snap is None:
            return None
        age = snap.service_focus_age
    elif age > int(THRESHOLDS.follow_up.max_service_focus_turn_age):
        return None
    label = (
        str(focus_decision.focus_label or "").strip()
        or catalog_service_label(client_id, service_id)
        or service_id
    )
    focus = {
        "service_id": service_id,
        "topic": str(focus_decision.focus_topic or "").strip().lower(),
        "label": label,
        "last_route": str(focus_decision.source or "").strip(),
    }
    if focus_decision.query_rewrite:
        focus["query_rewrite"] = str(focus_decision.query_rewrite).strip()
    return (
        focus,
        age,
    )


def prepare_follow_up_turn(
    q: str,
    st: dict[str, Any],
    *,
    client_id: str | None,
) -> FollowUpTurnContext | None:
    q0 = (q or "").strip()
    if not q0:
        return None

    dialog_focus = _dialog_focus_for_follow_up(q0, st=st, client_id=client_id)
    if dialog_focus:
        focus, age = dialog_focus
    else:
        if not is_short_attribute_followup(q0):
            return None
        snap = read_age_guarded_service_focus(st)
        if snap is None:
            return None
        focus = focus_dict_from_session_state(st)
        if not focus:
            return None
        age = snap.service_focus_age
    if is_explicit_topic_change(q0, focus, client_id=client_id):
        return None

    rewritten = str(focus.get("query_rewrite") or "").strip() or rewrite_follow_up_query(q0, focus)
    return FollowUpTurnContext(
        follow_up_mode=True,
        rewritten_query=rewritten,
        focus=focus,
        service_focus_age=age,
    )


def get_follow_up_turn_ctx(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
) -> FollowUpTurnContext | None:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            cached = follow_up_ctx_from_dict(request.ctx.get("follow_up"))
            if cached is not None:
                return cached
    except Exception:
        pass

    if not sid:
        return None
    from session import mem_get

    st = mem_get(sid)
    q0 = (q or "").strip()
    focus: dict[str, str] | None = None
    focus = focus_dict_from_session_state(st)

    if focus and is_explicit_topic_change(q0, focus, client_id=client_id):
        clear_target_service_focus(sid)
        return None

    ctx = prepare_follow_up_turn(q, st, client_id=client_id)
    if ctx is None:
        return None

    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            request.ctx["follow_up"] = follow_up_ctx_to_dict(ctx)
    except Exception:
        pass
    return ctx


def follow_up_turn_meta(ctx: FollowUpTurnContext | None) -> dict[str, Any]:
    if ctx is None or not ctx.follow_up_mode:
        return {"follow_up_mode": False}
    return {
        "follow_up_mode": True,
        "follow_up_rewritten": ctx.rewritten_query[:200],
        "focus_used": {
            "service_id": ctx.focus.get("service_id"),
            "topic": ctx.focus.get("topic"),
            "label": ctx.focus.get("label"),
        },
        "service_focus_age": ctx.service_focus_age,
    }
