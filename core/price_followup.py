"""Vague price follow-up — thin wrapper over core.attribute_followup."""
from __future__ import annotations

from typing import Any

from core.attribute_followup import (
    is_vague_attribute_followup,
    is_weak_catalog_match_for_vague_attribute,
    query_has_explicit_service_object,
)


def price_query_has_explicit_service_object(q: str) -> bool:
    """True when a price question names a service, not only «сколько стоит» / «по ценам»."""
    return query_has_explicit_service_object(q, kind="price")


def is_vague_price_followup(q: str) -> bool:
    return is_vague_attribute_followup(q, "price")


def is_weak_catalog_price_token_match(match: dict[str, Any], q: str) -> bool:
    return is_weak_catalog_match_for_vague_attribute(match, q, "price")
