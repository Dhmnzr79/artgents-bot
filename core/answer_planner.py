"""Deterministic aspect detection for follow-up routing (no legacy answer-plan API)."""

from __future__ import annotations

import re

from config import (
    ASPECT_PLANNER_LLM_ON,
    COMMERCIAL_INFO_RE,
    COMPARISON_QUERY_RE,
    PRICE_LOOKUP_RE,
    STEPS_VISITS_QUERY_RE,
)
from contracts.answer_plan import AspectKind
from contracts.decision_frame import DecisionFrame

_PAYMENT_ASPECT_RE = re.compile(
    r"(?:рассроч|оплат\w*\s+по\s+(?:част|этап)|оплат\w*\s+потом|кредит)",
    re.I | re.U,
)
_WARRANTY_ASPECT_RE = re.compile(r"гарант\w*", re.I | re.U)
_PAIN_ASPECT_RE = re.compile(
    r"(?:больно|боюсь|страш|страх|анестез|обезбол|безболезнен|седац|наркоз|во\s+сне)",
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
            for anchor in detect_aspects_regex(q, decision=decision):
                if anchor != "overview" and anchor not in aspects:
                    aspects.append(anchor)
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
