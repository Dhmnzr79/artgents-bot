"""Stage 5.1B authored alternatives loader validation and legacy separation."""

from __future__ import annotations

import config

from core.clinic_policies_loader import (
    find_service_alternative,
    load_authored_service_alternatives,
    load_clinic_policies,
)
from core.service_availability_presentation import load_authored_alternatives
from core.target_client_data import load_target_client_data


def test_demo_canonical_braces_to_aligners_row_loads() -> None:
    rows = load_authored_service_alternatives("demo")
    assert len(rows) == 1
    row = rows[0]
    assert row.requested_service_id == "braces"
    assert row.alternative_service_ids == ("aligners",)
    assert "элайнер" in row.approved_text.lower()


def test_authored_loader_ignores_legacy_keyword_rows() -> None:
    policies = load_clinic_policies("demo")
    assert policies is not None
    legacy = [alt for alt in policies.service_alternatives if alt.match_keywords]
    assert legacy
    authored_ids = {row.requested_service_id for row in load_authored_service_alternatives("demo")}
    assert authored_ids == {"braces"}


def test_load_authored_alternatives_validates_active_alternatives_only() -> None:
    bundle = load_target_client_data("demo").bundle
    rows = load_authored_alternatives(
        "demo",
        requested_service_id="braces",
        bundle=bundle,
    )
    assert len(rows) == 1
    assert rows[0].alternative_service_ids == ("aligners",)


def test_legacy_keyword_path_still_available_when_sales_one_plus_off() -> None:
    assert config.SALES_ONE_PLUS_ON is False
    alt = find_service_alternative("А брекеты делаете?", "demo")
    assert alt is not None
    assert "элайнер" in alt.note.lower()
