from __future__ import annotations

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from core.sales_fast_strict_evidence import build_pre_flash_prompt_hints
from core.sales_fast_turn_frame import build_provisional_turn_frame
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from core.target_client_data import load_target_client_data


def test_pre_flash_hints_exclude_authoritative_service_id() -> None:
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        "overview",
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    _, hints = build_pre_flash_prompt_hints(
        resolution=resolution,
        catalog_service_hint="имплантация",
        session_service_hint="classic",
    )
    assert hints["catalog_service_hint"] == "имплантация"
    assert hints["session_service_hint"] == "classic"
    assert "service_id" not in hints
    assert "amount" not in hints


def test_pre_flash_prompt_has_no_commercial_strict_facts_block() -> None:
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        "overview",
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=resolution,
        current_strict_facts=(),
        sales_context={"catalog_service_hint": "имплантация"},
        user_message="Как обеспечивается стерильность?",
    )
    assert "PRE_MODEL_HINTS" in suffix
    assert "CURRENT_STRICT_FACTS" not in suffix
    assert "EXACT_SALES_RESOLUTION" not in suffix
    assert "100 000" not in suffix


def test_microfact_turn_frame_stays_neutral() -> None:
    bundle = load_target_client_data("demo").bundle
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        "overview",
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    frame = build_provisional_turn_frame(
        resolution=resolution,
        user_message="Как обеспечивается стерильность?",
        client_id="demo",
        bundle=bundle,
    )
    assert frame.service_id is None
    assert frame.topic is None
