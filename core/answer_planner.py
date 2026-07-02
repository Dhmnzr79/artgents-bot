"""Deterministic answer planner (stage 4b): aspect + subject → append plan, no LLM."""

from __future__ import annotations

import re

from config import (
    ASPECT_PLANNER_LLM_ON,
    COMMERCIAL_INFO_RE,
    COMPARISON_QUERY_RE,
    PRICE_LOOKUP_RE,
    STEPS_VISITS_QUERY_RE,
)
from contracts.answer_plan import AnswerPlan, AspectKind, PlanAppendKind, PlanRiskKind
from contracts.decision_frame import DecisionFrame
from contracts.source_route_result import SourceRouteResult
from core.attribute_followup import (
    catalog_match_is_authoritative,
    detect_vague_attribute_kinds,
    is_vague_attribute_followup_any,
)
from core.dialog_focus import dialog_focus_from_ctx, dialog_focus_service_id
from query_selector import match_service_from_catalog
from core.service_followup import is_short_attribute_followup, normalize_service_id
from session import get_last_subject

_PAYMENT_ASPECT_RE = re.compile(
    r"(?:рассроч|оплат\w*\s+по\s+(?:част|этап)|оплат\w*\s+потом|кредит)",
    re.I | re.U,
)
_WARRANTY_ASPECT_RE = re.compile(r"гарант\w*", re.I | re.U)
_PAIN_ASPECT_RE = re.compile(
    r"(?:больно|боюсь|страш|страх|анестез|обезбол|безболезнен)",
    re.I | re.U,
)
_INCLUDED_ASPECT_RE = re.compile(
    r"(?:под\s+ключ|что\s+входит|входит\s+в\s+(?:акци|стоим|цен)|не\s+входит)",
    re.I | re.U,
)
_DURATION_ASPECT_RE = re.compile(
    r"(?:сколько\s+(?:длит|времени|по\s+времени)|длительн|срок\w*|месяц\w*|недел\w*)",
    re.I | re.U,
)

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

_PAYMENT_TERMS_REF = "clinic__info__payment_terms.md#korotko"
_WARRANTY_TERMS_REF = "clinic__info__warranty.md#korotko"


def payment_terms_ref() -> str:
    return _PAYMENT_TERMS_REF


def warranty_terms_ref() -> str:
    return _WARRANTY_TERMS_REF


def detect_aspects_regex(q: str, *, decision: DecisionFrame | None = None) -> list[AspectKind]:
    text = (q or "").strip()
    if not text:
        return []
    low = text.lower()
    found: list[AspectKind] = []
    if PRICE_LOOKUP_RE.search(text) or re.search(
        r"сколько\s+(?:стоит|будет|обойд)", low
    ):
        found.append("price")
    if _PAYMENT_ASPECT_RE.search(low) or (
        COMMERCIAL_INFO_RE.search(text) and re.search(r"рассроч|оплат", low)
    ):
        found.append("payment")
    if _INCLUDED_ASPECT_RE.search(low):
        found.append("included")
    if _WARRANTY_ASPECT_RE.search(low):
        found.append("warranty")
    if _PAIN_ASPECT_RE.search(low):
        found.append("pain")
    if _DURATION_ASPECT_RE.search(low) or STEPS_VISITS_QUERY_RE.search(text):
        found.append("duration")
    if COMPARISON_QUERY_RE.search(text) or (
        decision is not None
        and str(decision.query_mode or "").strip().lower() == "comparison"
    ):
        found.append("comparison")
    if "этап" in low and "payment" not in found and "duration" not in found:
        found.append("stages")
    if not found:
        found.append("overview")
    # Stable unique order by priority
    order = {a: i for i, a in enumerate(_ASPECT_PRIORITY)}
    uniq: list[AspectKind] = []
    for a in _ASPECT_PRIORITY:
        if a in found and a not in uniq:
            uniq.append(a)
    for a in found:
        if a not in uniq:
            uniq.append(a)
    return uniq


