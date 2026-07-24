"""Unified dialog focus snapshot.

Dialog focus carries the active service/topic for short follow-ups and can be
used as a bounded hint by follow-up rewrite, price routing, and doctor lookup.
It is not the patient-situation layer and should not classify clinical/business
scenarios such as missing teeth, bone deficit, or treatment option maps.
"""

from __future__ import annotations

import re
from typing import Any

from contracts.decision_frame import DecisionFrame
from contracts.dialog_focus import DialogFocusAttribute, DialogFocusDecision, DialogFocusSource
from contracts.turn_plan import TurnPlan
from core.attribute_followup import catalog_match_is_authoritative, detect_vague_attribute_kinds
from core.target_runtime_session import focus_dict_from_session_state
from core.routing_loader import THRESHOLDS
from core.service_followup import normalize_service_id
from session import mem_get

_PRICE_TOKEN_RE = re.compile(r"сто\w+|цен\w+|прайс|руб\w*|обойд\w*", re.I | re.U)
_DIRECT_PRICE_TOKEN_RE = re.compile(
    r"стоимост\w*|цен\w+|прайс|руб\w*|обойд\w*",
    re.I | re.U,
)
ATTRIBUTE_FOLLOWUP_KINDS = frozenset(
    {"price", "duration", "pain", "warranty", "doctor", "payment", "included", "general"}
)
_GRAY_FOLLOWUP_START_RE = re.compile(
    r"^(?:а|и|ну|так|ещ[её]|а\s+если|а\s+что|можно|мне|после|потом)\b",
    re.I | re.U,
)
_GRAY_TOPIC_CHANGE_RE = re.compile(
    r"\b(?:запис|адрес|телефон|контакт|цена|стоим|прайс|винир|брекет|отбелив|кариес)\w*",
    re.I | re.U,
)
_GRAY_BARE_ACK_RE = re.compile(
    r"^(?:да|нет|неа|ага|угу|ок|okay|спасибо|благодарю|понял|поняла|хорошо)[\s!.?]*$",
    re.I | re.U,
)


def _focus_from_target_runtime_session(st: dict[str, Any]) -> tuple[dict[str, str] | None, int | None]:
    focus = focus_dict_from_session_state(st)
    if focus is None:
        return None, None
    return focus, None


def _primary_attribute(q: str) -> DialogFocusAttribute:
    kinds = detect_vague_attribute_kinds(q)
    for kind in ("price", "doctor", "warranty", "duration", "included", "payment", "pain"):
        if kind in kinds:
            return kind  # type: ignore[return-value]

    q0 = (q or "").strip().lower().replace("ё", "е")
    if "сколько" in q0 and _PRICE_TOKEN_RE.search(q0):
        return "price"
    if _DIRECT_PRICE_TOKEN_RE.search(q0) and len(q0.split()) <= 10:
        return "price"
    return "overview" if q0 else "unknown"


def _explicit_service_match(q: str, *, client_id: str | None) -> str | None:
    from query_selector import match_service_from_catalog

    match = match_service_from_catalog(q, client_id=client_id)
    if not catalog_match_is_authoritative(match, q) and not bool(match.get("is_confident")):
        return None
    return normalize_service_id(str(match.get("matched_service_id") or "")) or None


def _gray_followup_candidate(q: str) -> bool:
    q0 = (q or "").strip()
    if not q0:
        return False
    if _GRAY_BARE_ACK_RE.match(q0):
        return False
    words = [w for w in re.split(r"\s+", q0, flags=re.U) if w]
    if len(words) > 10:
        return False
    if _GRAY_TOPIC_CHANGE_RE.search(q0):
        return False
    if _GRAY_FOLLOWUP_START_RE.search(q0):
        return True
    return len(words) <= 4


def _gray_llm_focus(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
    focus: dict[str, str] | None,
    attribute: DialogFocusAttribute,
    explicit_topic_change: bool,
) -> tuple[DialogFocusAttribute, bool, float | None, str | None, str | None, DialogFocusSource | None]:
    if attribute not in ("overview", "unknown"):
        return attribute, False, None, None, None, None
    if explicit_topic_change or not focus or not _gray_followup_candidate(q):
        return attribute, False, None, None, None, None
    service_id = normalize_service_id(str(focus.get("service_id") or ""))
    label = str(focus.get("label") or service_id).strip()
    if not service_id or not label:
        return attribute, False, None, None, None, None
    try:
        from core.dialog_focus_llm import classify_dialog_focus_gray_zone

        out = classify_dialog_focus_gray_zone(
            q,
            focus_service_id=service_id,
            focus_label=label,
            focus_topic=str(focus.get("topic") or "").strip() or None,
            client_id=client_id,
            sid=sid,
        )
    except Exception:
        return attribute, False, None, None, None, None
    if out is None:
        return attribute, False, None, None, None, None
    rewrite = str(out.query_rewrite or "").strip()
    if not rewrite:
        return attribute, False, None, None, None, None
    return "general", True, float(out.confidence), rewrite, "llm_gray", "llm_gray"


