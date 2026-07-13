from __future__ import annotations

from pathlib import Path

import pytest

from contracts.decision_frame import DecisionFrame
from contracts.turn_frame import FieldMeta, TurnFrame, TurnFrameMeta
from contracts.turn_plan import TurnPlan
from core.turn_frame_adapter import build_turn_frame_from_legacy


def _field_meta(**overrides: FieldMeta) -> TurnFrameMeta:
    base = FieldMeta(confidence=1.0, provenance="test", status="valid")
    defaults = {
        "intent": base,
        "topic": base,
        "aspects": base,
        "primary_aspect": base,
        "emotion": FieldMeta(confidence=0.0, provenance="default", status="defaulted"),
        "specificity": base,
        "patient_scope": base,
        "service_id": base,
        "follow_up": base,
        "followup_of": base,
        "needs_clarification": base,
    }
    defaults.update(overrides)
    return TurnFrameMeta(**defaults)


def _decision_frame(**overrides) -> DecisionFrame:
    payload = {
        "route_intent": "content",
        "service_topic": "unknown",
        "service_id": None,
        "query_mode": "overview",
        "confidence": {
            "intent": 0.9,
            "topic": 0.1,
            "service": 0.0,
            "query_mode": 0.8,
        },
        "needs_clarification": False,
    }
    payload.update(overrides)
    return DecisionFrame.model_validate(payload)


def test_valid_full_turn_frame_creates():
    frame = TurnFrame(
        intent="price_lookup",
        topic="prosthetics",
        aspects=["price", "duration"],
        primary_aspect="price",
        emotion="none",
        specificity="specific",
        patient_scope="one_tooth",
        service_id="classic",
        follow_up=True,
        followup_of="classic",
        needs_clarification=False,
        field_meta=_field_meta(),
    )

    assert frame.intent == "price_lookup"
    assert frame.primary_aspect == "price"


def test_unknown_field_rejected():
    with pytest.raises(ValueError):
        TurnFrame(
            intent="content",
            aspects=["overview"],
            primary_aspect="overview",
            field_meta=_field_meta(),
            extra_axis="forbidden",
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=1.5, provenance="test")


def test_empty_provenance_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="", status="valid")


def test_field_meta_status_is_required():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test")


@pytest.mark.parametrize("status", ["valid", "defaulted", "missing", "invalid"])
def test_field_meta_status_values_accepted_when_invariant_holds(status: str):
    error = "aspects_empty" if status == "invalid" else None
    meta = FieldMeta(confidence=0.5, provenance="test", status=status, error=error)
    assert meta.status == status


def test_field_meta_invalid_without_error_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test", status="invalid")


def test_field_meta_valid_with_error_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test", status="valid", error="aspects_empty")


@pytest.mark.parametrize("status", ["valid", "defaulted", "missing"])
def test_field_meta_non_invalid_forbids_error(status: str):
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test", status=status, error="aspects_empty")


def test_field_meta_unknown_status_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test", status="broken", error=None)  # type: ignore[arg-type]


def test_field_meta_unknown_error_rejected():
    with pytest.raises(ValueError):
        FieldMeta(
            confidence=0.5,
            provenance="test",
            status="invalid",
            error="not_a_real_reason",  # type: ignore[arg-type]
        )


def test_field_meta_extra_field_rejected():
    with pytest.raises(ValueError):
        FieldMeta(confidence=0.5, provenance="test", status="valid", extra="x")


def test_empty_aspects_with_null_primary_creates_partial_frame():
    frame = TurnFrame(
        intent="content",
        aspects=[],
        primary_aspect=None,
        field_meta=_field_meta(),
    )
    assert frame.aspects == []
    assert frame.primary_aspect is None


def test_nonempty_aspects_with_null_primary_creates_partial_frame():
    frame = TurnFrame(
        intent="content",
        aspects=["overview"],
        primary_aspect=None,
        field_meta=_field_meta(),
    )
    assert frame.primary_aspect is None


def test_empty_aspects_with_non_null_primary_rejected():
    with pytest.raises(ValueError, match="primary_aspect_not_in_aspects"):
        TurnFrame(
            intent="content",
            aspects=[],
            primary_aspect="overview",
            field_meta=_field_meta(),
        )


def test_serialization_preserves_status_and_error():
    frame = TurnFrame(
        intent="content",
        aspects=[],
        primary_aspect=None,
        field_meta=_field_meta(
            aspects=FieldMeta(
                confidence=0.0,
                provenance="turn_plan.raw.aspects",
                status="invalid",
                error="aspects_empty",
            ),
        ),
    )
    dumped = frame.model_dump()
    assert dumped["field_meta"]["aspects"]["status"] == "invalid"
    assert dumped["field_meta"]["aspects"]["error"] == "aspects_empty"


