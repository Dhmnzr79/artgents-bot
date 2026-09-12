from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from contracts.response_plan import (
    FinalizedCommercialIds,
    FrozenPriceOfferRow,
    ResponseSessionDelta,
    ResponseUIProjection,
    SessionKey,
    UiButtonCandidate,
)
from contracts.response_plan_session import (
    FINGERPRINT_FORMAT_VERSION,
    HistoricalPriceOffersSnapshot,
    PreparedSessionUpdate,
    ResponsePlanSessionContractError,
    ResponsePlanSessionSnapshot,
    ResponsePlanSessionState,
    SESSION_SCHEMA_VERSION,
    SessionContinuityPolicy,
    SessionDialoguePair,
    SessionSnapshotIdentity,
    TurnPipelineOutcome,
    TurnRequestBinding,
    attach_update_fingerprint,
    compute_update_fingerprint,
    empty_session_snapshot,
)
from core.response_plan_session import (
    apply_session_state_transition,
    create_turn_request_binding,
    prepare_session_update,
    validate_bound_pipeline_outcome,
    validate_topic_restoration_shown_snapshot_binding,
)
from tests.test_response_plan_contract import _minimal_answer_resolved, session


def _policy() -> SessionContinuityPolicy:
    return SessionContinuityPolicy(
        active_service_max_age_turns=3,
        active_topic_max_age_turns=3,
        situation_max_age_turns=3,
        shown_options_max_age_turns=3,
        history_pair_limit=10,
    )


def _minimal_ui() -> ResponseUIProjection:
    return ResponseUIProjection(projected_commercial_ids=FinalizedCommercialIds())


def _binding(snapshot: ResponsePlanSessionSnapshot, *, request_id: str = "r1") -> TurnRequestBinding:
    return create_turn_request_binding(
        snapshot,
        request_id=request_id,
        patient_message="hi",
    )


def test_empty_snapshot_has_zero_revision() -> None:
    snapshot = empty_session_snapshot(SessionKey(client_id="demo", sid="s1"))
    assert snapshot.exists_in_store is False
    assert snapshot.state.revision == 0
    assert snapshot.current_turn_index == 1


def test_session_continuity_policy_rejects_bool_age() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SessionContinuityPolicy(
            active_service_max_age_turns=True,  # type: ignore[arg-type]
            active_topic_max_age_turns=3,
            situation_max_age_turns=3,
            shown_options_max_age_turns=3,
            history_pair_limit=10,
        )


def test_dialogue_pair_requires_non_blank_text() -> None:
    with pytest.raises(ValidationError):
        SessionDialoguePair(
            patient_text=" ",
            assistant_text="ok",
            committed_at_turn=1,
        )


def test_fingerprint_changes_when_session_delta_changes() -> None:
    session_key = session(client_id="demo", sid="s1")
    snapshot = empty_session_snapshot(session_key)
    binding = _binding(snapshot)
    base_state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
        dialogue_pairs=(
            SessionDialoguePair(
                patient_text="hi",
                assistant_text="hello",
                committed_at_turn=1,
            ),
        ),
    )
    resolved_a = _minimal_answer_resolved(
        response_scope="clinic",
        session_delta=ResponseSessionDelta(session_key=session_key),
    )
    prepared_a = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="hi",
        rendered_text="hello",
        proposed_state=base_state,
        resolved_plan=resolved_a,
        ui_projection=_minimal_ui(),
        selection=_selection_stub(session_key),
        update_fingerprint="",
    )
    resolved_b = _minimal_answer_resolved(
        route="CLARIFY",
        mode="standard",
        response_scope="clinic",
        patient_text="clarify?",
        session_delta=ResponseSessionDelta(
            session_key=session_key,
            terminal_state="clarify",
            clarify_pending=True,
        ),
    )
    prepared_b = prepared_a.model_copy(update={"resolved_plan": resolved_b, "update_fingerprint": ""})
    assert compute_update_fingerprint(attach_update_fingerprint(prepared_a)) != compute_update_fingerprint(
        attach_update_fingerprint(prepared_b)
    )


