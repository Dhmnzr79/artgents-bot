"""Request-bound session turn bridge over existing Composer/materialization pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from contracts.response_plan_composer_input import ComposerInputContext
from contracts.response_plan_materialization import ResponsePlanMaterializationSources
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_plan_session import (
    PreparedSessionUpdate,
    ResponsePlanSessionContractError,
    ResponsePlanSessionSnapshot,
    SessionContinuityPolicy,
    TurnPipelineOutcome,
    TurnRequestBinding,
)
from contracts.response_schema import ResponseSchemaBundle
from core.response_plan_composer_authority import build_composer_decision_authority
from core.response_plan_composer_executor import execute_composer_decision
from core.response_plan_materialization import resolve_materialized_response
from core.response_plan_post_composer import resolve_post_composer_selection
from core.response_plan_session import (
    build_turn_read_bundle,
    create_turn_request_binding,
    prepare_session_update,
    resolve_topic_restoration_shown_snapshot,
    shown_options_freshness_policy,
    situation_continuity_policy,
    validate_bound_pipeline_outcome,
)
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui


class ComposerBackend(Protocol):
    def generate(self, invocation: object, /) -> str: ...


@dataclass(frozen=True, slots=True)
class BoundSessionTurn:
    snapshot: ResponsePlanSessionSnapshot
    policy: SessionContinuityPolicy
    request_binding: TurnRequestBinding
    read_bundle: object


def begin_bound_session_turn(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    policy: SessionContinuityPolicy,
    source_client_id: str,
    bundle: ResponseSchemaBundle,
    request_id: str,
    patient_message: str,
) -> BoundSessionTurn:
    read_bundle = build_turn_read_bundle(
        snapshot,
        policy=policy,
        source_client_id=source_client_id,
        bundle=bundle,
    )
    request_binding = create_turn_request_binding(
        snapshot,
        request_id=request_id,
        patient_message=patient_message,
    )
    return BoundSessionTurn(
        snapshot=snapshot,
        policy=policy,
        request_binding=request_binding,
        read_bundle=read_bundle,
    )


def materialization_sources_for_bound_turn(
    bound: BoundSessionTurn,
    *,
    base_sources: ResponsePlanMaterializationSources,
) -> ResponsePlanMaterializationSources:
    accumulated = bound.read_bundle.accumulated_shown_ids  # type: ignore[attr-defined]
    if base_sources.session_key != bound.request_binding.session_key:
        raise ValueError("materialization_sources_session_mismatch")
    return base_sources.model_copy(
        update={
            "shown_requested_fact_ids": accumulated.requested_fact_ids,
            "shown_promo_fact_ids": accumulated.promo_fact_ids,
            "shown_amplifier_fact_ids": accumulated.amplifier_fact_ids,
            "shown_service_value_ids": accumulated.service_value_ids,
        }
    )


def execute_bound_session_turn(
    bound: BoundSessionTurn,
    *,
    material: PostComposerMaterialAuthority,
    corpus,
    allowed_source_refs: tuple[str, ...],
    sources: ResponsePlanMaterializationSources,
    backend: ComposerBackend,
    as_of: date,
) -> TurnPipelineOutcome:
    read_bundle = bound.read_bundle
    authority = build_composer_decision_authority(
        material,
        allowed_source_refs=allowed_source_refs,
        history_turn_count=read_bundle.history_turn_count,  # type: ignore[attr-defined]
        active_session_service_id=read_bundle.active_session_service_id,  # type: ignore[attr-defined]
        as_of=as_of,
    )
    input_context = ComposerInputContext(
        current_user_message=bound.request_binding.patient_message,
        recent_dialogue=read_bundle.recent_dialogue,  # type: ignore[attr-defined]
        session_context=read_bundle.composer_session_context,  # type: ignore[attr-defined]
        full_context_corpus=corpus,
        decision_authority=authority,
        confirmed_shown_options=read_bundle.confirmed_shown_options,  # type: ignore[attr-defined]
    )
    composer_result = execute_composer_decision(input_context, backend)
    selection = resolve_post_composer_selection(
        session_key=bound.request_binding.session_key,
        adapted=composer_result.adapted_decision,
        material=material,
        active_session_service_id=read_bundle.active_session_service_id,  # type: ignore[attr-defined]
        prior_situation_state=read_bundle.prior_situation_state,  # type: ignore[attr-defined]
        current_turn_index=bound.request_binding.current_turn_index,
        policy=situation_continuity_policy(bound.policy),
        shown_options_policy=shown_options_freshness_policy(bound.policy),
        as_of=as_of,
        shown_options_snapshot=(
            bound.snapshot.state.shown_options_snapshot.to_runtime()
            if bound.snapshot.state.shown_options_snapshot is not None
            else None
        ),
    )
    bound_sources = materialization_sources_for_bound_turn(bound, base_sources=sources)
    materialized = resolve_materialized_response(
        selection,
        composer_result.adapted_decision,
        bound_sources,
        as_of=as_of,
    )
    rendered = render_response_text(materialized.resolved)
    ui = project_response_ui(materialized.resolved)
    pipeline = TurnPipelineOutcome(
        request_binding=bound.request_binding,
        adapted=composer_result.adapted_decision,
        selection=selection,
        materialized=materialized,
        rendered_text=rendered,
        ui_projection=ui,
    )
    validate_bound_pipeline_outcome(
        snapshot=bound.snapshot,
        expected_binding=bound.request_binding,
        pipeline=pipeline,
    )
    return pipeline


def prepare_bound_session_turn(
    bound: BoundSessionTurn,
    pipeline: TurnPipelineOutcome,
) -> PreparedSessionUpdate:
    if bound.request_binding != pipeline.request_binding:
        raise ResponsePlanSessionContractError("bound_pipeline_binding_mismatch")
    return prepare_session_update(
        bound.snapshot,
        policy=bound.policy,
        pipeline=pipeline,
        expected_binding=bound.request_binding,
        topic_restoration_shown_snapshot=resolve_topic_restoration_shown_snapshot(
            bound.snapshot.state,
            validated_shown=bound.read_bundle.validated_shown_options,  # type: ignore[attr-defined]
            selection=pipeline.selection,
        ),
    )
