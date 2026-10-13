"""Clinic policies loader tests for Stage 5.1B authored alternatives."""

from __future__ import annotations

import config
import pytest

from core import clinic_policies_loader as loader
from core.clinic_policies_loader import (
    clinic_business_policy_keys,
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


def test_demo_has_no_parallel_keyword_alternative_rows() -> None:
    bundle = load_clinic_policies("demo")
    assert bundle is not None
    keyword_rows = [alt for alt in bundle.service_alternatives if alt.match_keywords]
    assert keyword_rows == []
    authored = load_authored_service_alternatives("demo")
    assert all(not hasattr(row, "match_keywords") for row in authored)


def test_demo_has_no_legacy_keyword_alternative_with_sales_one_plus_off() -> None:
    assert config.SALES_ONE_PLUS_ON is False
    alt = find_service_alternative("ставите брекеты?", "demo")
    assert alt is None


def test_demo_business_policy_keys_include_oms_dms_pediatric() -> None:
    keys = clinic_business_policy_keys("demo")
    assert "no_pediatric_dentistry" in keys
    assert "no_oms" in keys
    assert "no_dms" in keys


@pytest.mark.parametrize("body", [
    "policies: []\n",
    "policies: {}\n",
    "policies:\n  no_oms: null\n",
    "policies:\n  no_oms:\n    triggers: [омс]\n    answer: ''\n",
    "policies:\n  no_oms:\n    triggers: []\n    text_ref: policy.md#rule\n",
    "policies:\n  no_oms:\n    triggers: [омс]\n    text_ref: policy.md#rule\n  no_dms: null\n",
    "policies:\n  no_oms:\n    triggers: [12]\n    text_ref: policy.md#rule\n",
    "policies: [unterminated\n",
])
def test_d1r_boundary_rejects_raw_malformed_policy_rows(tmp_path, monkeypatch, body) -> None:
    path = tmp_path / "clinic_policies.yaml"
    path.write_text(body, encoding="utf-8")
    (tmp_path / "md").mkdir()
    (tmp_path / "md/policy.md").write_text("### Правило {#rule}\nНет ОМС", encoding="utf-8")
    monkeypatch.setattr(loader, "_policies_path", lambda _cid: str(path))
    loader._CACHE.pop("demo", None)
    with pytest.raises(ValueError):
        loader.validate_raw_clinic_business_policies("demo")
    loader._CACHE.pop("demo", None)