def test_turn_plan_empty_aspects_still_rejected():
    with pytest.raises(ValueError):
        TurnPlan(route="content", aspects=[])


def test_primary_aspect_not_in_aspects_rejected():
    with pytest.raises(ValueError, match="primary_aspect_not_in_aspects"):
        TurnFrame(
            intent="content",
            aspects=["price"],
            primary_aspect="pain",
            field_meta=_field_meta(),
        )


def test_adapter_transfers_explicit_legacy_fields():
    turn_plan = TurnPlan(
        route="price_lookup",
        aspects=["price", "pain"],
        service_id="veneers",
        followup_of="veneers",
        needs_clarify=True,
    )
    decision = _decision_frame(
        route_intent="price_lookup",
        service_topic="prosthetics",
        query_mode="specific",
    )

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.intent == "price_lookup"
    assert frame.topic == "prosthetics"
    assert frame.field_meta.topic.provenance == "decision_frame.service_topic"
    assert frame.aspects == ["price", "pain"]
    assert frame.service_id == "veneers"
    assert frame.followup_of == "veneers"
    assert frame.needs_clarification is True


def test_adapter_prefers_native_topic_over_decision_frame():
    turn_plan = TurnPlan(
        route="content",
        aspects=["overview"],
        topic="whitening",
        topic_confidence=0.85,
    )
    decision = _decision_frame(service_topic="implantation")

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.topic == "whitening"
    assert frame.field_meta.topic.confidence == 0.85
    assert frame.field_meta.topic.provenance == "turn_plan.topic"


def test_turn_plan_topic_normalization_and_invariants():
    plan = TurnPlan(
        route="content",
        aspects=["overview"],
        topic="  ProSthetics  ",
        topic_confidence=0.5,
    )
    assert plan.topic == "prosthetics"

    empty = TurnPlan(route="content", aspects=["overview"], topic="   ")
    assert empty.topic is None
    assert empty.topic_confidence == 0.0

    with pytest.raises(ValueError):
        TurnPlan(
            route="content",
            aspects=["overview"],
            topic_confidence=1.1,
        )

    with pytest.raises(ValueError, match="topic_confidence_requires_topic"):
        TurnPlan(
            route="content",
            aspects=["overview"],
            topic_confidence=0.3,
        )


def test_turn_plan_legacy_payload_without_topic_fields():
    plan = TurnPlan.model_validate(
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        }
    )

    assert plan.topic is None
    assert plan.topic_confidence == 0.0


def test_native_topic_does_not_change_other_adapter_axes():
    turn_plan = TurnPlan(
        route="price_lookup",
        aspects=["price", "duration"],
        service_id="classic",
        followup_of="classic",
        needs_clarify=True,
        topic="treatment",
        topic_confidence=0.7,
    )
    decision = _decision_frame(
        route_intent="content",
        service_topic="implantation",
        query_mode="specific",
    )

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.intent == "content"
    assert frame.aspects == ["price", "duration"]
    assert frame.service_id == "classic"
    assert frame.followup_of == "classic"
    assert frame.needs_clarification is True
    assert frame.topic == "treatment"


def test_adapter_does_not_invent_topic_without_legacy_topic():
    turn_plan = TurnPlan(route="content", aspects=["overview"])
    decision = _decision_frame(service_topic="unknown")

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.topic is None

    frame_no_decision = build_turn_frame_from_legacy(turn_plan=turn_plan)

    assert frame_no_decision.topic is None


def test_adapter_follow_up_only_from_followup_of():
    with_followup = TurnPlan(
        route="price_lookup",
        aspects=["price"],
        followup_of="all_on_4",
    )
    without_followup = TurnPlan(route="price_lookup", aspects=["price"], followup_of=None)

    assert build_turn_frame_from_legacy(turn_plan=with_followup).follow_up is True
    assert build_turn_frame_from_legacy(turn_plan=without_followup).follow_up is False


def test_adapter_default_emotion_none_with_default_provenance():
    turn_plan = TurnPlan(route="content", aspects=["overview"])

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan)

    assert frame.emotion == "none"
    assert frame.field_meta.emotion.provenance == "default"


def test_adapter_unknown_decision_frame_topic_preserves_metadata():
    turn_plan = TurnPlan(route="content", aspects=["overview"])
    decision = _decision_frame(
        service_topic="unknown",
        confidence={
            "intent": 0.9,
            "topic": 0.15,
            "service": 0.0,
            "query_mode": 0.8,
        },
    )

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.topic is None
    assert frame.field_meta.topic.status == "missing"
    assert frame.field_meta.topic.provenance == "decision_frame.service_topic"
    assert frame.field_meta.topic.confidence == 0.15
    assert frame.field_meta.topic.error is None


