"""Canonical multi-offer price block formatter (CP-EXACT-1B-MULTI-V1)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetService
from core.resolve_precomposer_selected_offer import order_precomposer_offers_neutral
from core.sales_fast_authoritative_commerce import _offer_amount_only


class MultiOfferPriceBlockError(ValueError):
    """Typed formatter failure for an unsafe multi-offer set."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MultiOfferPriceBlockResult:
    block: str | None
    diagnostic: str | None
    offer_ids: tuple[str, ...] = ()


def _titlecase_service_alias(alias: str) -> str:
    parts = alias.split("-")
    if not parts:
        return alias
    first = parts[0]
    titled_first = first[:1].upper() + first[1:] if first else first
    return "-".join([titled_first, *parts[1:]])


def _patient_facing_cost_label(service: TargetService) -> str:
    name = str(service.name).strip()
    for alias in service.aliases:
        alias_text = str(alias).strip()
        if not alias_text:
            continue
        if alias_text.casefold() in name.casefold():
            return _titlecase_service_alias(alias_text)
    return name


def _offer_row_label(bundle: ResponseSchemaBundle, offer: TargetOffer) -> str | None:
    if offer.brand_id:
        brand = bundle.brands.brands.get(offer.brand_id)
        if brand is not None and str(brand.canonical_name).strip():
            return str(brand.canonical_name).strip()
    if offer.option_id:
        service = bundle.services.get(offer.service_id)
        if service is not None:
            for option in service.options:
                if option.option_id == offer.option_id:
                    label = str(option.name).strip()
                    if label:
                        return label
    return None


def _shared_package_footer(offers: tuple[TargetOffer, ...]) -> str | None:
    if not offers:
        return None
    billing_units = {str(offer.price.billing_unit or "").strip() for offer in offers}
    package_labels = {str(offer.package.label or "").strip() for offer in offers}
    if len(billing_units) != 1 or len(package_labels) != 1:
        return None
    package_label = next(iter(package_labels))
    if not package_label:
        return None
    return f"Условия для всех вариантов: {package_label}"


def _offer_line(bundle: ResponseSchemaBundle, offer: TargetOffer, *, shared_footer: bool) -> str:
    label = _offer_row_label(bundle, offer)
    if not label:
        raise MultiOfferPriceBlockError("multi_offer_malformed")
    amount_text = _offer_amount_only(offer)
    if not amount_text:
        raise MultiOfferPriceBlockError("multi_offer_malformed")
    if shared_footer:
        return f"- {label} — {amount_text}"
    package_label = str(offer.package.label or "").strip()
    if not package_label:
        raise MultiOfferPriceBlockError("multi_offer_malformed")
    return f"- {label} — {amount_text}; {package_label}"


def build_canonical_multi_offer_price_block(
    *,
    bundle: ResponseSchemaBundle,
    selection: PrecomposerSelectedOfferResult,
) -> MultiOfferPriceBlockResult:
    if selection.availability != "multiple":
        return MultiOfferPriceBlockResult(block=None, diagnostic="not_multiple")
    raw_offers = selection.offers
    if not (2 <= len(raw_offers) <= 3):
        return MultiOfferPriceBlockResult(
            block=None,
            diagnostic="multi_offer_too_many",
            offer_ids=tuple(offer.offer_id for offer in raw_offers),
        )
    service_id = selection.service_id or raw_offers[0].service_id
    offers = order_precomposer_offers_neutral(
        raw_offers,
        bundle=bundle,
        service_id=service_id,
    )
    service = bundle.services.get(service_id)
    if service is None:
        return MultiOfferPriceBlockResult(
            block=None,
            diagnostic="multi_offer_malformed",
            offer_ids=tuple(offer.offer_id for offer in offers),
        )
    try:
        shared_footer = _shared_package_footer(offers)
        shared = shared_footer is not None
        lines = [_offer_line(bundle, offer, shared_footer=shared) for offer in offers]
    except MultiOfferPriceBlockError as exc:
        return MultiOfferPriceBlockResult(
            block=None,
            diagnostic=exc.code,
            offer_ids=tuple(offer.offer_id for offer in offers),
        )
    heading = f"Стоимость {_patient_facing_cost_label(service)}:"
    parts = [heading, "", *lines]
    if shared_footer:
        parts.extend(["", shared_footer])
    return MultiOfferPriceBlockResult(
        block="\n".join(parts),
        diagnostic=None,
        offer_ids=tuple(offer.offer_id for offer in offers),
    )
