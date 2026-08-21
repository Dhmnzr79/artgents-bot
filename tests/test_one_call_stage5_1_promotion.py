"""Stage 5.1 promotion intent and PresentationResult offline tests."""

from __future__ import annotations

from datetime import date

import pytest

from contracts.one_call_envelope import OneCallEnvelope
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from core.one_call_envelope_protocol import (
    OneCallEnvelopeProtocolError,
    dumps_production_envelope,
    parse_production_envelope_json,
)
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.sales_fast_authoritative_commerce import (
    AuthoritativeCommerceResult,
    build_authoritative_commerce_result,
    gate_commerce_result_by_intent,
)
from contracts.doctor_schema_refs import build_doctor_source_refs
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.target_client_data import client_pack_root, load_target_client_data
from core.target_marketing_selector import select_stage51_marketing
from core.target_presentation_decision import decide_target_presentation, TargetPresentationCadenceState
from contracts.target_response_spec import TargetResponseSpec
from tests.test_sales_one_plus_turn import _DEMO_CATALOG, _DEMO_REF_CATALOG, answer_envelope

_DEMO_MD_ROOT = client_pack_root("demo") / "md"


def _demo_stage51_inputs():
    data = load_target_client_data("demo")
    doctors = load_doctor_catalog(client_pack_root("demo") / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(_DEMO_MD_ROOT)
    doctor_refs = build_doctor_source_refs(doctors)
    external_index = ResponseSchemaExternalIndex(kb_refs=kb_refs, doctor_refs=doctor_refs)
    return data.bundle, doctors, external_index


def test_prompt_contract_version_four() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 4


def test_envelope_promotion_scope_invariants() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError, match="promotion_scope_forbidden"):
        parse_production_envelope_json(
            answer_envelope("Ответ.", commercial_intent="none", promotion_scope="general"),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
        )
    envelope = parse_production_envelope_json(
        answer_envelope(
            "Какие акции?",
            commercial_intent="promotion",
            promotion_scope="general",
        ),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert envelope.commercial_intent == "promotion"
    assert envelope.promotion_scope == "general"


def test_clarify_forces_promotion_scope_none() -> None:
    frame = SalesOnePlusSemanticFrame(
        route="CLARIFY",
        service_id=None,
        service_id_provenance="null",
        extent=None,
        extent_provenance="null",
        jaw=None,
        jaw_provenance="null",
        stage=None,
        stage_provenance="null",
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis="service",
        clarify_service_options=("all_on_4", "classic"),
        service_reference_status="none",
        requested_service_id=None,
        availability_status="none",
    )
    assert frame.promotion_scope == "none"


def test_automatic_priority_promo_first_eligible() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
        marketing_scenarios=(),
        shown_fact_ids=(),
        shown_amplifier_refs=(),
    )
    assert outcome.fail_closed_reason is None
    assert outcome.selection is not None
    assert "fact:implant_same_day_discount" in outcome.selection.selected_refs
    assert outcome.selection.selected_refs.count("fact:implant_same_day_discount") == 1


def test_no_auto_promo_when_service_id_null() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="default",
        service_id=None,
        today=date(2026, 8, 1),
    )
    promo_refs = [r for r in (outcome.selection.selected_refs if outcome.selection else ())]
    assert not any(r == "fact:implant_same_day_discount" for r in promo_refs)


def test_general_overview_exact_three_in_order() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="general",
        semantic_context="default",
        service_id=None,
        today=date(2026, 8, 1),
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == (
        "fact:implant_same_day_discount",
        "fact:professional_whitening_discount",
        "fact:free_implant_consult",
    )
    assert outcome.selection.selection_mode == "promotion_general"


def test_general_overview_drops_expired_on_later_date() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="general",
        semantic_context="default",
        service_id=None,
        today=date(2026, 8, 16),
    )
    assert outcome.selection is not None
    assert "fact:professional_whitening_discount" not in outcome.selection.selected_refs
    assert len(outcome.selection.selected_refs) <= 3


def test_shown_fail_closed_without_session_promo() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="shown",
        semantic_context="default",
        service_id="all_on_4",
        today=date(2026, 8, 1),
        last_rendered_promo_fact_id=None,
    )
    assert outcome.fail_closed_reason == "promotion_shown_without_session_promo"


