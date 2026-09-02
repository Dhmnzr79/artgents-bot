from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_composer import (
    AdaptedComposerDecision,
    ComposerDecision,
    ComposerPatientSituation,
    ComposerSourceIdentityEnvelope,
)
from contracts.response_plan_post_composer import (
    ResponseSituationState,
    SituationContinuityPolicy,
)
from core.response_plan_situation_continuity import merge_situation_continuity
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
SESSION = SessionKey(client_id="demo", sid="s1")
POLICY = SituationContinuityPolicy(max_age_turns=3)


def _situation(**overrides: object) -> ComposerPatientSituation:
    payload = {
        "extent": "unknown",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": (),
    }
    payload.update(overrides)
    return ComposerPatientSituation(**payload)  # type: ignore[arg-type]


def _adapted(**overrides: object) -> AdaptedComposerDecision:
    decision_payload = {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "test",
        "service_reference_kind": "none",
        "option_reference_kind": "none",
        "topic_id": "implantation",
        "explicit_service_id": None,
        "requested_aspect_ids": ("overview",),
        "patient_situation": _situation(),
        "requested_fact_ids": (),
        "source_identity": None,
    }
    decision_payload.update(overrides)
    return AdaptedComposerDecision(
        decision=ComposerDecision(**decision_payload),  # type: ignore[arg-type]
        source_identity=None,
        warnings=(),
        diagnostics=(),
    )


def _prior(**overrides: object) -> ResponseSituationState:
    payload = {
        "session_key": SESSION,
        "topic_id": "implantation",
        "extent": "full_arch",
        "jaw": "upper",
        "stage": "unknown",
        "modifiers": (),
        "set_at_turn": 1,
    }
    payload.update(overrides)
    return ResponseSituationState(**payload)  # type: ignore[arg-type]


def test_full_arch_upper_preserved() -> None:
    result = merge_situation_continuity(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
        ),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=None,
        current_turn_index=1,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "full_arch"
    assert result.effective_scope.jaw == "upper"
    assert result.situation_delta.action == "upsert"
    assert result.situation_delta.state is not None
    assert result.situation_delta.state.set_at_turn == 1


def test_unknown_axes_inherit_session_full_arch_upper() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=_prior(),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "full_arch"
    assert result.effective_scope.jaw == "upper"
    assert result.situation_delta.action == "keep"


def test_current_jaw_overrides_prior() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation(jaw="lower")),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=_prior(jaw="upper"),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.effective_scope.jaw == "lower"
    assert result.situation_delta.action == "upsert"


def test_current_extent_overrides_prior() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation(extent="one_tooth")),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=_prior(extent="full_arch"),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "one_tooth"


def test_new_topic_does_not_inherit_implantation_axes() -> None:
    result = merge_situation_continuity(
        _adapted(topic_id=None, patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id=None,
        response_scope="clinic",
        prior_state=_prior(),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "unknown"
    assert result.effective_scope.jaw == "unknown"


def test_stale_state_not_inherited() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=_prior(set_at_turn=1),
        current_turn_index=10,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "unknown"
    assert any(d.code == "situation_session_stale" for d in result.diagnostics)


def test_read_only_inheritance_does_not_update_set_at_turn() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=_prior(set_at_turn=1),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.situation_delta.action == "keep"
    if result.merged_state is not None:
        assert result.merged_state.set_at_turn == 1


def test_current_known_axis_triggers_upsert() -> None:
    result = merge_situation_continuity(
        _adapted(patient_situation=_situation(extent="few_teeth")),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=None,
        current_turn_index=4,
        policy=POLICY,
    )
    assert result.situation_delta.action == "upsert"
    assert result.situation_delta.state is not None
    assert result.situation_delta.state.set_at_turn == 4


def test_topic_change_without_new_axes_clears() -> None:
    result = merge_situation_continuity(
        _adapted(topic_id="prosthetics", patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="prosthetics",
        response_scope="topic",
        prior_state=_prior(topic_id="implantation"),
        current_turn_index=3,
        policy=POLICY,
    )
    assert result.situation_delta.action == "clear"


def test_clinic_scope_no_stale_leakage() -> None:
    result = merge_situation_continuity(
        _adapted(topic_id=None, patient_situation=_situation()),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id=None,
        response_scope="clinic",
        prior_state=_prior(),
        current_turn_index=2,
        policy=POLICY,
    )
    assert result.effective_scope.extent == "unknown"
    assert result.effective_scope.topic is None


def test_session_key_mismatch_raises() -> None:
    other_session = SessionKey(client_id="demo", sid="other")
    with pytest.raises(Exception):
        merge_situation_continuity(
            _adapted(),
            session_key=other_session,
            source_client_id="demo",
            resolved_topic_id="implantation",
            response_scope="topic",
            prior_state=_prior(),
            current_turn_index=2,
            policy=POLICY,
        )


def test_reported_bone_deficit_maps_to_effective_scope() -> None:
    result = merge_situation_continuity(
        _adapted(
            patient_situation=_situation(
                extent="full_arch",
                jaw="upper",
                modifiers=("reported_bone_deficit",),
            ),
        ),
        session_key=SESSION,
        source_client_id="demo",
        resolved_topic_id="implantation",
        response_scope="topic",
        prior_state=None,
        current_turn_index=1,
        policy=POLICY,
    )
    assert result.effective_scope.reported_context == "reported_bone_deficit"
