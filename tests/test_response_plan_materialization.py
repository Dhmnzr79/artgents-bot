from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.effective_scope import EffectiveScope
from contracts.response_plan import (
    CommercialFactCandidate,
    RequiredOfferConditionBlock,
    RequiredOfferConditionOfferEntry,
    SessionKey,
)
from contracts.response_plan_adapter import (
    CanonicalContactCandidate,
    ResponsePlanAdapterTerminalAuthority,
)
from contracts.response_plan_composer import AdaptedComposerDecision, ComposerDecision, ComposerPatientSituation
from contracts.response_plan_materialization import (
    MaterializationContractError,
    MaterializationOwnershipError,
    OfferConditionEvidence,
    ResponsePlanMaterializationSources,
)
from contracts.response_plan_post_composer import (
    PostComposerMaterialAuthority,
    PostComposerSelectionPlan,
    ResponseSituationDelta,
)
from contracts.response_schema import ResponseSchemaBundle
from core.response_plan_materialization import materialize_pre_composer_payload, resolve_materialized_response
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
SESSION = SessionKey(client_id="demo", sid="s1")
AS_OF = date(2026, 8, 15)


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle):
    return PostComposerMaterialAuthority(source_client_id="demo", bundle=demo_bundle)


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
        "patient_text": "Ответ.",
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


def _terminal_authorities() -> tuple[ResponsePlanAdapterTerminalAuthority, ...]:
    contact = CanonicalContactCandidate(source_client_id="demo", phone="+7 (495) 000-00-00")
    return (
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ANSWER",
            mode="contacts",
            authority="contacts",
            display_text="Контакты demo",
            canonical_contact=contact,
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ADMIN",
            mode="standard",
            authority="governed_ui",
            display_text="ADMIN standard",
            canonical_contact=contact,
        ),
        ResponsePlanAdapterTerminalAuthority(
            source_client_id="demo",
            route="ADMIN",
            mode="medical_terminal",
            authority="deterministic_policy_terminal",
            display_text="ADMIN medical",
            canonical_contact=contact,
        ),
    )


def _sources(material, **overrides) -> ResponsePlanMaterializationSources:
    payload = {
        "session_key": SESSION,
        "context_strategy": "full_context",
        "material_authority": material,
        "condition_evidence_by_offer": {},
        "terminal_authorities": _terminal_authorities(),
    }
    payload.update(overrides)
    return ResponsePlanMaterializationSources(**payload)


def _selection_from_post_composer(adapted, material, **kwargs):
    from contracts.response_plan_post_composer import SituationContinuityPolicy
    from core.response_plan_post_composer import resolve_post_composer_selection

    return resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=material,
        active_session_service_id=kwargs.get("active_session_service_id"),
        prior_situation_state=kwargs.get("prior"),
        current_turn_index=kwargs.get("turn", 1),
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=kwargs.get("shown_options_snapshot"),
    )


def _complete_empty_evidence(*offer_ids: str) -> dict[str, OfferConditionEvidence]:
    return {
        offer_id: OfferConditionEvidence(
            source_client_id="demo",
            offer_id=offer_id,
            completeness="complete",
            conditions=(),
        )
        for offer_id in offer_ids
    }


def _complete_with_conditions(
    offer_id: str,
    *,
    condition_id: str = "package_includes",
    text: str,
) -> OfferConditionEvidence:
    return OfferConditionEvidence(
        source_client_id="demo",
        offer_id=offer_id,
        completeness="complete",
        conditions=(
            RequiredOfferConditionBlock(
                source_client_id="demo",
                condition_id=condition_id,  # type: ignore[arg-type]
                completeness="complete",
                entries=(
                    RequiredOfferConditionOfferEntry(
                        offer_id=offer_id,
                        display_text=text,
                    ),
                ),
            ),
        ),
    )


