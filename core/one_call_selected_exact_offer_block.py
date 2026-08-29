"""Dynamic SELECTED_EXACT_OFFER block for Composer (CP-EXACT-1B-SINGLE)."""

from __future__ import annotations

import json

from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult
from contracts.response_schema import ResponseSchemaBundle, TargetOffer

SELECTED_EXACT_OFFER_HEADER = "=== SELECTED_EXACT_OFFER ==="


def _brand_label(bundle: ResponseSchemaBundle, brand_id: str | None) -> str | None:
    if not brand_id:
        return None
    brand = bundle.brands.brands.get(brand_id)
    if brand is None:
        return None
    return brand.canonical_name


def _option_label(bundle: ResponseSchemaBundle, offer: TargetOffer) -> str | None:
    if offer.option_id is None:
        return None
    service = bundle.services.get(offer.service_id)
    if service is None:
        return None
    for option in service.options:
        if option.option_id == offer.option_id:
            return option.label
    return offer.option_id


def build_selected_exact_offer_block(
    *,
    bundle: ResponseSchemaBundle,
    selection: PrecomposerSelectedOfferResult,
) -> str:
    if selection.availability != "selected" or selection.offer is None:
        payload = {
            "availability": "none",
            "price_text_allowed": False,
        }
        return f"{SELECTED_EXACT_OFFER_HEADER}\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"

    offer = selection.offer
    price = offer.price
    payload = {
        "availability": "selected",
        "offer_id": offer.offer_id,
        "service_id": offer.service_id,
        "brand_label": _brand_label(bundle, offer.brand_id),
        "option_label": _option_label(bundle, offer),
        "price_mode": price.mode,
        "amount": int(price.amount) if price.amount is not None else None,
        "currency": price.currency,
        "billing_unit": price.billing_unit,
        "package_label": str(offer.package.label or "").strip() or None,
        "price_text_allowed": True,
    }
    return f"{SELECTED_EXACT_OFFER_HEADER}\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
