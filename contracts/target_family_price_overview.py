"""Contracts for deterministic family price overview selection (W1)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.target_response_spec import CanonicalToken


@dataclass(frozen=True, slots=True)
class FamilyPriceOverviewServiceEntry:
    service_id: str
    service_name: str
    offer_id: str
    catalog_order: int
    role_rank: int


@dataclass(frozen=True, slots=True)
class FamilyPriceOverviewSelection:
    turn_topic: CanonicalToken
    entries: tuple[FamilyPriceOverviewServiceEntry, ...]

    @property
    def service_ids(self) -> tuple[str, ...]:
        return tuple(entry.service_id for entry in self.entries)
