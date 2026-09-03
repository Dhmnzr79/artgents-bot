from __future__ import annotations

import json

from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_session import (
    PersistedActiveService,
    PersistedSituationState,
    ResponsePlanSessionContractError,
    ResponsePlanSessionState,
    SESSION_SCHEMA_VERSION,
    SessionContinuityPolicy,
    SessionDialoguePair,
    empty_session_snapshot,
)
from core.response_plan_session import build_turn_read_bundle, serialize_prior_patient_situation
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def _policy() -> SessionContinuityPolicy:
    return SessionContinuityPolicy(
        active_service_max_age_turns=3,
        active_topic_max_age_turns=3,
        situation_max_age_turns=3,
        shown_options_max_age_turns=3,
        history_pair_limit=10,
    )


def test_empty_read_bundle_has_no_active_service(demo_bundle) -> None:
    snapshot = empty_session_snapshot(SessionKey(client_id="demo", sid="s1"))
    bundle = build_turn_read_bundle(
        snapshot, policy=_policy(), source_client_id="demo", bundle=demo_bundle
    )
    assert bundle.active_session_service_id is None
    assert bundle.recent_dialogue == ()
    assert bundle.history_turn_count == 0
    assert snapshot.current_turn_index == 1


def test_stale_active_service_not_model_visible(demo_bundle) -> None:
    session_key = SessionKey(client_id="demo", sid="s1")
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=5,
        active_service=PersistedActiveService(
            service_id="all_on_4",
            provenance="explicit_current",
            set_at_turn=1,
        ),
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": state, "exists_in_store": True})
    bundle = build_turn_read_bundle(
        snapshot, policy=_policy(), source_client_id="demo", bundle=demo_bundle
    )
    assert bundle.active_session_service_id is None
    assert bundle.composer_session_context.active_service_id is None
    assert any(item.lane == "active_service" for item in bundle.freshness_diagnostics)


def test_situation_serializes_to_prior_patient_situation(demo_bundle) -> None:
    session_key = SessionKey(client_id="demo", sid="s1")
    situation = PersistedSituationState(
        session_key=session_key,
        topic_id="implantation",
        extent="full_arch",
        jaw="upper",
        stage="unknown",
        modifiers=(),
        set_at_turn=1,
    )
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
        situation_state=situation,
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": state, "exists_in_store": True})
    bundle = build_turn_read_bundle(
        snapshot, policy=_policy(), source_client_id="demo", bundle=demo_bundle
    )
    assert bundle.prior_situation_state is not None
    assert bundle.prior_situation_state.extent == "full_arch"
    assert bundle.composer_session_context.prior_patient_situation == serialize_prior_patient_situation(
        situation.to_runtime()
    )
    payload = json.loads(bundle.composer_session_context.prior_patient_situation or "{}")
    assert payload["jaw"] == "upper"


def test_history_trimmed_to_max_composer_messages(demo_bundle) -> None:
    session_key = SessionKey(client_id="demo", sid="s1")
    pairs = tuple(
        SessionDialoguePair(
            patient_text=f"p{i}",
            assistant_text=f"a{i}",
            committed_at_turn=i,
        )
        for i in range(1, 6)
    )
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=5,
        last_committed_turn_index=5,
        dialogue_pairs=pairs,
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": state, "exists_in_store": True})
    bundle = build_turn_read_bundle(
        snapshot, policy=_policy(), source_client_id="demo", bundle=demo_bundle
    )
    assert len(bundle.recent_dialogue) == 6
    assert bundle.recent_dialogue[0].text == "p3"
    assert snapshot.current_turn_index == 6
    assert bundle.history_turn_count == 6


def test_future_set_at_turn_raises(demo_bundle) -> None:
    session_key = SessionKey(client_id="demo", sid="s1")
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=0,
        last_committed_turn_index=0,
        active_service=PersistedActiveService(
            service_id="all_on_4",
            provenance="explicit_current",
            set_at_turn=3,
        ),
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": state})
    with pytest.raises(ResponsePlanSessionContractError, match="future_set_at_turn"):
        build_turn_read_bundle(
            snapshot, policy=_policy(), source_client_id="demo", bundle=demo_bundle
        )


