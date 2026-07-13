"""Pure raw planner payload -> partial-capable TurnFrame builder (A7)."""

from __future__ import annotations

from typing import Any, cast, get_args

from contracts.answer_plan import AspectKind
from contracts.decision_frame import RouteIntent
from contracts.turn_frame import (
    FieldErrorReason,
    FieldMeta,
    FieldStatus,
    TurnFrame,
    TurnFrameMeta,
)

_ALLOWED_ASPECTS = frozenset(get_args(AspectKind))
_ALLOWED_ROUTES = frozenset(get_args(RouteIntent))
_RAW_ROUTE = "turn_plan.raw.route"
_RAW_TOPIC = "turn_plan.raw.topic"
_RAW_ASPECTS = "turn_plan.raw.aspects"
_NOT_MIGRATED = "a7.not_migrated"


def _meta(
    *,
    provenance: str,
    status: FieldStatus,
    confidence: float = 0.0,
    error: FieldErrorReason | None = None,
) -> FieldMeta:
    return FieldMeta(
        confidence=confidence,
        provenance=provenance,
        status=status,
        error=error,
    )


def _defaulted_meta() -> FieldMeta:
    return _meta(provenance=_NOT_MIGRATED, status="defaulted")


def _intent_from_raw(raw: dict[str, Any]) -> tuple[RouteIntent, FieldMeta]:
    raw_route = raw.get("route")
    if isinstance(raw_route, str) and raw_route in _ALLOWED_ROUTES:
        return cast(RouteIntent, raw_route), _meta(provenance=_RAW_ROUTE, status="valid")
    return "unknown", _meta(
        provenance=_RAW_ROUTE,
        status="invalid",
        error="route_invalid",
    )


def _confidence_from_raw(raw: object) -> tuple[float | None, bool]:
    if raw is None:
        return None, True
    if isinstance(raw, bool):
        return None, False
    if isinstance(raw, (int, float)):
        value = float(raw)
        if 0.0 <= value <= 1.0:
            return value, True
    return None, False


def _topic_from_raw(
    raw: dict[str, Any],
    *,
    allowed_topics: frozenset[str],
) -> tuple[str | None, FieldMeta]:
    raw_topic = raw.get("topic")
    confidence, confidence_valid = _confidence_from_raw(raw.get("topic_confidence"))

    if raw_topic is None or (isinstance(raw_topic, str) and not raw_topic.strip()):
        if not confidence_valid or (confidence is not None and confidence > 0.0):
            return None, _meta(
                provenance=_RAW_TOPIC,
                status="invalid",
                error="topic_confidence_invalid",
            )
        return None, _meta(provenance=_RAW_TOPIC, status="missing")

    if not isinstance(raw_topic, str):
        return None, _meta(
            provenance=_RAW_TOPIC,
            status="invalid",
            error="topic_invalid_type",
        )

    topic = raw_topic.strip().lower()
    if topic not in allowed_topics:
        return None, _meta(
            provenance=_RAW_TOPIC,
            status="invalid",
            error="topic_not_allowed",
        )
    if not confidence_valid:
        return None, _meta(
            provenance=_RAW_TOPIC,
            status="invalid",
            error="topic_confidence_invalid",
        )
    return topic, _meta(
        provenance=_RAW_TOPIC,
        status="valid",
        confidence=confidence if confidence is not None else 0.0,
    )


def _aspects_from_raw(
    raw: dict[str, Any],
) -> tuple[list[AspectKind], FieldMeta, AspectKind | None, FieldMeta]:
    raw_aspects = raw.get("aspects")
    if not isinstance(raw_aspects, list):
        aspects_error: FieldErrorReason = "aspects_invalid_type"
    elif not raw_aspects:
        aspects_error = "aspects_empty"
    elif any(not isinstance(item, str) or item not in _ALLOWED_ASPECTS for item in raw_aspects):
        aspects_error = "aspect_not_allowed"
    else:
        aspects = cast(list[AspectKind], list(raw_aspects))
        return (
            aspects,
            _meta(provenance=_RAW_ASPECTS, status="valid"),
            aspects[0],
            _meta(provenance="turn_plan.raw.aspects[0]", status="valid"),
        )

    return (
        [],
        _meta(provenance=_RAW_ASPECTS, status="invalid", error=aspects_error),
        None,
        _meta(
            provenance=_RAW_ASPECTS,
            status="invalid",
            error="primary_aspect_unavailable",
        ),
    )


def build_turn_frame_from_raw(
    raw: dict[str, Any],
    *,
    allowed_topics: frozenset[str],
) -> TurnFrame:
    """Build a safe shadow frame without mutating or repairing the raw payload."""
    intent, intent_meta = _intent_from_raw(raw)
    topic, topic_meta = _topic_from_raw(raw, allowed_topics=allowed_topics)
    aspects, aspects_meta, primary_aspect, primary_meta = _aspects_from_raw(raw)
    defaulted = _defaulted_meta

    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=aspects,
        primary_aspect=primary_aspect,
        emotion="none",
        specificity="unknown",
        patient_scope=None,
        service_id=None,
        follow_up=False,
        followup_of=None,
        needs_clarification=False,
        field_meta=TurnFrameMeta(
            intent=intent_meta,
            topic=topic_meta,
            aspects=aspects_meta,
            primary_aspect=primary_meta,
            emotion=defaulted(),
            specificity=defaulted(),
            patient_scope=defaulted(),
            service_id=defaulted(),
            follow_up=defaulted(),
            followup_of=defaulted(),
            needs_clarification=defaulted(),
        ),
    )
