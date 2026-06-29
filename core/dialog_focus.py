"""Unified dialog focus snapshot.

Stage 1 is observe-only: the decision is recorded in request context but does
not change source routing, price routing, doctors lookup, or retrieval.
"""

from __future__ import annotations

import re
from typing import Any

from contracts.decision_frame import DecisionFrame
from contracts.dialog_focus import DialogFocusAttribute, DialogFocusDecision, DialogFocusSource
from core.attribute_followup import catalog_match_is_authoritative, detect_vague_attribute_kinds
from core.follow_up_rewrite import focus_from_legacy_session
from core.routing_loader import THRESHOLDS
from core.service_followup import normalize_service_id
from session import mem_get

_PRICE_TOKEN_RE = re.compile(r"сто\w+|цен\w+|прайс|руб\w*|обойд\w*", re.I | re.U)


def _focus_from_last_subject(st: dict[str, Any]) -> tuple[dict[str, str] | None, int | None]:
    sub = st.get("last_subject")
    if not isinstance(sub, dict) or not str(sub.get("service_id") or "").strip():
        return None, None
    age = int(st.get("subject_turn_age") or 0)
    if age > int(THRESHOLDS.follow_up.max_subject_turn_age):
        return None, age
    service_id = normalize_service_id(str(sub.get("service_id") or ""))
    if not service_id:
        return None, age
    return (
        {
            "service_id": service_id,
            "topic": str(sub.get("topic") or "").strip().lower(),
            "label": str(sub.get("label") or service_id).strip(),
            "last_route": str(sub.get("last_route") or "").strip(),
        },
        age,
    )


def _primary_attribute(q: str) -> DialogFocusAttribute:
    kinds = detect_vague_attribute_kinds(q)
    for kind in ("price", "doctor", "warranty", "duration", "included", "payment", "pain"):
        if kind in kinds:
            return kind  # type: ignore[return-value]

    q0 = (q or "").strip().lower().replace("ё", "е")
    if "сколько" in q0 and _PRICE_TOKEN_RE.search(q0):
        return "price"
    if _PRICE_TOKEN_RE.search(q0) and len(q0.split()) <= 10:
        return "price"
    return "overview" if q0 else "unknown"


def _explicit_service_match(q: str, *, client_id: str | None) -> str | None:
    from query_selector import match_service_from_catalog

    match = match_service_from_catalog(q, client_id=client_id)
    if not catalog_match_is_authoritative(match, q) and not bool(match.get("is_confident")):
        return None
    return normalize_service_id(str(match.get("matched_service_id") or "")) or None


def build_dialog_focus_decision(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
    decision: DecisionFrame | None = None,
) -> DialogFocusDecision:
    """Build an observe-only focus decision for the current turn."""
    q0 = (q or "").strip()
    attribute = _primary_attribute(q0)
    st = mem_get(sid) if sid else {}

    focus, age = _focus_from_last_subject(st)
    source: DialogFocusSource = "last_subject" if focus else "none"
    if focus is None and st:
        legacy = focus_from_legacy_session(st, client_id=client_id)
        if legacy:
            focus = legacy
            age = int(st.get("subject_turn_age") or 0)
            source = "legacy_session"

    explicit_service_id = _explicit_service_match(q0, client_id=client_id) if q0 else None
    focus_service_id = normalize_service_id(str((focus or {}).get("service_id") or "")) or None
    decision_service_id = (
        normalize_service_id(str(decision.service_id or "")) if decision is not None else None
    )
    explicit_topic_change = bool(
        explicit_service_id and focus_service_id and explicit_service_id != focus_service_id
    )
    resolved_service_id = (
        explicit_service_id
        if explicit_topic_change
        else (focus_service_id or explicit_service_id or decision_service_id)
    )
    out_source = "explicit_service" if explicit_service_id and explicit_service_id != focus_service_id else source
    confidence = 0.0
    reason_bits: list[str] = []
    if focus_service_id:
        confidence = max(confidence, 0.75)
        reason_bits.append(source)
    if explicit_service_id:
        confidence = max(confidence, 0.9)
        reason_bits.append("explicit_service")
    if decision_service_id:
        confidence = max(confidence, 0.85)
        reason_bits.append("resolver_service")
    if attribute not in ("overview", "unknown"):
        confidence = max(confidence, 0.8 if confidence else 0.6)
        reason_bits.append(f"attribute:{attribute}")
    if explicit_topic_change:
        reason_bits.append("explicit_topic_change")

    return DialogFocusDecision(
        focus_service_id=focus_service_id,
        focus_topic=str((focus or {}).get("topic") or "").strip().lower() or None,
        focus_label=str((focus or {}).get("label") or "").strip() or None,
        focus_turn_age=age,
        attribute=attribute,
        explicit_topic_change=explicit_topic_change,
        resolved_service_id=resolved_service_id,
        source=out_source,
        used_llm=False,
        confidence=confidence,
        reason="|".join(reason_bits) if reason_bits else "no_focus",
    )


def publish_dialog_focus_decision(focus: DialogFocusDecision) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            request.ctx["dialog_focus_decision"] = focus.model_dump()
            request.ctx["dialog_focus_service_id"] = focus.focus_service_id
            request.ctx["dialog_focus_attribute"] = focus.attribute
            request.ctx["dialog_focus_explicit_topic_change"] = focus.explicit_topic_change
    except Exception:
        pass


def record_dialog_focus_ctx(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
    decision: DecisionFrame | None = None,
) -> DialogFocusDecision:
    focus = build_dialog_focus_decision(q, sid=sid, client_id=client_id, decision=decision)
    publish_dialog_focus_decision(focus)
    return focus
