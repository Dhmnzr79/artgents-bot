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
_RAW_SERVICE_ID = "turn_plan.raw.service_id"
_RAW_FOLLOWUP_OF = "turn_plan.raw.followup_of"
_RAW_NEEDS_CLARIFY = "turn_plan.raw.needs_clarify"
_DERIVED_FOLLOWUP_OF = "derived.followup_of"
_SCHEMA_DEFAULT = "turn_plan.schema_default"
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


def _not_migrated_meta() -> FieldMeta:
    return _meta(provenance=_NOT_MIGRATED, status="defaulted")


def _schema_default_meta() -> FieldMeta:
    return _meta(provenance=_SCHEMA_DEFAULT, status="defaulted")


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


def _catalog_id_from_raw(
    raw: dict[str, Any],
    *,
    field: str,
    provenance: str,
    allowed_service_ids: frozenset[str],
    invalid_type_error: FieldErrorReason,
    not_allowed_error: FieldErrorReason,
) -> tuple[str | None, FieldMeta]:
    if field not in raw:
        return None, _schema_default_meta()

    raw_value = raw.get(field)
    if raw_value is None:
        return None, _meta(provenance=provenance, status="valid")
    if not isinstance(raw_value, str):
        return None, _meta(
            provenance=provenance,
            status="invalid",
            error=invalid_type_error,
        )

    value = raw_value.strip()
    if not value or value not in allowed_service_ids:
        return None, _meta(
            provenance=provenance,
            status="invalid",
            error=not_allowed_error,
        )
    return value, _meta(provenance=provenance, status="valid")


def _service_id_from_raw(
    raw: dict[str, Any],
    *,
    allowed_service_ids: frozenset[str],
) -> tuple[str | None, FieldMeta]:
    return _catalog_id_from_raw(
        raw,
        field="service_id",
        provenance=_RAW_SERVICE_ID,
        allowed_service_ids=allowed_service_ids,
        invalid_type_error="service_id_invalid_type",
        not_allowed_error="service_id_not_allowed",
    )


def _followup_from_raw(
    raw: dict[str, Any],
    *,
    allowed_service_ids: frozenset[str],
) -> tuple[str | None, FieldMeta, bool, FieldMeta]:
    followup_of, followup_meta = _catalog_id_from_raw(
        raw,
        field="followup_of",
        provenance=_RAW_FOLLOWUP_OF,
        allowed_service_ids=allowed_service_ids,
        invalid_type_error="followup_of_invalid_type",
        not_allowed_error="followup_of_not_allowed",
    )
    if followup_meta.status == "defaulted":
        return None, followup_meta, False, _schema_default_meta()
    if followup_meta.status == "invalid":
        return (
            None,
            followup_meta,
            False,
            _meta(
                provenance=_DERIVED_FOLLOWUP_OF,
                status="invalid",
                error="follow_up_unavailable",
            ),
        )
    return (
        followup_of,
        followup_meta,
        followup_of is not None,
        _meta(provenance=_DERIVED_FOLLOWUP_OF, status="valid"),
    )


def _needs_clarification_from_raw(raw: dict[str, Any]) -> tuple[bool, FieldMeta]:
    if "needs_clarify" not in raw:
        return False, _schema_default_meta()
    raw_value = raw.get("needs_clarify")
    if type(raw_value) is bool:
        return raw_value, _meta(provenance=_RAW_NEEDS_CLARIFY, status="valid")
    return False, _meta(
        provenance=_RAW_NEEDS_CLARIFY,
        status="invalid",
        error="needs_clarification_invalid_type",
    )


def build_turn_frame_from_raw(
    raw: dict[str, Any],
    *,
    allowed_topics: frozenset[str],
    allowed_service_ids: frozenset[str] = frozenset(),
) -> TurnFrame:
    """Build a safe shadow frame without mutating or repairing the raw payload."""
    intent, intent_meta = _intent_from_raw(raw)
    topic, topic_meta = _topic_from_raw(raw, allowed_topics=allowed_topics)
    aspects, aspects_meta, primary_aspect, primary_meta = _aspects_from_raw(raw)
    service_id, service_meta = _service_id_from_raw(
        raw,
        allowed_service_ids=allowed_service_ids,
    )
    followup_of, followup_meta, follow_up, follow_up_meta = _followup_from_raw(
        raw,
        allowed_service_ids=allowed_service_ids,
    )
    needs_clarification, needs_clarification_meta = _needs_clarification_from_raw(raw)
    not_migrated = _not_migrated_meta

    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=aspects,
        primary_aspect=primary_aspect,
        emotion="none",
        specificity="unknown",
        patient_scope=None,
        service_id=service_id,
        follow_up=follow_up,
        followup_of=followup_of,
        needs_clarification=needs_clarification,
        field_meta=TurnFrameMeta(
            intent=intent_meta,
            topic=topic_meta,
            aspects=aspects_meta,
            primary_aspect=primary_meta,
            emotion=not_migrated(),
            specificity=not_migrated(),
            patient_scope=not_migrated(),
            service_id=service_meta,
            follow_up=follow_up_meta,
            followup_of=followup_meta,
            needs_clarification=needs_clarification_meta,
        ),
    )