def test_fingerprint_changes_when_ui_buttons_change() -> None:
    session_key = session(client_id="demo", sid="s1")
    snapshot = empty_session_snapshot(session_key)
    binding = _binding(snapshot)
    base_state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
    )
    resolved = _minimal_answer_resolved(
        response_scope="clinic",
        session_delta=ResponseSessionDelta(session_key=session_key),
    )
    ui_a = _minimal_ui()
    ui_b = ResponseUIProjection(
        projected_commercial_ids=FinalizedCommercialIds(),
        buttons=(
            UiButtonCandidate(
                source_client_id="demo",
                button_id="book",
                label="Записаться",
                action_kind="cta",
            ),
        ),
    )
    prepared_a = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="hi",
        rendered_text="hello",
        proposed_state=base_state,
        resolved_plan=resolved,
        ui_projection=ui_a,
        selection=_selection_stub(session_key),
        update_fingerprint="",
    )
    prepared_b = prepared_a.model_copy(update={"ui_projection": ui_b, "update_fingerprint": ""})
    assert compute_update_fingerprint(attach_update_fingerprint(prepared_a)) != compute_update_fingerprint(
        attach_update_fingerprint(prepared_b)
    )


def test_fingerprint_format_version_constant() -> None:
    assert FINGERPRINT_FORMAT_VERSION == 3


def test_historical_price_row_foreign_client_rejected() -> None:
    with pytest.raises(ValidationError):
        ResponsePlanSessionState(
            schema_version=SESSION_SCHEMA_VERSION,
            session_key=SessionKey(client_id="demo", sid="s1"),
            revision=1,
            last_committed_turn_index=1,
            historical_price_offers=HistoricalPriceOffersSnapshot(
                rows=(
                    FrozenPriceOfferRow(
                        source_client_id="nikadent",
                        offer_id="offer_1",
                        service_id="svc",
                        offer_label="Label",
                        amount=1000,
                        currency="RUB",
                        billing_unit="service",
                    ),
                ),
                shown_at_turn=1,
            ),
        )


def test_persisted_active_service_rejects_padded_id() -> None:
    from contracts.response_plan_session import PersistedActiveService

    with pytest.raises(ValidationError):
        PersistedActiveService(
            service_id=" all_on_4",
            provenance="explicit_current",
            set_at_turn=1,
        )


def _selection_stub(session_key: SessionKey):
    from contracts.response_plan_post_composer import PostComposerSelectionPlan, ResponseSituationDelta
    from contracts.response_plan_composer import ComposerDecision, ComposerPatientSituation
    from contracts.effective_scope import EffectiveScope

    decision = ComposerDecision(
        route="ANSWER",
        mode="standard",
        patient_text="hello",
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
    return PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id=session_key.client_id,
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


@pytest.mark.parametrize(
    ("value", "factory"),
    [
        (True, lambda v: SessionContinuityPolicy(active_service_max_age_turns=v, active_topic_max_age_turns=3, situation_max_age_turns=3, shown_options_max_age_turns=3, history_pair_limit=10)),
        (1.0, lambda v: SessionContinuityPolicy(active_service_max_age_turns=v, active_topic_max_age_turns=3, situation_max_age_turns=3, shown_options_max_age_turns=3, history_pair_limit=10)),
        ("1", lambda v: SessionContinuityPolicy(active_service_max_age_turns=v, active_topic_max_age_turns=3, situation_max_age_turns=3, shown_options_max_age_turns=3, history_pair_limit=10)),
        (-1, lambda v: SessionContinuityPolicy(active_service_max_age_turns=v, active_topic_max_age_turns=3, situation_max_age_turns=3, shown_options_max_age_turns=3, history_pair_limit=10)),
    ],
)
def test_session_policy_rejects_non_strict_integers(value: object, factory) -> None:
    with pytest.raises((ValidationError, ValueError)):
        factory(value)


def test_fingerprint_changes_when_resolved_patient_text_changes() -> None:
    session_key = session(client_id="demo", sid="s1")
    snapshot = empty_session_snapshot(session_key)
    binding = _binding(snapshot)
    base_state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
    )
    resolved_a = _minimal_answer_resolved(
        response_scope="clinic",
        session_delta=ResponseSessionDelta(session_key=session_key),
    )
    resolved_b = resolved_a.model_copy(update={"patient_text": "Другой ответ"})
    prepared_a = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="hi",
        rendered_text="hello",
        proposed_state=base_state,
        resolved_plan=resolved_a,
        ui_projection=_minimal_ui(),
        selection=_selection_stub(session_key),
        update_fingerprint="",
    )
    prepared_b = prepared_a.model_copy(update={"resolved_plan": resolved_b, "update_fingerprint": ""})
    assert compute_update_fingerprint(attach_update_fingerprint(prepared_a)) != compute_update_fingerprint(
        attach_update_fingerprint(prepared_b)
    )


