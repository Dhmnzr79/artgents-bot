"""DEMO-PRICE-CONDITIONS-1: catalog-backed required offer conditions on response-plan path."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope
from contracts.response_plan import SessionKey
from contracts.response_plan_composer import AdaptedComposerDecision
from contracts.response_plan_post_composer import PostComposerMaterialAuthority, PostComposerSelectionPlan, ResponseSituationDelta
from contracts.response_schema import ResponseSchemaBundle, TargetFixedPrice
from core.response_plan_condition_evidence import (
    build_condition_evidence_by_offer,
    materialization_price_scope_label,
)
from core.response_plan_materialization import resolve_materialized_response
from core.response_plan_materialization_sources import build_response_plan_materialization_sources
from core.response_plan_production_adapter import format_single_price_display
from core.response_schema_loader import load_response_schema_bundle
from core.response_text_renderer import _condition_display_texts, render_response_text
from tests.test_response_plan_dialogue_acceptance import (
    TurnSpec,
    _assert_accumulated_group,
    _composer_dict,
    _demo_context,
    _policy,
    _store,
)
from tests.test_response_plan_materialization import (
    AS_OF,
    SESSION,
    _adapted,
    _selection_from_post_composer,
    _situation,
    _terminal_authorities,
)

TARGET_ROOT = Path("clients/demo/target_response")
ALL_ON_4_IMPLANTIUM = "all_on_4.jaw.implantium"
ALL_ON_4_IMPRO = "all_on_4.jaw.impro"
MANDATORY_EXCLUSION_TEXT = "КТ и костная пластика по показаниям — отдельно"
NEUTRAL_PATIENT_TEXT = "Покажу актуальную стоимость и обязательные условия."


@pytest.fixture
def demo_bundle() -> ResponseSchemaBundle:
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle: ResponseSchemaBundle) -> PostComposerMaterialAuthority:
    return PostComposerMaterialAuthority(source_client_id="demo", bundle=demo_bundle)


def _offer_by_id(bundle: ResponseSchemaBundle, offer_id: str):
    for offer in bundle.offers:
        if offer.offer_id == offer_id:
            return offer
    raise KeyError(offer_id)


def _catalog_sources(material: PostComposerMaterialAuthority):
    return build_response_plan_materialization_sources(
        session_key=SESSION,
        material=material,
        terminal_authorities=_terminal_authorities(),
    )


def _price_selection(adapted, material: PostComposerMaterialAuthority, *, service_id: str = "all_on_4"):
    return _selection_from_post_composer(
        adapted,
        material,
        active_session_service_id=service_id,
    )


def _assert_price_block_has_no_duplicate_scope(price_text: str) -> None:
    for line in price_text.splitlines():
        assert ": за одну челюсть" not in line
        if "за одну челюсть" in line:
            assert line.count("за одну челюсть") == 1


def _material_with_only_implantium_all_on_4(material: PostComposerMaterialAuthority) -> PostComposerMaterialAuthority:
    offers = tuple(
        offer.model_copy(update={"active": False})
        if offer.service_id == "all_on_4" and offer.offer_id != ALL_ON_4_IMPLANTIUM
        else offer
        for offer in material.bundle.offers
    )
    return PostComposerMaterialAuthority(
        source_client_id=material.source_client_id,
        bundle=material.bundle.model_copy(update={"offers": offers}),
    )


def _assert_single_price_render_order(resolved, rendered: str, *, patient_text: str) -> None:
    assert resolved.price_block is not None
    price_text = resolved.price_block.display_text.strip()
    condition_texts = _condition_display_texts(resolved.required_offer_conditions)
    patient_clean = patient_text.strip()
    price_end = rendered.index(price_text) + len(price_text)
    patient_start = rendered.index(patient_clean)
    for condition_text in condition_texts:
        condition_start = rendered.index(condition_text)
        condition_end = condition_start + len(condition_text)
        assert price_end <= condition_start
        assert condition_end <= patient_start


def test_catalog_sources_all_on_4_implantium_mandatory_exclusion(demo_material) -> None:
    evidence = _catalog_sources(demo_material).condition_evidence_by_offer[ALL_ON_4_IMPLANTIUM]
    assert evidence.completeness == "complete"
    assert len(evidence.conditions) == 1
    assert evidence.conditions[0].condition_id == "mandatory_exclusion"
    assert evidence.conditions[0].entries[0].display_text == MANDATORY_EXCLUSION_TEXT


def test_demo_all_on_4_price_from_disk_without_manual_evidence(demo_material) -> None:
    material = _material_with_only_implantium_all_on_4(demo_material)
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        patient_text=NEUTRAL_PATIENT_TEXT,
    )
    selection = _price_selection(adapted, material)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _catalog_sources(material),
        as_of=AS_OF,
    )
    rendered = render_response_text(outcome.resolved)
    assert outcome.resolved.patient_text == NEUTRAL_PATIENT_TEXT
    assert "318 000" in rendered
    assert rendered.count("318 000") == 1
    assert MANDATORY_EXCLUSION_TEXT in rendered
    assert rendered.count(MANDATORY_EXCLUSION_TEXT) == 1
    assert outcome.resolved.price_block is not None
    assert MANDATORY_EXCLUSION_TEXT not in outcome.resolved.price_block.display_text
    _assert_price_block_has_no_duplicate_scope(outcome.resolved.price_block.display_text)
    assert "All-on-4 Implantium" in outcome.resolved.price_block.display_text
    assert rendered.count(outcome.resolved.price_block.display_text.strip()) == 1
    _assert_single_price_render_order(outcome.resolved, rendered, patient_text=NEUTRAL_PATIENT_TEXT)


def test_tomography_complete_empty_conditions_show_price_without_fake_condition(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="tomography",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    sources = _catalog_sources(demo_material)
    offer = _offer_by_id(demo_material.bundle, "tomography.default")
    tomography_evidence = sources.condition_evidence_by_offer["tomography.default"]
    assert tomography_evidence.completeness == "complete"
    assert tomography_evidence.conditions == ()
    assert materialization_price_scope_label(offer) == ""
    outcome = resolve_materialized_response(selection, adapted, sources, as_of=AS_OF)
    assert outcome.resolved.price_block is not None
    price_text = outcome.resolved.price_block.display_text
    assert "3 000" in price_text
    assert price_text.count("за одну процедуру") == 1
    assert "за одно исследование" not in price_text
    assert outcome.resolved.required_offer_conditions == ()
    legacy_display = format_single_price_display(offer)
    assert offer.package.label in legacy_display
    assert "за одно исследование" in legacy_display


def test_two_offers_keep_distinct_conditions_and_labels(demo_material, demo_bundle) -> None:
    offers = tuple(
        offer.model_copy(update={"active": False})
        if offer.offer_id == "all_on_4.jaw.nobel"
        else offer
        for offer in demo_material.bundle.offers
    )
    material = PostComposerMaterialAuthority(
        source_client_id="demo",
        bundle=demo_material.bundle.model_copy(update={"offers": offers}),
    )
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        patient_text=NEUTRAL_PATIENT_TEXT,
    )
    selection = PostComposerSelectionPlan(
        session_key=SESSION,
        source_client_id="demo",
        decision=adapted.decision,
        resolved_topic_id="implantation",
        response_scope="service",
        reference_service_id="all_on_4",
        reference_service_status="compatible",
        effective_scope=EffectiveScope(topic="implantation", extent="full_arch", jaw="upper"),
        ranked_service_ids=("all_on_4",),
        visible_service_option_ids=(),
        price_candidate_service_ids=("all_on_4",),
        comparison_service_ids=(),
        selection_basis="referenced_service",
        selection_intent="price_candidates",
        requested_fact_candidates=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        adapter_diagnostics=(),
        diagnostics=(),
    )
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _catalog_sources(material),
        as_of=AS_OF,
    )
    rendered = render_response_text(outcome.resolved)
    implantium_offer = _offer_by_id(demo_bundle, ALL_ON_4_IMPLANTIUM)
    impro_offer = _offer_by_id(demo_bundle, ALL_ON_4_IMPRO)
    assert outcome.resolved.price_block is not None
    price_text = outcome.resolved.price_block.display_text
    assert "318 000" in rendered
    assert "368 000" in rendered
    assert rendered.count("318 000") == 1
    assert rendered.count("368 000") == 1
    assert rendered.count(MANDATORY_EXCLUSION_TEXT) == 2
    assert "Implantium" in price_text
    assert "Impro" in price_text
    assert materialization_price_scope_label(implantium_offer) == ""
    assert materialization_price_scope_label(impro_offer) == ""
    assert MANDATORY_EXCLUSION_TEXT not in price_text
    _assert_price_block_has_no_duplicate_scope(price_text)
    for row in outcome.resolved.price_block.offer_rows:
        offer = _offer_by_id(demo_bundle, row.offer_id)
        assert isinstance(offer.price, TargetFixedPrice)
        line = f"{row.amount // 1000} 000" if row.amount >= 1000 else str(row.amount)
        assert price_text.count(line) == 1
    _assert_single_price_render_order(outcome.resolved, rendered, patient_text=NEUTRAL_PATIENT_TEXT)


def test_missing_metadata_excludes_offer_and_preserves_patient_text(demo_material) -> None:
    offers = tuple(
        offer.model_copy(update={"required_conditions_metadata": None})
        if offer.service_id == "all_on_4"
        else offer
        for offer in demo_material.bundle.offers
    )
    material = PostComposerMaterialAuthority(
        source_client_id="demo",
        bundle=demo_material.bundle.model_copy(update={"offers": offers}),
    )
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        requested_aspect_ids=("price",),
        patient_text="Стоимость All-on-4.",
    )
    selection = _price_selection(adapted, material)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        build_response_plan_materialization_sources(
            session_key=SESSION,
            material=material,
            terminal_authorities=_terminal_authorities(),
        ),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is None
    assert outcome.resolved.patient_text == "Стоимость All-on-4."
    assert any(
        item.code == "materialization_price_conditions_unknown"
        for item in outcome.materialization_diagnostics
    )


def test_nikadent_catalog_does_not_inherit_demo_complete_confirmation() -> None:
    bundle = load_response_schema_bundle(Path("clients/nikadent/target_response"))
    material = PostComposerMaterialAuthority(source_client_id="nikadent", bundle=bundle)
    evidence = build_condition_evidence_by_offer(material)
    fixed = [offer for offer in bundle.offers if offer.active and isinstance(offer.price, TargetFixedPrice)]
    assert fixed
    assert all(item.completeness == "unknown" for item in evidence.values())


def test_legacy_single_price_display_keeps_full_package_label(demo_bundle) -> None:
    offer = _offer_by_id(demo_bundle, ALL_ON_4_IMPLANTIUM)
    display = format_single_price_display(offer)
    assert offer.package.label in display
    assert MANDATORY_EXCLUSION_TEXT in display


def test_data_backed_dialogue_price_turn_uses_public_sources(tmp_path: Path) -> None:
    from tests.test_response_plan_dialogue_acceptance import DialogueRunner

    base_ctx = _demo_context()
    material = _material_with_only_implantium_all_on_4(base_ctx.material)
    ctx = replace(base_ctx, material=material)
    runner = DialogueRunner(store=_store(tmp_path), ctx=ctx, policy=_policy())
    prior = runner.read().state.accumulated_shown_ids
    outcome = runner.run_turn(
        TurnSpec(
            patient_message="Сколько стоит All-on-4 Implantium?",
            request_id="price-conditions-e2e",
            composer_json=_composer_dict(
                patient_text=NEUTRAL_PATIENT_TEXT,
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["price"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    rendered = outcome.prepared.rendered_text
    assert resolved.patient_text == NEUTRAL_PATIENT_TEXT
    assert resolved.price_block is not None
    assert "318 000" in rendered
    assert rendered.count("318 000") == 1
    assert MANDATORY_EXCLUSION_TEXT in rendered
    assert rendered.count(MANDATORY_EXCLUSION_TEXT) == 1
    price_text = resolved.price_block.display_text.strip()
    assert rendered.count(price_text) == 1
    assert MANDATORY_EXCLUSION_TEXT not in price_text
    _assert_price_block_has_no_duplicate_scope(price_text)
    _assert_single_price_render_order(resolved, rendered, patient_text=NEUTRAL_PATIENT_TEXT)

    finalized = resolved.finalized_commercial_ids
    assert finalized.price_offer_ids
    assert finalized.required_offer_condition_ids
    after = runner.read().state.accumulated_shown_ids
    _assert_accumulated_group(prior, finalized, after, group="price_offer_ids")
    _assert_accumulated_group(prior, finalized, after, group="required_offer_condition_ids")
    assert len(after.price_offer_ids) == len(set(after.price_offer_ids))
    assert len(after.required_offer_condition_ids) == len(set(after.required_offer_condition_ids))
    for offer_id in finalized.price_offer_ids:
        assert offer_id in after.price_offer_ids
    for condition_id in finalized.required_offer_condition_ids:
        assert condition_id in after.required_offer_condition_ids