def test_shown_repeats_last_rendered_promo() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="shown",
        semantic_context="default",
        service_id="all_on_4",
        today=date(2026, 8, 1),
        shown_fact_ids=("implant_same_day_discount",),
        last_rendered_promo_fact_id="implant_same_day_discount",
    )
    assert outcome.selection is not None
    assert outcome.selection.selection_mode == "promotion_shown"
    assert "fact:implant_same_day_discount" in outcome.selection.selected_refs


def test_service_promotion_sets_selection_mode() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
    )
    assert outcome.selection is not None
    assert outcome.selection.selection_mode == "promotion_service"


def test_session_global_suppression_cross_service() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="all_on_6",
        today=date(2026, 8, 1),
        shown_fact_ids=("implant_same_day_discount",),
    )
    assert outcome.selection is not None
    assert "fact:implant_same_day_discount" not in outcome.selection.selected_refs


def test_promotion_intent_suppresses_commerce_surfaces() -> None:
    commerce = AuthoritativeCommerceResult(
        service_id="all_on_4",
        presentation_mode="exact_offer",
        entry_price_amount=318000,
        entry_price_text="318 000 ₽",
        ordered_offers=(),
        featured_offer_id="x",
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=frozenset({318000}),
        patient_price_block="318 000 ₽",
        widget_offer_payload={"amount": 318000},
    )
    gated = gate_commerce_result_by_intent(commerce, commercial_intent="promotion")
    assert gated.widget_offer_payload is None
    assert gated.presentation_mode == "none"


def test_primary_price_channel_records_shown_followups() -> None:
    from core.target_response_followup_materializer import TargetPriceFollowup
    from core.target_response_followup_policy import TargetResponseFollowupSelection

    spec = TargetResponseSpec(
        service_id="all_on_4",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("price",),
        response_mode="answer",
        allow_marketing_facts=False,
        allow_consultation_close=False,
        allow_cta=True,
    )
    followups = TargetResponseFollowupSelection(
        source="price",
        content=(),
        price=(
            TargetPriceFollowup(
                id="included",
                label="Что входит",
                ref="price:included",
                action="show",
                source_offer_ids=("all_on_4.default",),
            ),
        ),
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=None,
        spec=spec,
        navigation_followups=(),
        selected_followups=followups,
        primary_content_ref=None,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert decision.channel == "price"
    assert decision.cadence_update.shown_price_followup_refs == ("price:included",)


def test_no_promo_on_clarify_route() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="CLARIFY",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ()


def test_service_promo_scope_only_own_service() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
    )
    assert outcome.selection is not None
    assert "fact:professional_whitening_discount" not in outcome.selection.selected_refs
    assert "fact:implant_same_day_discount" in outcome.selection.selected_refs


def test_shown_fail_closed_when_promo_no_longer_eligible() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="shown",
        semantic_context="service",
        service_id="professional_whitening",
        today=date(2026, 8, 16),
        last_rendered_promo_fact_id="professional_whitening_discount",
    )
    assert outcome.fail_closed_reason == "promotion_shown_promo_no_longer_eligible"


def test_priority_promo_in_marketing_limit_not_amplifier() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
        marketing_scenarios=("cost",),
    )
    assert outcome.selection is not None
    assert "fact:implant_same_day_discount" in outcome.selection.selected_refs
    assert len(outcome.selection.selected_refs) <= 3
    assert len(outcome.selection.amplifier_refs) <= 2
    assert "fact:implant_same_day_discount" not in outcome.selection.amplifier_refs or (
        outcome.selection.amplifier_refs.count("fact:implant_same_day_discount") == 0
    )


def test_automatic_none_none_does_not_open_commerce_surfaces() -> None:
    gated = gate_commerce_result_by_intent(
        AuthoritativeCommerceResult(
            service_id="all_on_4",
            presentation_mode="exact_offer",
            entry_price_amount=318000,
            entry_price_text="318 000 ₽",
            ordered_offers=(),
            featured_offer_id="x",
            selected_exact_offer=None,
            needs_consultation_quote=False,
            authoritative_amounts=frozenset({318000}),
            patient_price_block="318 000 ₽",
            widget_offer_payload={"amount": 318000},
        ),
        commercial_intent="none",
    )
    assert gated.widget_offer_payload is None
    assert gated.presentation_mode == "none"