def _manual_selection(
    adapted: AdaptedComposerDecision,
    *,
    price_ids: tuple[str, ...] = (),
    visible_ids: tuple[str, ...] = (),
    basis: str = "referenced_service",
    reference_id: str | None = None,
    reference_status: str = "compatible",
    scope: str = "service",
    topic: str | None = "implantation",
    effective_scope: EffectiveScope | None = None,
    requested_fact_candidates: tuple[CommercialFactCandidate, ...] = (),
) -> PostComposerSelectionPlan:
    return PostComposerSelectionPlan(
        session_key=SESSION,
        source_client_id="demo",
        decision=adapted.decision,
        resolved_topic_id=topic,
        response_scope=scope,  # type: ignore[arg-type]
        reference_service_id=reference_id,
        reference_service_status=reference_status,  # type: ignore[arg-type]
        effective_scope=effective_scope or EffectiveScope(extent="unknown", jaw="unknown", topic=topic),
        ranked_service_ids=(),
        visible_service_option_ids=visible_ids,
        price_candidate_service_ids=price_ids,
        comparison_service_ids=(),
        selection_basis=basis,  # type: ignore[arg-type]
        selection_intent="price_candidates" if price_ids else "none",
        requested_fact_candidates=requested_fact_candidates,
        situation_delta=ResponseSituationDelta(action="keep"),
        adapter_diagnostics=(),
        diagnostics=(),
    )


def _synthetic_filter_bundle() -> ResponseSchemaBundle:
    from tests.test_target_offer_projection import _bundle, _offer

    bundle = _bundle()
    offers = list(bundle.offers)
    offers.extend(
        [
            {**_offer("cap_from", mode="from"), "offer_id": "cap_from"},
            {**_offer("cap_range", mode="range"), "offer_id": "cap_range"},
            {**_offer("cap_no_public", mode="no_public_price"), "offer_id": "cap_no_public"},
            {**_offer("cap_fixed", mode="fixed"), "offer_id": "cap_fixed"},
        ]
    )
    data = bundle.model_dump()
    data["offers"] = offers
    data["strategy"]["default_offer_priorities"].update(
        {
            "cap_from": 100,
            "cap_range": 90,
            "cap_no_public": 80,
            "cap_fixed": 10,
        }
    )
    return ResponseSchemaBundle.model_validate(data)