def test_fingerprint_stable_for_identical_prepared() -> None:
    session_key = session(client_id="demo", sid="s1")
    snapshot = empty_session_snapshot(session_key)
    binding = _binding(snapshot)
    base_state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
    )
    resolved = _minimal_answer_resolved(
        response_scope="clinic",
        session_delta=ResponseSessionDelta(session_key=session_key),
    )
    prepared = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="hi",
        rendered_text="hello",
        proposed_state=base_state,
        resolved_plan=resolved,
        ui_projection=_minimal_ui(),
        selection=_selection_stub(session_key),
        update_fingerprint="",
    )
    first = compute_update_fingerprint(attach_update_fingerprint(prepared))
    second = compute_update_fingerprint(attach_update_fingerprint(prepared))
    assert first == second


def test_prepared_rendered_text_mismatch_rejected() -> None:
    from contracts.response_plan_post_composer import ResponseSituationDelta
    from core.response_plan_session import validate_prepared_response_coherence
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui

    session_key = session(client_id="demo", sid="s1")
    snapshot = empty_session_snapshot(session_key)
    binding = _binding(snapshot)
    from dataclasses import replace

    resolved = _minimal_answer_resolved(
        response_scope="topic",
        session_delta=ResponseSessionDelta(session_key=session_key, active_topic_id="implantation"),
    )
    rendered = render_response_text(resolved)
    ui = project_response_ui(resolved)
    selection = replace(
        _selection_stub(session_key),
        decision=replace(_selection_stub(session_key).decision, patient_text=resolved.patient_text),
    )
    prepared = PreparedSessionUpdate(
        request_binding=binding,
        patient_message="hi",
        rendered_text=rendered + " tampered",
        proposed_state=snapshot.state,
        resolved_plan=resolved,
        ui_projection=ui,
        selection=selection,
        update_fingerprint="",
    )
    with pytest.raises(ResponsePlanSessionContractError, match="prepared_rendered_text_mismatch"):
        validate_prepared_response_coherence(
            selection=prepared.selection,
            resolved=prepared.resolved_plan,
            rendered_text=prepared.rendered_text,
            ui_projection=prepared.ui_projection,
            situation_delta=ResponseSituationDelta(action="keep"),
        )


def test_coherence_rejects_mismatched_patient_text() -> None:
    from contracts.response_plan_post_composer import ResponseSituationDelta
    from core.response_plan_session import validate_prepared_response_coherence
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui

    session_key = session(client_id="demo", sid="s1")
    selection = _selection_stub(session_key)
    resolved_a = _minimal_answer_resolved(
        response_scope="clinic",
        session_delta=ResponseSessionDelta(session_key=session_key),
        patient_text="Ответ A",
    )
    resolved_b = resolved_a.model_copy(update={"patient_text": "Ответ B"})
    from dataclasses import replace

    selection = replace(selection, decision=replace(selection.decision, patient_text="Ответ A"))
    with pytest.raises(ResponsePlanSessionContractError, match="prepared_patient_text_mismatch"):
        validate_prepared_response_coherence(
            selection=selection,
            resolved=resolved_b,
            rendered_text=render_response_text(resolved_b),
            ui_projection=project_response_ui(resolved_b),
            situation_delta=ResponseSituationDelta(action="keep"),
        )


def test_coherence_rejects_price_row_for_foreign_service() -> None:
    from contracts.response_plan import FinalizedCommercialIds, FrozenPriceOfferRow, ResolvedPriceBlock
    from contracts.response_plan_post_composer import ResponseSituationDelta
    from core.response_plan_session import validate_prepared_response_coherence
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui
    from dataclasses import replace

    session_key = session(client_id="demo", sid="s1")
    selection = _selection_stub(session_key)
    selection = replace(
        selection,
        response_scope="service",
        reference_service_id="all_on_4",
        reference_service_status="compatible",
        price_candidate_service_ids=("all_on_4",),
        decision=replace(
            selection.decision,
            patient_text="Цена",
            service_reference_kind="explicit_current",
            explicit_service_id="all_on_4",
        ),
    )
    price_row = FrozenPriceOfferRow(
        source_client_id="demo",
        offer_id="offer_other",
        service_id="other_service",
        offer_label="Other",
        amount=100_000,
        currency="RUB",
        billing_unit="service",
    )
    resolved = _minimal_answer_resolved(
        response_scope="service",
        patient_text="Цена",
        session_delta=ResponseSessionDelta(
            session_key=session_key,
            active_service_id="all_on_4",
            shown_price_offer_ids=("offer_other",),
        ),
        price_block=ResolvedPriceBlock(
            source_client_id="demo",
            offer_ids=("offer_other",),
            display_text="100 000 ₽",
            owner="canonical_single",
            amount=100_000,
            currency="RUB",
            billing_unit="service",
            offer_rows=(price_row,),
        ),
        finalized_commercial_ids=FinalizedCommercialIds(price_offer_ids=("offer_other",)),
    )
    with pytest.raises(ResponsePlanSessionContractError, match="prepared_price_row_service_mismatch"):
        validate_prepared_response_coherence(
            selection=selection,
            resolved=resolved,
            rendered_text=render_response_text(resolved),
            ui_projection=project_response_ui(resolved),
            situation_delta=ResponseSituationDelta(action="keep"),
        )