def test_active_topic_restored_from_shown_options_snapshot_preserves_timestamp() -> None:
    from contracts.response_plan import ResponseSessionDelta
    from contracts.response_plan_post_composer import PostComposerSelectionPlan, ResponseSituationDelta
    from contracts.response_plan_composer import ComposerDecision, ComposerPatientSituation
    from contracts.effective_scope import EffectiveScope
    from contracts.response_plan_session import (
        PersistedShownOptionsSnapshot,
        TurnRequestBinding,
    )
    from core.response_plan_session import apply_session_state_transition, create_turn_request_binding
    from tests.test_response_plan_contract import _minimal_answer_resolved

    session_key = SessionKey(client_id="demo", sid="s1")
    shown = PersistedShownOptionsSnapshot(
        session_key=session_key,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    prior = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=3,
        last_committed_turn_index=3,
        shown_options_snapshot=shown,
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": prior, "exists_in_store": True})
    binding = create_turn_request_binding(
        snapshot,
        request_id="t4",
        patient_message="Продолжаем",
    )
    decision = ComposerDecision(
        route="ANSWER",
        mode="standard",
        patient_text="Ответ.",
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        explicit_service_id=None,
        requested_aspect_ids=("overview",),
        patient_situation=ComposerPatientSituation(
            extent="unknown",
            jaw="unknown",
            stage="unknown",
            modifiers=(),
        ),
        requested_fact_ids=(),
        source_identity=None,
    )
    selection = PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id="demo",
        decision=decision,
        resolved_topic_id="implantation",
        response_scope="topic",
        reference_service_id=None,
        reference_service_status="none",
        effective_scope=EffectiveScope(),
        ranked_service_ids=(),
        visible_service_option_ids=(),
        price_candidate_service_ids=(),
        comparison_service_ids=(),
        selection_basis="none",
        selection_intent="none",
        requested_fact_candidates=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        adapter_diagnostics=(),
        diagnostics=(),
    )
    resolved = _minimal_answer_resolved(
        response_scope="topic",
        session_delta=ResponseSessionDelta(session_key=session_key, active_topic_id="implantation"),
    )
    result = apply_session_state_transition(
        prior,
        policy=_policy(),
        binding=binding,
        rendered_text="Ответ.",
        selection=selection,
        resolved=resolved,
        topic_restoration_shown_snapshot=shown,
    )
    assert result.active_topic is not None
    assert result.active_topic.topic_id == "implantation"
    assert result.active_topic.provenance == "shown_options"
    assert result.active_topic.set_at_turn == 1


def test_explicit_topic_confirmation_updates_timestamp() -> None:
    from contracts.response_plan import ResponseSessionDelta
    from contracts.response_plan_post_composer import PostComposerSelectionPlan, ResponseSituationDelta
    from contracts.response_plan_composer import ComposerDecision, ComposerPatientSituation
    from contracts.effective_scope import EffectiveScope
    from core.response_plan_session import apply_session_state_transition, create_turn_request_binding
    from tests.test_response_plan_contract import _minimal_answer_resolved

    session_key = SessionKey(client_id="demo", sid="s1")
    prior = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=0,
        last_committed_turn_index=0,
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": prior})
    binding = create_turn_request_binding(snapshot, request_id="t1", patient_message="Тема")
    decision = ComposerDecision(
        route="ANSWER",
        mode="standard",
        patient_text="Ответ.",
        service_reference_kind="none",
        option_reference_kind="none",
        topic_id="implantation",
        explicit_service_id=None,
        requested_aspect_ids=("overview",),
        patient_situation=ComposerPatientSituation(
            extent="unknown",
            jaw="unknown",
            stage="unknown",
            modifiers=(),
        ),
        requested_fact_ids=(),
        source_identity=None,
    )
    selection = PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id="demo",
        decision=decision,
        resolved_topic_id="implantation",
        response_scope="topic",
        reference_service_id=None,
        reference_service_status="none",
        effective_scope=EffectiveScope(),
        ranked_service_ids=(),
        visible_service_option_ids=(),
        price_candidate_service_ids=(),
        comparison_service_ids=(),
        selection_basis="none",
        selection_intent="none",
        requested_fact_candidates=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        adapter_diagnostics=(),
        diagnostics=(),
    )
    resolved = _minimal_answer_resolved(
        response_scope="topic",
        session_delta=ResponseSessionDelta(session_key=session_key, active_topic_id="implantation"),
    )
    result = apply_session_state_transition(
        prior,
        policy=_policy(),
        binding=binding,
        rendered_text="Ответ.",
        selection=selection,
        resolved=resolved,
    )
    assert result.active_topic is not None
    assert result.active_topic.provenance == "explicit_topic"
    assert result.active_topic.set_at_turn == 1