def test_materialization_foreign_client_rejected(demo_material) -> None:
    selection = PostComposerSelectionPlan(
        session_key=SessionKey(client_id="other", sid="s1"),
        source_client_id="other",
        decision=_adapted().decision,
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
    with pytest.raises(MaterializationOwnershipError):
        materialize_pre_composer_payload(
            selection,
            _adapted(),
            _sources(demo_material),
            as_of=AS_OF,
        )


def test_overview_full_arch_materializes_service_options(demo_material) -> None:
    adapted = _adapted(
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert payload.plan.service_options_block is not None
    assert payload.plan.price_plan.kind == "none"
    option_ids = [item.service_id for item in payload.plan.service_options_block.options]
    assert option_ids == list(selection.visible_service_option_ids[:3])


def test_price_without_condition_evidence_omits_price_block(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert payload.plan.price_plan.kind == "none"
    assert any(d.code == "materialization_price_conditions_unknown" for d in payload.materialization_diagnostics)


def test_complete_empty_conditions_allow_catalog_reference_price(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        patient_situation=_situation(extent="one_tooth", jaw="upper"),
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    evidence = _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert payload.plan.price_plan.kind == "multi"
    assert payload.trace.price_lookup_mode == "catalog_reference"
    assert len(payload.trace.selected_offers) == 3


def test_catalog_reference_conflict_preserves_price(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        patient_situation=_situation(extent="one_tooth", jaw="upper"),
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    assert selection.price_candidate_service_ids == ("all_on_4",)
    evidence = _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert outcome.resolved.price_block.owner == "canonical_multi"
    assert outcome.trace.price_lookup_mode == "catalog_reference"
    if selection.reference_service_status == "conflict":
        assert any(d.code == "explicit_service_situation_conflict" for d in selection.diagnostics)


def test_unsupported_price_modes_are_not_materialized() -> None:
    bundle = _synthetic_filter_bundle()
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="service_one",
        requested_aspect_ids=("price",),
    )
    selection = _manual_selection(
        adapted,
        price_ids=("service_one",),
        reference_id="service_one",
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(material, condition_evidence_by_offer=_complete_empty_evidence("cap_fixed")),
        as_of=AS_OF,
    )
    assert payload.plan.price_plan.kind == "single"
    assert payload.plan.price_plan.single is not None
    assert payload.plan.price_plan.single.offer_id == "cap_fixed"
    assert any(d.code == "materialization_unsupported_price_mode" for d in payload.materialization_diagnostics)


def test_filter_before_cap_keeps_lower_priority_materializable_offer() -> None:
    bundle = _synthetic_filter_bundle()
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="service_one",
        requested_aspect_ids=("price",),
    )
    selection = _manual_selection(
        adapted,
        price_ids=("service_one",),
        reference_id="service_one",
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(material, condition_evidence_by_offer=_complete_empty_evidence("cap_fixed")),
        as_of=AS_OF,
    )
    excluded = {t.offer_id for t in payload.trace.considered_offers if t.excluded}
    assert {"cap_from", "cap_range", "cap_no_public"}.issubset(excluded)
    assert payload.trace.selected_offers[0].offer_id == "cap_fixed"


def test_unknown_condition_completeness_excludes_offer(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(
            demo_material,
            condition_evidence_by_offer={
                "all_on_4.jaw.implantium": OfferConditionEvidence(
                    source_client_id="demo",
                    offer_id="all_on_4.jaw.implantium",
                    completeness="unknown",
                    conditions=(),
                )
            },
        ),
        as_of=AS_OF,
    )
    assert payload.plan.price_plan.kind == "none"


def test_complete_with_conditions_renders_linked_entries(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    offer_id = "all_on_4.jaw.implantium"
    evidence = {
        offer_id: _complete_with_conditions(offer_id, text="Пакет A"),
    }
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert outcome.resolved.required_offer_conditions
    block = outcome.resolved.required_offer_conditions[0]
    assert block.entries[0].offer_id == offer_id
    assert ": Пакет A" in outcome.rendered_text


def test_invalid_runtime_contract_rejected() -> None:
    with pytest.raises(ValidationError):
        OfferConditionEvidence(
            source_client_id="demo",
            offer_id="x",
            completeness="complete",
            conditions=(
                RequiredOfferConditionBlock(
                    source_client_id="demo",
                    condition_id="package_includes",
                    completeness="unknown",
                    entries=(),
                ),
            ),
        )


def test_terminal_route_requires_terminal_authorities(demo_material) -> None:
    adapted = _adapted(route="ADMIN", mode="standard", patient_text=None, topic_id=None)
    selection = _selection_from_post_composer(adapted, demo_material)
    with pytest.raises(MaterializationContractError):
        materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(demo_material, terminal_authorities=()),
            as_of=AS_OF,
        )


def test_foreign_condition_owner_rejected(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    with pytest.raises(ValidationError):
        materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(
                demo_material,
                condition_evidence_by_offer={
                    "all_on_4.jaw.implantium": OfferConditionEvidence(
                        source_client_id="foreign",
                        offer_id="all_on_4.jaw.implantium",
                        completeness="complete",
                        conditions=(),
                    )
                },
            ),
            as_of=AS_OF,
        )


def test_condition_dict_key_mismatch_rejected(demo_material) -> None:
    with pytest.raises(ValidationError):
        ResponsePlanMaterializationSources(
            session_key=SESSION,
            context_strategy="full_context",
            material_authority=demo_material,
            condition_evidence_by_offer={
                "wrong_key": OfferConditionEvidence(
                    source_client_id="demo",
                    offer_id="all_on_4.jaw.implantium",
                    completeness="complete",
                    conditions=(),
                )
            },
            terminal_authorities=_terminal_authorities(),
        )


def test_condition_entry_wrong_offer_rejected(demo_material) -> None:
    with pytest.raises(ValidationError):
        OfferConditionEvidence(
            source_client_id="demo",
            offer_id="all_on_4.jaw.implantium",
            completeness="complete",
            conditions=(
                RequiredOfferConditionBlock(
                    source_client_id="demo",
                    condition_id="package_includes",
                    completeness="complete",
                    entries=(
                        RequiredOfferConditionOfferEntry(
                            offer_id="all_on_4.jaw.impro",
                            display_text="wrong",
                        ),
                    ),
                ),
            ),
        )


def test_adapted_decision_mismatch_rejected(demo_material) -> None:
    adapted = _adapted(requested_aspect_ids=("overview",))
    other = _adapted(requested_aspect_ids=("price",))
    selection = _selection_from_post_composer(adapted, demo_material)
    with pytest.raises(MaterializationContractError):
        materialize_pre_composer_payload(selection, other, _sources(demo_material), as_of=AS_OF)


def test_mixed_currency_selected_but_finalized_empty(demo_material) -> None:
    bundle = _synthetic_mixed_currency_bundle()
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="service_one",
        requested_aspect_ids=("price",),
    )
    selection = _manual_selection(
        adapted,
        price_ids=("service_one",),
        reference_id="service_one",
    )
    evidence = _complete_empty_evidence("offer_rub", "offer_usd")
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is None
    assert outcome.trace.selected_offers
    assert outcome.trace.finalized_offers == ()


def test_finalized_trace_matches_price_block(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    evidence = _complete_empty_evidence("all_on_4.jaw.implantium")
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert outcome.resolved.price_block.offer_rows
    assert [row.offer_id for row in outcome.trace.finalized_offers] == list(
        outcome.resolved.price_block.offer_ids
    )
    row = outcome.trace.finalized_offers[0]
    frozen = outcome.resolved.price_block.offer_rows[0]
    assert row.amount == frozen.amount
    assert row.currency == frozen.currency
    assert row.billing_unit == frozen.billing_unit
    assert row.offer_label == frozen.offer_label


def test_frozen_trace_immune_to_bundle_swap(demo_material) -> None:
    from core.response_plan_materialization import _build_finalized_offer_trace
    from core.response_plan_resolver import resolve_response_plan

    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    evidence = _complete_empty_evidence("all_on_4.jaw.implantium")
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    resolved = resolve_response_plan(payload.plan, payload.composer_result)
    trace_before = _build_finalized_offer_trace(resolved)
    trace_after = _build_finalized_offer_trace(resolved)
    assert trace_before == trace_after
    assert trace_before[0].amount == resolved.price_block.offer_rows[0].amount  # type: ignore[union-attr]


def test_distinguishable_labels_with_shared_package_label(demo_material) -> None:
    turn1 = _selection_from_post_composer(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("overview",),
        ),
        demo_material,
    )
    adapted = _adapted(
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        patient_situation=_situation(),
        requested_aspect_ids=("price",),
    )
    from contracts.response_plan_dialogue_context import ShownServiceOptionsSnapshot

    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    from contracts.response_plan_post_composer import SituationContinuityPolicy
    from core.response_plan_post_composer import resolve_post_composer_selection

    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=turn1.situation_delta.state,
        current_turn_index=2,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=snapshot,
    )
    evidence = _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_6.jaw.implantium",
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    labels = {row.offer_id: row.offer_label for row in payload.plan.price_plan.offer_rows}
    assert "All-on-4" in labels["all_on_4.jaw.implantium"]
    assert "All-on-6" in labels["all_on_6.jaw.implantium"]
    assert labels["all_on_4.jaw.implantium"] != labels["all_on_6.jaw.implantium"]


def test_two_variants_same_service_distinguish_by_brand(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _manual_selection(
        adapted,
        price_ids=("all_on_4",),
        reference_id="all_on_4",
        basis="referenced_service",
    )
    evidence = _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    labels = {row.offer_id: row.offer_label for row in payload.plan.price_plan.offer_rows}
    assert "Implantium" in labels["all_on_4.jaw.implantium"]
    assert "Impro" in labels["all_on_4.jaw.impro"]
    assert labels["all_on_4.jaw.implantium"] != labels["all_on_4.jaw.impro"]


def test_promo_selected_materialized_and_visible(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert payload.plan.promo_candidate_ids
    materialized = {
        fact.fact_id
        for fact in payload.plan.commercial_facts
        if "promo" in fact.allowed_roles
    }
    assert materialized.issuperset(set(payload.plan.promo_candidate_ids))
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    visible_promo_ids = {block.fact_id for block in outcome.resolved.promo_blocks}
    assert visible_promo_ids
    assert visible_promo_ids <= set(outcome.resolved.finalized_commercial_ids.promo_fact_ids)


def test_amplifier_selected_materialized_and_visible(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    evidence = _complete_empty_evidence("all_on_4.jaw.implantium")
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert payload.plan.automatic_amplifier_candidate_ids
    materialized = {
        fact.fact_id
        for fact in payload.plan.commercial_facts
        if "automatic_amplifier" in fact.allowed_roles
    }
    assert materialized.issuperset(set(payload.plan.automatic_amplifier_candidate_ids))
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    visible = {block.fact_id for block in outcome.resolved.automatic_amplifier_blocks}
    assert visible
    assert visible <= set(outcome.resolved.finalized_commercial_ids.amplifier_fact_ids)


def test_marketing_overlap_requested_and_promo_single_visible_fact(demo_material) -> None:
    from core.response_plan_fact_projection import project_commercial_fact_candidate

    fact_id = "implant_same_day_discount"
    fact = demo_material.bundle.facts[fact_id]
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
        requested_fact_ids=(fact_id,),
    )
    selection = _manual_selection(
        adapted,
        reference_id="all_on_4",
        scope="service",
        requested_fact_candidates=(
            project_commercial_fact_candidate(
                demo_material.bundle,
                fact,
                source_client_id="demo",
                allowed_roles=("requested_fact",),
            ),
        ),
    )
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    matches = [fact for fact in payload.plan.commercial_facts if fact.fact_id == fact_id]
    assert len(matches) == 1
    assert "promo" in matches[0].allowed_roles
    assert "requested_fact" in matches[0].allowed_roles
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    roles = {
        block.fact_id: block.role
        for block in (
            *outcome.resolved.requested_fact_blocks,
            *outcome.resolved.promo_blocks,
        )
    }
    assert fact_id in roles
    assert roles[fact_id] == "requested_fact"


def test_marketing_conflict_text_rejected(demo_material) -> None:
    fact_id = "implant_same_day_discount"
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
        requested_fact_ids=(fact_id,),
    )
    selection = _manual_selection(
        adapted,
        reference_id="all_on_4",
        scope="service",
        requested_fact_candidates=(
            CommercialFactCandidate(
                fact_id=fact_id,
                display_text="WRONG TEXT",
                explicit_only=False,
                allowed_roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("all_on_4",),
                source_client_id="demo",
            ),
        ),
    )
    with pytest.raises(MaterializationContractError, match="materialization_fact_conflict"):
        materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(demo_material),
            as_of=AS_OF,
        )


def test_marketing_conflict_policy_rejected(demo_material) -> None:
    from core.response_plan_fact_projection import project_commercial_fact_candidate

    fact_id = "implant_same_day_discount"
    fact = demo_material.bundle.facts[fact_id]
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
        requested_fact_ids=(fact_id,),
    )
    requested = project_commercial_fact_candidate(
        demo_material.bundle,
        fact,
        source_client_id="demo",
        allowed_roles=("requested_fact",),
    )
    selection = _manual_selection(
        adapted,
        reference_id="all_on_4",
        scope="service",
        requested_fact_candidates=(requested.model_copy(update={"requires_implant_scope": True}),),
    )
    with pytest.raises(MaterializationContractError, match="materialization_fact_conflict"):
        materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(demo_material),
            as_of=AS_OF,
        )


