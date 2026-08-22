"""Offline Nikadent price authority: MD isolation and structured price paths."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundTerminalResponse
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import dumps_production_envelope, parse_production_envelope_json
from core.one_call_presentation_pass import build_one_call_presentation_result
from core.sales_fast_strict_evidence import (
    effective_scope_from_semantic_frame,
    exact_sales_resolution_from_semantic_frame,
    resolve_sales_fast_bound_package,
)
from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_client_data import load_target_client_data
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_runtime_client_context import load_target_runtime_client_context
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_strategy_context import strategy_match_from_effective_scope
from tests.test_sales_one_plus_turn import answer_envelope

_NIKADENT_MD_ROOT = Path(__file__).resolve().parents[1] / "clients" / "nikadent" / "md"
_DEMO_MD_ROOT = Path(__file__).resolve().parents[1] / "clients" / "demo" / "md"

_COMMERCIAL_CURRENCY_RE = re.compile(
    r"\d[\d\s]*\s*(?:₽|руб(?:лей)?|р\.)",
    re.IGNORECASE | re.UNICODE,
)

_NIKADENT_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot.from_bundle(
    load_target_client_data("nikadent").bundle
)


def _assert_no_commercial_currency_in_md(md_root: Path) -> None:
    offenders: list[str] = []
    for path in sorted(md_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if _COMMERCIAL_CURRENCY_RE.search(line):
                offenders.append(f"{path.relative_to(md_root)}:{line_no}: {line.strip()}")
    assert offenders == []


def test_nikadent_md_has_no_commercial_currency_tokens() -> None:
    _assert_no_commercial_currency_in_md(_NIKADENT_MD_ROOT)


def test_demo_md_has_no_commercial_currency_tokens() -> None:
    _assert_no_commercial_currency_in_md(_DEMO_MD_ROOT)


def _nikadent_presentation(
    *,
    user_message: str,
    service_id: str,
    commercial_intent: str,
    patient_text: str = "Короткий ответ о услуге.",
    today: date = date(2026, 8, 1),
) -> object:
    data = load_target_client_data("nikadent")
    catalog = ActiveServiceCatalogSnapshot.from_bundle(data.bundle)
    ref_catalog = ServiceReferenceCatalogSnapshot.from_bundle(data.bundle)
    context = load_target_runtime_client_context("nikadent")
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    governed = governed_ui_authority_from_resolution(
        ExactSalesResolution(None, None, None, None, None, unknown, unknown, unknown, unknown, unknown)
    )
    envelope_json = answer_envelope(
        patient_text,
        commercial_intent=commercial_intent,
        promotion_scope="none",
        scenario="none",
        service_id=service_id,
        service_reference_status="resolved",
        requested_service_id=service_id,
    )
    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=catalog,
        service_reference_catalog=ref_catalog,
        commercial_fact_catalog=_NIKADENT_COMMERCIAL_CATALOG,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed,
        active_service_catalog=catalog,
        service_reference_catalog=ref_catalog,
    )
    turn_frame = build_turn_frame_from_semantic_frame(
        semantic=semantic,
        user_message=user_message,
        bundle=data.bundle,
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
        client_id="nikadent",
    )
    if isinstance(bound, TargetTurnFrameBoundTerminalResponse):
        pytest.fail(f"unexpected terminal dispatch: {bound.dispatch.terminal_mode}")
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
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        last_rendered_promo_fact_id=None,
        today=today,
    )


@pytest.mark.parametrize(
    ("user_message", "service_id"),
    [
        ("Сколько стоит металлокерамическая коронка?", "metal_ceramic_crowns"),
        ("Сколько стоит циркониевая коронка?", "zirconia_crowns"),
    ],
)
def test_nikadent_crown_price_uses_family_context_not_exact_card(
    user_message: str,
    service_id: str,
) -> None:
    result = _nikadent_presentation(
        user_message=user_message,
        service_id=service_id,
        commercial_intent="price",
    )
    assert result.status == "ok"
    assert "22" in result.final_patient_text and "000" in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER in result.final_patient_text
    assert result.authoritative_commerce is None


def test_nikadent_fixed_bridge_price_exact_offer_with_unit() -> None:
    result = _nikadent_presentation(
        user_message="Сколько стоит мост?",
        service_id="fixed_bridge",
        commercial_intent="price",
    )
    assert result.status == "ok"
    assert "10" in result.final_patient_text and "000" in result.final_patient_text
    assert "единиц" in result.final_patient_text.lower()
    commerce = result.authoritative_commerce
    assert commerce is not None
    assert commerce.widget_offer_payload is not None
    assert commerce.widget_offer_payload.get("offer_id") == "fixed_bridge.default"
    assert commerce.presentation_mode == "exact_offer"


def test_nikadent_core_inlay_price_exact_offer_per_tooth() -> None:
    result = _nikadent_presentation(
        user_message="Сколько стоит культевая вкладка?",
        service_id="core_inlay",
        commercial_intent="price",
    )
    assert result.status == "ok"
    assert "7" in result.final_patient_text and "000" in result.final_patient_text
    assert "зуб" in result.final_patient_text.lower()
    commerce = result.authoritative_commerce
    assert commerce is not None
    assert commerce.widget_offer_payload is not None
    assert commerce.widget_offer_payload.get("offer_id") == "core_inlay.default"
    assert commerce.presentation_mode == "exact_offer"


def test_nikadent_all_on_4_price_family_context_not_exact_protocol_card() -> None:
    result = _nikadent_presentation(
        user_message="Сколько стоит All-on-4?",
        service_id="all_on_4",
        commercial_intent="price",
    )
    assert result.status == "ok"
    assert "35" in result.final_patient_text and "000" in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER in result.final_patient_text
    assert result.authoritative_commerce is None


@pytest.mark.parametrize(
    ("user_message", "service_id"),
    [
        ("Что такое металлокерамическая коронка?", "metal_ceramic_crowns"),
        ("Что такое мостовидный протез?", "fixed_bridge"),
        ("Что такое культевая вкладка?", "core_inlay"),
        ("Что такое All-on-4?", "all_on_4"),
    ],
)
def test_nikadent_neutral_info_intent_has_no_price_surface(
    user_message: str,
    service_id: str,
) -> None:
    result = _nikadent_presentation(
        user_message=user_message,
        service_id=service_id,
        commercial_intent="none",
    )
    assert result.status == "ok"
    assert "₽" not in result.final_patient_text
    assert not re.search(r"\d[\d\s]{2,}\s*000", result.final_patient_text)
    assert result.authoritative_commerce is None or result.authoritative_commerce.widget_offer_payload is None


def test_nikadent_prosthodontics_services_map_to_prosthetics_topic() -> None:
    data = load_target_client_data("nikadent")
    catalog = ActiveServiceCatalogSnapshot.from_bundle(data.bundle)
    ref_catalog = ServiceReferenceCatalogSnapshot.from_bundle(data.bundle)
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    governed = governed_ui_authority_from_resolution(
        ExactSalesResolution(None, None, None, None, None, unknown, unknown, unknown, unknown, unknown)
    )
    for service_id in ("metal_ceramic_crowns", "fixed_bridge", "core_inlay"):
        envelope = parse_production_envelope_json(
            answer_envelope(
                "тест",
                service_id=service_id,
                service_reference_status="resolved",
                requested_service_id=service_id,
            ),
            active_service_catalog=catalog,
            service_reference_catalog=ref_catalog,
            commercial_fact_catalog=_NIKADENT_COMMERCIAL_CATALOG,
        )
        semantic = bind_semantic_frame(
            envelope=envelope,
            governed_ui=governed,
            active_service_catalog=catalog,
            service_reference_catalog=ref_catalog,
        )
        frame = build_turn_frame_from_semantic_frame(
            semantic=semantic,
            user_message="тест",
            bundle=data.bundle,
        )
        assert frame.topic == "prosthetics"
