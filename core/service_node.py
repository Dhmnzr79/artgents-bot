"""Unified read-only service view (catalog + pricebook), dormant adapter for 5.5a."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.price_offer import PriceOffer
from contracts.pricebook import PriceFollowup, PricebookServiceEntry, SimplePrice
from core.patient_playbook import _read_service_catalog
from core.pricebook_loader import (
    default_unit_for_service_entry,
    list_pricebook_service_ids,
    load_pricebook_service,
    offers_from_service_entry,
)

PriceModel = Literal["simple", "complex"]


@dataclass(frozen=True)
class ServiceNodePaymentStage:
    name: str
    amount: int


@dataclass(frozen=True)
class ServiceNodeOffer:
    offer_id: str
    brand: str
    brand_label: str
    total: int
    unit: str
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    payment_stages: tuple[ServiceNodePaymentStage, ...] = ()
    recommended: bool = False
    currency: str = "RUB"


@dataclass(frozen=True)
class ServiceNodeFollowup:
    label: str
    action: str
    service_id: str | None = None
    aspect: str | None = None
    ref: str | None = None
    detail_ref: str | None = None
    group_id: str | None = None


@dataclass(frozen=True)
class ServiceNode:
    service_id: str
    title: str
    active: bool
    content_ref: str | None
    price_model: PriceModel | None
    default_unit: str | None
    tags: tuple[str, ...]
    offers: tuple[ServiceNodeOffer, ...]
    followups: tuple[ServiceNodeFollowup, ...]
    cta_key: str | None
    intro_text: str | None


def _catalog_entry(client_id: str | None, service_id: str) -> dict | None:
    entry = _read_service_catalog(client_id).get(service_id)
    return entry if isinstance(entry, dict) else None


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _payment_stages_from_offer(offer: PriceOffer) -> tuple[ServiceNodePaymentStage, ...]:
    return tuple(
        ServiceNodePaymentStage(name=str(stage.name), amount=int(stage.amount))
        for stage in offer.payment_stages
    )


def _offer_from_price_offer(offer: PriceOffer) -> ServiceNodeOffer:
    return ServiceNodeOffer(
        offer_id=str(offer.offer_id),
        brand=str(offer.brand),
        brand_label=str(offer.brand_label),
        total=int(offer.total),
        unit=str(offer.unit),
        includes=tuple(str(x) for x in offer.includes),
        excludes=tuple(str(x) for x in offer.excludes),
        payment_stages=_payment_stages_from_offer(offer),
        recommended=bool(offer.recommended),
        currency=str(offer.currency),
    )


def _simple_offer(
    *,
    service_id: str,
    title: str,
    price: SimplePrice,
    default_unit: str | None,
) -> ServiceNodeOffer:
    # Unit is optional: many simple services (отбеливание, лечение, КТ) have no
    # default_unit but still carry a valid price — keep the price, unit stays "".
    return ServiceNodeOffer(
        offer_id=service_id,
        brand=title,
        brand_label=title,
        total=int(price.value),
        unit=_clean_text(default_unit) or "",
        currency=str(price.currency),
    )


def _offers_for_entry(
    entry: PricebookServiceEntry | None,
    *,
    title: str,
) -> tuple[ServiceNodeOffer, ...]:
    if entry is None:
        return ()
    if entry.price_model == "complex":
        return tuple(_offer_from_price_offer(offer) for offer in offers_from_service_entry(entry))
    if entry.price_model == "simple" and entry.price is not None:
        return (
            _simple_offer(
                service_id=entry.service_id,
                title=title,
                price=entry.price,
                default_unit=default_unit_for_service_entry(entry),
            ),
        )
    return ()


def _followup_from_pricebook(raw: PriceFollowup) -> ServiceNodeFollowup:
    return ServiceNodeFollowup(
        label=str(raw.label),
        action=str(raw.action),
        service_id=_clean_text(raw.service_id),
        aspect=_clean_text(raw.aspect),
        ref=_clean_text(raw.ref),
        detail_ref=_clean_text(raw.detail_ref),
        group_id=_clean_text(raw.group_id),
    )


def _service_node_ids(client_id: str | None) -> list[str]:
    catalog_ids = {
        str(sid).strip()
        for sid in _read_service_catalog(client_id).keys()
        if str(sid).strip()
    }
    pricebook_ids = set(list_pricebook_service_ids(client_id))
    return sorted(catalog_ids | pricebook_ids)


def load_service_node(client_id: str | None, service_id: str) -> ServiceNode | None:
    """Return a merged read-only service view, or None when neither source has it."""
    sid = _clean_text(service_id)
    if not sid:
        return None

    catalog = _catalog_entry(client_id, sid)
    entry = load_pricebook_service(client_id, sid)
    if catalog is None and entry is None:
        return None

    title = (
        _clean_text((catalog or {}).get("title"))
        or _clean_text(getattr(entry, "display_name", None))
        or sid
    )
    active = False if isinstance(catalog, dict) and catalog.get("active") is False else True
    content_ref = _clean_text((catalog or {}).get("md_entry_ref"))
    tags = tuple(str(x) for x in (getattr(entry, "tags", None) or []) if str(x).strip())
    default_unit = _clean_text(default_unit_for_service_entry(entry))

    return ServiceNode(
        service_id=sid,
        title=title,
        active=active,
        content_ref=content_ref,
        price_model=getattr(entry, "price_model", None),
        default_unit=default_unit,
        tags=tags,
        offers=_offers_for_entry(entry, title=title),
        followups=tuple(
            _followup_from_pricebook(followup)
            for followup in (getattr(entry, "followups", None) or [])
        ),
        cta_key=_clean_text(getattr(entry, "cta_key", None)),
        intro_text=_clean_text(getattr(entry, "intro_text", None)),
    )


def list_service_nodes(client_id: str | None) -> list[ServiceNode]:
    return [
        node
        for sid in _service_node_ids(client_id)
        if (node := load_service_node(client_id, sid)) is not None
    ]