def test_marketing_foreign_owner_rejected(demo_material) -> None:
    fact_id = "implant_same_day_discount"
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
        requested_fact_ids=(fact_id,),
    )
    selection = _manual_selection(
        adapted,
        reference_id="all_on_4",
        scope="service",
        requested_fact_candidates=(
            CommercialFactCandidate(
                fact_id=fact_id,
                display_text=demo_material.bundle.facts[fact_id].text_fact,
                explicit_only=False,
                allowed_roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("all_on_4",),
                source_client_id="foreign",
            ),
        ),
    )
    with pytest.raises(MaterializationOwnershipError):
        materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(demo_material),
            as_of=AS_OF,
        )


def test_rendered_price_text_uses_distinguishable_offer_labels(demo_material) -> None:
    from contracts.response_plan_dialogue_context import ShownServiceOptionsSnapshot
    from contracts.response_plan_post_composer import SituationContinuityPolicy
    from core.response_plan_post_composer import resolve_post_composer_selection

    turn1 = _selection_from_post_composer(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("overview",),
        ),
        demo_material,
    )
    adapted = _adapted(
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        patient_situation=_situation(),
        requested_aspect_ids=("price",),
    )
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=turn1.situation_delta.state,
        current_turn_index=2,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=snapshot,
    )
    evidence = _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_6.jaw.implantium",
    )
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    rendered = outcome.rendered_text
    assert "All-on-4" in rendered
    assert "All-on-6" in rendered
    rows = outcome.resolved.price_block.offer_rows
    for row in rows:
        assert row.offer_label in rendered
    assert [row.offer_id for row in rows] == [row.offer_id for row in outcome.trace.finalized_offers]


