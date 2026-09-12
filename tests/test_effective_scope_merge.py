from __future__ import annotations

from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref
from contracts.ui_stage_action import UiStageAction, build_ui_stage_ref
from core.target_effective_scope import session_patient_facts_from_ui_action
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
    simulate_session_patient_facts_after_turn,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_strategy_context import selection_patient_context_from_inputs


def _native_frame(patient_scope: dict, *, topic: str = "implantation"):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": patient_scope,
        },
        allowed_topics=frozenset({"implantation", "prosthetics"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def test_ui_scope_action_controls_extent_over_a9() -> None:
    ui = UiScopeAction(
        extent="few_teeth",
        topic="implantation",
        ref=build_ui_scope_ref(topic="implantation", extent="few_teeth"),
    )
    frame = _native_frame({"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=2,
            session_facts=None,
            current_ui_scope_action=ui,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.extent == "few_teeth"
    assert merged.extent_axis.source == "ui_action"


def test_a9_extent_supplements_when_no_ui_action() -> None:
    frame = _native_frame({"extent": "full_arch", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.extent == "full_arch"
    assert merged.extent_axis.source == "a9_turn"


def test_unknown_a9_extent_does_not_erase_session_extent() -> None:
    session = session_patient_facts_from_ui_action(
        UiScopeAction(
            extent="few_teeth",
            topic="implantation",
            ref=build_ui_scope_ref(topic="implantation", extent="few_teeth"),
        ),
        set_at_turn=1,
    )
    frame = _native_frame({"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=2,
            session_facts=session,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.extent == "few_teeth"
    assert merged.extent_axis.source == "session"


def test_a9_correction_replaces_session_extent() -> None:
    session = session_patient_facts_from_ui_action(
        UiScopeAction(
            extent="full_arch",
            topic="implantation",
            ref=build_ui_scope_ref(topic="implantation", extent="full_arch"),
        ),
        set_at_turn=1,
    )
    frame = _native_frame({"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=2,
            session_facts=session,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.extent == "one_tooth"
    assert merged.extent_axis.source == "a9_turn"


def test_jaw_arrives_second_preserves_extent() -> None:
    session = session_patient_facts_from_ui_action(
        UiScopeAction(
            extent="full_arch",
            topic="implantation",
            ref=build_ui_scope_ref(topic="implantation", extent="full_arch"),
        ),
        set_at_turn=1,
    )
    frame = _native_frame({"extent": "unknown", "jaw": "upper", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=2,
            session_facts=session,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.extent == "full_arch"
    assert merged.jaw == "upper"
    assert merged.jaw_axis.source == "a9_turn"


def test_jaw_both_preserved_not_split() -> None:
    frame = _native_frame({"extent": "unknown", "jaw": "both", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.jaw == "both"
    patient = selection_patient_context_from_inputs(merged)
    assert patient.jaw is None


def test_stage_action_controls_stage() -> None:
    stage_action = UiStageAction(
        topic="prosthetics",
        stage="natural_tooth_present",
        ref=build_ui_stage_ref(topic="prosthetics", stage="natural_tooth_present"),
    )
    frame = _native_frame(
        {"extent": "unknown", "jaw": "unknown", "stage": "implant_placed", "modifiers": []},
        topic="prosthetics",
    )
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="prosthetics",
            session_turn_count=1,
            session_facts=None,
            current_ui_stage_action=stage_action,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    assert merged.stage == "natural_tooth_present"
    assert merged.stage_axis.source == "ui_stage_action"


def test_natural_tooth_present_reaches_selection_patient_context() -> None:
    frame = _native_frame(
        {"extent": "one_tooth", "jaw": "unknown", "stage": "natural_tooth_present", "modifiers": []},
        topic="prosthetics",
    )
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="prosthetics",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    patient = selection_patient_context_from_inputs(merged)
    assert patient.stage == "natural_tooth_present"
    assert patient.extent == "one_tooth"


def test_simulated_session_write_only_on_usable_a9_axes() -> None:
    frame = _native_frame({"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=project_patient_scope_from_turn_frame(frame),
        )
    )
    sim = simulate_session_patient_facts_after_turn(
        merged=merged,
        prior=None,
        current_topic="implantation",
        session_turn_count=1,
    )
    assert sim.wrote is False
    assert sim.facts is None
