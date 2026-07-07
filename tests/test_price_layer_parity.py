"""Cross-layer price parity gate (weak point #2).

Router (select_price_service_route) and the composer overlay defer-helpers
reason about price scope independently. This gate drives BOTH off ONE canonical
query set so a new phrasing added to one layer cannot silently diverge from the
other (money bug: a jaw question answered as a single protocol). Regexes remain
the source of truth (5.5a-2 cancelled) - this only asserts the layers agree.
"""

from __future__ import annotations

import pytest

from orchestration.composer_flow import (
    _composer_should_defer_group_price,
    _composer_should_defer_jaw_scope_price,
)
from price_query_cases import (
    FULL_JAW_CASES,
    GENERIC_CASES,
    ONE_TOOTH_CASES,
    SPECIFIC_CASES,
    UPPER_JAW_CASES,
)
from query_selector import select_price_service_route


def _route(q: str) -> dict:
    return select_price_service_route(
        q, client_id="demo", sid="price-parity", intent_override="price_lookup"
    )


@pytest.mark.parametrize("q", FULL_JAW_CASES + UPPER_JAW_CASES)
def test_jaw_group_router_and_composer_agree(q: str):
    assert _route(q).get("mode") == "group_overview"
    assert _composer_should_defer_jaw_scope_price(q) is True


@pytest.mark.parametrize("q", GENERIC_CASES)
def test_generic_router_and_composer_agree(q: str):
    pr = _route(q)
    assert pr.get("mode") == "group_overview"
    assert _composer_should_defer_group_price(q, pr) is True


@pytest.mark.parametrize("q,service_id", SPECIFIC_CASES)
def test_named_protocol_matches_and_composer_does_not_defer(q: str, service_id: str):
    assert _route(q).get("matched_service_id") == service_id
    assert _composer_should_defer_jaw_scope_price(q) is False


@pytest.mark.parametrize("q", ONE_TOOTH_CASES)
def test_one_tooth_composer_does_not_jaw_defer(q: str):
    assert _composer_should_defer_jaw_scope_price(q) is False
