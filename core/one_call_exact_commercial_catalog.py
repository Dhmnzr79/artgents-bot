"""Immutable full exact-commercial catalog snapshot for ONE_CALL stable prefix (CP-EXACT-1A)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetCommercialFact,
    TargetOffer,
    TargetPaymentStage,
    TargetPrice,
    TargetPricePackage,
    TargetService,
)

_EXACT_COMMERCIAL_CATALOG_HEADER = "=== EXACT_COMMERCIAL_CATALOG ==="


def _serialize_price(price: TargetPrice) -> dict[str, object]:
    if price.mode == "fixed":
        return {
            "mode": "fixed",
            "amount": int(price.amount),
            "currency": str(price.currency),
            "billing_unit": str(price.billing_unit),
        }
    if price.mode == "from":
        return {
            "mode": "from",
            "min_amount": int(price.min_amount),
            "currency": str(price.currency),
            "billing_unit": str(price.billing_unit),
        }
    if price.mode == "range":
        return {
            "mode": "range",
            "min_amount": int(price.min_amount),
            "max_amount": int(price.max_amount),
            "currency": str(price.currency),
            "billing_unit": str(price.billing_unit),
        }
    return {
        "mode": "no_public_price",
        "approved_text": str(price.approved_text),
    }


def _serialize_package(package: TargetPricePackage) -> dict[str, object]:
    return {
        "label": str(package.label),
        "includes": [str(item) for item in package.includes],
    }


def _serialize_payment_stages(
    stages: list[TargetPaymentStage] | None,
) -> list[dict[str, object]]:
    if not stages:
        return []
    return [
        {
            "label": str(stage.label),
            "amount": int(stage.amount),
            "currency": str(stage.currency),
        }
        for stage in stages
    ]


def _serialize_fact_row(fact_id: str, fact: TargetCommercialFact) -> dict[str, object]:
    row: dict[str, object] = {
        "fact_id": str(fact_id),
        "kind": str(fact.kind),
        "catalog_label": str(fact.catalog_label),
        "text_fact": str(fact.text_fact),
        "render_mode": str(fact.render_mode),
        "active": bool(fact.active),
        "allowed_service_ids": sorted(str(item) for item in fact.allowed_service_ids),
        "allowed_topics": sorted(str(item) for item in fact.allowed_topics),
        "incompatible_with": sorted(str(item) for item in fact.incompatible_with),
    }
    if fact.active_from is not None:
        row["active_from"] = str(fact.active_from)
    if fact.active_until is not None:
        row["active_until"] = str(fact.active_until)
    if fact.detail_ref is not None:
        row["detail_ref"] = str(fact.detail_ref)
    return row


def _serialize_offer_row(offer: TargetOffer) -> dict[str, object]:
    row: dict[str, object] = {
        "offer_id": str(offer.offer_id),
        "service_id": str(offer.service_id),
        "active": bool(offer.active),
        "price": _serialize_price(offer.price),
        "package": _serialize_package(offer.package),
        "payment_stages": _serialize_payment_stages(offer.payment_stages),
        "fact_refs": sorted(str(item) for item in offer.fact_refs),
    }
    if offer.option_id is not None:
        row["option_id"] = str(offer.option_id)
    if offer.brand_id is not None:
        row["brand_id"] = str(offer.brand_id)
    if offer.applies_to_extents is not None:
        row["applies_to_extents"] = sorted(str(item) for item in offer.applies_to_extents)
    return row


def _serialize_service_row(
    service_id: str,
    service: TargetService,
    *,
    offer_ids: tuple[str, ...],
) -> dict[str, object]:
    row: dict[str, object] = {
        "service_id": str(service_id),
        "name": str(service.name),
        "family": str(service.family),
        "offer_ids": list(offer_ids),
    }
    if service.service_value_ref is not None:
        row["service_value_ref"] = str(service.service_value_ref)
    return row


@dataclass(frozen=True, slots=True)
class ExactCommercialCatalogSnapshot:
    """Deterministic full commercial catalog derived from the current client bundle."""

    canonical_json: str
    fact_ids: frozenset[str] = field(default_factory=frozenset)
    active_fact_ids: frozenset[str] = field(default_factory=frozenset)
    offer_ids: frozenset[str] = field(default_factory=frozenset)
    active_offer_ids: frozenset[str] = field(default_factory=frozenset)
    active_service_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_bundle(cls, bundle: ResponseSchemaBundle) -> ExactCommercialCatalogSnapshot:
        fact_rows = [
            _serialize_fact_row(fact_id, bundle.facts[fact_id])
            for fact_id in sorted(bundle.facts)
        ]
        offer_rows = [
            _serialize_offer_row(offer)
            for offer in sorted(bundle.offers, key=lambda item: item.offer_id)
        ]
        offers_by_service: dict[str, list[str]] = {}
        for offer in bundle.offers:
            offers_by_service.setdefault(str(offer.service_id), []).append(str(offer.offer_id))
        service_rows = [
            _serialize_service_row(
                service_id,
                bundle.services[service_id],
                offer_ids=tuple(sorted(offers_by_service.get(service_id, ()))),
            )
            for service_id in sorted(bundle.services)
            if bundle.services[service_id].active
        ]
        canonical = {
            "facts": fact_rows,
            "offers": offer_rows,
            "services": service_rows,
        }
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        all_fact_ids = {str(fact_id) for fact_id in bundle.facts}
        active_fact_ids = {
            str(fact_id)
            for fact_id, fact in bundle.facts.items()
            if fact.active
        }
        all_offer_ids = {str(offer.offer_id) for offer in bundle.offers}
        active_offer_ids = {
            str(offer.offer_id) for offer in bundle.offers if offer.active
        }
        active_service_ids = {
            str(service_id)
            for service_id, service in bundle.services.items()
            if service.active
        }
        return cls(
            canonical_json=canonical_json,
            fact_ids=frozenset(all_fact_ids),
            active_fact_ids=frozenset(active_fact_ids),
            offer_ids=frozenset(all_offer_ids),
            active_offer_ids=frozenset(active_offer_ids),
            active_service_ids=frozenset(active_service_ids),
        )

    def block_text(self) -> str:
        return f"{_EXACT_COMMERCIAL_CATALOG_HEADER}\n{self.canonical_json}"

    def date_eligible_fact_ids(self, as_of: date) -> tuple[str, ...]:
        payload = json.loads(self.canonical_json)
        today_iso = as_of.isoformat()
        eligible: list[str] = []
        for row in payload["facts"]:
            if not bool(row.get("active", True)):
                continue
            active_from = row.get("active_from")
            active_until = row.get("active_until")
            if isinstance(active_from, str) and today_iso < active_from:
                continue
            if isinstance(active_until, str) and today_iso > active_until:
                continue
            eligible.append(str(row["fact_id"]))
        return tuple(sorted(eligible))


CommercialAsOfAvailability = Literal["ok", "unavailable"]

COMMERCIAL_AS_OF_HEADER = "=== COMMERCIAL_AS_OF ==="
COMMERCIAL_AS_OF_UNAVAILABLE = "commercial_as_of_unavailable"
COMMERCIAL_AS_OF_OK = "commercial_as_of_ok"


def _record_commercial_as_of_diagnostic(code: str) -> None:
    from core import turn_timing

    try:
        stored = turn_timing.summary_for_turn_complete().get("commercial_as_of_diagnostics")
        codes = list(stored) if isinstance(stored, list) else []
        if code not in codes:
            codes.append(code)
        turn_timing.set_flag("commercial_as_of_diagnostics", codes)
    except Exception:
        return


def build_commercial_as_of_block(
    exact_catalog: ExactCommercialCatalogSnapshot | None,
    *,
    as_of_date: date,
) -> str:
    """Build dynamic COMMERCIAL_AS_OF block with soft degradation on optional failure."""

    try:
        if exact_catalog is None:
            raise ValueError("exact_commercial_catalog_missing")
        eligible = exact_catalog.date_eligible_fact_ids(as_of_date)
        payload = {
            "as_of_date": as_of_date.isoformat(),
            "date_eligible_fact_ids": list(eligible),
            "availability": "ok",
        }
        _record_commercial_as_of_diagnostic(COMMERCIAL_AS_OF_OK)
    except Exception:
        payload = {
            "as_of_date": as_of_date.isoformat(),
            "date_eligible_fact_ids": [],
            "availability": "unavailable",
        }
        _record_commercial_as_of_diagnostic(COMMERCIAL_AS_OF_UNAVAILABLE)
    return (
        f"{COMMERCIAL_AS_OF_HEADER}\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
