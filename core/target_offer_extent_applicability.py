"""Offer-level patient-extent applicability for price routes."""

from __future__ import annotations

from contracts.response_schema import TargetOffer, TargetService
from contracts.ui_scope_action import ScopeExtent

_ALL_EXTENTS: tuple[ScopeExtent, ...] = ("one_tooth", "few_teeth", "full_arch")


def resolve_offer_applies_to_extents(
    offer: TargetOffer,
    service: TargetService,
) -> tuple[ScopeExtent, ...]:
    if offer.applies_to_extents is not None:
        return tuple(offer.applies_to_extents)  # type: ignore[return-value]

    offer_id = offer.offer_id
    if ".one_tooth." in offer_id or offer_id.endswith(".one_tooth"):
        return ("one_tooth",)
    if ".few_teeth." in offer_id or offer_id.endswith(".few_teeth"):
        return ("few_teeth",)
    if ".jaw." in offer_id or ".full_arch." in offer_id or offer_id.endswith(".jaw"):
        return ("full_arch",)

    selection = service.selection
    if selection.extent:
        return tuple(selection.extent)  # type: ignore[return-value]
    return _ALL_EXTENTS


def offer_applies_to_extent(
    offer: TargetOffer,
    service: TargetService,
    extent: ScopeExtent,
) -> bool:
    return extent in resolve_offer_applies_to_extents(offer, service)


def filter_offers_for_extent(
    offers: tuple[TargetOffer, ...],
    service: TargetService,
    extent: ScopeExtent | None,
) -> tuple[TargetOffer, ...]:
    if extent is None:
        return offers
    return tuple(
        offer
        for offer in offers
        if offer_applies_to_extent(offer, service, extent)
    )
