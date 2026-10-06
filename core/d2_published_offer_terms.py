"""Pure D2 projection of the price terms already published in TargetOffer."""

from __future__ import annotations

from contracts.response_plan_materialization import D2PublishedOfferTerms
from contracts.response_schema import TargetOffer
from core.response_plan_condition_evidence import materialization_price_scope_label


def build_d2_published_offer_terms(*, offer: TargetOffer, source_client_id: str) -> D2PublishedOfferTerms:
    """Keep every explicit published term without inventing any absent condition."""
    terms: list[str] = []
    scope = materialization_price_scope_label(offer)
    if scope and scope != offer.package.label:
        terms.append(scope)
    terms.extend(item for item in offer.package.includes if item != offer.package.label)
    terms.extend(item for item in offer.package.excludes if item != offer.package.label)
    for stage in offer.payment_stages or ():
        timing = f" — {stage.timing_text}" if stage.timing_text else ""
        terms.append(f"{stage.label}: {stage.amount} {stage.currency}{timing}")
    if offer.required_conditions_metadata is not None:
        terms.extend(item.display_text for item in offer.required_conditions_metadata.conditions)
    # Exact duplicate text is redundant; semantic deduplication is deliberately absent.
    unique = tuple(dict.fromkeys(item.strip() for item in terms if item.strip()))
    return D2PublishedOfferTerms(
        source_client_id=source_client_id,
        offer_id=offer.offer_id,
        package_label=offer.package.label,
        condition_texts=unique,
    )
