"""Pre-Composer single fixed-offer selection contract (CP-EXACT-1B-SINGLE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.response_schema import TargetOffer

PrecomposerSelectedOfferAvailability = Literal["selected", "none"]
PriceTextOwner = Literal["model_price_text", "canonical_fallback", "legacy_authoritative", "none"]
PriceTextDiagnostic = Literal[
    "missing",
    "wrong_amount",
    "wrong_unit",
    "extra_amount",
    "wrong_scope",
    "unexpected_nonprice",
    "canonical_fallback_used",
    "patient_text_duplicate_amount",
]


@dataclass(frozen=True, slots=True)
class PrecomposerSelectedOfferResult:
    """Exactly one active fixed offer chosen before Composer, or none."""

    availability: PrecomposerSelectedOfferAvailability
    offer: TargetOffer | None = None
    service_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedPriceText:
    """Validated model price line or canonical fallback for one selected offer."""

    line: str
    owner: PriceTextOwner
    diagnostic: PriceTextDiagnostic | None = None
    selected_offer_id: str | None = None
