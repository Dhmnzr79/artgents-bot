"""C2d-D1: seven approved clinic strategy rules without legacy patient_playbook.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.test_demo_target_clinic_strategy import EXPECTED_RULES

TARGET_STRATEGY = Path("clients/demo/target_response/clinic_strategy.yaml")

# Intentionally not migrated from deleted patient_playbook.yaml (current-only leftovers).
DROPPED_LEGACY_RULE_IDS = frozenset({"bone_deficit_solution"})
DROPPED_LEGACY_SECTIONS = frozenset({"patient_situations"})


def test_clinic_strategy_has_seven_approved_rules_only() -> None:
    raw = yaml.safe_load(TARGET_STRATEGY.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    rules = raw.get("rules")
    assert isinstance(rules, list)
    assert [rule["id"] for rule in rules] == [rule["id"] for rule in EXPECTED_RULES]
    assert DROPPED_LEGACY_RULE_IDS.isdisjoint({rule["id"] for rule in rules})
    assert DROPPED_LEGACY_SECTIONS.isdisjoint(raw.keys())


def test_clinic_strategy_matches_expected_priorities_and_caps() -> None:
    raw = yaml.safe_load(TARGET_STRATEGY.read_text(encoding="utf-8"))
    by_id = {rule["id"]: rule for rule in raw["rules"]}
    for expected in EXPECTED_RULES:
        actual = by_id[expected["id"]]
        assert actual["match"] == expected["match"]
        assert actual["max_options"] == expected["max_options"]
        assert actual["service_priorities"] == expected["service_priorities"]
        assert actual.get("offer_priorities", {}) == expected.get("offer_priorities", {})


def test_legacy_patient_playbook_yaml_removed() -> None:
    assert not Path("clients/demo/patient_playbook.yaml").exists()