def test_general_direct_promotion_bypasses_shown_suppression() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="general",
        semantic_context="default",
        service_id=None,
        today=date(2026, 8, 1),
        shown_fact_ids=("implant_same_day_discount",),
    )
    assert outcome.selection is not None
    assert "fact:implant_same_day_discount" in outcome.selection.selected_refs


def test_service_direct_promotion_bypasses_shown_suppression() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id="all_on_4",
        today=date(2026, 8, 1),
        shown_fact_ids=("implant_same_day_discount",),
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:implant_same_day_discount",)


def test_direct_service_promo_not_returned_after_expiry() -> None:
    bundle, doctors, external_index = _demo_stage51_inputs()
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id="professional_whitening",
        today=date(2026, 8, 16),
    )
    promo_refs = (
        outcome.selection.selected_refs if outcome.selection is not None else ()
    )
    assert "fact:professional_whitening_discount" not in promo_refs


def test_gate_unknown_commercial_intent_fail_closed() -> None:
    commerce = AuthoritativeCommerceResult(
        service_id="all_on_4",
        presentation_mode="exact_offer",
        entry_price_amount=318000,
        entry_price_text="318 000 ₽",
        ordered_offers=(),
        featured_offer_id="x",
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=frozenset({318000}),
        patient_price_block="318 000 ₽",
        widget_offer_payload={"amount": 318000},
    )
    gated = gate_commerce_result_by_intent(commerce, commercial_intent="future_intent")
    assert gated.presentation_mode == "none"
    assert gated.widget_offer_payload is None
    assert gated.patient_price_block is None
    assert gated.entry_price_amount is None


def test_automatic_promo_no_rotation_when_first_shown() -> None:
    from contracts.response_schema import ResponseSchemaBundle

    bundle = ResponseSchemaBundle.model_validate(
        {
            "services": {
                "service_one": {
                    "name": "Service One",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "selection": {"mode": "context"},
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": {
                "promo_a": {
                    "id": "promo_a",
                    "kind": "promo",
                    "catalog_label": "Promo A topic",
                    "text_fact": "Promo A.",
                    "render_mode": "strict",
                    "active": True,
                    "allowed_service_ids": ["service_one"],
                },
                "promo_b": {
                    "id": "promo_b",
                    "kind": "promo",
                    "catalog_label": "Promo B topic",
                    "text_fact": "Promo B.",
                    "render_mode": "strict",
                    "active": True,
                    "allowed_service_ids": ["service_one"],
                },
            },
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 3,
                    "max_amplifiers_per_turn": 2,
                    "max_scenarios_per_turn": 2,
                },
                "priority_service_promos": {
                    "service_one": {
                        "ordered_fact_refs": ["fact:promo_a", "fact:promo_b"],
                    },
                },
                "promotion_overview": {"ordered_fact_refs": []},
                "scenario_rules": {},
                "cta_contexts": {"service": "plan", "default": "callback"},
            },
        }
    )
    doctors, external_index = _demo_stage51_inputs()[1], _demo_stage51_inputs()[2]
    first = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="service_one",
        today=date(2026, 8, 1),
    )
    assert first.selection is not None
    assert first.selection.selected_refs == ("fact:promo_a",)
    second = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="service_one",
        today=date(2026, 8, 1),
        shown_fact_ids=("promo_a",),
    )
    assert second.selection is not None
    assert "fact:promo_a" not in second.selection.selected_refs
    assert "fact:promo_b" not in second.selection.selected_refs


