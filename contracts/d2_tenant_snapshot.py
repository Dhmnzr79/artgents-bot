"""Immutable tenant data objects used only by the isolated D2 path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import field_validator, model_validator

from contracts.response_plan import ResponsePlanModel

from contracts.response_plan_materialization import D2AuthoredContentAuthority, D2PublishedOfferTerms
from contracts.response_schema import ResponseSchemaBundle, TargetBrandCatalog
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


def _require_non_blank(*values: str) -> None:
    if any(not value or value != value.strip() for value in values):
        raise ValueError("commercial_blank")


class D2CommercialPromoFact(ResponsePlanModel):
    fact_id: str
    short_text: str
    full_text: str

    @model_validator(mode="after")
    def _validate_promo(self) -> Self:
        _require_non_blank(self.fact_id, self.short_text, self.full_text)
        return self


class D2CommercialPackage(ResponsePlanModel):
    package_id: str
    name: str
    body_text: str

    @model_validator(mode="after")
    def _validate_package(self) -> Self:
        _require_non_blank(self.package_id, self.name, self.body_text)
        return self


class D2ServiceCommercialProfile(ResponsePlanModel):
    service_id: str
    promo_refs: tuple[str, ...] = ()
    price_booster_id: str | None = None
    also_list_id: str | None = None

    @field_validator("price_booster_id", "also_list_id", mode="before")
    @classmethod
    def _single_optional_package(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            raise ValueError("commercial_package_not_single")
        return value

    @model_validator(mode="after")
    def _validate_profile(self) -> Self:
        _require_non_blank(self.service_id, *self.promo_refs)
        if any(not value or value != value.strip() for value in (self.price_booster_id, self.also_list_id) if value is not None):
            raise ValueError("commercial_blank")
        if len(self.promo_refs) > 2:
            raise ValueError("commercial_promo_ref_cap")
        if len(set(self.promo_refs)) != len(self.promo_refs):
            raise ValueError("commercial_promo_ref_duplicate")
        return self


class D2IncompatibilityGroup(ResponsePlanModel):
    group_id: str
    offer_or_fact_ids: tuple[str, ...]
    explanation_text: str

    @model_validator(mode="after")
    def _validate_group(self) -> Self:
        _require_non_blank(self.group_id, self.explanation_text, *self.offer_or_fact_ids)
        if len(self.offer_or_fact_ids) < 2:
            raise ValueError("commercial_incompatibility_too_small")
        if len(set(self.offer_or_fact_ids)) != len(self.offer_or_fact_ids):
            raise ValueError("commercial_incompatibility_duplicate_ref")
        return self


class D2CommercialPack(ResponsePlanModel):
    version: Literal[1]
    client_id: str | None = None
    promo_facts: tuple[D2CommercialPromoFact, ...] = ()
    price_booster_packages: tuple[D2CommercialPackage, ...] = ()
    also_list_packages: tuple[D2CommercialPackage, ...] = ()
    service_profiles: tuple[D2ServiceCommercialProfile, ...] = ()
    incompatibility_groups: tuple[D2IncompatibilityGroup, ...] = ()

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        if self.client_id is not None:
            _require_non_blank(self.client_id)
        if len({item.fact_id for item in self.promo_facts}) != len(self.promo_facts):
            raise ValueError("commercial_promo_fact_duplicate")
        package_ids = tuple(item.package_id for item in (*self.price_booster_packages, *self.also_list_packages))
        if len(set(package_ids)) != len(package_ids):
            raise ValueError("commercial_package_duplicate")
        if len({item.service_id for item in self.service_profiles}) != len(self.service_profiles):
            raise ValueError("commercial_profile_duplicate")
        if len({item.group_id for item in self.incompatibility_groups}) != len(self.incompatibility_groups):
            raise ValueError("commercial_incompatibility_duplicate")
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
    brand_catalog: TargetBrandCatalog
    published_terms: tuple[D2PublishedOfferTerms, ...]
    direction_prices: tuple[D2DirectionPriceConfig, ...] = ()
    commercial: D2CommercialPack = field(default_factory=lambda: D2CommercialPack(version=1))
