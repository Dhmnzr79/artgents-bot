"""Fake production parity tests for arch-compare boundary capture."""

from __future__ import annotations

from core.target_runtime_client_context import load_target_runtime_client_context
from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID
from evals.v5.arch_compare.arch_compare_production_parity import (
    ARCH_COMPARE_CAPTURE_CALL_GRAPH,
    WIDGET_PRODUCTION_CALL_GRAPH,
    call_graph_comparison_markdown,
    capture_arch_compare_price_turn,
    scenario_turn_or_raise,
)
from evals.v5.arch_compare.arch_compare_prompt_build import resolve_precomposer_for_turn
from tests.test_one_call_exact_1b_single_offline import (
    _count_amount_token,
    _normalize_visible_text,
)
from tests.test_sales_one_plus_turn import answer_envelope

_NOBEL_PRICE = (
    "Стоимость All-on-4 на Nobel Biocare — 428 000 ₽ за одну челюсть; "
    "КТ и костная пластика по показаниям — отдельно."
)
_MULTI_OFFER_IDS = frozenset(
    {
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    }
)
_REBUILD_SHA = "2364bc4afc2f23539d467a43ffd7e428981b9047"


def _precomposer_for_turn(*, scenario_id: str, turn_id: str):
    scenario, turn = scenario_turn_or_raise(scenario_id=scenario_id, turn_id=turn_id)
    ctx = load_target_runtime_client_context(CLIENT_ID)
    return scenario, turn, resolve_precomposer_for_turn(ctx, turn)


def test_call_graphs_document_shared_production_functions() -> None:
    widget_symbols = {step.symbol for step in WIDGET_PRODUCTION_CALL_GRAPH}
    arch_symbols = {step.symbol for step in ARCH_COMPARE_CAPTURE_CALL_GRAPH}
    assert "bind_semantic_frame" in widget_symbols
    assert "bind_semantic_frame" in arch_symbols
    assert "build_one_call_presentation_result" in widget_symbols
    assert "build_one_call_presentation_result" in arch_symbols
    assert "capture_provider_turn_boundary" in arch_symbols
    assert "run_sales_fast_widget_turn" in widget_symbols
    doc = call_graph_comparison_markdown()
    assert "resolve_sales_fast_bound_package" in doc


def test_single_nobel_model_price_text_via_arch_compare_boundary() -> None:
    scenario, turn, precomposer = _precomposer_for_turn(scenario_id="BRD-01", turn_id="BRD-01_t1")
    patient = "Nobel Biocare — премиальный вариант All-on-4."
    envelope_json = answer_envelope(
        patient,
        commercial_intent="price",
        service_id="all_on_4",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        price_text=_NOBEL_PRICE,
    )
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=envelope_json,
        patient_text=patient,
    )
    assert precomposer.availability == "selected"
    assert precomposer.offer is not None
    assert precomposer.offer.offer_id == "all_on_4.jaw.nobel"
    assert precomposer.offer.brand_id == "nobel_biocare"
    assert precomposer.offer.service_id == "all_on_4"
    assert capture.resolved_price_owner == "model_price_text"
    assert capture.resolved_selected_offer_id == "all_on_4.jaw.nobel"
    assert capture.resolved_price_text is not None
    assert "428" in capture.resolved_price_text
    assert "челюсть" in capture.resolved_price_text.casefold()
    assert capture.resolved_price_owner != "canonical_fallback"
    assert _count_amount_token(capture.visible_answer, "428000") == 1
    assert patient in capture.visible_answer


def test_single_nobel_canonical_fallback_via_arch_compare_boundary() -> None:
    scenario, turn, precomposer = _precomposer_for_turn(scenario_id="BRD-01", turn_id="BRD-01_t1")
    patient = "Nobel Biocare — премиальный вариант All-on-4."
    envelope_json = answer_envelope(
        patient,
        commercial_intent="price",
        service_id="all_on_4",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        price_text=None,
    )
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=envelope_json,
        patient_text=patient,
    )
    assert precomposer.availability == "selected"
    assert precomposer.offer is not None
    assert precomposer.offer.offer_id == "all_on_4.jaw.nobel"
    assert capture.resolved_price_owner == "canonical_fallback"
    assert capture.resolved_selected_offer_id == "all_on_4.jaw.nobel"
    assert capture.resolved_price_diagnostic == "missing"
    assert capture.resolved_price_text is not None
    assert "428" in capture.resolved_price_text
    assert "челюсть" in capture.resolved_price_text.casefold()
    assert capture.resolved_price_owner != "model_price_text"
    assert _count_amount_token(capture.visible_answer, "428000") == 1
    assert patient in capture.visible_answer


def test_multi_all_on_4_via_arch_compare_boundary() -> None:
    scenario, turn, precomposer = _precomposer_for_turn(scenario_id="PRC-01", turn_id="PRC-01_t1")
    patient = "All-on-4 — полное восстановление челюсти на 4 имплантах."
    envelope_json = answer_envelope(
        patient,
        commercial_intent="price",
        service_id="all_on_4",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        price_text=None,
    )
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=envelope_json,
        patient_text=patient,
    )
    assert precomposer.availability == "multiple"
    assert len(precomposer.offers) == 3
    assert {offer.offer_id for offer in precomposer.offers} == _MULTI_OFFER_IDS
    assert capture.resolved_price_owner == "canonical_multi"
    assert frozenset(capture.resolved_multi_offer_ids) == _MULTI_OFFER_IDS
    assert capture.resolved_price_text is not None
    resolved = capture.resolved_price_text
    assert "318" in resolved
    assert "368" in resolved
    assert "428" in resolved
    assert "Implantium" in resolved
    assert "Impro" in resolved
    assert "Nobel Biocare" in resolved
    assert "челюсть" in resolved.casefold()
    normalized = _normalize_visible_text(capture.visible_answer)
    assert "318000" in normalized
    assert "368000" in normalized
    assert "428000" in normalized
    assert "челюсть" in normalized
