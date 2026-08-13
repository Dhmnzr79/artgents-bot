"""Clinic policies loader tests for Stage 5.1B authored alternatives."""

from __future__ import annotations

import config

from core.clinic_policies_loader import (
    find_service_alternative,
    load_authored_service_alternatives,
    load_clinic_policies,
)


def test_load_authored_service_alternatives_demo_canonical_row() -> None:
    rows = load_authored_service_alternatives("demo")
    assert len(rows) == 1
    row = rows[0]
    assert row.requested_service_id == "braces"
    assert row.alternative_service_ids == ("aligners",)
    assert row.approved_text.strip()


def test_legacy_keyword_rows_remain_in_policy_bundle_only() -> None:
    bundle = load_clinic_policies("demo")
    assert bundle is not None
    keyword_rows = [alt for alt in bundle.service_alternatives if alt.match_keywords]
    assert keyword_rows
    authored = load_authored_service_alternatives("demo")
    assert all(not hasattr(row, "match_keywords") for row in authored)


def test_legacy_keyword_helper_still_works_with_sales_one_plus_off() -> None:
    assert config.SALES_ONE_PLUS_ON is False
    alt = find_service_alternative("ставите брекеты?", "demo")
    assert alt is not None
    assert alt.suggest_ref
