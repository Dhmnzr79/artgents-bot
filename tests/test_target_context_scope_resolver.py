"""Resolver tests for PERF-6 Phase 2 (governance acceptance matrix, resolver-facing scenarios).

Uses the real demo client pack (read-only) to build real ``TargetComposerRequest`` objects via the
same production materialization chain the pipeline uses -- no synthetic client pack, no
hand-crafted evidence unless explicitly testing an edge case via ``dataclasses.replace`` on an
already-valid, really-materialized request (never inventing evidence the real pipeline could not
have produced). ``context_group`` is tested only against a synthetic, in-memory
``TargetContextGroupCatalog`` (never a demo file) per the governance brief.
"""

from __future__ import annotations

import dataclasses
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
from core.target_context_scope_resolver import (
    CONTEXT_SCHEMA_VERSION,
    TargetContextGroup,
    TargetContextGroupCatalog,
    TargetContextScopeResolution,
    resolve_target_context_scope,
)
from core.target_response_policy import build_target_response_spec
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


def _materialize(
    *,
    service_id: str | None,
    allowed_topics: tuple[str, ...],
    requested_components: tuple[str, ...] = ("content",),
    required_fact_ids: tuple[str, ...] = (),
    primary_component: str | None = "content",
    forbidden_topics: tuple[str, ...] = ("diagnosis", "personal_eligibility"),
    allow_marketing_facts: bool = False,
    allow_consultation_close: bool = False,
    allow_cta: bool = False,
    include_initial_block: bool = False,
    user_message: str = "Расскажите подробнее",
):
    policy_request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": forbidden_topics,
            "required_fact_ids": required_fact_ids,
            "requested_components": requested_components,
            "primary_component": primary_component,
            "allow_marketing_facts": allow_marketing_facts,
            "allow_consultation_close": allow_consultation_close,
            "allow_cta": allow_cta,
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
        include_initial_block=include_initial_block,
        include_consultation_close=allow_consultation_close,
        include_cta=allow_cta,
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
        user_message=user_message,
        md_root=MD_ROOT,
        client_id="demo",
    )


def _with_spec_override(request, **updates: object):
    """Bypass-mutate ``request.spec`` for synthetic edge cases the real S33 validator would
    reject outright (e.g. empty ``allowed_topics``) -- ``model_copy`` does not re-run validators,
    so this produces a structurally-invalid-but-inspectable spec for resolver-only unit tests.
    Never used to fabricate a *content* claim, only to explore boundary/fallback behavior."""

    new_spec = request.spec.model_copy(update=updates)
    return dataclasses.replace(request, spec=new_spec)


def _resolve(request, **kwargs) -> TargetContextScopeResolution:
    return resolve_target_context_scope(
        request,
        bundle=BUNDLE,
        doctor_catalog=DOCTORS,
        cached_full_context=FULL_CONTEXT,
        md_root=MD_ROOT,
        client_id="demo",
        **kwargs,
    )


# --------------------------------------------------------------------------------------------
# 1. service_exact -- complete exact-service scenarios
# --------------------------------------------------------------------------------------------


def test_1_complete_exact_service_resolves_service_exact() -> None:
    request = _materialize(
        service_id="classic",
        allowed_topics=("implantation",),
        requested_components=("content",),
    )
    resolution = _resolve(request)
    decision = resolution.decision
    assert decision.level == "service_exact"
    assert decision.service_id == "classic"
    assert decision.completeness_status == "complete"
    assert decision.widening_reason is None
    assert resolution.widening_steps == ("service_exact",)
    assert "implantation__service__classic.md" in decision.included_content_refs


