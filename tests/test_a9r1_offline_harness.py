"""A9R1 offline harness against frozen patient_scope_a9r_matrix.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from contracts.ui_scope_action import UiScopeAction
from core.target_effective_scope import SessionPatientFacts
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
    simulate_session_patient_facts_after_turn,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from core.target_strategy_context import selection_patient_context_from_inputs
from core.turn_frame_from_raw import build_turn_frame_from_raw
from session import mem_get, mem_reset

_MATRIX = Path("evals/v5/demo/patient_scope_a9r_matrix.json")
_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic"})


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _load_matrix() -> dict:
    return json.loads(_MATRIX.read_text(encoding="utf-8"))


def _native_frame(
    patient_scope: dict,
    *,
    topic: str = "implantation",
    service_id: str | None = None,
):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": service_id,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": patient_scope,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _project_and_merge(
    patient_scope: dict,
    *,
    topic: str = "implantation",
    service_id: str | None = None,
    **merge_kwargs,
):
    frame = _native_frame(patient_scope, topic=topic, service_id=service_id)
    projected = project_patient_scope_from_turn_frame(frame)
    return merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            projected_turn_scope=projected,
            **merge_kwargs,
        )
    )


def _session_from_setup(raw: dict) -> SessionPatientFacts:
    return SessionPatientFacts(
        extent=raw["extent"],
        topic=raw["topic"],
        provenance=raw["provenance"],
        ref=raw["ref"],
        set_at_turn=raw["set_at_turn"],
        stage=raw.get("stage"),
        jaw=raw.get("jaw"),
        reported_context=raw.get("reported_context"),
    )


def test_a9r_matrix_blob_unchanged() -> None:
    assert _git_blob_hash(_MATRIX) == "36d137112007a3fb0a96ad0759aa111af6115a35"


def test_a9_v1_v2_matrix_blobs_unchanged() -> None:
    assert _git_blob_hash(Path("evals/v5/demo/patient_scope_shadow_matrix.json")) == (
        "d459073bbf8767f7ff590ece2958f7aa8cb18b25"
    )
    assert _git_blob_hash(Path("evals/v5/demo/patient_scope_shadow_matrix_v2.json")) == (
        "8de7698266bb61f237618f39b18a8b984e8ea5cd"
    )


@pytest.mark.parametrize(
    "case_id",
    [
        "a9r_extent_01_full_arch_price_question",
        "a9r_extent_02_one_tooth_restore",
        "a9r_extent_03_few_teeth_missing",
        "a9r_jaw_01_upper",
        "a9r_jaw_02_lower",
        "a9r_jaw_03_both",
        "a9r_stage_01_implant_placed",
        "a9r_stage_02_natural_tooth_present",
    ],
)
def test_matrix_positive_cases_project_and_merge(case_id: str) -> None:
    case = next(c for c in _load_matrix()["cases"] if c["id"] == case_id)
    expected = case["expected_effective_scope"]
    patient_scope = {
        "extent": expected.get("extent", "unknown"),
        "jaw": expected.get("jaw", "unknown"),
        "stage": expected.get("stage", "unknown"),
        "modifiers": list(expected.get("modifiers") or []),
    }
    merged = _project_and_merge(
        patient_scope,
        topic=case["topic"],
        current_topic=case["topic"],
        session_turn_count=1,
        session_facts=None,
    )
    assert merged.extent == expected["extent"]
    assert merged.jaw == expected["jaw"]
    if expected.get("stage") == "unknown":
        assert merged.stage is None
    else:
        assert merged.stage == expected["stage"]


@pytest.mark.parametrize(
    "case_id",
    [
        "a9r_negative_01_all_on_4_info",
        "a9r_negative_02_all_on_4_price",
        "a9r_negative_03_implant_word_only",
        "a9r_ambiguous_01_contradictory_extent",
        "a9r_ambiguous_02_vague_several",
    ],
)
def test_matrix_negative_and_ambiguous_do_not_invent_scope(case_id: str) -> None:
    case = next(c for c in _load_matrix()["cases"] if c["id"] == case_id)
    service_id = "all_on_4" if "all_on_4" in case_id else None
    merged = _project_and_merge(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        topic=case["topic"],
        service_id=service_id,
        current_topic=case["topic"],
        session_turn_count=1,
        session_facts=None,
    )
    assert merged.extent == "unknown"
    assert merged.jaw == "unknown"
    assert merged.stage is None


def test_matrix_correction_replaces_session_extent() -> None:
    case = next(
        c for c in _load_matrix()["cases"]
        if c["id"] == "a9r_correction_01_one_tooth_after_full_arch"
    )
    turn1 = case["turns"][0]
    turn2 = case["turns"][1]
    merged1 = _project_and_merge(
        {
            "extent": turn1["expected_effective_scope"]["extent"],
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        },
        topic=case["topic"],
        current_topic=case["topic"],
        session_turn_count=1,
        session_facts=None,
    )
    sim1 = simulate_session_patient_facts_after_turn(
        merged=merged1,
        prior=None,
        current_topic=case["topic"],
        session_turn_count=1,
    )
    assert sim1.wrote is True
    assert sim1.facts is not None
    assert sim1.facts.extent == "full_arch"

    merged2 = _project_and_merge(
        {
            "extent": turn2["expected_effective_scope"]["extent"],
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        },
        topic=case["topic"],
        current_topic=case["topic"],
        session_turn_count=2,
        session_facts=sim1.facts,
    )
    assert merged2.extent == "one_tooth"
    assert merged2.extent != turn1["expected_effective_scope"]["extent"]


def test_matrix_ui_priority_case() -> None:
    case = next(c for c in _load_matrix()["cases"] if c["id"] == "a9r_ui_priority_01_scope_click_beats_text")
    setup = case["setup"]
    ui = UiScopeAction(
        extent=setup["current_ui_action"]["extent"],
        topic=setup["current_ui_action"]["topic"],
        ref=setup["current_ui_action"]["ref"],
    )
    merged = _project_and_merge(
        setup["planner_patient_scope"],
        current_topic="implantation",
        session_turn_count=1,
        session_facts=None,
        current_ui_scope_action=ui,
    )
    assert merged.extent == case["expected_effective_scope"]["extent"]
    assert merged.extent_axis.source == "ui_action"


def test_matrix_session_topic_change_clears() -> None:
    case = next(c for c in _load_matrix()["cases"] if c["id"] == "a9r_session_01_topic_change_clears")
    setup = case["setup"]
    session = _session_from_setup(setup["session_patient_facts"])
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic=setup["current_topic"],
            session_turn_count=setup["session_turn_count"],
            session_facts=session,
            projected_turn_scope=None,
        )
    )
    assert merged.extent == "unknown"
    assert merged.source == "unknown"


def test_matrix_stale_session_ignored() -> None:
    case = next(c for c in _load_matrix()["cases"] if c["id"] == "a9r_session_02_stale_session_ignored")
    setup = case["setup"]
    session = _session_from_setup(setup["session_patient_facts"])
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic=setup["current_topic"],
            session_turn_count=setup["session_turn_count"],
            session_facts=session,
            projected_turn_scope=None,
        )
    )
    assert merged.extent == "unknown"


def test_matrix_reset_clears_session() -> None:
    sid = "a9r-reset-test"
    mem_reset(sid)
    mem_get(sid)["patient_facts"] = {
        "extent": "few_teeth",
        "topic": "implantation",
        "provenance": "test",
        "ref": "test",
        "set_at_turn": 1,
    }
    mem_reset(sid)
    assert "patient_facts" not in mem_get(sid)


def test_matrix_sid_isolation() -> None:
    sid_a = "s-a9r-a"
    sid_b = "s-a9r-b"
    mem_reset(sid_a)
    mem_reset(sid_b)
    mem_get(sid_a)["patient_facts"] = {
        "extent": "one_tooth",
        "topic": "implantation",
        "provenance": "test",
        "ref": "test",
        "set_at_turn": 1,
    }
    assert "patient_facts" not in mem_get(sid_b)
    merged_b = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=2,
            session_facts=None,
            projected_turn_scope=None,
        )
    )
    assert merged_b.extent == "unknown"


def test_matrix_scalar_bridge_shadow_only_not_authority() -> None:
    case = next(
        c for c in _load_matrix()["cases"]
        if c["id"] == "a9r_deterministic_01_scalar_bridge_one_tooth"
    )
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "patient_situation": case["raw_patient_situation"],
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    assert frame.patient_scope.extent == case["expected_shadow_scope"]["extent"]
    projected = project_patient_scope_from_turn_frame(frame)
    assert projected.extent.usable is False
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=projected,
        )
    )
    assert merged.extent == "unknown"


def test_natural_tooth_present_reaches_selection_patient_context_via_harness() -> None:
    case = next(
        c for c in _load_matrix()["cases"]
        if c["id"] == "a9r_stage_02_natural_tooth_present"
    )
    expected = case["expected_effective_scope"]
    merged = _project_and_merge(
        {
            "extent": expected["extent"],
            "jaw": expected["jaw"],
            "stage": expected["stage"],
            "modifiers": [],
        },
        topic=case["topic"],
        current_topic=case["topic"],
        session_turn_count=1,
        session_facts=None,
    )
    patient = selection_patient_context_from_inputs(merged)
    assert patient.stage == "natural_tooth_present"


def test_invalid_session_not_overwritten_by_unknown_turn() -> None:
    session = _session_from_setup(
        {
            "extent": "few_teeth",
            "topic": "implantation",
            "provenance": "target:ui_scope/implantation/few_teeth",
            "ref": "target:ui_scope/implantation/few_teeth",
            "set_at_turn": 1,
        }
    )
    merged = _project_and_merge(
        {"extent": "several", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        current_topic="implantation",
        session_turn_count=2,
        session_facts=session,
    )
    assert merged.extent == "few_teeth"
    sim = simulate_session_patient_facts_after_turn(
        merged=merged,
        prior=session,
        current_topic="implantation",
        session_turn_count=2,
    )
    assert sim.wrote is False
