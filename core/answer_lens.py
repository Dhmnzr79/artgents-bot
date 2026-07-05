"""Read-only projections of a ServiceNode for future answer rendering."""
from __future__ import annotations

from dataclasses import dataclass

from contracts.patient_playbook import PatientOptionsResult
from contracts.patient_situation import PatientSituationResult
from core.patient_playbook import select_patient_options
from core.service_node import (
    PriceModel,
    ServiceNode,
    ServiceNodeFollowup,
    ServiceNodeOffer,
    load_service_node,
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


@dataclass(frozen=True)
class SituationItem:
    node: ServiceNode
    role: str
    positioning: str
    priority: int


@dataclass(frozen=True)
class SituationView:
    situation_kind: str
    patient_scope: str
    primary_cta: str
    strategy: str
    items: tuple[SituationItem, ...]


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


def situation_view(options: PatientOptionsResult, client_id: str | None) -> SituationView:
    items: list[SituationItem] = []
    for option in options.options:
        node = load_service_node(client_id, option.service_id)
        if node is None:
            continue
        items.append(
            SituationItem(
                node=node,
                role=option.role,
                positioning=option.positioning,
                priority=option.priority,
            )
        )
    return SituationView(
        situation_kind=options.situation_kind,
        patient_scope=options.patient_scope,
        primary_cta=options.primary_cta,
        strategy=options.strategy,
        items=tuple(items),
    )


def situation_view_from(
    situation: PatientSituationResult,
    q: str,
    client_id: str | None,
) -> SituationView | None:
    options = select_patient_options(situation, q, client_id)
    if options is None:
        return None
    return situation_view(options, client_id)
