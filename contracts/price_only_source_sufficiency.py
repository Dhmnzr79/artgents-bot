"""Shared price-only offer source sufficiency contract (FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TargetResponseComponent = Literal["content", "price", "doctors"]
_PRICE_ONLY_COMPONENTS: tuple[TargetResponseComponent, ...] = ("price",)


@dataclass(frozen=True, slots=True)
class PriceOnlySourceContext:
    service_id: str | None
    required_components: tuple[str, ...]
    requested_components: tuple[str, ...]
    offer_ids: tuple[str, ...]
    offer_service_ids: tuple[str, ...]
    offer_active_flags: tuple[bool, ...]
    selected_content_ref: str | None
    primary_content_ref: str | None
    unfulfilled_components: tuple[str, ...]
    response_stage: str | None
    is_generic_fullcontext: bool
    is_scope_aware_price: bool
    is_structured_service_availability: bool


def is_price_only_offer_source_sufficient(ctx: PriceOnlySourceContext) -> bool:
    """Return True when MD content source is not required for a service-bound price answer."""

    service_id = str(ctx.service_id or "").strip()
    if not service_id:
        return False
    if ctx.is_generic_fullcontext:
        return False
    if ctx.is_scope_aware_price:
        return False
    if ctx.is_structured_service_availability:
        return False
    if ctx.response_stage in {"stage_clarify", "data_gap"}:
        return False
    if ctx.required_components != _PRICE_ONLY_COMPONENTS:
        return False
    if ctx.requested_components != _PRICE_ONLY_COMPONENTS:
        return False
    if "content" in ctx.required_components or "content" in ctx.requested_components:
        return False
    if ctx.unfulfilled_components:
        return False
    if not ctx.offer_ids:
        return False
    if len(ctx.offer_ids) != len(ctx.offer_service_ids) or len(ctx.offer_ids) != len(
        ctx.offer_active_flags
    ):
        return False
    if any(not active for active in ctx.offer_active_flags):
        return False
    if any(offer_service_id != service_id for offer_service_id in ctx.offer_service_ids):
        return False
    if ctx.selected_content_ref is not None or ctx.primary_content_ref is not None:
        return False
    return True


def price_only_topic_fallback(allowed_topics: tuple[str, ...]) -> str:
    return next(iter(allowed_topics), "clinic")


def offer_identity_rows(
    materials_offers: tuple[object, ...],
    offer_ids: tuple[str, ...],
) -> tuple[tuple[str, bool], ...]:
    by_id = {
        str(getattr(offer, "offer_id", "") or "").strip(): offer
        for offer in materials_offers
    }
    rows: list[tuple[str, bool]] = []
    for offer_id in offer_ids:
        offer = by_id.get(offer_id)
        if offer is None:
            rows.append(("", False))
            continue
        rows.append(
            (
                str(getattr(offer, "service_id", "") or "").strip(),
                bool(getattr(offer, "active", False)),
            )
        )
    return tuple(rows)
