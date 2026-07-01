"""Bounded LLM hook for composite question aspect planning."""

from __future__ import annotations

from contracts.answer_plan import AspectKind
from contracts.aspect_planner import AspectPlannerOutput
from llm import classify_question_aspects as _llm_classify_question_aspects

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

_MIN_CONFIDENCE = 0.65


def order_aspects(aspects: list[AspectKind]) -> list[AspectKind]:
    uniq: list[AspectKind] = []
    for aspect in _ASPECT_PRIORITY:
        if aspect in aspects and aspect not in uniq:
            uniq.append(aspect)
    for aspect in aspects:
        if aspect not in uniq:
            uniq.append(aspect)
    return uniq


def classify_aspects_llm(
    q: str,
    *,
    client_id: str | None = None,
    sid: str | None = None,
    context_hint: str | None = None,
) -> list[AspectKind] | None:
    raw = _llm_classify_question_aspects(
        q,
        client_id=client_id,
        sid=sid,
        context_hint=context_hint,
    )
    if not raw:
        return None
    try:
        out = AspectPlannerOutput.model_validate(raw)
    except Exception:
        return None
    if out.confidence < _MIN_CONFIDENCE:
        return None
    aspects = order_aspects(list(out.aspects))
    if not aspects:
        return None
    return aspects
