"""Boundary-enforced FullContext offline response orchestration (S46, unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_medical_boundary import (
    TargetMedicalBoundaryResult,
    TargetMedicalBoundaryTerminalEnforcement,
)
from contracts.target_response_spec import CanonicalToken
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.turn_frame import TurnFrame
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
)
from core.target_response_verifier import TargetSemanticVerifierBackend
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_turn_frame_policy_envelope_enforcement import (
    enforce_target_medical_boundary_on_envelope,
)


def run_target_offline_boundary_enforced_fullcontext_response(
    turn_frame: TurnFrame,
    boundary: TargetMedicalBoundaryResult,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    tone_key: CanonicalToken,
    allowed_topics: tuple[CanonicalToken, ...],
    forbidden_topics: tuple[CanonicalToken, ...] = (),
    required_fact_ids: tuple[CanonicalToken, ...] = (),
    allow_marketing_facts: bool = False,
    allow_consultation_close: bool = False,
    allow_cta: bool = False,
    min_topic_confidence: float = 0.0,
    min_service_confidence: float = 0.0,
    min_intent_confidence: float = 0.0,
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
) -> (
    TargetMedicalBoundaryTerminalEnforcement
    | TargetTurnFrameBoundMaterializeResponse
    | TargetTurnFrameBoundTerminalResponse
):
    """Enforce medical boundary once, then run S41 FullContext response or return terminal."""

    enforcement = enforce_target_medical_boundary_on_envelope(
        boundary,
        tone_key=tone_key,
        allowed_topics=allowed_topics,
        forbidden_topics=forbidden_topics,
        required_fact_ids=required_fact_ids,
        allow_marketing_facts=allow_marketing_facts,
        allow_consultation_close=allow_consultation_close,
        allow_cta=allow_cta,
        min_topic_confidence=min_topic_confidence,
        min_service_confidence=min_service_confidence,
        min_intent_confidence=min_intent_confidence,
    )
    if type(enforcement) is TargetMedicalBoundaryTerminalEnforcement:
        return enforcement
    return run_target_offline_turn_frame_bound_response(
        turn_frame,
        enforcement.envelope,
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
    )
