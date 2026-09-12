"""Client-owned family price situation groups (W1b)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.target_response_spec import CanonicalToken
from contracts.target_service_content_topic import service_catalog_content_topic_matches


def _non_blank(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("string_must_not_be_blank")
    return value


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]


class FamilyPriceGroupEntry(BaseModel):
    """One pinned offer or service-level representative shorthand."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    service_id: CanonicalToken | None = None
    offer_id: CanonicalToken | None = None
    option_id: CanonicalToken | None = None

    @model_validator(mode="after")
    def _entry_shape(self) -> "FamilyPriceGroupEntry":
        if self.offer_id is None and self.service_id is None:
            raise ValueError("family_price_group_entry_invalid")
        if self.option_id is not None and self.offer_id is None:
            raise ValueError("family_price_group_option_without_offer")
        return self


class FamilyPriceSituationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: CanonicalToken
    label: NonBlankStr
    entries: tuple[FamilyPriceGroupEntry, ...] = Field(min_length=1)

    @field_validator("entries", mode="before")
    @classmethod
    def _entries_as_tuple(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _unique_offer_pins(self) -> "FamilyPriceSituationGroup":
        offer_ids = [entry.offer_id for entry in self.entries if entry.offer_id is not None]
        if len(offer_ids) != len(set(offer_ids)):
            raise ValueError("family_price_group_duplicate_offer")
        return self


class FamilyPriceTopicGroups(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: tuple[FamilyPriceSituationGroup, ...] = Field(min_length=1)

    @field_validator("groups", mode="before")
    @classmethod
    def _groups_as_tuple(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _unique_group_ids(self) -> "FamilyPriceTopicGroups":
        group_ids = [group.id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("family_price_group_duplicate_id")
        return self


class FamilyPriceGroupsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: int = Field(..., ge=1)
    topics: dict[CanonicalToken, FamilyPriceTopicGroups]

    @model_validator(mode="after")
    def _topics_non_empty(self) -> "FamilyPriceGroupsConfig":
        if not self.topics:
            raise ValueError("family_price_groups_topics_empty")
        return self


def _offer_by_id(bundle: object) -> dict[str, object]:
    offers: dict[str, object] = {}
    for offer in bundle.offers:  # type: ignore[attr-defined]
        if offer.offer_id in offers:
            raise ValueError("bundle_offer_id_duplicate")
        offers[offer.offer_id] = offer
    return offers


def validate_family_price_groups_against_bundle(
    config: FamilyPriceGroupsConfig,
    bundle: object,
) -> None:
    """Fail-closed cross-check of group entries against catalog and pricebook."""

    services = bundle.services  # type: ignore[attr-defined]
    offers = _offer_by_id(bundle)
    for topic, topic_groups in config.topics.items():
        for group in topic_groups.groups:
            for entry in group.entries:
                if entry.offer_id is not None:
                    offer = offers.get(entry.offer_id)
                    if offer is None:
                        raise ValueError("family_price_group_offer_missing")
                    if entry.service_id is not None and offer.service_id != entry.service_id:  # type: ignore[attr-defined]
                        raise ValueError("family_price_group_service_offer_mismatch")
                    if entry.option_id is not None and offer.option_id != entry.option_id:  # type: ignore[attr-defined]
                        raise ValueError("family_price_group_option_mismatch")
                    service_id = offer.service_id  # type: ignore[attr-defined]
                else:
                    service_id = entry.service_id
                    if service_id is None or service_id not in services:
                        raise ValueError("family_price_group_service_missing")
                service = services[service_id]
                if not service.active:
                    raise ValueError("family_price_group_service_inactive")
                if not service_catalog_content_topic_matches(service.content_ref, topic):
                    raise ValueError("family_price_group_topic_mismatch")
