"""Resolve clinic-owned generic price policy from strategy context."""

from __future__ import annotations

from contracts.response_schema import (
    TargetClinicStrategy,
    TargetGenericPricePolicy,
    TargetStrategyMatch,
)
from core.response_strategy import _first_matching_rule


def resolve_effective_generic_price_policy(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
) -> TargetGenericPricePolicy | None:
    matched_rule = _first_matching_rule(strategy, context)
    if matched_rule is not None and matched_rule.generic_price_policy is not None:
        return matched_rule.generic_price_policy
    return strategy.default_generic_price_policy