def test_coherence_allows_exact_service_price() -> None:
    from contracts.response_plan import FinalizedCommercialIds, FrozenPriceOfferRow, ResolvedPriceBlock
    from contracts.response_plan_post_composer import ResponseSituationDelta
    from core.response_plan_session import validate_prepared_response_coherence
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui
    from dataclasses import replace

    session_key = session(client_id="demo", sid="s1")
    selection = _selection_stub(session_key)
    selection = replace(
        selection,
        response_scope="service",
        reference_service_id="all_on_4",
        reference_service_status="compatible",
        price_candidate_service_ids=("all_on_4",),
        decision=replace(
            selection.decision,
            patient_text="Цена",
            service_reference_kind="explicit_current",
            explicit_service_id="all_on_4",
        ),
    )
    price_row = FrozenPriceOfferRow(
        source_client_id="demo",
        offer_id="offer_a",
        service_id="all_on_4",
        offer_label="All-on-4",
        amount=120_000,
        currency="RUB",
        billing_unit="service",
    )
    resolved = _minimal_answer_resolved(
        response_scope="service",
        patient_text="Цена",
        session_delta=ResponseSessionDelta(
            session_key=session_key,
            active_service_id="all_on_4",
            shown_price_offer_ids=("offer_a",),
        ),
        price_block=ResolvedPriceBlock(
            source_client_id="demo",
            offer_ids=("offer_a",),
            display_text="120 000 ₽",
            owner="canonical_single",
            amount=120_000,
            currency="RUB",
            billing_unit="service",
            offer_rows=(price_row,),
        ),
        finalized_commercial_ids=FinalizedCommercialIds(price_offer_ids=("offer_a",)),
    )
    validate_prepared_response_coherence(
        selection=selection,
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        situation_delta=ResponseSituationDelta(action="keep"),
    )


def _source_shown_snapshot(session_key: SessionKey) -> "PersistedShownOptionsSnapshot":
    from contracts.response_plan_session import PersistedShownOptionsSnapshot

    return PersistedShownOptionsSnapshot(
        session_key=session_key,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )


def _source_state_with_shown(session_key: SessionKey) -> ResponsePlanSessionState:
    return ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
        shown_options_snapshot=_source_shown_snapshot(session_key),
    )


def _minimal_pipeline(
    snapshot: ResponsePlanSessionSnapshot,
    binding: TurnRequestBinding,
) -> TurnPipelineOutcome:
    from contracts.response_plan_composer import AdaptedComposerDecision
    from contracts.response_plan_materialization import MaterializationTrace, MaterializedResponseOutcome
    from contracts.response_plan_post_composer import ResponseSituationDelta
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui

    session_key = snapshot.state.session_key
    selection = _selection_stub(session_key)
    resolved = _minimal_answer_resolved(
        response_scope="topic",
        session_delta=ResponseSessionDelta(session_key=session_key, active_topic_id="implantation"),
    )
    from dataclasses import replace

    selection = replace(
        selection,
        decision=replace(selection.decision, patient_text=resolved.patient_text),
    )
    rendered = render_response_text(resolved)
    ui = project_response_ui(resolved)
    adapted = AdaptedComposerDecision(
        decision=selection.decision,
        source_identity=None,
        warnings=(),
        diagnostics=(),
    )
    materialized = MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=rendered,
        ui_projection=ui,
        materialization_diagnostics=(),
        selection_diagnostics=(),
        adapter_diagnostics=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        trace=MaterializationTrace(
            price_lookup_mode=None,
            considered_offers=(),
            selected_offers=(),
        ),
    )
    return TurnPipelineOutcome(
        request_binding=binding,
        adapted=adapted,
        selection=selection,
        materialized=materialized,
        rendered_text=rendered,
        ui_projection=ui,
    )


