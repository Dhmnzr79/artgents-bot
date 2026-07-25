"""Offline blast-radius tests for A9R2c full planner backend (no LLM)."""

from __future__ import annotations

import os

from config import QWEN_PLUS_MODEL
from core.turn_planner_llm import _PATIENT_SCOPE_PROMPT, _SYSTEM
from evals.v5 import a9r2b_patient_scope_live_contract as a9r2b_contract
from evals.v5 import a9r2c_patient_scope_live_contract as contract
from evals.v5.a9r2_patient_scope_live_contract import assert_frozen_a9r2_live_artifacts_unchanged
from evals.v5.a9r2_patient_scope_live_harness import configure_live_env
from evals.v5.a9r2_patient_scope_live_scoring import score_planner_call
from tests.test_a9r2_planner_prompt_calibration_offline import (
    test_all_on_4_info_and_price_remain_all_unknown,
    test_ambiguous_conflict_stays_unknown,
    test_installed_implant_extracts_implant_placed,
    test_prompt_contains_semantic_calibration_rules,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_a9r1_offline_harness import (
    test_a9_v1_v2_matrix_blobs_unchanged as _a9_shadow_blobs_unchanged,
)
from tests.test_patient_scope_a9r_matrix_v3_contract import test_a9r_v3_matrix_blob_frozen


def test_a9r2c_uses_qwen37_plus_model() -> None:
    assert contract.OWNER_APPROVED_PLANNER_MODEL == QWEN_PLUS_MODEL == "qwen3.7-plus"


def test_configure_live_env_pins_a9r2c_model() -> None:
    prior = os.environ.get("TURN_PLANNER_LLM_MODEL")
    try:
        configure_live_env(contract=contract)
        assert os.environ["TURN_PLANNER_LLM_MODEL"] == "qwen3.7-plus"
    finally:
        if prior is None:
            os.environ.pop("TURN_PLANNER_LLM_MODEL", None)
        else:
            os.environ["TURN_PLANNER_LLM_MODEL"] = prior


def test_planner_system_prompt_preserves_service_topic_routing() -> None:
    for snippet in (
        "service_id",
        "topic",
        "route",
        "aspects",
        "All-on-4",
        "needs_clarify",
        "followup_of",
    ):
        assert snippet in _SYSTEM
    assert _PATIENT_SCOPE_PROMPT in _SYSTEM


def test_no_new_prompt_rules_beyond_calibration_baseline() -> None:
    test_prompt_contains_semantic_calibration_rules()


def test_patient_scope_matrix_v3_behaviors_unchanged() -> None:
    test_all_on_4_info_and_price_remain_all_unknown()
    test_ambiguous_conflict_stays_unknown()
    test_installed_implant_extracts_implant_placed()


def test_reported_context_not_material_gate_axis() -> None:
    matrix = contract.load_frozen_matrix_v3()
    call = next(
        call for call in contract.iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_negative_01_all_on_4_info"
    )
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_scope": {
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": ["reported_bone_deficit"],
            },
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["material_false_positive_axis_count"] == 0
    assert score["diagnostic_false_positive_axis_count"] == 1


def test_frozen_matrices_and_live_artifacts_unchanged() -> None:
    test_a9r_v3_matrix_blob_frozen()
    _a9_shadow_blobs_unchanged()
    test_w1b_snapshot_checksums_unchanged()
    assert_frozen_a9r2_live_artifacts_unchanged()
    a9r2b_contract.assert_frozen_a9r2b_live_artifacts_unchanged()
