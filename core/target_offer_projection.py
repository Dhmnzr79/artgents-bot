"""Pure active-offer projection for one target service (S23, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import (
    TargetClinicStrategy,
    TargetOffer,
    TargetStrategyMatch,
)
from core.response_strategy import resolve_target_strategy
from core.service_data_context import ServiceDataContext


@dataclass(frozen=True, slots=True)
class TargetOfferProjection:
    service_id: str
    selected_option_id: str | None
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]


class TargetOfferProjectionError(ValueError):
    """Typed error for invalid explicit S23-only identifiers."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _is_nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def project_target_service_offers(
    service_context: ServiceDataContext,
    strategy: TargetClinicStrategy,
    strategy_context: TargetStrategyMatch,
    *,
    selected_option_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetOfferProjection:
    """Filter and rank authored offers without selecting a service or changing money."""

    if selected_option_id is not None and not _is_nonblank_string(selected_option_id):
        raise TargetOfferProjectionError(
            "offer_projection_option_id_invalid", selected_option_id
        )

    options_by_id = {
        option.option_id: option for option in service_context.service.options
    }
    if selected_option_id is not None and selected_option_id not in options_by_id:
        raise TargetOfferProjectionError(
            "offer_projection_option_not_found", selected_option_id
        )

    if explicit_offer_id is not None and not _is_nonblank_string(explicit_offer_id):
        raise TargetOfferProjectionError(
            "offer_projection_explicit_offer_id_invalid", explicit_offer_id
        )

    eligible_offers: list[TargetOffer] = []
    if service_context.service.active:
        for offer in service_context.offers:
            if not offer.active:
                continue
            if selected_option_id is not None:
                if offer.option_id != selected_option_id:
                    continue
                if options_by_id[selected_option_id].active is False:
                    continue
            elif offer.option_id is not None:
                if options_by_id[offer.option_id].active is False:
                    continue
            eligible_offers.append(offer)

    resolution = resolve_target_strategy(
        strategy,
        strategy_context,
        offer_ids=tuple(offer.offer_id for offer in eligible_offers),
        explicit_offer_id=explicit_offer_id,
    )
    eligible_by_id = {offer.offer_id: offer for offer in eligible_offers}

    return TargetOfferProjection(
        service_id=service_context.service_id,
        selected_option_id=selected_option_id,
        matched_rule_id=resolution.matched_rule_id,
        max_options=resolution.max_options,
        offers=tuple(
            eligible_by_id[offer_id].model_copy(deep=True)
            for offer_id in resolution.offer_ids
        ),
    )