def test_topic_restoration_binding_accepts_matching_source() -> None:
    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    binding = _binding(empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True}))
    shown = _source_shown_snapshot(session_key)
    validate_topic_restoration_shown_snapshot_binding(
        source_state=source,
        request_binding=binding,
        topic_restoration_shown_snapshot=shown,
    )


def test_topic_restoration_binding_accepts_none() -> None:
    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    binding = _binding(empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True}))
    validate_topic_restoration_shown_snapshot_binding(
        source_state=source,
        request_binding=binding,
        topic_restoration_shown_snapshot=None,
    )


@pytest.mark.parametrize(
    ("foreign_key", "expected_error"),
    [
        (SessionKey(client_id="other", sid="s1"), "topic_restoration_source_session_mismatch"),
        (SessionKey(client_id="demo", sid="s2"), "topic_restoration_source_session_mismatch"),
    ],
)
def test_topic_restoration_binding_rejects_foreign_session(
    foreign_key: SessionKey,
    expected_error: str,
) -> None:
    from contracts.response_plan_session import PersistedShownOptionsSnapshot

    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    binding = _binding(empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True}))
    foreign = PersistedShownOptionsSnapshot(
        session_key=foreign_key,
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    with pytest.raises(ResponsePlanSessionContractError, match=expected_error):
        validate_topic_restoration_shown_snapshot_binding(
            source_state=source,
            request_binding=binding,
            topic_restoration_shown_snapshot=foreign,
        )


@pytest.mark.parametrize(
    "field_name,field_value",
    [
        ("shown_at_turn", 4),
        ("topic_id", "other_topic"),
        ("service_ids", ("all_on_6",)),
        ("service_ids", ("all_on_4", "all_on_6")),
        ("provenance", "finalized_plan_price_offers"),
    ],
)
def test_topic_restoration_binding_rejects_altered_source_fields(
    field_name: str,
    field_value: object,
) -> None:
    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    binding = _binding(empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True}))
    altered = _source_shown_snapshot(session_key).model_copy(update={field_name: field_value})
    with pytest.raises(ResponsePlanSessionContractError, match="topic_restoration_source_snapshot_mismatch"):
        validate_topic_restoration_shown_snapshot_binding(
            source_state=source,
            request_binding=binding,
            topic_restoration_shown_snapshot=altered,
        )


def test_topic_restoration_binding_rejects_source_when_prior_snapshot_missing() -> None:
    session_key = session(client_id="demo", sid="s1")
    source = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=session_key,
        revision=1,
        last_committed_turn_index=1,
    )
    binding = _binding(empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True}))
    with pytest.raises(ResponsePlanSessionContractError, match="topic_restoration_source_snapshot_missing"):
        validate_topic_restoration_shown_snapshot_binding(
            source_state=source,
            request_binding=binding,
            topic_restoration_shown_snapshot=_source_shown_snapshot(session_key),
        )


def test_prepare_rejects_foreign_topic_restoration_source() -> None:
    from contracts.response_plan_session import PersistedShownOptionsSnapshot

    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True})
    binding = _binding(snapshot)
    pipeline = _minimal_pipeline(snapshot, binding)
    foreign = PersistedShownOptionsSnapshot(
        session_key=SessionKey(client_id="other", sid="s1"),
        topic_id="implantation",
        service_ids=("all_on_4",),
        shown_at_turn=1,
    )
    with pytest.raises(ResponsePlanSessionContractError, match="topic_restoration_source_session_mismatch"):
        prepare_session_update(
            snapshot,
            policy=_policy(),
            pipeline=pipeline,
            expected_binding=binding,
            topic_restoration_shown_snapshot=foreign,
        )


def test_prepare_accepts_matching_topic_restoration_source() -> None:
    session_key = session(client_id="demo", sid="s1")
    source = _source_state_with_shown(session_key)
    snapshot = empty_session_snapshot(session_key).model_copy(update={"state": source, "exists_in_store": True})
    binding = _binding(snapshot)
    pipeline = _minimal_pipeline(snapshot, binding)
    prepared = prepare_session_update(
        snapshot,
        policy=_policy(),
        pipeline=pipeline,
        expected_binding=binding,
        topic_restoration_shown_snapshot=_source_shown_snapshot(session_key),
    )
    assert prepared.topic_restoration_shown_snapshot == _source_shown_snapshot(session_key)
