"""Offline blast-radius tests for A9R2 planner prompt calibration (Checkpoint B)."""

from __future__ import annotations

from core.turn_planner_llm import _PATIENT_SCOPE_PROMPT
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from evals.v5.a9r2_patient_scope_live_contract import (
    POSITIVE_CATEGORIES,
    iter_live_planner_calls,
    load_frozen_matrix_v2,
)
from evals.v5.a9r2_patient_scope_live_scoring import score_planner_call

_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic"})


def _frame(scope: dict, *, topic: str = "implantation", service_id: str | None = None):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": service_id,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": scope,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def test_prompt_contains_semantic_calibration_rules() -> None:
    for snippet in (
        "названия услуги или протокола",
        "All-on-4",
        "не означает implant_placed",
        "natural_tooth_present",
        "missing teeth",
        "extraction_context",
        "jaw upper/lower/both не определяет extent",
        "Неоднозначные или конфликтующие",
        "по типичной медицинской ситуации",
    ):
        assert snippet in _PATIENT_SCOPE_PROMPT


def test_positive_matrix_axes_still_project_when_explicit() -> None:
    matrix = load_frozen_matrix_v2()
    positive_axis_hits = 0
    for call in iter_live_planner_calls(matrix):
        if call["category"] not in POSITIVE_CATEGORIES:
            continue
        scope = {
            "extent": call["expected_scope"].get("extent", "unknown"),
            "jaw": call["expected_scope"].get("jaw", "unknown"),
            "stage": call["expected_scope"].get("stage", "unknown"),
            "modifiers": list(call["expected_scope"].get("modifiers") or []),
        }
        frame = _frame(scope, topic=call["topic"])
        score = score_planner_call(
            frame=frame,
            planner_status="ok",
            call_spec=call,
        )
        assert score["transport_provider_error"] is False
        for axis, outcome in score["axis_outcomes"].items():
            if outcome == "correct_expected_axis":
                positive_axis_hits += 1
    assert positive_axis_hits >= 12


def test_all_on_4_info_and_price_remain_all_unknown() -> None:
    matrix = load_frozen_matrix_v2()
    for case_id in ("a9r_negative_01_all_on_4_info", "a9r_negative_02_all_on_4_price"):
        call = next(call for call in iter_live_planner_calls(matrix) if call["case_id"] == case_id)
        frame = _frame(
            {
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
            topic=call["topic"],
            service_id="all_on_4",
        )
        projected = project_patient_scope_from_turn_frame(frame)
        assert projected.extent.usable is False
        assert projected.jaw.usable is False
        assert projected.stage.usable is False
        score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
        assert score["composite_turn_exact"] is True


def test_missing_teeth_does_not_infer_stage_axes() -> None:
    matrix = load_frozen_matrix_v2()
    call = next(
        call for call in iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_ambiguous_02_vague_several"
    )
    frame = _frame(
        {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["composite_turn_exact"] is True
    assert score["false_positive_axis_count"] == 0


def test_installed_implant_extracts_implant_placed() -> None:
    matrix = load_frozen_matrix_v2()
    call = next(
        call for call in iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_stage_01_implant_placed"
    )
    frame = _frame(
        {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "implant_placed",
            "modifiers": [],
        },
        topic="prosthetics",
    )
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.stage.usable is True
    assert projected.stage.value == "implant_placed"
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["axis_outcomes"]["stage"] == "correct_expected_axis"


def test_explicit_correction_replaces_extent() -> None:
    matrix = load_frozen_matrix_v2()
    turn2 = next(
        call for call in iter_live_planner_calls(matrix)
        if call["call_id"].endswith(":turn2")
    )
    frame = _frame({"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []})
    projected = project_patient_scope_from_turn_frame(frame)
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic=turn2["topic"],
            session_turn_count=2,
            session_facts=None,
            projected_turn_scope=projected,
        )
    )
    score = score_planner_call(
        frame=frame,
        planner_status="ok",
        call_spec=turn2,
        prior_session=None,
        session_turn_count=2,
    )
    assert merged.extent == "one_tooth"
    assert score["correction_success"] is True


def test_ambiguous_conflict_stays_unknown() -> None:
    matrix = load_frozen_matrix_v2()
    call = next(
        call for call in iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_ambiguous_01_contradictory_extent"
    )
    frame = _frame(
        {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["composite_turn_exact"] is True
    assert score["false_positive_axis_count"] == 0