def test_single_rendered_price_matches_frozen_row(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    evidence = _complete_empty_evidence("all_on_4.jaw.implantium")
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    row = outcome.resolved.price_block.offer_rows[0]  # type: ignore[union-attr]
    assert row.offer_label in outcome.rendered_text
    assert str(row.amount)[0:3] in outcome.rendered_text.replace(" ", "")


def test_explicit_only_promo_not_automatically_shown(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    for fact_id in payload.plan.promo_candidate_ids:
        if fact_id in {"implant_warranty", "clinic_warranty"}:
            matching = [fact for fact in payload.plan.commercial_facts if fact.fact_id == fact_id]
            assert not matching or all(fact.explicit_only for fact in matching)


def test_optional_marketing_failure_preserves_patient_text(demo_material) -> None:
    from contracts.response_plan_post_composer import PostComposerMaterialAuthority
    from tests.test_target_offer_projection import _bundle

    empty_bundle = PostComposerMaterialAuthority(
        source_client_id="demo",
        bundle=_bundle(),
    )
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
        patient_text="Базовый ответ без маркетинга.",
    )
    selection = _selection_from_post_composer(adapted, empty_bundle)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(empty_bundle),
        as_of=AS_OF,
    )
    assert outcome.resolved.patient_text == "Базовый ответ без маркетинга."
    assert outcome.resolved.promo_blocks == ()