def test_priority_promo_service_applicability_invalid_at_load() -> None:
    from contracts.response_schema import ResponseSchemaBundle

    with pytest.raises(ValueError, match="marketing_priority_promo_service_applicability_invalid"):
        ResponseSchemaBundle.model_validate(
            {
                "services": {
                    "all_on_4": {
                        "name": "All-on-4",
                        "family": "implantology",
                        "roles": ["protocol"],
                        "active": True,
                        "selection": {"mode": "context"},
                    },
                    "professional_whitening": {
                        "name": "Whitening",
                        "family": "therapy",
                        "roles": ["protocol"],
                        "active": True,
                        "selection": {"mode": "context"},
                    },
                },
                "brands": {"version": 1, "brands": {}},
                "offers": [],
                "facts": {
                    "professional_whitening_discount": {
                        "id": "professional_whitening_discount",
                        "kind": "promo",
                        "catalog_label": "Скидка на профессиональное отбеливание",
                        "text_fact": "Whitening promo.",
                        "render_mode": "strict",
                        "active": True,
                        "allowed_service_ids": ["professional_whitening"],
                    },
                },
                "strategy": {"version": 1, "default_max_options": 3, "rules": []},
                "marketing": {
                    "version": 1,
                    "limits": {
                        "max_marketing_facts_per_turn": 3,
                        "max_amplifiers_per_turn": 2,
                        "max_scenarios_per_turn": 2,
                    },
                    "priority_service_promos": {
                        "all_on_4": {
                            "ordered_fact_refs": ["fact:professional_whitening_discount"],
                        },
                    },
                    "promotion_overview": {"ordered_fact_refs": []},
                    "scenario_rules": {},
                    "cta_contexts": {"default": "callback"},
                },
            }
        )


def test_sanitize_removes_ungrounded_model_promo_percent() -> None:
    from core.sales_fast_authoritative_commerce import sanitize_model_text_for_authoritative_marketing

    cleaned = sanitize_model_text_for_authoritative_marketing(
        "All-on-4 — популярный протокол имплантации. На All-on-4 действует скидка 50%.",
        allowed_amounts=frozenset(),
        allowed_percents=frozenset({"15"}),
    )
    assert "50%" not in cleaned
    assert "All-on-4" in cleaned
    assert "15%" not in cleaned


def test_sanitize_preserves_informational_percent_without_commercial_marker() -> None:
    from core.sales_fast_authoritative_commerce import sanitize_model_text_for_authoritative_marketing

    source_text = "По статистике клиники приживаемость имплантов — 99,8%."
    cleaned = sanitize_model_text_for_authoritative_marketing(
        source_text,
        allowed_amounts=frozenset(),
        allowed_percents=frozenset(),
    )
    assert cleaned == source_text
    assert "99,8%" in cleaned


def test_direct_promotion_text_from_authoritative_facts_only() -> None:
    from core.target_marketing_selector import TargetMarketingSelection
    from contracts.target_response_spec import TargetResponseSpec
    from core.sales_fast_presentation import build_direct_promotion_patient_text
    from core.target_offline_response_assembly import TargetOfflineResponseMaterials
    from core.target_offline_response_package import TargetOfflineResponsePackage
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from core.target_response_materialization_plan import build_target_response_materialization_plan
    from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

    bundle, _, _ = _demo_stage51_inputs()
    fact = bundle.facts["implant_same_day_discount"]
    materials = TargetOfflineResponseMaterials(
        service_id="all_on_4",
        service=bundle.services["all_on_4"],
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=0,
        offers=(),
        doctors=(),
        selected_content_ref=None,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=("fact:implant_same_day_discount",),
            amplifier_refs=(),
            cta_key="plan",
        ),
        commercial_facts=(fact,),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=1,
        amplifier_slots_used=0,
    )
    spec = TargetResponseSpec(
        response_mode="answer",
        service_id="all_on_4",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("content",),
        allow_marketing_facts=True,
    )
    plan = build_target_response_materialization_plan(
        materials, required_components=spec.required_components
    )
    package = TargetOfflineResponsePackage(
        materials=materials,
        plan=plan,
        followup_candidates=(),
        selected_followups=TargetResponseFollowupSelection(
            source="content", content=(), price=()
        ),
        navigation_followups=(),
    )
    bound = TargetSpecBoundOfflineResponsePackage(
        spec=spec,
        package=package,
        selected_cta_key="plan",
    )
    text = build_direct_promotion_patient_text(bound)
    assert "50%" not in text
    assert str(fact.text_fact) in text


