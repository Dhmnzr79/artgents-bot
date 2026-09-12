from __future__ import annotations

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallEnvelope
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import dumps_production_envelope, production_envelope_template
from core.sales_fast_authoritative_commerce import (
    AuthoritativeCommerceResult,
    gate_commerce_result_by_intent,
)
from core.sales_fast_presentation import materialize_sales_fast_answer_payload
from core.sales_fast_strict_evidence import (
    assemble_sales_fast_bound_package,
    effective_scope_from_semantic_frame,
    exact_sales_resolution_from_semantic_frame,
)
from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.target_client_data import load_target_client_data
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_runtime_client_context import load_target_runtime_client_context, runtime_today
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
from core.target_strategy_context import strategy_match_from_effective_scope
from session import mem_reset

_DEMO_CATALOG = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
_DEMO_REF_CATALOG = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)


def _sample_commerce() -> AuthoritativeCommerceResult:
    return AuthoritativeCommerceResult(
        service_id="classic",
        presentation_mode="exact_offer",
        entry_price_amount=120000,
        entry_price_text=None,
        ordered_offers=(),
        featured_offer_id=None,
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=frozenset({120000}),
        patient_price_block="Стоимость — 120 000 ₽.",
        widget_offer_payload={"mode": "exact_offer", "amount": 120000},
    )


def _clarify_envelope(
    text: str,
    *,
    commercial_intent: str = "price",
) -> str:
    return dumps_production_envelope(
        route="CLARIFY",
        patient_text=text,
        clarify_axis="extent",
        clarify_service_options=None,
        commercial_intent=commercial_intent,
        service_id="classic",
        extent=None,
        scenario="cost",
    )


class _Backend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self.output


def _run_clarify_widget(*, commercial_intent: str) -> tuple[object, _Backend]:
    mem_reset("clarify-widget")
    backend = _Backend(
        _clarify_envelope(
            "Уточните, один зуб или несколько?",
            commercial_intent=commercial_intent,
        )
    )
    outcome = run_sales_fast_widget_turn(
        client_id="demo",
        sid="clarify-widget",
        user_message="Сколько стоит имплант?",
        backend=backend,
    )
    return outcome, backend


def test_commercial_intent_none_suppresses_price_surface() -> None:
    gated = gate_commerce_result_by_intent(_sample_commerce(), commercial_intent="none")
    assert gated.presentation_mode == "none"
    assert gated.widget_offer_payload is None
    assert gated.authoritative_amounts == frozenset()


def test_commercial_intent_price_preserves_price_surface() -> None:
    commerce = _sample_commerce()
    gated = gate_commerce_result_by_intent(commerce, commercial_intent="price")
    assert gated.presentation_mode == "exact_offer"
    assert gated.widget_offer_payload == commerce.widget_offer_payload


def test_commercial_intent_payment_does_not_open_price_surface() -> None:
    gated = gate_commerce_result_by_intent(_sample_commerce(), commercial_intent="payment")
    assert gated.presentation_mode == "none"
    assert gated.patient_price_block is None


def test_commercial_intent_included_does_not_open_price_surface() -> None:
    gated = gate_commerce_result_by_intent(_sample_commerce(), commercial_intent="included")
    assert gated.presentation_mode == "none"
    assert gated.widget_offer_payload is None


@pytest.mark.parametrize("commercial_intent", ("price", "payment", "included"))
def test_clarify_widget_path_has_no_commerce_surface(commercial_intent: str) -> None:
    outcome, backend = _run_clarify_widget(commercial_intent=commercial_intent)
    payload = outcome.widget.payload
    assert outcome.model_route == "clarify"
    assert backend.call_count == 1
    assert payload.get("offer") is None
    assert "120 000" not in str(payload.get("answer") or "")
    assert "76200" not in str(payload.get("answer") or "").replace(" ", "")


def test_presentation_fail_closed_blocks_clarify_commerce_even_if_intent_price() -> None:
    clarify_envelope = OneCallEnvelope.model_validate(
        {
            **production_envelope_template(),
            "route": "CLARIFY",
            "patient_text": "Уточните объём.",
            "clarify_axis": "extent",
            "commercial_intent": "price",
            "service_id": "classic",
            "extent": None,
            "scenario": "cost",
        }
    )
    answer_envelope = OneCallEnvelope.model_validate(
        {
            **production_envelope_template(),
            "route": "ANSWER",
            "patient_text": "Стоимость зависит от объёма.",
            "commercial_intent": "price",
            "service_id": "classic",
            "extent": "one_tooth",
            "scenario": "cost",
        }
    )
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    governed_ui = governed_ui_authority_from_resolution(
        ExactSalesResolution(None, None, None, None, None, unknown, unknown, unknown, unknown, unknown)
    )
    clarify_semantic = bind_semantic_frame(
        envelope=clarify_envelope,
        governed_ui=governed_ui,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    answer_semantic = bind_semantic_frame(
        envelope=answer_envelope,
        governed_ui=governed_ui,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    context = load_target_runtime_client_context("demo")
    user_message = "Сколько стоит классический имплант за один зуб?"
    clarify_turn_frame = build_turn_frame_from_semantic_frame(
        semantic=clarify_semantic,
        user_message=user_message,
        bundle=context.bundle,
    )
    answer_turn_frame = build_turn_frame_from_semantic_frame(
        semantic=answer_semantic,
        user_message=user_message,
        bundle=context.bundle,
    )
    assert clarify_turn_frame.needs_clarification is True
    effective_scope = effective_scope_from_semantic_frame(
        answer_semantic,
        current_ui_action=None,
        current_ui_stage_action=None,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=resolve_target_runtime_strategy_context(
            context.bundle,
            service_id=answer_turn_frame.service_id,
        ).family,
    )
    bound = assemble_sales_fast_bound_package(
        turn_frame=answer_turn_frame,
        bundle=context.bundle,
        doctor_catalog=context.doctor_catalog,
        external_index=context.external_index,
        consultation_values=context.consultation_values,
        strategy_context=strategy_context,
        effective_scope=effective_scope,
        allowed_topics=context.allowed_topics,
        today=runtime_today(),
        md_root=context.md_root,
        client_id="demo",
    )
    assert isinstance(bound, TargetSpecBoundOfflineResponsePackage)
    commerce_resolution = exact_sales_resolution_from_semantic_frame(answer_semantic)
    widget = materialize_sales_fast_answer_payload(
        bound_package=bound,
        context=context,
        turn_frame=clarify_turn_frame,
        patient_text=clarify_envelope.patient_text or "",
        user_message=user_message,
        sid="clarify-presentation",
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
        resolution=commerce_resolution,
        strategy_context=strategy_context,
        commercial_intent="price",
    )
    assert widget.payload.get("offer") is None
    assert "76200" not in str(widget.payload.get("answer") or "").replace(" ", "")