def build_dialog_focus_decision(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
    decision: DecisionFrame | None = None,
) -> DialogFocusDecision:
    """Build a bounded context hint for the current turn."""
    q0 = (q or "").strip()
    attribute = _primary_attribute(q0)
    st = mem_get(sid) if sid else {}

    focus, age = _focus_from_target_runtime_session(st)
    source: DialogFocusSource = "last_subject" if focus else "none"

    explicit_service_id = _explicit_service_match(q0, client_id=client_id) if q0 else None
    focus_service_id = normalize_service_id(str((focus or {}).get("service_id") or "")) or None
    decision_service_id = (
        normalize_service_id(str(decision.service_id or "")) if decision is not None else None
    )
    explicit_topic_change = bool(
        explicit_service_id and focus_service_id and explicit_service_id != focus_service_id
    )
    (
        attribute,
        used_llm,
        llm_confidence,
        query_rewrite,
        llm_reason,
        llm_source,
    ) = _gray_llm_focus(
        q0,
        sid=sid,
        client_id=client_id,
        focus=focus,
        attribute=attribute,
        explicit_topic_change=explicit_topic_change,
    )
    resolved_service_id = (
        explicit_service_id
        if explicit_topic_change
        else (focus_service_id or explicit_service_id or decision_service_id)
    )
    out_source = "explicit_service" if explicit_service_id and explicit_service_id != focus_service_id else source
    if llm_source:
        out_source = llm_source
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
    if used_llm and llm_confidence is not None:
        confidence = max(confidence, llm_confidence)
        if llm_reason:
            reason_bits.append(llm_reason)
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
        used_llm=used_llm,
        confidence=confidence,
        reason="|".join(reason_bits) if reason_bits else "no_focus",
        query_rewrite=query_rewrite,
    )


def publish_dialog_focus_decision(focus: DialogFocusDecision) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            request.ctx["dialog_focus_decision"] = focus.model_dump()
            request.ctx["dialog_focus_service_id"] = focus.focus_service_id
            request.ctx["dialog_focus_attribute"] = focus.attribute
            request.ctx["dialog_focus_explicit_topic_change"] = focus.explicit_topic_change
            request.ctx["dialog_focus_resolved_service_id"] = focus.resolved_service_id
            request.ctx["dialog_focus_source"] = focus.source
            request.ctx["dialog_focus_used_llm"] = focus.used_llm
            if focus.query_rewrite:
                request.ctx["dialog_focus_query_rewrite"] = focus.query_rewrite
    except Exception:
        pass


def build_dialog_focus_from_turn_plan(
    plan: TurnPlan,
    *,
    sid: str | None,
    client_id: str | None,
    decision: DecisionFrame | None = None,
) -> DialogFocusDecision:
    """Publish focus telemetry from turn planner output without gray-zone LLM."""
    _ = client_id
    st = mem_get(sid) if sid else {}
    focus, age = _focus_from_target_runtime_session(st)
    focus_service_id = normalize_service_id(str(plan.followup_of or (focus or {}).get("service_id") or "")) or None
    resolved_service_id = normalize_service_id(str(plan.service_id or plan.followup_of or "")) or None
    decision_service_id = (
        normalize_service_id(str(decision.service_id or "")) if decision is not None else None
    )
    if not resolved_service_id:
        resolved_service_id = decision_service_id
    explicit_topic_change = bool(
        resolved_service_id
        and focus_service_id
        and resolved_service_id != focus_service_id
        and not plan.followup_of
    )
    attr: DialogFocusAttribute = "overview"
    for aspect in ("price", "payment", "included", "warranty", "pain", "duration"):
        if aspect in plan.aspects:
            attr = aspect  # type: ignore[assignment]
            break
    if "overview" in plan.aspects and attr == "overview":
        attr = "overview"
    source: DialogFocusSource = "none"
    if plan.followup_of:
        source = "last_subject"
    elif resolved_service_id:
        source = "explicit_service"
    elif focus_service_id:
        source = "last_subject"
    reason_bits = ["turn_planner"]
    if plan.followup_of:
        reason_bits.append("followup_of")
    if explicit_topic_change:
        reason_bits.append("explicit_topic_change")
    return DialogFocusDecision(
        focus_service_id=focus_service_id,
        focus_topic=str((focus or {}).get("topic") or getattr(decision, "service_topic", "") or "").strip().lower() or None,
        focus_label=str((focus or {}).get("label") or focus_service_id or "").strip() or None,
        focus_turn_age=age,
        attribute=attr,
        explicit_topic_change=explicit_topic_change,
        resolved_service_id=resolved_service_id,
        source=source,
        used_llm=False,
        confidence=0.9,
        reason="|".join(reason_bits),
        query_rewrite=None,
    )


def dialog_focus_from_ctx() -> DialogFocusDecision | None:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            raw = request.ctx.get("dialog_focus_decision")
            if isinstance(raw, dict):
                return DialogFocusDecision.model_validate(raw)
    except Exception:
        return None
    return None


def dialog_focus_for_turn(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
    decision: DecisionFrame | None = None,
) -> DialogFocusDecision | None:
    cached = dialog_focus_from_ctx()
    if cached is not None:
        return cached
    try:
        return build_dialog_focus_decision(q, sid=sid, client_id=client_id, decision=decision)
    except Exception:
        return None


def dialog_focus_service_id(focus: DialogFocusDecision | None) -> str | None:
    if focus is None or focus.attribute not in ATTRIBUTE_FOLLOWUP_KINDS:
        return None
    sid = normalize_service_id(focus.resolved_service_id or focus.focus_service_id)
    return sid or None


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