def is_composite_question(q: str) -> bool:
    """Heuristic: long or multi-part question that may need LLM aspect planning."""
    text = (q or "").strip()
    if not text:
        return False
    low = text.lower()
    words = len(text.split())
    if words >= 12 or len(text) >= 60:
        return True
    if text.count("?") >= 2:
        return True
    if low.count(" и ") >= 2:
        return True
    if re.search(r",\s*.+\s+и\s+", low):
        return True
    if words >= 8 and " и " in low and (
        PRICE_LOOKUP_RE.search(text)
        or _PAIN_ASPECT_RE.search(low)
        or _WARRANTY_ASPECT_RE.search(low)
        or _DURATION_ASPECT_RE.search(low)
        or _PAYMENT_ASPECT_RE.search(low)
    ):
        return True
    return False


def _real_aspect_count(aspects: list[AspectKind]) -> int:
    return len([a for a in aspects if a != "overview"])


def _record_aspect_planner_ctx(*, source: str, aspects: list[AspectKind]) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["aspect_planner_source"] = source
            request.ctx["aspect_planner_aspects"] = list(aspects)
    except Exception:
        pass


def detect_aspects(
    q: str,
    *,
    decision: DecisionFrame | None = None,
    client_id: str | None = None,
    sid: str | None = None,
) -> list[AspectKind]:
    try:
        from core.turn_planner_llm import turn_plan_from_ctx

        turn_plan = turn_plan_from_ctx()
        if turn_plan is not None:
            aspects = list(turn_plan.aspects or [])
            # Deterministic augmentation: comparison questions are already
            # detected by regex/decision; the planner must not lose them.
            if "comparison" not in aspects and (
                COMPARISON_QUERY_RE.search(q or "")
                or (
                    decision is not None
                    and str(getattr(decision, "query_mode", None) or "").strip().lower()
                    == "comparison"
                )
            ):
                aspects.append("comparison")
            _record_aspect_planner_ctx(source="turn_planner", aspects=aspects)
            return aspects
    except Exception:
        pass
    regex_aspects = detect_aspects_regex(q, decision=decision)
    if not ASPECT_PLANNER_LLM_ON or not is_composite_question(q):
        _record_aspect_planner_ctx(source="regex", aspects=regex_aspects)
        return regex_aspects
    if _real_aspect_count(regex_aspects) > 1:
        _record_aspect_planner_ctx(source="regex", aspects=regex_aspects)
        return regex_aspects

    from core.aspect_planner_llm import classify_aspects_llm

    llm_aspects = classify_aspects_llm(q, client_id=client_id, sid=sid)
    if llm_aspects:
        _record_aspect_planner_ctx(source="llm", aspects=llm_aspects)
        return llm_aspects
    _record_aspect_planner_ctx(source="regex", aspects=regex_aspects)
    return regex_aspects


def pick_primary_aspect(aspects: list[AspectKind]) -> AspectKind | None:
    """Primary aspect from the current turn only (telemetry / facet arbitration)."""
    if not aspects or aspects == ["overview"]:
        return None
    for a in _ASPECT_PRIORITY:
        if a in aspects:
            return a
    return aspects[0]


def _pick_primary_aspect(aspects: list[AspectKind]) -> AspectKind | None:
    return pick_primary_aspect(aspects)