def _run_presentation_result(
    *,
    envelope_json: str,
    patient_text: str,
    user_message: str = "тест",
    marketing_scenarios: tuple[str, ...] | None = None,
    today: date = date(2026, 8, 1),
    context_override: object | None = None,
    shown_fact_ids: tuple[str, ...] = (),
    shown_amplifier_refs: tuple[str, ...] = (),
    shown_consultation_value_refs: tuple[str, ...] = (),
    last_rendered_promo_fact_id: str | None = None,
) -> object:
    from dataclasses import replace

    from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
    from core.one_call_presentation_pass import build_one_call_presentation_result
    from core.sales_fast_strict_evidence import (
        effective_scope_from_semantic_frame,
        exact_sales_resolution_from_semantic_frame,
        resolve_sales_fast_bound_package,
    )
    from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
    from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
    from core.target_runtime_client_context import load_target_runtime_client_context
    from core.target_runtime_strategy import resolve_target_runtime_strategy_context
    from core.target_strategy_context import strategy_match_from_effective_scope

    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    governed_ui = governed_ui_authority_from_resolution(
        ExactSalesResolution(None, None, None, None, None, unknown, unknown, unknown, unknown, unknown)
    )
    context = context_override or load_target_runtime_client_context("demo")
    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed_ui,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    turn_frame = build_turn_frame_from_semantic_frame(
        semantic=semantic,
        user_message=user_message,
        bundle=context.bundle,
    )
    if marketing_scenarios is not None:
        turn_frame = turn_frame.model_copy(
            update={"marketing_scenarios": list(marketing_scenarios)}
        )
    effective_scope = effective_scope_from_semantic_frame(
        semantic,
        current_ui_action=None,
        current_ui_stage_action=None,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=resolve_target_runtime_strategy_context(
            context.bundle,
            service_id=turn_frame.service_id,
        ).family,
    )
    bound = resolve_sales_fast_bound_package(
        turn_frame=turn_frame,
        semantic=semantic,
        bundle=context.bundle,
        doctor_catalog=context.doctor_catalog,
        external_index=context.external_index,
        consultation_values=context.consultation_values,
        strategy_context=strategy_context,
        effective_scope=effective_scope,
        allowed_topics=context.allowed_topics,
        today=today,
        md_root=context.md_root,
        client_id="demo",
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
    )
    resolution = exact_sales_resolution_from_semantic_frame(semantic)
    return build_one_call_presentation_result(
        bound_package=bound,
        context=context,
        turn_frame=turn_frame,
        semantic=semantic,
        patient_text=patient_text,
        user_message=user_message,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
        resolution=resolution,
        strategy_context=strategy_context,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        last_rendered_promo_fact_id=last_rendered_promo_fact_id,
        today=today,
    )


def test_presentation_general_promotion_verifies_all_three_overview_facts() -> None:
    from core.doctor_schema_loader import load_doctor_catalog
    from core.target_composer_request import materialize_target_composer_request
    from core.target_scoped_response_evidence import build_target_scoped_response_evidence
    from tests.test_target_scoped_response_evidence import _demo_general_promotion_bound

    data = load_target_client_data("demo")
    bundle = data.bundle
    expected_ids = (
        "implant_same_day_discount",
        "professional_whitening_discount",
        "free_implant_consult",
    )
    expected_refs = tuple(f"fact:{fact_id}" for fact_id in expected_ids)
    expected_texts = tuple(str(bundle.facts[fact_id].text_fact) for fact_id in expected_ids)
    envelope = answer_envelope(
        "Расскажу об актуальных акциях клиники.",
        commercial_intent="promotion",
        promotion_scope="general",
        service_id=None,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Расскажу об актуальных акциях клиники.",
        user_message="Какие акции у вас есть?",
    )
    assert result.status == "ok"
    assert result.verified_for_session is not None
    for text in expected_texts:
        assert text in result.final_patient_text
    assert result.rendered_promo_fact_ids == expected_ids
    assert result.pending_session_delta is not None
    assert result.pending_session_delta.shown_fact_ids == expected_ids
    used_refs = result.verified_for_session.used_content_refs
    assert all(
        not ref.startswith(("fact:", "offer:", "doctor:")) for ref in used_refs
    )
    bound = _demo_general_promotion_bound()
    scoped = build_target_scoped_response_evidence(bound, md_root=_DEMO_MD_ROOT)
    assert scoped.commercial_fact_ids == expected_ids
    assert scoped.covered_fact_ids == expected_ids
    composer = materialize_target_composer_request(
        bound,
        bundle,
        load_doctor_catalog(client_pack_root("demo") / "doctor_catalog.json"),
        (),
        user_message="Какие акции у вас есть?",
        md_root=_DEMO_MD_ROOT,
        client_id="demo",
    )
    commercial_blocks = [
        block for block in composer.evidence_blocks if block.kind == "commercial_fact"
    ]
    assert len(commercial_blocks) == 3
    assert tuple(block.ref for block in commercial_blocks) == expected_refs
    for block, fact_id in zip(commercial_blocks, expected_ids, strict=True):
        assert block.text == str(bundle.facts[fact_id].text_fact)


