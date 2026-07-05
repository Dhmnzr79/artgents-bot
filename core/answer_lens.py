"""Read-only projections of a ServiceNode for future answer rendering."""
from __future__ import annotations

from dataclasses import dataclass

from core.service_node import (
    PriceModel,
    ServiceNode,
    ServiceNodeFollowup,
    ServiceNodeOffer,
)


@dataclass(frozen=True)
class DescribeView:
    service_id: str
    title: str
    content_ref: str | None
    intro_text: str | None
    followups: tuple[ServiceNodeFollowup, ...]


@dataclass(frozen=True)
class PriceView:
    service_id: str
    title: str
    price_model: PriceModel | None
    default_unit: str | None
    offers: tuple[ServiceNodeOffer, ...]
    min_total: int | None
    has_brand_choice: bool
    cta_key: str | None


def describe_view(node: ServiceNode) -> DescribeView:
    return DescribeView(
        service_id=node.service_id,
        title=node.title,
        content_ref=node.content_ref,
        intro_text=node.intro_text,
        followups=tuple(node.followups),
    )


def price_view(node: ServiceNode) -> PriceView:
    offers = tuple(sorted(node.offers, key=lambda offer: offer.total))
    return PriceView(
        service_id=node.service_id,
        title=node.title,
        price_model=node.price_model,
        default_unit=node.default_unit,
        offers=offers,
        min_total=offers[0].total if offers else None,
        has_brand_choice=len({offer.brand for offer in offers}) > 1,
        cta_key=node.cta_key,
    )
