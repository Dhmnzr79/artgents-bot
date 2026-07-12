from __future__ import annotations

from pathlib import Path

import pytest

from contracts.decision_frame import DecisionFrame
from contracts.turn_frame import FieldMeta, TurnFrame, TurnFrameMeta
from contracts.turn_plan import TurnPlan
from core.turn_frame_adapter import build_turn_frame_from_legacy


def _field_meta(**overrides: FieldMeta) -> TurnFrameMeta:
    base = FieldMeta(confidence=1.0, provenance="test")
    defaults = {
        "intent": base,
        "topic": base,
        "aspects": base,
        "primary_aspect": base,
        "emotion": FieldMeta(confidence=0.0, provenance="default"),
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
        FieldMeta(confidence=0.5, provenance="")


def test_empty_aspects_rejected():
    with pytest.raises(ValueError):
        TurnFrame(
            intent="content",
            aspects=[],
            primary_aspect="overview",
            field_meta=_field_meta(),
        )


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
    assert frame.aspects == ["price", "pain"]
    assert frame.service_id == "veneers"
    assert frame.followup_of == "veneers"
    assert frame.needs_clarification is True


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
