"""Canonical response stage for scope-aware price flow (AC3)."""

from __future__ import annotations

from typing import Literal

ResponseStage = Literal[
    "broad_family_price",
    "scoped_family_price",
    "concrete_service_price",
    "stage_clarify",
    "data_gap",
]

_SCOPE_AWARE_PRICE_STAGES: frozenset[str] = frozenset(
    {
        "broad_family_price",
        "scoped_family_price",
        "concrete_service_price",
        "stage_clarify",
        "data_gap",
    }
)


def is_scope_aware_price_stage(stage: str | None) -> bool:
    return stage in _SCOPE_AWARE_PRICE_STAGES


def is_nav_scope_stage(stage: str | None) -> bool:
    return stage == "broad_family_price"


def is_nav_stage_clarify(stage: str | None) -> bool:
    return stage == "stage_clarify"