def test_service_value_visible_for_service_scope_overview(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert outcome.resolved.service_value_block is not None
    assert outcome.resolved.finalized_commercial_ids.service_value_ids


def test_warranty_proposed_by_selector_not_automatically_materialized(demo_material) -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from contracts.response_plan_post_composer import PostComposerMaterialAuthority
    from contracts.response_schema import TargetCommercialFact
    from tests.test_target_offer_projection import _bundle

    bundle = _bundle()
    bundle.facts["custom_warranty_fixture"] = TargetCommercialFact(
        id="custom_warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия",
        text_fact="Гарантия 1 год по договору.",
        render_mode="strict",
        allowed_service_ids=["service_one"],
    )
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="service_one",
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, material)
    marketing_result = SimpleNamespace(
        selected_refs=(),
        amplifier_refs=("fact:custom_warranty_fixture",),
        applied_scenarios=(),
        cta_key="service",
    )
    with patch(
        "core.response_plan_materialization.select_target_marketing",
        return_value=marketing_result,
    ):
        payload = materialize_pre_composer_payload(
            selection,
            adapted,
            _sources(material),
            as_of=AS_OF,
        )
        outcome = resolve_materialized_response(
            selection,
            adapted,
            _sources(material),
            as_of=AS_OF,
        )
    assert "custom_warranty_fixture" not in payload.plan.automatic_amplifier_candidate_ids
    assert "custom_warranty_fixture" not in payload.plan.promo_candidate_ids
    assert outcome.resolved.automatic_amplifier_blocks == ()
    assert outcome.resolved.finalized_commercial_ids.amplifier_fact_ids == ()