def test_f6_sanitize_without_selected_promo() -> None:
    from core.sales_fast_authoritative_commerce import sanitize_model_text_for_authoritative_marketing

    cleaned = sanitize_model_text_for_authoritative_marketing(
        "Сейчас действует скидка 50%.",
        allowed_amounts=frozenset(),
        allowed_percents=frozenset(),
    )
    assert "50%" not in cleaned


def test_presentation_automatic_promo_strips_model_claim() -> None:
    envelope = answer_envelope(
        "All-on-4 — популярный протокол. На All-on-4 действует скидка 50%.",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="All-on-4 — популярный протокол. На All-on-4 действует скидка 50%.",
    )
    assert result.status == "ok"
    assert "50%" not in result.final_patient_text
    assert "15%" in result.final_patient_text
    assert result.rendered_promo_fact_ids == ("implant_same_day_discount",)
    assert result.pending_session_delta is not None
    assert "implant_same_day_discount" in result.pending_session_delta.shown_fact_ids
    assert result.pending_session_delta.last_rendered_promo_fact_id == "implant_same_day_discount"


def test_presentation_no_promo_strips_model_claim() -> None:
    envelope = answer_envelope("Общий вопрос о клинике.", service_id=None)
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Сейчас действует скидка 50%.",
    )
    assert result.status == "ok"
    assert "50%" not in result.final_patient_text
    assert result.rendered_promo_fact_ids == ()
    assert result.pending_session_delta is None or (
        result.pending_session_delta.last_rendered_promo_fact_id is None
    )


def test_presentation_amplifier_cannot_legalize_model_discount() -> None:
    envelope = answer_envelope(
        "Стоимость All-on-4 на нижнюю челюсть.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        scenario="cost",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="На All-on-4 действует скидка 13%.",
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        marketing_scenarios=("cost",),
    )
    assert result.status == "ok"
    assert "скидка 13%" not in result.final_patient_text.lower()
    assert "15%" in result.final_patient_text


def test_presentation_direct_promotion_cost_scenario_promo_only() -> None:
    envelope = answer_envelope(
        "Рассрочка до 12 месяцев доступна.",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        scenario="cost",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Рассрочка до 12 месяцев доступна.",
        marketing_scenarios=("cost",),
    )
    assert result.status == "ok"
    assert "рассроч" not in result.final_patient_text.lower()
    assert "installment_12" not in str(result.rendered_marketing_fact_ids)
    assert result.rendered_promo_fact_ids == ("implant_same_day_discount",)
    commerce = result.authoritative_commerce
    assert commerce is None or commerce.widget_offer_payload is None


def test_presentation_direct_promotion_no_eligible_fail_closed() -> None:
    envelope = answer_envelope(
        "Какие акции на классическую имплантацию?",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="classic",
        extent="one_tooth",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Какие акции на классическую имплантацию?",
        user_message="Какие акции на классическую имплантацию?",
    )
    assert result.status == "fail_closed"
    assert result.reason_code == "promotion_no_eligible_facts"
    assert result.final_patient_text.strip()
    assert result.rendered_promo_fact_ids == ()
    assert result.pending_session_delta is None


def test_presentation_preserves_informational_evidence_percent() -> None:
    survivability_text = "По статистике клиники приживаемость имплантов — 99,8%."
    envelope = answer_envelope(
        survivability_text,
        service_id="classic",
        extent="one_tooth",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=survivability_text,
        user_message="Какая приживаемость имплантов?",
    )
    assert result.status == "ok"
    assert "99,8%" in result.final_patient_text
    assert result.rendered_promo_fact_ids == ()
    assert result.pending_session_delta is None or (
        result.pending_session_delta.last_rendered_promo_fact_id is None
    )
    commerce = result.authoritative_commerce
    assert commerce is None or commerce.widget_offer_payload is None
