"""TurnFrame-bound offline response orchestration (S41, unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.turn_frame import TurnFrame
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
)
from core.target_policy_bound_verified_response_pipeline import (
    run_target_offline_policy_bound_verified_response_pipeline_with_selection,
)
from core.target_response_verifier import TargetSemanticVerifierBackend
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response


def run_target_offline_turn_frame_bound_response(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    md_root: Path,
    cached_full_context: TargetCachedFullContext,
    include_initial_block: bool,
    include_consultation_close: bool,
    include_cta: bool,
    user_message: str,
    tone: TargetComposerTone,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetTurnFrameBoundMaterializeResponse | TargetTurnFrameBoundTerminalResponse:
    """Dispatch one TurnFrame and return either terminal spec or one exact verified response."""

    dispatch = dispatch_target_turn_frame_response(turn_frame, envelope)
    if dispatch.kind == "terminal":
        return TargetTurnFrameBoundTerminalResponse(kind="terminal", dispatch=dispatch)
    verified, session_selection = run_target_offline_policy_bound_verified_response_pipeline_with_selection(
        dispatch.policy_request,
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        md_root=md_root,
        cached_full_context=cached_full_context,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        include_cta=include_cta,
        user_message=user_message,
        tone=tone,
        composer_backend=composer_backend,
        semantic_backend=semantic_backend,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        turn_topic=turn_frame.topic,
    )
    return TargetTurnFrameBoundMaterializeResponse(
        kind="materialize",
        dispatch=dispatch,
        verified=verified,
        session_selection=session_selection,
    )
