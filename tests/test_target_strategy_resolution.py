from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from contracts.response_schema import TargetClinicStrategy, TargetStrategyMatch
from core.response_strategy import (
    TargetStrategyResolutionError,
    resolve_target_strategy,
)


def _strategy() -> TargetClinicStrategy:
    return TargetClinicStrategy.model_validate(
        {
            "version": 1,
            "default_max_options": 3,
            "default_service_priorities": {
                "service_alpha": 20,
                "service_beta": 10,
                "service_negative": -5,
            },
            "default_offer_priorities": {
                "offer_alpha": 10,
                "offer_beta": 20,
            },
            "rules": [
                {
                    "id": "extraction_first",
                    "match": {"stage": "extraction_context"},
                    "max_options": 2,
                    "service_priorities": {
                        "service_alpha": 5,
                        "service_beta": 50,
                    },
                    "offer_priorities": {"offer_alpha": 40},
                },
                {
                    "id": "one_tooth_later",
                    "match": {"extent": "one_tooth"},
                    "max_options": 3,
                    "service_priorities": {"service_alpha": 100},
                    "offer_priorities": {"offer_beta": 100},
                },
            ],
        }
    )


def _error_code(callable_: object) -> str:
    with pytest.raises(TargetStrategyResolutionError) as exc_info:
        callable_()
    return exc_info.value.code


def test_first_matching_rule_wins_without_later_rule_merge() -> None:
    result = resolve_target_strategy(
        _strategy(),
        TargetStrategyMatch(stage="extraction_context", extent="one_tooth"),
        service_ids=["service_alpha", "service_beta", "service_other"],
        offer_ids=["offer_alpha", "offer_beta", "offer_other"],
    )

    assert result.matched_rule_id == "extraction_first"
    assert result.max_options == 2
    assert result.service_ids == ("service_beta", "service_alpha")
    assert result.offer_ids == ("offer_alpha", "offer_beta")


def test_required_rule_fields_match_exactly_and_unknown_does_not_match() -> None:
    strategy = TargetClinicStrategy.model_validate(
        {
            "rules": [
                {
                    "id": "upper_full_arch",
                    "match": {"extent": "full_arch", "jaw": "upper"},
                    "service_priorities": {"upper_service": 100},
                }
            ]
        }
    )

    unknown = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(extent="full_arch"),
        service_ids=["other", "upper_service"],
    )
    lower = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(extent="full_arch", jaw="lower"),
        service_ids=["other", "upper_service"],
    )
    upper = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(extent="full_arch", jaw="upper"),
        service_ids=["other", "upper_service"],
    )

    assert unknown.matched_rule_id is None
    assert lower.matched_rule_id is None
    assert upper.matched_rule_id == "upper_full_arch"
    assert upper.max_options == strategy.default_max_options
    assert upper.service_ids[0] == "upper_service"


def test_defaults_selected_overrides_missing_zero_and_stable_ties() -> None:
    result = resolve_target_strategy(
        _strategy(),
        TargetStrategyMatch(extent="few_teeth"),
        service_ids=[
            "service_other_first",
            "service_negative",
            "service_alpha",
            "service_other_second",
            "service_beta",
        ],
    )

    assert result.matched_rule_id is None
    assert result.max_options == 3
    assert result.service_ids == (
        "service_alpha",
        "service_beta",
        "service_other_first",
    )


def test_rule_overrides_only_listed_default_values_without_mutation() -> None:
    strategy = _strategy()
    strategy_before = strategy.model_dump()
    services = ["service_alpha", "service_beta", "service_other"]
    services_before = list(services)

    result = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(stage="extraction_context"),
        service_ids=services,
    )

    assert result.service_ids == ("service_beta", "service_alpha")
    assert strategy.model_dump() == strategy_before
    assert services == services_before


def test_service_and_offer_lists_sort_and_cap_independently() -> None:
    result = resolve_target_strategy(
        _strategy(),
        TargetStrategyMatch(family="therapy"),
        service_ids=["service_other", "service_beta", "service_alpha"],
        offer_ids=["offer_other", "offer_alpha", "offer_beta"],
    )

    assert result.max_options == 3
    assert result.service_ids == ("service_alpha", "service_beta", "service_other")
    assert result.offer_ids == ("offer_beta", "offer_alpha", "offer_other")


def test_explicit_candidates_are_pinned_before_priority_and_cap() -> None:
    result = resolve_target_strategy(
        _strategy(),
        TargetStrategyMatch(stage="extraction_context"),
        service_ids=["service_alpha", "service_beta", "service_named"],
        offer_ids=["offer_alpha", "offer_beta", "offer_named"],
        explicit_service_id="service_named",
        explicit_offer_id="offer_named",
    )

    assert result.service_ids == ("service_named", "service_beta")
    assert result.offer_ids == ("offer_named", "offer_alpha")


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        (
            {"service_ids": ["service_one"], "explicit_service_id": "missing"},
            "strategy_explicit_service_not_candidate",
        ),
        (
            {"offer_ids": ["offer_one"], "explicit_offer_id": "missing"},
            "strategy_explicit_offer_not_candidate",
        ),
        (
            {"service_ids": ["same", "same"]},
            "strategy_candidate_service_duplicate",
        ),
        (
            {"offer_ids": ["same", "same"]},
            "strategy_candidate_offer_duplicate",
        ),
        (
            {"service_ids": ["   "]},
            "strategy_candidate_service_invalid",
        ),
        (
            {"offer_ids": [1]},
            "strategy_candidate_offer_invalid",
        ),
        (
            {"service_ids": "service_one"},
            "strategy_candidate_service_invalid",
        ),
        (
            {"offer_ids": {"offer_one"}},
            "strategy_candidate_offer_invalid",
        ),
    ],
)
def test_invalid_candidate_inputs_have_stable_errors(
    kwargs: dict[str, object], code: str
) -> None:
    assert (
        _error_code(
            lambda: resolve_target_strategy(
                _strategy(), TargetStrategyMatch(), **kwargs
            )
        )
        == code
    )


def test_priority_maps_cannot_add_candidates_and_empty_single_are_valid() -> None:
    strategy = _strategy()

    empty = resolve_target_strategy(strategy, TargetStrategyMatch())
    single = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(),
        service_ids=["only_service"],
        offer_ids=["only_offer"],
    )

    assert empty.service_ids == empty.offer_ids == ()
    assert single.service_ids == ("only_service",)
    assert single.offer_ids == ("only_offer",)
    assert "service_alpha" not in single.service_ids
    assert "offer_beta" not in single.offer_ids


def test_resolver_imports_only_stdlib_and_target_contract() -> None:
    source_path = Path("core/response_strategy.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "contracts.response_schema",
    }
