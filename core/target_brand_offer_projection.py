"""Pure exact-brand offer projection for one target service (S24, unwired)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import (
    TargetBrand,
    TargetBrandCatalog,
    TargetClinicStrategy,
    TargetOffer,
    TargetStrategyMatch,
)
from core.service_data_context import ServiceDataContext
from core.target_offer_projection import project_target_service_offers


@dataclass(frozen=True, slots=True)
class TargetBrandOfferProjection:
    service_id: str
    selected_option_id: str | None
    selected_brand_id: str
    brand: TargetBrand
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]


class TargetBrandOfferProjectionError(ValueError):
    """Typed error for an invalid or unknown exact S24 brand identifier."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def project_target_service_brand_offers(
    service_context: ServiceDataContext,
    brand_catalog: TargetBrandCatalog,
    strategy: TargetClinicStrategy,
    strategy_context: TargetStrategyMatch,
    *,
    selected_brand_id: str,
    selected_option_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetBrandOfferProjection:
    """Keep one exact brand, then delegate active/option/order semantics to S23."""

    if not isinstance(selected_brand_id, str) or not selected_brand_id.strip():
        raise TargetBrandOfferProjectionError(
            "brand_offer_projection_brand_id_invalid", selected_brand_id
        )

    brand = brand_catalog.brands.get(selected_brand_id)
    if brand is None:
        raise TargetBrandOfferProjectionError(
            "brand_offer_projection_brand_not_found", selected_brand_id
        )

    filtered_context = ServiceDataContext(
        service_id=service_context.service_id,
        service=service_context.service,
        offers=tuple(
            offer
            for offer in service_context.offers
            if offer.brand_id == selected_brand_id
        ),
        doctors=service_context.doctors,
    )
    offer_projection = project_target_service_offers(
        filtered_context,
        strategy,
        strategy_context,
        selected_option_id=selected_option_id,
        explicit_offer_id=explicit_offer_id,
    )

    return TargetBrandOfferProjection(
        service_id=offer_projection.service_id,
        selected_option_id=offer_projection.selected_option_id,
        selected_brand_id=selected_brand_id,
        brand=brand.model_copy(deep=True),
        matched_rule_id=offer_projection.matched_rule_id,
        max_options=offer_projection.max_options,
        offers=offer_projection.offers,
    )
