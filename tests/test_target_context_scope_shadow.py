"""Shadow comparison tests for PERF-6 Phase 2 (post-verification, log-only)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_request import materialize_target_composer_request
from core.target_context_scope_resolver import resolve_target_context_scope
from core.target_context_scope_shadow import (
    SHADOW_TIMING_MARK,
    compare_target_context_scope_shadow,
    emit_target_context_scope_shadow_blocked_event,
    emit_target_context_scope_shadow_event,
)
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)

DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
BUNDLE = load_response_schema_bundle(TARGET_ROOT)
DOCTORS = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
_KB_REFS = build_response_schema_kb_refs(MD_ROOT)
_DOCTOR_INDEX = DoctorCatalogExternalIndex(service_ids=tuple(BUNDLE.services), kb_refs=_KB_REFS)
assert validate_doctor_catalog_external_refs(DOCTORS, _DOCTOR_INDEX) is None
EXTERNAL_INDEX = ResponseSchemaExternalIndex(
    kb_refs=_KB_REFS,
    doctor_refs=build_doctor_source_refs(DOCTORS),
)
assert validate_response_schema_external_refs(BUNDLE, EXTERNAL_INDEX) is None
CONSULTATIONS = build_service_consultation_values(MD_ROOT)
assert validate_service_consultation_refs(CONSULTATIONS, BUNDLE.services) is None
FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)
FULL_TOKENS = len(FULL_CONTEXT.corpus_text) // 4


def _materialize(*, service_id: str | None, allowed_topics: tuple[str, ...]):
    policy_request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "requested_components": ("content",),
            "primary_component": "content",
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )
    spec = build_target_response_spec(policy_request)
    bound_package = assemble_target_spec_offline_response_package(
        BUNDLE,
        DOCTORS,
        EXTERNAL_INDEX,
        CONSULTATIONS,
        spec=spec,
        brand_term=None,
        strategy_context=TargetStrategyMatch(family="implantology", extent="full_arch"),
        semantic_context="service",
        today=date(2026, 7, 31),
        md_root=MD_ROOT,
        include_initial_block=False,
        include_consultation_close=False,
        include_cta=False,
        marketing_scenarios=(),
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        turn_topic=None,
        effective_scope=None,
        client_id="demo",
    )
    return materialize_target_composer_request(
        bound_package,
        BUNDLE,
        DOCTORS,
        CONSULTATIONS,
        user_message="Расскажите подробнее",
        md_root=MD_ROOT,
        client_id="demo",
    )


def _verified(request, *, primary_content_ref, used_content_refs) -> TargetVerifiedComposedResponse:
    return TargetVerifiedComposedResponse(
        text="некий проверенный текст ответа",
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
        primary_content_ref=primary_content_ref,
        used_content_refs=used_content_refs,
    )


def test_24_validated_primary_inside_candidate_is_hit() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    verified = _verified(
        request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=("implantation__service__classic.md",),
    )
    comparison = compare_target_context_scope_shadow(
        decision, request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is True
    assert comparison.missing_source_classes == ()
    assert comparison.comparison_status == "compared"


def test_25_validated_used_secondary_outside_candidate_is_miss() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    verified = _verified(
        request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=(
            "implantation__service__classic.md",
            "implantation__service__all_on_6.md",  # not in the classic service_exact closure
        ),
    )
    comparison = compare_target_context_scope_shadow(
        decision, request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is False
    assert "content" in comparison.missing_source_classes


def test_26_required_offer_outside_candidate_is_miss() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    price_spec = request.spec.model_copy(update={"required_components": ("price",)})
    price_request = request.__class__(
        user_message=request.user_message,
        spec=price_spec,
        evidence_blocks=(),  # no offer blocks -> decision.included_offer_ids won't cover it
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    verified = _verified(price_request, primary_content_ref=None, used_content_refs=())
    comparison = compare_target_context_scope_shadow(
        decision, price_request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is False
    assert "offer" in comparison.missing_source_classes


def test_27_required_fact_outside_candidate_is_miss() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    fact_spec = request.spec.model_copy(update={"required_fact_ids": ("free_implant_consult",)})
    fact_request = request.__class__(
        user_message=request.user_message,
        spec=fact_spec,
        evidence_blocks=request.evidence_blocks,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    verified = _verified(
        fact_request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=("implantation__service__classic.md",),
    )
    comparison = compare_target_context_scope_shadow(
        decision, fact_request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is False
    assert "fact" in comparison.missing_source_classes


def test_28_invented_ref_never_expands_candidate() -> None:
    """A ref the Composer invented (never in the real MD corpus) never reaches this comparison at
    all -- the real Verifier already drops it via validate_used_content_refs before
    TargetVerifiedComposedResponse.used_content_refs is populated (seam audit §1 item 9). This
    test proves the comparison itself is honest about an out-of-corpus ref, in case that
    invariant is ever violated upstream."""

    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    verified = _verified(
        request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=("implantation__service__classic.md", "totally_invented_doc.md"),
    )
    comparison = compare_target_context_scope_shadow(
        decision, request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is False
    assert "content" in comparison.missing_source_classes


def test_full_level_is_always_a_trivial_hit() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation",))
    full_spec = request.spec.model_copy(update={"allowed_topics": ()})
    full_request = request.__class__(
        user_message=request.user_message,
        spec=full_spec,
        evidence_blocks=(),
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    decision = resolve_target_context_scope(
        full_request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    assert decision.level == "full"
    verified = _verified(full_request, primary_content_ref=None, used_content_refs=())
    comparison = compare_target_context_scope_shadow(
        decision, full_request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.shadow_hit is True
    assert comparison.estimated_reduction_tokens == 0


def test_49_token_reduction_arithmetic() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    verified = _verified(
        request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=("implantation__service__classic.md",),
    )
    comparison = compare_target_context_scope_shadow(
        decision, request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    assert comparison.estimated_reduction_tokens == FULL_TOKENS - decision.estimated_tokens


def test_51_shadow_event_emission_never_raises_and_contains_no_pii(caplog) -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    verified = _verified(
        request,
        primary_content_ref="implantation__service__classic.md",
        used_content_refs=("implantation__service__classic.md",),
    )
    comparison = compare_target_context_scope_shadow(
        decision, request, verified, full_context_estimated_tokens=FULL_TOKENS
    )
    # Must never raise, regardless of Flask request context availability.
    emit_target_context_scope_shadow_event(
        decision,
        comparison,
        widening_steps=("service_exact",),
        full_context_estimated_tokens=FULL_TOKENS,
        resolver_ms=3,
        client_id="demo",
    )


def test_verifier_blocked_event_never_raises() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    decision = resolve_target_context_scope(
        request, bundle=BUNDLE, doctor_catalog=DOCTORS, cached_full_context=FULL_CONTEXT, md_root=MD_ROOT
    ).decision
    emit_target_context_scope_shadow_blocked_event(
        decision,
        widening_steps=("service_exact",),
        full_context_estimated_tokens=FULL_TOKENS,
        resolver_ms=2,
        client_id="demo",
    )


def test_shadow_timing_mark_name_distinct_from_legacy_resolver() -> None:
    assert SHADOW_TIMING_MARK == "scoped_context_shadow_ms"
    assert SHADOW_TIMING_MARK != "resolver_ms"