def test_explicit_warranty_request_shown_as_requested_fact(demo_material) -> None:
    from contracts.response_plan_post_composer import PostComposerMaterialAuthority
    from contracts.response_schema import TargetCommercialFact
    from core.response_plan_fact_projection import project_commercial_fact_candidate
    from tests.test_target_offer_projection import _bundle

    bundle = _bundle()
    bundle.facts["custom_warranty_fixture"] = TargetCommercialFact(
        id="custom_warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия",
        text_fact="Гарантия 1 год по договору.",
        render_mode="strict",
        allowed_service_ids=["service_one"],
    )
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    fact = bundle.facts["custom_warranty_fixture"]
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="service_one",
        requested_aspect_ids=("overview",),
        requested_fact_ids=("custom_warranty_fixture",),
    )
    selection = _manual_selection(
        adapted,
        reference_id="service_one",
        scope="service",
        requested_fact_candidates=(
            project_commercial_fact_candidate(
                bundle,
                fact,
                source_client_id="demo",
                allowed_roles=("requested_fact",),
            ),
        ),
    )
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(material),
        as_of=AS_OF,
    )
    assert outcome.resolved.requested_fact_blocks
    assert outcome.resolved.requested_fact_blocks[0].fact_id == "custom_warranty_fixture"
    assert outcome.resolved.finalized_commercial_ids.requested_fact_ids == (
        "custom_warranty_fixture",
    )


def test_invalid_materialization_trace_rejected() -> None:
    with pytest.raises(MaterializationContractError):
        from contracts.response_plan_materialization import MaterializationTrace

        MaterializationTrace("INVALID", (), ())  # type: ignore[arg-type]


def _synthetic_mixed_currency_bundle() -> ResponseSchemaBundle:
    from tests.test_target_offer_projection import _bundle, _offer

    bundle = _bundle()
    offers = list(bundle.offers)
    offers.extend(
        [
            {**_offer("offer_rub", mode="fixed"), "offer_id": "offer_rub", "price": {"mode": "fixed", "amount": 100000, "currency": "RUB", "billing_unit": "jaw"}},
            {**_offer("offer_usd", mode="fixed"), "offer_id": "offer_usd", "price": {"mode": "fixed", "amount": 1200, "currency": "USD", "billing_unit": "jaw"}},
        ]
    )
    data = bundle.model_dump()
    data["offers"] = offers
    data["strategy"]["default_offer_priorities"].update({"offer_rub": 100, "offer_usd": 90})
    return ResponseSchemaBundle.model_validate(data)