def test_adapter_follow_up_false_metadata():
    turn_plan = TurnPlan(route="content", aspects=["overview"], followup_of=None)

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan)

    assert frame.follow_up is False
    assert frame.field_meta.follow_up.status == "defaulted"
    assert frame.field_meta.follow_up.provenance == "missing_legacy_axis"
    assert frame.field_meta.follow_up.confidence == 0.0
    assert frame.field_meta.follow_up.error is None


def test_adapter_legacy_metadata_status_table_with_decision_frame():
    turn_plan = TurnPlan(
        route="price_lookup",
        aspects=["price", "pain"],
        service_id="veneers",
        followup_of="veneers",
        needs_clarify=True,
        topic="whitening",
        topic_confidence=0.85,
    )
    decision = _decision_frame(
        route_intent="price_lookup",
        service_topic="prosthetics",
        query_mode="specific",
    )

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)
    meta = frame.field_meta

    assert meta.intent.status == "valid"
    assert meta.topic.status == "valid"
    assert meta.aspects.status == "valid"
    assert meta.primary_aspect.status == "valid"
    assert meta.emotion.status == "defaulted"
    assert meta.emotion.provenance == "default"
    assert meta.specificity.status == "valid"
    assert meta.patient_scope.status == "missing"
    assert meta.service_id.status == "valid"
    assert meta.follow_up.status == "valid"
    assert meta.followup_of.status == "valid"
    assert meta.needs_clarification.status == "valid"
    for name in TurnFrameMeta.model_fields:
        assert getattr(meta, name).error is None


def test_adapter_legacy_metadata_status_table_without_decision_frame():
    turn_plan = TurnPlan(route="content", aspects=["overview"], followup_of=None, needs_clarify=False)

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan)
    meta = frame.field_meta

    assert meta.intent.status == "valid"
    assert meta.topic.status == "missing"
    assert meta.aspects.status == "valid"
    assert meta.primary_aspect.status == "valid"
    assert meta.emotion.status == "defaulted"
    assert meta.emotion.provenance == "default"
    assert meta.specificity.status == "missing"
    assert meta.patient_scope.status == "missing"
    assert meta.service_id.status == "missing"
    assert meta.follow_up.status == "defaulted"
    assert meta.follow_up.provenance == "missing_legacy_axis"
    assert meta.followup_of.status == "missing"
    assert meta.needs_clarification.status == "valid"
    for name in TurnFrameMeta.model_fields:
        assert getattr(meta, name).error is None


def test_adapter_explicit_statuses_valid_defaulted_missing_only():
    turn_plan = TurnPlan(
        route="content",
        aspects=["overview"],
        topic="whitening",
        topic_confidence=0.85,
    )
    decision = _decision_frame(service_topic="unknown")

    frame = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)

    assert frame.field_meta.intent.status == "valid"
    assert frame.field_meta.topic.status == "valid"
    assert frame.field_meta.aspects.status == "valid"
    assert frame.field_meta.emotion.status == "defaulted"
    assert frame.field_meta.service_id.status == "missing"
    for name in TurnFrameMeta.model_fields:
        assert getattr(frame.field_meta, name).error is None


def test_adapter_meta_helper_requires_explicit_status():
    source = Path("core/turn_frame_adapter.py").read_text(encoding="utf-8")
    assert 'status: FieldStatus = "valid"' not in source
    assert "status: FieldStatus," in source


def test_adapter_never_marks_metadata_invalid():
    turn_plan = TurnPlan(route="price_lookup", aspects=["price"], followup_of=None)
    frame = build_turn_frame_from_legacy(turn_plan=turn_plan)
    for name in TurnFrameMeta.model_fields:
        meta = getattr(frame.field_meta, name)
        assert meta.status != "invalid", name


def test_adapter_has_no_thematic_exception_branches():
    source = Path("core/turn_frame_adapter.py").read_text(encoding="utf-8").lower()
    banned = (
        "survival",
        "all_on_4",
        "all-on-4",
        "all_on_6",
        "приживаем",
        "implantation",
        "prosthetics",
        "preservation",
    )
    hits = [token for token in banned if token in source]
    assert hits == []


def test_adapter_does_not_mutate_legacy_inputs():
    turn_plan = TurnPlan(
        route="content",
        aspects=["duration", "overview"],
        service_id="classic",
        followup_of=None,
        needs_clarify=False,
    )
    decision = _decision_frame(route_intent="content", service_topic="implantation")
    turn_before = turn_plan.model_dump()
    decision_before = decision.model_dump()

    frame = build_turn_frame_from_legacy(
        turn_plan=turn_plan,
        decision_frame=decision,
        primary_aspect="duration",
    )

    assert frame.primary_aspect == "duration"
    assert turn_plan.model_dump() == turn_before
    assert decision.model_dump() == decision_before
