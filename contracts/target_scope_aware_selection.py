"""Typed scope-aware selection result (AC2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import TargetOffer, TargetStrategyMatch
from contracts.ui_scope_action import ScopeExtent

SelectionKind = Literal["broad_anchors", "scoped_shortlist"]


@dataclass(frozen=True, slots=True)
class TargetPriceAnchor:
    """Commercial scope price orientation; not a treatment recommendation."""

    extent: ScopeExtent
    service_id: str
    offer_id: str
    provenance: str = "scope_aware_selection"


@dataclass(frozen=True, slots=True)
class TargetScopeAwareSelectionResult:
    topic: str
    effective_scope: EffectiveScope
    kind: SelectionKind
    strategy_context: TargetStrategyMatch
    matched_rule_id: str | None
    service_ids: tuple[str, ...]
    offers_by_service_id: dict[str, tuple[TargetOffer, ...]] = field(default_factory=dict)
    anchors: tuple[TargetPriceAnchor, ...] = ()
    exclusions: tuple[str, ...] = ()
    price_confirmed_extents: tuple[ScopeExtent, ...] = ()
    price_navigable_extents: tuple[ScopeExtent, ...] = ()
