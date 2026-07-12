"""Pure legacy → TurnFrame adapter (A1; no runtime wiring)."""

from __future__ import annotations

from contracts.answer_plan import AspectKind
from contracts.decision_frame import DecisionFrame, QueryMode, RouteIntent
from contracts.turn_frame import FieldMeta, SpecificityKind, TurnFrame, TurnFrameMeta
from contracts.turn_plan import TurnPlan

_MISSING = "missing_legacy_axis"
_DEFAULT = "default"


def _meta(*, confidence: float, provenance: str) -> FieldMeta:
    return FieldMeta(confidence=confidence, provenance=provenance)


def _missing_meta() -> FieldMeta:
    return _meta(confidence=0.0, provenance=_MISSING)


def _specificity_from_query_mode(
    query_mode: QueryMode | None,
    *,
    query_mode_confidence: float,
) -> tuple[SpecificityKind, FieldMeta]:
    if query_mode == "specific":
        return "specific", _meta(confidence=query_mode_confidence, provenance="decision_frame.query_mode")
    if query_mode in {"overview", "comparison", "process"}:
        return "general", _meta(confidence=query_mode_confidence, provenance="decision_frame.query_mode")
    return "unknown", _missing_meta()


def build_turn_frame_from_legacy(
    *,
    turn_plan: TurnPlan,
    decision_frame: DecisionFrame | None = None,
    primary_aspect: AspectKind | None = None,
) -> TurnFrame:
    """Map explicit legacy planner/resolver fields into TurnFrame without inference."""
    aspects = list(turn_plan.aspects)
    resolved_primary = primary_aspect if primary_aspect is not None else aspects[0]
    primary_provenance = (
        "explicit.primary_aspect" if primary_aspect is not None else "turn_plan.aspects[0]"
    )

    if decision_frame is not None:
        intent: RouteIntent = decision_frame.route_intent
        intent_meta = _meta(
            confidence=decision_frame.confidence.intent,
            provenance="decision_frame.route_intent",
        )
        specificity, specificity_meta = _specificity_from_query_mode(
            decision_frame.query_mode,
            query_mode_confidence=decision_frame.confidence.query_mode,
        )
    else:
        intent = turn_plan.route
        intent_meta = _meta(confidence=0.0, provenance="turn_plan.route")
        specificity = "unknown"
        specificity_meta = _missing_meta()

    if turn_plan.topic:
        topic: str | None = turn_plan.topic
        topic_meta = _meta(
            confidence=turn_plan.topic_confidence,
            provenance="turn_plan.topic",
        )
    elif decision_frame is not None:
        topic_raw = decision_frame.service_topic
        if topic_raw and topic_raw != "unknown":
            topic = str(topic_raw)
            topic_meta = _meta(
                confidence=decision_frame.confidence.topic,
                provenance="decision_frame.service_topic",
            )
        else:
            topic = None
            topic_meta = _meta(
                confidence=decision_frame.confidence.topic,
                provenance="decision_frame.service_topic",
            )
    else:
        topic = None
        topic_meta = _missing_meta()

    if turn_plan.service_id is not None:
        service_id = turn_plan.service_id
        service_meta = _meta(confidence=0.0, provenance="turn_plan.service_id")
    elif decision_frame is not None and decision_frame.service_id is not None:
        service_id = decision_frame.service_id
        service_meta = _meta(
            confidence=decision_frame.confidence.service,
            provenance="decision_frame.service_id",
        )
    else:
        service_id = None
        service_meta = _missing_meta()

    patient_raw = turn_plan.patient_situation
    if patient_raw is not None and str(patient_raw) != "unknown":
        patient_scope: str | None = str(patient_raw)
        patient_meta = _meta(confidence=0.0, provenance="turn_plan.patient_situation")
    else:
        patient_scope = None
        patient_meta = _missing_meta()

    followup_of = turn_plan.followup_of
    follow_up = bool(followup_of)
    followup_meta = (
        _meta(confidence=1.0, provenance="turn_plan.followup_of")
        if followup_of
        else _missing_meta()
    )

    return TurnFrame(
        intent=intent,
        topic=topic,
        aspects=aspects,
        primary_aspect=resolved_primary,
        emotion="none",
        specificity=specificity,
        patient_scope=patient_scope,
        service_id=service_id,
        follow_up=follow_up,
        followup_of=followup_of,
        needs_clarification=bool(turn_plan.needs_clarify),
        field_meta=TurnFrameMeta(
            intent=intent_meta,
            topic=topic_meta,
            aspects=_meta(confidence=0.0, provenance="turn_plan.aspects"),
            primary_aspect=_meta(confidence=0.0, provenance=primary_provenance),
            emotion=_meta(confidence=0.0, provenance=_DEFAULT),
            specificity=specificity_meta,
            patient_scope=patient_meta,
            service_id=service_meta,
            follow_up=_meta(
                confidence=1.0 if follow_up else 0.0,
                provenance="turn_plan.followup_of" if follow_up else _MISSING,
            ),
            followup_of=followup_meta,
            needs_clarification=_meta(
                confidence=0.0,
                provenance="turn_plan.needs_clarify",
            ),
        ),
    )