def test_stale_shown_options_snapshot_does_not_restore_active_topic() -> None:
    from contracts.response_plan import ResponseSessionDelta
    from contracts.response_plan_post_composer import PostComposerSelectionPlan, ResponseSituationDelta
    from contracts.response_plan_composer import ComposerDecision, ComposerPatientSituation
    from contracts.effective_scope import EffectiveScope
    from contracts.response_plan_session import PersistedActiveService, PersistedShownOptionsSnapshot
    from core.response_plan_session import apply_session_state_transition, create_turn_request_binding
    from tests.test_response_plan_contract import _minimal_answer_resolved

    session_key = SessionKey(client_id="demo", sid="s1")
    stale_policy = SessionContinuityPolicy(
        active_service_max_age_turns=5,
        active_topic_max_age_turns=5,
        situation_max_age_turns=5,
        shown_options_max_age_turns=1,
        history_pair_limit=10,
    )
    shown = PersistedShownOptionsSnapshot(
        session_key=session_key,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    prior = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=3,
        last_committed_turn_index=3,
        active_service=PersistedActiveService(
            service_id="all_on_4",
            provenance="explicit_current",
            set_at_turn=1,
        ),
        shown_options_snapshot=shown,
    )
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": prior, "exists_in_store": True})
    binding = create_turn_request_binding(
        snapshot,
        request_id="t4",
        patient_message="Продолжаем",
    )
    decision = ComposerDecision(
        route="ANSWER",
        mode="standard",
        patient_text="Ответ.",
        service_reference_kind="active_session",
        option_reference_kind="shown_options",
        topic_id=None,
        explicit_service_id=None,
        requested_aspect_ids=("overview",),
        patient_situation=ComposerPatientSituation(
            extent="unknown",
            jaw="unknown",
            stage="unknown",
            modifiers=(),
        ),
        requested_fact_ids=(),
        source_identity=None,
    )
    selection = PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id="demo",
        decision=decision,
        resolved_topic_id="implantation",
        response_scope="topic",
        reference_service_id="all_on_4",
        reference_service_status="compatible",
        effective_scope=EffectiveScope(),
        ranked_service_ids=(),
        visible_service_option_ids=(),
        price_candidate_service_ids=(),
        comparison_service_ids=(),
        selection_basis="none",
        selection_intent="none",
        requested_fact_candidates=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        adapter_diagnostics=(),
        diagnostics=(),
    )
    resolved = _minimal_answer_resolved(
        response_scope="topic",
        session_delta=ResponseSessionDelta(session_key=session_key, active_topic_id="implantation"),
    )
    result = apply_session_state_transition(
        prior,
        policy=stale_policy,
        binding=binding,
        rendered_text="Ответ.",
        selection=selection,
        resolved=resolved,
        topic_restoration_shown_snapshot=None,
    )
    assert result.active_topic is None or result.active_topic.provenance != "shown_options"
