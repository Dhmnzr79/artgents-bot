"""Deterministic target clinic-strategy resolution (S15, offline and unwired)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from contracts.response_schema import (
    TargetClinicStrategy,
    TargetStrategyMatch,
    TargetStrategyRule,
)


_MATCH_FIELDS = ("family", "extent", "stage", "jaw", "reported_context")


@dataclass(frozen=True, slots=True)
class TargetStrategyResolution:
    matched_rule_id: str | None
    max_options: int
    service_ids: tuple[str, ...]
    offer_ids: tuple[str, ...]


class TargetStrategyResolutionError(ValueError):
    """Typed error for invalid already-filtered candidate inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _validated_candidates(
    values: Sequence[str],
    *,
    invalid_code: str,
    duplicate_code: str,
) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TargetStrategyResolutionError(invalid_code, values)
    copied = tuple(values)
    for value in copied:
        if not isinstance(value, str) or not value.strip():
            raise TargetStrategyResolutionError(invalid_code, value)
    if len(copied) != len(set(copied)):
        raise TargetStrategyResolutionError(duplicate_code, copied)
    return copied


def _rule_matches(rule: TargetStrategyRule, context: TargetStrategyMatch) -> bool:
    return all(
        expected is None or getattr(context, field) == expected
        for field in _MATCH_FIELDS
        for expected in (getattr(rule.match, field),)
    )


def _first_matching_rule(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
) -> TargetStrategyRule | None:
    return next((rule for rule in strategy.rules if _rule_matches(rule, context)), None)


def _effective_priorities(
    defaults: Mapping[str, int],
    overrides: Mapping[str, int] | None,
) -> dict[str, int]:
    effective = dict(defaults)
    if overrides is not None:
        effective.update(overrides)
    return effective


def _rank_candidates(
    candidates: tuple[str, ...],
    priorities: Mapping[str, int],
    *,
    explicit_id: str | None,
    explicit_not_candidate_code: str,
    limit: int,
) -> tuple[str, ...]:
    if explicit_id is not None and explicit_id not in candidates:
        raise TargetStrategyResolutionError(explicit_not_candidate_code, explicit_id)

    ordered = sorted(
        enumerate(candidates),
        key=lambda item: (
            0 if explicit_id is not None and item[1] == explicit_id else 1,
            -priorities.get(item[1], 0),
            item[0],
        ),
    )
    return tuple(candidate for _, candidate in ordered[:limit])


def resolve_target_strategy(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
    *,
    service_ids: Sequence[str] = (),
    offer_ids: Sequence[str] = (),
    explicit_service_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetStrategyResolution:
    """Rank only supplied candidates using defaults plus the first matching rule."""

    services = _validated_candidates(
        service_ids,
        invalid_code="strategy_candidate_service_invalid",
        duplicate_code="strategy_candidate_service_duplicate",
    )
    offers = _validated_candidates(
        offer_ids,
        invalid_code="strategy_candidate_offer_invalid",
        duplicate_code="strategy_candidate_offer_duplicate",
    )
    matched_rule = _first_matching_rule(strategy, context)
    max_options = (
        matched_rule.max_options
        if matched_rule is not None and matched_rule.max_options is not None
        else strategy.default_max_options
    )

    service_priorities = _effective_priorities(
        strategy.default_service_priorities,
        matched_rule.service_priorities if matched_rule is not None else None,
    )
    offer_priorities = _effective_priorities(
        strategy.default_offer_priorities,
        matched_rule.offer_priorities if matched_rule is not None else None,
    )

    return TargetStrategyResolution(
        matched_rule_id=matched_rule.id if matched_rule is not None else None,
        max_options=max_options,
        service_ids=_rank_candidates(
            services,
            service_priorities,
            explicit_id=explicit_service_id,
            explicit_not_candidate_code="strategy_explicit_service_not_candidate",
            limit=max_options,
        ),
        offer_ids=_rank_candidates(
            offers,
            offer_priorities,
            explicit_id=explicit_offer_id,
            explicit_not_candidate_code="strategy_explicit_offer_not_candidate",
            limit=max_options,
        ),
    )
