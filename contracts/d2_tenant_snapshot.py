"""Immutable tenant data objects used only by the isolated D2 path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import model_validator

from contracts.response_plan import ResponsePlanModel

from contracts.response_plan_materialization import D2AuthoredContentAuthority, D2PublishedOfferTerms
from contracts.response_schema import ResponseSchemaBundle
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot


class D2DirectionPriceConfig(ResponsePlanModel):
    """Explicit clinic-owned offer order, not inferred from a topic label."""

    topic_id: str
    service_ids: tuple[str, ...]
    offer_ids: tuple[str, ...]
    introduction_text: str
    unknown_extent_text: str

    @model_validator(mode="after")
    def _validate_config(self) -> Self:
        for values in ((self.topic_id, self.introduction_text, self.unknown_extent_text),
                       self.service_ids, self.offer_ids):
            if not values or any(not value or value != value.strip() for value in values):
                raise ValueError("direction_price_blank")
        if len(set(self.service_ids)) != len(self.service_ids) or len(set(self.offer_ids)) != len(self.offer_ids):
            raise ValueError("direction_price_duplicate_ref")
        return self


class D2DirectionPricePack(ResponsePlanModel):
    version: Literal[1]
    directions: tuple[D2DirectionPriceConfig, ...]

    @model_validator(mode="after")
    def _unique_topics(self) -> Self:
        if len({item.topic_id for item in self.directions}) != len(self.directions):
            raise ValueError("direction_price_duplicate_topic")
        return self


@dataclass(frozen=True, slots=True)
class D2TenantSnapshot:
    client_id: str
    fingerprint: str
    bundle: ResponseSchemaBundle
    files: tuple[tuple[str, bytes], ...]
    content: tuple[D2AuthoredContentAuthority, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class D2ModelView:
    client_id: str
    fingerprint: str
    active_service_catalog: ActiveServiceCatalogSnapshot
    service_reference_catalog: ServiceReferenceCatalogSnapshot
    commercial_fact_catalog: CommercialFactCatalogSnapshot
    content: tuple[D2AuthoredContentAuthority, ...]
    published_terms: tuple[D2PublishedOfferTerms, ...]
    direction_prices: tuple[D2DirectionPriceConfig, ...] = ()
