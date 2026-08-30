"""Pre-Composer fixed-offer selection contract (CP-EXACT-1B-SINGLE / MULTI-V1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.response_schema import TargetOffer

PrecomposerSelectedOfferAvailability = Literal["none", "selected", "multiple"]
PriceTextOwner = Literal[
    "model_price_text",
    "canonical_fallback",
    "canonical_multi",
    "legacy_authoritative",
    "none",
]
PriceTextDiagnostic = Literal[
    "missing",
    "wrong_amount",
    "wrong_unit",
    "extra_amount",
    "wrong_scope",
    "unexpected_nonprice",
    "unexpected_multi_price_text",
    "canonical_fallback_used",
    "patient_text_duplicate_amount",
]
PrecomposerOfferDiagnostic = Literal[
    "multi_offer_too_many",
    "multi_offer_malformed",
    "multi_offer_mixed_price_modes",
    "multi_offer_unsafe_scope",
]


class PrecomposerSelectedOfferContractError(ValueError):
    """Typed error for an invalid precomposer selection state."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PrecomposerSelectedOfferResult:
    """Zero, one, or 2–3 active fixed offers chosen before Composer."""

    availability: PrecomposerSelectedOfferAvailability
    offer: TargetOffer | None = None
    offers: tuple[TargetOffer, ...] = ()
    service_id: str | None = None
    diagnostic: PrecomposerOfferDiagnostic | None = None

    def __post_init__(self) -> None:
        validate_precomposer_selected_offer_result(self)


def validate_precomposer_selected_offer_result(
    result: PrecomposerSelectedOfferResult,
) -> None:
    if result.availability == "none":
        if result.offer is not None or result.offers:
            raise PrecomposerSelectedOfferContractError("none_invariant")
        return
    if result.availability == "selected":
        if result.offer is None or result.offers:
            raise PrecomposerSelectedOfferContractError("selected_invariant")
        return
    if result.availability == "multiple":
        if result.offer is not None:
            raise PrecomposerSelectedOfferContractError("multiple_offer_invariant")
        offers = result.offers
        if not (2 <= len(offers) <= 3):
            raise PrecomposerSelectedOfferContractError("multiple_count_invariant")
        offer_ids = [offer.offer_id for offer in offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise PrecomposerSelectedOfferContractError("multiple_duplicate_ids")
        service_ids = {offer.service_id for offer in offers}
        if len(service_ids) != 1:
            raise PrecomposerSelectedOfferContractError("multiple_mixed_services")
        for offer in offers:
            if not offer.active:
                raise PrecomposerSelectedOfferContractError("multiple_inactive_offer")
            price = offer.price
            if price.mode != "fixed":
                raise PrecomposerSelectedOfferContractError("multiple_non_fixed_offer")
            if price.amount is None or int(price.amount) < 0:
                raise PrecomposerSelectedOfferContractError("multiple_malformed_amount")
            if not str(price.currency or "").strip():
                raise PrecomposerSelectedOfferContractError("multiple_malformed_currency")
            if not str(price.billing_unit or "").strip():
                raise PrecomposerSelectedOfferContractError("multiple_malformed_billing_unit")
            if not str(offer.package.label or "").strip():
                raise PrecomposerSelectedOfferContractError("multiple_malformed_package_label")
        if result.service_id is None or result.service_id not in service_ids:
            raise PrecomposerSelectedOfferContractError("multiple_service_id_mismatch")
        return
    raise PrecomposerSelectedOfferContractError("availability_invalid")


@dataclass(frozen=True, slots=True)
class ResolvedPriceText:
    """Validated model price line, canonical single line, or canonical multi block."""

    line: str
    owner: PriceTextOwner
    diagnostic: PriceTextDiagnostic | None = None
    selected_offer_id: str | None = None
    multi_offer_ids: tuple[str, ...] = ()
