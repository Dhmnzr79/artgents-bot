"""Owner-approved generic price acceptance (Stage 3C v3)."""

from __future__ import annotations

import pytest

from evals.v5.one_call_stage3c_generic_price_acceptance import (
    GENERIC_PRICE_ACCEPTANCE_V3,
    GenericPriceAcceptanceCase,
)
from core.sales_fast_authoritative_commerce import build_authoritative_commerce_result
from contracts.effective_scope import EffectiveScope
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from core.target_client_data import load_target_client_data
from core.target_strategy_context import strategy_match_from_effective_scope
from types import SimpleNamespace


def _authority() -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(authority="exact_turn", provenance="test")


def _resolution() -> ExactSalesResolution:
    auth = _authority()
    return ExactSalesResolution(
        service_id="classic",
        aspect="price",
        extent="one_tooth",
        jaw=None,
        stage=None,
        service_id_authority=auth,
        aspect_authority=auth,
        extent_authority=auth,
        jaw_authority=auth,
        stage_authority=auth,
    )


def _bound_package(offers: tuple, *, brand: str | None = None) -> object:
    materials = SimpleNamespace(
        offers=offers,
        consultation_close=None,
        selected_brand_id=brand,
        commercial_facts=(),
        marketing_selection=SimpleNamespace(selected_refs=()),
        max_options=3,
        service_id="classic",
    )
    return SimpleNamespace(package=SimpleNamespace(materials=materials))


@pytest.mark.parametrize("case", GENERIC_PRICE_ACCEPTANCE_V3, ids=lambda c: c.case_id)
def test_generic_price_acceptance_v3(case: GenericPriceAcceptanceCase) -> None:
    bundle = load_target_client_data("demo").bundle
    if case.explicit_brand:
        offers = tuple(
            offer
            for offer in bundle.offers
            if offer.service_id == "classic" and "one_tooth" in offer.applies_to_extents
        )
        brand = case.explicit_brand
        if brand == "implantium":
            brand = "implantium"
        elif brand == "impro":
            brand = "impro"
        bound = _bound_package(offers, brand=brand)
    else:
        offers = tuple(
            offer
            for offer in bundle.offers
            if offer.service_id == "classic" and "one_tooth" in offer.applies_to_extents
        )
        bound = _bound_package(offers)
    strategy_context = strategy_match_from_effective_scope(
        EffectiveScope(extent="one_tooth"),
        service_family="implantology",
    )
    result = build_authoritative_commerce_result(
        bound_package=bound,
        resolution=_resolution(),
        bundle=bundle,
        strategy_context=strategy_context,
    )
    text = (result.patient_price_block or "").lower()
    for token in case.critical_required_all:
        assert token.lower() in text
    normalized = text.replace("\u00a0", "").replace(" ", "")
    for token in case.forbidden_price_tokens:
        assert token not in normalized
    if case.expected_mode:
        assert result.presentation_mode == case.expected_mode
    if case.featured_offer_id:
        assert result.featured_offer_id == case.featured_offer_id
    if case.required_offer_ids:
        widget_ids = [
            str(row.get("offer_id"))
            for row in (result.widget_offer_payload or {}).get("offers", [])
        ]
        if result.presentation_mode == "exact_offer":
            assert result.selected_exact_offer is not None
            assert result.selected_exact_offer.offer_id in case.required_offer_ids
        else:
            assert set(widget_ids) == set(case.required_offer_ids)
