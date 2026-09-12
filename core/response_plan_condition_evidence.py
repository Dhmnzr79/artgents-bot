"""Catalog-backed OfferConditionEvidence projection for response-plan materialization."""

from __future__ import annotations

from contracts.response_plan import (
    RequiredOfferConditionBlock,
    RequiredOfferConditionOfferEntry,
)
from contracts.response_plan_materialization import OfferConditionEvidence
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_schema import TargetFixedPrice, TargetOffer
from core.response_plan_production_adapter import billing_unit_phrase


def materialization_price_scope_label(offer: TargetOffer) -> str:
    scope = offer.package.price_scope_label
    if scope is None or not str(scope).strip():
        return ""
    scope_text = str(scope).strip()
    fixed = offer.price
    if isinstance(fixed, TargetFixedPrice):
        unit_phrase = billing_unit_phrase(fixed.billing_unit)
        if scope_text.casefold() == unit_phrase.casefold():
            return ""
    return scope_text


def build_condition_evidence_for_offer(
    *,
    offer: TargetOffer,
    source_client_id: str,
) -> OfferConditionEvidence:
    metadata = offer.required_conditions_metadata
    if metadata is None:
        return OfferConditionEvidence(
            source_client_id=source_client_id,
            offer_id=offer.offer_id,
            completeness="unknown",
            conditions=(),
        )
    blocks: list[RequiredOfferConditionBlock] = []
    for entry in metadata.conditions:
        blocks.append(
            RequiredOfferConditionBlock(
                source_client_id=source_client_id,
                condition_id=entry.condition_id,
                completeness="complete",
                entries=(
                    RequiredOfferConditionOfferEntry(
                        offer_id=offer.offer_id,
                        display_text=entry.display_text,
                    ),
                ),
            )
        )
    return OfferConditionEvidence(
        source_client_id=source_client_id,
        offer_id=offer.offer_id,
        completeness="complete",
        conditions=tuple(blocks),
    )


def build_condition_evidence_by_offer(
    material: PostComposerMaterialAuthority,
) -> dict[str, OfferConditionEvidence]:
    client_id = material.source_client_id
    return {
        offer.offer_id: build_condition_evidence_for_offer(
            offer=offer,
            source_client_id=client_id,
        )
        for offer in material.bundle.offers
    }
