"""Straight-line offline target response from explicit policy (S40, unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.effective_scope import EffectiveScope
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
)
from contracts.target_response_stage import is_scope_aware_price_stage
from core.target_response_policy import build_target_response_spec
from core.target_scope_aware_price_package import is_scope_aware_price_spec
from core.target_response_verifier import (
    TargetSemanticVerifierBackend,
    TargetVerifiedComposedResponse,
)
from core.target_session_selection import (
    TargetMaterializedSessionSelection,
    extract_target_session_selection,
)
from core.target_spec_offline_response_package import (
    TargetSpecBoundOfflineResponsePackage,
    assemble_target_spec_offline_response_package,
)
from core.target_verified_response_pipeline import (
    run_target_offline_verified_response_pipeline,
)


def _assemble_bound_package(
    policy_request: TargetResponsePolicyRequest,
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
    include_initial_block: bool,
    include_consultation_close: bool,
    include_cta: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
    turn_topic: str | None = None,
    effective_scope: EffectiveScope | None = None,
    client_id: str = "demo",
) -> TargetSpecBoundOfflineResponsePackage:
    spec = build_target_response_spec(policy_request)
    if is_scope_aware_price_spec(spec):
        include_consultation_close = False
        resolved_stage = spec.response_stage
        if resolved_stage == "stage_clarify":
            brand_term = None
            include_initial_block = False
            include_cta = False
            marketing_scenarios = ()
        elif resolved_stage not in {None, "broad_family_price"}:
            brand_term = None
            include_initial_block = False
            include_cta = False
            marketing_scenarios = ()
    return assemble_target_spec_offline_response_package(
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        spec=spec,
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        md_root=md_root,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        include_cta=include_cta,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        turn_topic=turn_topic,
        effective_scope=effective_scope,
        client_id=client_id,
    )


def run_target_offline_policy_bound_verified_response_pipeline_with_selection(
    policy_request: TargetResponsePolicyRequest,
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
    turn_topic: str | None = None,
    effective_scope: EffectiveScope | None = None,
    client_id: str = "demo",
) -> tuple[TargetVerifiedComposedResponse, TargetMaterializedSessionSelection]:
    """Build spec-bound package and return one exact verified target response.

    Composer governed UI action context is resolved from the runtime turn binding
    established in ``target_runtime_turn``.
    """
    bound_package = _assemble_bound_package(
        policy_request,
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        md_root=md_root,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        include_cta=include_cta,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        turn_topic=turn_topic,
        effective_scope=effective_scope,
        client_id=client_id,
    )
    verified = run_target_offline_verified_response_pipeline(
        bound_package,
        bundle,
        doctor_catalog,
        consultation_values,
        user_message=user_message,
        md_root=md_root,
        cached_full_context=cached_full_context,
        tone=tone,
        composer_backend=composer_backend,
        semantic_backend=semantic_backend,
    )
    return verified, extract_target_session_selection(bound_package)


def run_target_offline_policy_bound_verified_response_pipeline(
    policy_request: TargetResponsePolicyRequest,
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
    turn_topic: str | None = None,
    effective_scope: EffectiveScope | None = None,
    client_id: str = "demo",
) -> TargetVerifiedComposedResponse:
    """Build spec-bound package and return one exact verified target response."""

    verified, _selection = run_target_offline_policy_bound_verified_response_pipeline_with_selection(
        policy_request,
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
        turn_topic=turn_topic,
        effective_scope=effective_scope,
        client_id=client_id,
    )
    return verified
