"""Straight-line offline target response from explicit policy (S40, unwired).

PERF-6 Phase 2 deviation (owner-approved): ``run_target_offline_policy_bound_verified_response_
pipeline_with_selection`` additionally resolves a local, shadow-only ``TargetContextScopeDecision``
around its call to ``run_target_offline_verified_response_pipeline`` and, after the real
Composer/Verifier finish, compares it against what was actually needed and emits one anonymized
log event. Chosen over touching ``core/target_verified_response_pipeline.py`` itself because that
module's ``run_target_offline_verified_response_pipeline`` is protected by an AST "exact
straight-line, no control flow" contract test (S39) that this deviation must not violate; this
file's ``_with_selection`` entry point carries no such contract. The decision is a local variable
only -- never a ``ContextVar``, global, or session value -- and the real call to
``run_target_offline_verified_response_pipeline`` below is byte-for-byte unchanged (same
arguments, same order). See
``docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md`` and
``TASK.md``'s PERF-6 Phase 2 completion record for the full rationale.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.effective_scope import EffectiveScope
from contracts.target_cached_full_context import TargetCachedFullContext
from contracts.target_context_scope_decision import TargetContextScopeDecision
from contracts.target_response_length_profile import TargetResponseLengthProfile
from contracts.target_response_policy import TargetResponsePolicyRequest
from core import turn_timing
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
)
from contracts.target_response_stage import is_scope_aware_price_stage
from core.target_composer_request import (
    TargetComposerRequest,
    materialize_target_composer_request,
)
from core.target_context_scope_resolver import (
    ContextScopeLevel,
    resolve_target_context_scope,
)
from core.target_context_scope_shadow import (
    SHADOW_TIMING_MARK,
    compare_target_context_scope_shadow,
    emit_target_context_scope_shadow_blocked_event,
    emit_target_context_scope_shadow_event,
)
from core.target_response_policy import build_target_response_spec
from core.target_fullcontext_content_package import is_fullcontext_service_optional_spec
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
from core.target_verified_primary_content_cta_projection import (
    project_verified_primary_content_cta,
)
from core.target_verified_response_pipeline import (
    run_target_offline_verified_response_pipeline,
)
from logging_setup import get_logger

logger = get_logger("target_context_scope_shadow_hook")


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
    if is_fullcontext_service_optional_spec(spec):
        include_initial_block = False
        brand_term = None
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


def _resolve_shadow_decision_safely(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    user_message: str,
    md_root: Path,
    cached_full_context: TargetCachedFullContext,
    contact_fields: tuple[str, ...] | None,
    client_id: str,
    response_length_profile: TargetResponseLengthProfile | None,
) -> tuple[TargetContextScopeDecision, tuple[ContextScopeLevel, ...], int, TargetComposerRequest] | None:
    """Best-effort local-only shadow resolve (PERF-6 Phase 2). Never raises -- ``None`` on failure.

    Re-materializes a ``TargetComposerRequest`` purely to read its ``evidence_blocks`` for the
    resolver -- ``materialize_target_composer_request`` is pure/offline (no provider call, no
    filesystem write), so recomputing it here is a deliberate, safe redundancy that avoids adding
    control flow to the protected straight-line ``run_target_offline_verified_response_pipeline``
    (S39). The real request used for the actual Composer/Verifier call is materialized again,
    identically, inside that unmodified function below -- this shadow copy is never passed to it.
    """

    try:
        started = time.monotonic()
        shadow_request = materialize_target_composer_request(
            bound_package,
            bundle,
            doctor_catalog,
            consultation_values,
            user_message=user_message,
            md_root=md_root,
            contact_fields=contact_fields,
            client_id=client_id,
            response_length_profile=response_length_profile,
        )
        resolution = resolve_target_context_scope(
            shadow_request,
            bundle=bundle,
            doctor_catalog=doctor_catalog,
            cached_full_context=cached_full_context,
            md_root=md_root,
            client_id=client_id,
        )
        resolver_ms = int((time.monotonic() - started) * 1000)
        # Reuses the existing PERF-0 per-request timing bucket (safe outside a request context
        # too -- see core/turn_timing.py) under a name distinct from the legacy resolver.py
        # `resolver_ms` mark, exactly as the seam audit specified.
        turn_timing.record_ms(SHADOW_TIMING_MARK, resolver_ms)
        return resolution.decision, resolution.widening_steps, resolver_ms, shadow_request
    except Exception:  # noqa: BLE001 -- shadow must never affect the real response
        try:
            logger.warning("scoped_context_shadow_resolve_failed", exc_info=True)
        except Exception:  # noqa: BLE001
            pass
        return None


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
    contact_fields: tuple[str, ...] | None = None,
    response_length_profile: TargetResponseLengthProfile | None = None,
) -> tuple[TargetVerifiedComposedResponse, TargetMaterializedSessionSelection]:
    """Build spec-bound package and return one exact verified target response.

    Composer governed UI action context is resolved from the runtime turn binding
    established in ``target_runtime_turn``. ``response_length_profile`` (PERF-5,
    corrected) is the already-decided typed profile from the one production seam
    (``core/target_turn_frame_bound_response.py``) -- passed straight through, never
    recomputed here.
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

    # PERF-6 Phase 2 shadow: resolved once, held only in this local variable. The real call below
    # is byte-for-byte unchanged -- this decision is never read by it.
    shadow = _resolve_shadow_decision_safely(
        bound_package,
        bundle,
        doctor_catalog,
        consultation_values,
        user_message=user_message,
        md_root=md_root,
        cached_full_context=cached_full_context,
        contact_fields=contact_fields,
        client_id=client_id,
        response_length_profile=response_length_profile,
    )
    full_context_estimated_tokens = len(cached_full_context.corpus_text) // 4

    try:
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
            contact_fields=contact_fields,
            client_id=client_id,
            response_length_profile=response_length_profile,
        )
    except Exception:
        # Verifier blocked or raised: the real exception is never touched or replaced. Best-effort
        # shadow bookkeeping only, then the exact same exception is re-raised unchanged.
        if shadow is not None:
            decision, widening_steps, resolver_ms, _shadow_request = shadow
            emit_target_context_scope_shadow_blocked_event(
                decision,
                widening_steps=widening_steps,
                full_context_estimated_tokens=full_context_estimated_tokens,
                resolver_ms=resolver_ms,
                client_id=client_id,
            )
        raise

    if shadow is not None:
        decision, widening_steps, resolver_ms, shadow_request = shadow
        try:
            comparison = compare_target_context_scope_shadow(
                decision,
                shadow_request,
                verified,
                full_context_estimated_tokens=full_context_estimated_tokens,
            )
            emit_target_context_scope_shadow_event(
                decision,
                comparison,
                widening_steps=widening_steps,
                full_context_estimated_tokens=full_context_estimated_tokens,
                resolver_ms=resolver_ms,
                client_id=client_id,
            )
        except Exception:  # noqa: BLE001 -- shadow comparison must never affect the real response
            try:
                logger.warning("scoped_context_shadow_compare_failed", exc_info=True)
            except Exception:  # noqa: BLE001
                pass

    verified = project_verified_primary_content_cta(
        verified,
        client_id=client_id,
        md_root=md_root,
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
    contact_fields: tuple[str, ...] | None = None,
    response_length_profile: TargetResponseLengthProfile | None = None,
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
        contact_fields=contact_fields,
        response_length_profile=response_length_profile,
    )
    return verified