def _resolve_service_id(
    *,
    q: str,
    client_id: str | None,
    decision: DecisionFrame | None,
    source_route: SourceRouteResult | None,
    sid: str,
) -> tuple[str | None, str | None]:
    try:
        from core.turn_planner_llm import turn_plan_from_ctx

        turn_plan = turn_plan_from_ctx()
        if turn_plan is not None and turn_plan.service_id:
            svc = normalize_service_id(str(turn_plan.service_id or ""))
            topic = str(getattr(decision, "service_topic", None) or "").strip().lower() or None
            return svc or None, topic
    except Exception:
        pass
    svc = normalize_service_id(str(getattr(source_route, "service_id", None) or ""))
    topic: str | None = None
    if decision is not None:
        if not svc:
            svc = normalize_service_id(str(decision.service_id or ""))
        topic = str(decision.service_topic or "").strip().lower() or None
    focus_decision = dialog_focus_from_ctx()
    focus_svc = dialog_focus_service_id(focus_decision)
    if focus_svc and (not svc or bool(focus_decision and focus_decision.explicit_topic_change)):
        svc = focus_svc
        topic = (
            str(getattr(focus_decision, "focus_topic", None) or topic or "").strip().lower()
            or topic
        )
    subject = get_last_subject(sid)
    vague_kinds = detect_vague_attribute_kinds(q)
    if not svc and subject and vague_kinds:
        svc = normalize_service_id(str(subject.get("service_id") or ""))
        topic = str(subject.get("topic") or topic or "").strip().lower() or topic
    if not svc:
        match = match_service_from_catalog(q, client_id=client_id)
        if catalog_match_is_authoritative(match, q):
            svc = normalize_service_id(str(match.get("matched_service_id") or ""))
    if not svc and subject and (
        is_short_attribute_followup(q)
        or is_vague_attribute_followup_any(q)
        or len((q or "").split()) <= 12
    ):
        svc = normalize_service_id(str(subject.get("service_id") or ""))
        topic = str(subject.get("topic") or topic or "").strip().lower() or topic
    if subject and not topic:
        topic = str(subject.get("topic") or "").strip().lower() or None
    return svc or None, topic


def _append_for_aspects(
    aspects: list[AspectKind],
    *,
    service_id: str | None,
    route_intent: str,
) -> list[PlanAppendKind]:
    append: list[PlanAppendKind] = []
    ri = (route_intent or "content").strip().lower()
    if "price" in aspects and service_id and ri in ("content", "price_lookup", "unknown"):
        append.append("price_offer")
    if "payment" in aspects:
        append.append("payment_terms")
    if "warranty" in aspects:
        append.append("warranty_terms")
    if "included" in aspects and service_id and "price_offer" not in append:
        append.append("price_offer")
    return append


def _risk_for_aspects(aspects: list[AspectKind]) -> list[PlanRiskKind]:
    risk: list[PlanRiskKind] = []
    if "price" in aspects or "included" in aspects:
        risk.append("price")
    if "warranty" in aspects:
        risk.append("warranty")
    if "pain" in aspects:
        risk.append("pain")
    if "included" in aspects:
        risk.append("included")
    return risk


def build_answer_plan(
    *,
    q: str,
    sid: str,
    client_id: str | None,
    intent: str,
    decision: DecisionFrame | None,
    source_route: SourceRouteResult | None,
) -> AnswerPlan:
    aspects = detect_aspects(q, decision=decision, client_id=client_id, sid=sid)
    primary = _pick_primary_aspect(aspects)
    service_id, topic = _resolve_service_id(
        q=q,
        client_id=client_id,
        decision=decision,
        source_route=source_route,
        sid=sid,
    )
    route_intent = str(getattr(decision, "route_intent", None) or intent or "content")
    append = _append_for_aspects(aspects, service_id=service_id, route_intent=route_intent)
    risk = _risk_for_aspects(aspects)
    reason_bits: list[str] = []
    if len(aspects) > 1:
        reason_bits.append("composite")
    focus_decision = dialog_focus_from_ctx()
    if service_id and focus_decision and focus_decision.attribute in (
        "duration",
        "pain",
        "warranty",
        "payment",
        "included",
    ):
        reason_bits.append("dialog_focus")
    if service_id and get_last_subject(sid):
        reason_bits.append("subject_carry")
    try:
        from core.turn_planner_llm import turn_plan_from_ctx

        if turn_plan_from_ctx() is not None:
            reason_bits.append("turn_planner")
    except Exception:
        pass
    return AnswerPlan(
        aspects=aspects,
        primary_aspect=primary,
        service_id=service_id,
        topic=topic,
        primary_chunk_ref=None,
        append=append,
        risk=risk,
        plan_reason="|".join(reason_bits) if reason_bits else "single",
    )


def publish_answer_plan(plan: AnswerPlan) -> None:
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["answer_plan"] = plan.model_dump()
    except Exception:
        pass


def answer_plan_from_ctx() -> AnswerPlan | None:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return None
        raw = request.ctx.get("answer_plan")
        if not isinstance(raw, dict):
            return None
        return AnswerPlan.model_validate(raw)
    except Exception:
        return None