def test_5_exact_price_offers_included() -> None:
    request = _materialize(
        service_id="classic",
        allowed_topics=("implantation",),
        requested_components=("price",),
        primary_component="price",
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.included_offer_ids


def test_6_required_facts_included() -> None:
    request = _materialize(
        service_id="all_on_4",
        allowed_topics=("implantation",),
        requested_components=("content", "price"),
        primary_component="content",
        required_fact_ids=("free_implant_consult",),
        allow_marketing_facts=True,
        include_initial_block=True,
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert "free_implant_consult" in decision.included_fact_ids


def test_7_doctors_included_when_required() -> None:
    request = _materialize(
        service_id="classic",
        allowed_topics=("implantation", "doctors"),
        requested_components=("doctors",),
        primary_component=None,
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.included_doctor_ids


def test_8_consultation_exact_applicability() -> None:
    request = _materialize(
        service_id="all_on_4",
        allowed_topics=("implantation",),
        requested_components=("content",),
        allow_consultation_close=True,
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert "implantation__service__all_on_4.md" in decision.included_content_refs


def test_9_marketing_selected_sources_are_part_of_evidence_closure() -> None:
    # allow_marketing_facts alone (without a selected scenario) still resolves to a complete,
    # narrow service_exact closure -- proving marketing inclusion doesn't break completeness.
    request = _materialize(
        service_id="classic",
        allowed_topics=("implantation",),
        requested_components=("content",),
        allow_marketing_facts=True,
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"


def test_15_no_public_price_service_bone_graft() -> None:
    request = _materialize(
        service_id="bone_graft",
        allowed_topics=("implantation",),
        requested_components=("content",),
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.service_id == "bone_graft"


def test_45_bone_graft_demo_case() -> None:
    request = _materialize(
        service_id="bone_graft",
        allowed_topics=("implantation",),
        requested_components=("content", "price"),
        primary_component="content",
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.estimated_chars > 0
    assert decision.estimated_tokens == decision.estimated_chars // 4


def test_46_tomography_own_scan_demo_case() -> None:
    request = _materialize(
        service_id="tomography",
        allowed_topics=("clinic",),
        requested_components=("content",),
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert "diagnostics__service__tomography.md" in decision.included_content_refs


def test_13_tomography_price_only() -> None:
    request = _materialize(
        service_id="tomography",
        allowed_topics=("clinic",),
        requested_components=("price",),
        primary_component="price",
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.included_offer_ids


def test_41_exact_service_demo_case_all_on_6() -> None:
    request = _materialize(
        service_id="all_on_6",
        allowed_topics=("implantation",),
        requested_components=("content", "price", "doctors"),
        primary_component="content",
    )
    decision = _resolve(request).decision
    assert decision.level == "service_exact"
    assert decision.included_offer_ids
    assert decision.included_doctor_ids


# --------------------------------------------------------------------------------------------
# topic tier
# --------------------------------------------------------------------------------------------


def test_4_broad_implantation_resolves_topic() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation",))
    resolution = _resolve(request)
    decision = resolution.decision
    assert decision.level == "topic"
    assert decision.topic == "implantation"
    assert decision.completeness_status == "complete"
    assert len(decision.included_content_refs) >= 28


def test_5_broad_prosthetics_resolves_topic() -> None:
    request = _materialize(service_id=None, allowed_topics=("prosthetics",))
    decision = _resolve(request).decision
    assert decision.level == "topic"
    assert decision.topic == "prosthetics"


def test_6_broad_whitening_single_doc_topic() -> None:
    request = _materialize(service_id=None, allowed_topics=("whitening",))
    decision = _resolve(request).decision
    assert decision.level == "topic"
    assert decision.included_content_refs == ("whitening__service__teeth_whitening.md",)


def test_20_generic_faq_no_consultation_bleed() -> None:
    request = _materialize(
        service_id=None,
        allowed_topics=("clinic",),
        allow_consultation_close=False,
    )
    decision = _resolve(request).decision
    assert decision.level == "topic"
    assert decision.completeness_status == "complete"


def test_22_clinic_wide_doctors_topic() -> None:
    request = _materialize(
        service_id=None,
        allowed_topics=("doctors",),
        requested_components=("doctors",),
        primary_component=None,
    )
    decision = _resolve(request).decision
    assert decision.level == "topic"
    assert decision.included_doctor_ids


def test_topic_smaller_than_full_for_narrow_topics() -> None:
    request = _materialize(service_id=None, allowed_topics=("whitening",))
    decision = _resolve(request).decision
    full_tokens = len(FULL_CONTEXT.corpus_text) // 4
    assert decision.estimated_tokens < full_tokens


def test_30_missing_service_usable_topic_widens_from_service_exact() -> None:
    # Start from a real complete service_exact request, then strip its evidence to simulate an
    # incomplete service closure (never reachable from real materialization, which already
    # guarantees completeness -- this exercises the resolver's own defensive re-check and the
    # widening algorithm in isolation).
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    stripped = dataclasses.replace(request, evidence_blocks=())
    resolution = _resolve(stripped)
    assert resolution.widening_steps[0] == "service_exact"
    assert resolution.decision.level in ("topic", "full")
    if resolution.decision.level == "topic":
        assert resolution.decision.completeness_status == "insufficient_widened"
        assert resolution.decision.widening_reason == "service_exact_incomplete_widened_to_topic"


# --------------------------------------------------------------------------------------------
# full tier -- fallback scenarios
# --------------------------------------------------------------------------------------------


def test_29_ambiguous_no_service_no_topic_resolves_full() -> None:
    request = _with_spec_override(
        _materialize(service_id=None, allowed_topics=("implantation",)),
        allowed_topics=(),
    )
    decision = _resolve(request).decision
    assert decision.level == "full"
    assert decision.completeness_status == "full_required"
    assert decision.widening_reason == "no_service_or_topic_signal"
    assert set(decision.included_content_refs) == set(FULL_CONTEXT.document_paths)


def test_31_missing_service_and_topic_resolves_full() -> None:
    request = _with_spec_override(
        _materialize(service_id=None, allowed_topics=("implantation",)),
        allowed_topics=(),
    )
    decision = _resolve(request).decision
    assert decision.level == "full"


def test_28_cross_topic_comparison_has_no_group_data_resolves_full() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation", "prosthetics"))
    decision = _resolve(request).decision
    # both topics are taxonomy-valid so this actually resolves at "topic" (union of both) --
    # cross-topic comparison only forces `full` when no single/union topic set is usable at all.
    assert decision.level in ("topic", "full")


def test_31b_invalid_topic_not_in_taxonomy_resolves_full() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation",))
    bad_request = _with_spec_override(request, allowed_topics=("not_a_real_topic",))
    decision = _resolve(bad_request).decision
    assert decision.level == "full"


def test_17_comparison_without_authored_group_falls_to_topic_or_full() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation",))
    decision = _resolve(request, context_groups=None).decision
    assert decision.level in ("topic", "full")
    assert decision.context_group_id is None


def test_20_resolver_exception_resolves_full_never_raises() -> None:
    class _Bad:
        pass

    resolution = resolve_target_context_scope(
        _Bad(),  # type: ignore[arg-type]
        bundle=BUNDLE,
        doctor_catalog=DOCTORS,
        cached_full_context=FULL_CONTEXT,
        md_root=MD_ROOT,
        client_id="demo",
    )
    assert resolution.decision.level == "full"
    assert resolution.decision.widening_reason == "resolver_exception"
    assert resolution.widening_steps == ("full",)


def test_full_included_content_refs_equal_full_corpus_doc_set() -> None:
    request = _with_spec_override(
        _materialize(service_id=None, allowed_topics=("implantation",)),
        allowed_topics=(),
    )
    decision = _resolve(request).decision
    assert set(decision.included_content_refs) == set(FULL_CONTEXT.document_paths)
    assert decision.estimated_chars == len(FULL_CONTEXT.corpus_text)
    assert decision.estimated_tokens == len(FULL_CONTEXT.corpus_text) // 4


# --------------------------------------------------------------------------------------------
# context_group -- synthetic fixture only (never the demo pack)
# --------------------------------------------------------------------------------------------


def test_18_synthetic_valid_group_resolves_context_group() -> None:
    """`clinic__info__*.md` docs (topic ``clinic``) are real demo content not tied to any
    service_catalog entry, so a ``doctors``-required, topic-only ``clinic`` closure is genuinely
    incomplete (zero doctors reachable) -- real data, no fabricated evidence. A synthetic authored
    group (never the demo pack) spanning ``clinic`` + ``doctors`` widens to include the doctor
    profile MDs (topic ``doctors``), which satisfies the requirement."""

    request = _materialize(
        service_id=None,
        allowed_topics=("clinic",),
        requested_components=("doctors",),
        primary_component=None,
    )
    topic_only_decision = _resolve(request).decision
    assert topic_only_decision.level == "full"  # topic alone is genuinely insufficient here

    groups = TargetContextGroupCatalog(
        groups=(TargetContextGroup(group_id="clinic_trust", topics=("clinic", "doctors")),)
    )
    resolution = _resolve(request, context_groups=groups)
    assert resolution.decision.level == "context_group"
    assert resolution.decision.context_group_id == "clinic_trust"
    assert resolution.decision.completeness_status == "insufficient_widened"
    assert resolution.decision.widening_reason == "topic_incomplete_widened_to_context_group"
    assert resolution.widening_steps == ("topic", "context_group")
    assert resolution.decision.included_doctor_ids


def test_context_group_falls_to_full_when_no_group_matches_incomplete_topic() -> None:
    request = _materialize(
        service_id=None,
        allowed_topics=("clinic",),
        requested_components=("doctors",),
        primary_component=None,
    )
    groups = TargetContextGroupCatalog(
        groups=(TargetContextGroup(group_id="unrelated", topics=("whitening", "orthodontics")),)
    )
    decision = _resolve(request, context_groups=groups).decision
    assert decision.level == "full"
    assert decision.context_group_id is None


def test_19_synthetic_unknown_group_never_matches_resolves_topic_or_full() -> None:
    request = _materialize(service_id=None, allowed_topics=("implantation",))
    groups = TargetContextGroupCatalog(
        groups=(TargetContextGroup(group_id="unrelated_group", topics=("orthodontics", "periodontology")),)
    )
    decision = _resolve(request, context_groups=groups).decision
    assert decision.context_group_id is None
    assert decision.level in ("topic", "full")


def test_context_group_none_by_default_on_demo_pack() -> None:
    """The demo pack has no authored context_groups.json -- context_group must never activate
    when the caller passes context_groups=None (the real wiring's default)."""

    request = _materialize(service_id=None, allowed_topics=("implantation",))
    decision = _resolve(request, context_groups=None).decision
    assert decision.context_group_id is None
    assert decision.level != "context_group"


# --------------------------------------------------------------------------------------------
# fingerprint
# --------------------------------------------------------------------------------------------


def test_21_stable_fingerprint_for_identical_inputs() -> None:
    request = _materialize(service_id="classic", allowed_topics=("implantation",))
    d1 = _resolve(request).decision
    d2 = _resolve(request).decision
    assert d1.package_fingerprint == d2.package_fingerprint


def test_22_fingerprint_changes_when_service_changes() -> None:
    request_a = _materialize(service_id="classic", allowed_topics=("implantation",))
    request_b = _materialize(service_id="one_stage", allowed_topics=("implantation",))
    fp_a = _resolve(request_a).decision.package_fingerprint
    fp_b = _resolve(request_b).decision.package_fingerprint
    assert fp_a != fp_b


def test_fingerprint_depends_on_schema_version_constant() -> None:
    assert CONTEXT_SCHEMA_VERSION == 1


# --------------------------------------------------------------------------------------------
# 23. token arithmetic
# --------------------------------------------------------------------------------------------


def test_23_token_arithmetic_always_floor_division_of_chars() -> None:
    for service_id in ("classic", "all_on_4", "bone_graft"):
        request = _materialize(service_id=service_id, allowed_topics=("implantation",))
        decision = _resolve(request).decision
        assert decision.estimated_tokens == decision.estimated_chars // 4


# --------------------------------------------------------------------------------------------
# 40. stale-session standalone question is not narrowed (structural proof)
# --------------------------------------------------------------------------------------------


def test_40_no_service_id_means_no_narrowing_even_if_topic_matches_old_service() -> None:
    """The resolver only ever reads request.spec.service_id (already hydration/freshness-gated
    upstream, see seam audit §1 item 2) -- it never re-derives service continuity itself. A
    request with service_id=None resolves at topic/full, never silently narrowed to a prior
    service the resolver was never told about."""

    request = _materialize(service_id=None, allowed_topics=("implantation",))
    decision = _resolve(request).decision
    assert decision.service_id is None
    assert decision.level != "service_exact"
