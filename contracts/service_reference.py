"""Service reference and availability types (Stage 5.1B)."""

from __future__ import annotations

from typing import Literal

ServiceReferenceStatus = Literal["none", "resolved", "unresolved"]
AvailabilityStatus = Literal["none", "offered", "known_not_offered", "unresolved"]
PriceCoverageKind = Literal[
    "none",
    "exact_numeric",
    "no_public_price",
    "family_context",
    "data_gap",
]
