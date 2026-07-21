from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetClinicStrategy,
    TargetStrategyMatch,
)
from core.response_strategy import resolve_target_strategy


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
TARGET_STRATEGY = TARGET_ROOT / "clinic_strategy.yaml"
TARGET_SERVICES = TARGET_ROOT / "service_catalog.json"
TARGET_BRANDS = TARGET_ROOT / "brand_catalog.json"
TARGET_FACTS = TARGET_ROOT / "pricebook/facts.json"
TARGET_OFFERS = TARGET_ROOT / "pricebook/services"
CURRENT_PLAYBOOK = DEMO_ROOT / "patient_playbook.yaml"
CURRENT_OFFERS = DEMO_ROOT / "pricebook/services"

EXPECTED_RULES = [
    {
        "id": "existing_implant_prosthetic_stage",
        "match": {"stage": "implant_placed"},
        "max_options": 3,
        "service_priorities": {
            "implant_supported_prosthetics": 100,
            "zirconia_crowns": 60,
            "temporary_teeth": 40,
        },
        "offer_priorities": {},
    },
    {
        "id": "extraction_then_implant_restore",
        "match": {"extent": "one_tooth", "stage": "extraction_context"},
        "max_options": 3,
        "service_priorities": {
            "one_stage": 100,
            "classic": 80,
            "tooth_extraction": 40,
        },
        "offer_priorities": {},
    },
    {
        "id": "upper_full_arch_with_bone_deficit",
        "match": {
            "extent": "full_arch",
            "jaw": "upper",
            "reported_context": "reported_bone_deficit",
        },
        "max_options": 3,
        "service_priorities": {
            "zygomatic_implants": 100,
            "all_on_4": 90,
            "all_on_6": 80,
            "removable_dentures": 40,
        },
        "offer_priorities": {},
    },
    {
        "id": "upper_full_arch_restore",
        "match": {"extent": "full_arch", "jaw": "upper"},
        "max_options": 3,
        "service_priorities": {
            "all_on_4": 100,
            "all_on_6": 90,
            "zygomatic_implants": 70,
            "removable_dentures": 40,
        },
        "offer_priorities": {},
    },
    {
        "id": "full_arch_restore",
        "match": {"extent": "full_arch"},
        "max_options": 3,
        "service_priorities": {
            "all_on_4": 100,
            "all_on_6": 90,
            "removable_dentures": 50,
            "zygomatic_implants": 40,
        },
        "offer_priorities": {},
    },
    {
        "id": "one_tooth_restore",
        "match": {"extent": "one_tooth"},
        "max_options": 2,
        "service_priorities": {"classic": 100, "one_stage": 80},
        "offer_priorities": {},
    },
    {
        "id": "few_teeth_restore",
        "match": {"extent": "few_teeth"},
        "max_options": 3,
        "service_priorities": {
            "implant_supported_prosthetics": 100,
            "classic": 80,
            "clasp_dentures": 50,
            "removable_dentures": 40,
        },
        "offer_priorities": {},
    },
]

EXPECTED_RECOMMENDED_OFFERS = {
    "all_on_4.jaw.impro",
    "all_on_6.jaw.impro",
    "classic.one_tooth.impro",
    "one_stage.one_tooth.impro",
    "removable_dentures.jaw.partial",
    "sinus_lift.one_site.closed",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate_mapping_key:{key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(value, dict):
        raise TypeError("yaml_top_level_must_be_mapping")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("json_top_level_must_be_mapping")
    return value


def _target_offer_records() -> list[dict[str, Any]]:
    return [_load_json(path) for path in sorted(TARGET_OFFERS.glob("*.json"))]


def _strategy() -> TargetClinicStrategy:
    return TargetClinicStrategy.model_validate(_load_yaml(TARGET_STRATEGY))


def _real_bundle() -> ResponseSchemaBundle:
    return ResponseSchemaBundle.model_validate(
        {
            "services": _load_json(TARGET_SERVICES),
            "brands": _load_json(TARGET_BRANDS),
            "offers": _target_offer_records(),
            "facts": _load_json(TARGET_FACTS),
            "strategy": _load_yaml(TARGET_STRATEGY),
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 0,
                    "max_amplifiers_per_turn": 0,
                    "max_scenarios_per_turn": 0,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": {},
                "cta_contexts": {"default": "validation_only"},
            },
        }
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_strategy_is_exact_strict_target_wire_data() -> None:
    raw = _load_yaml(TARGET_STRATEGY)

    assert raw == {
        "version": 1,
        "default_max_options": 3,
        "default_service_priorities": {},
        "default_offer_priorities": {
            offer_id: 1 for offer_id in sorted(EXPECTED_RECOMMENDED_OFFERS)
        },
        "rules": EXPECTED_RULES,
    }
    assert (
        TargetClinicStrategy.model_validate(raw).model_dump(exclude_none=True) == raw
    )
    assert _real_bundle().strategy.model_dump(exclude_none=True) == raw


def test_seven_rules_preserve_current_priorities_and_approved_caps() -> None:
    target_rules = {rule["id"]: rule for rule in _load_yaml(TARGET_STRATEGY)["rules"]}
    current_rules = {
        rule["id"]: rule for rule in _load_yaml(CURRENT_PLAYBOOK)["rules"]
    }

    assert list(target_rules) == [rule["id"] for rule in EXPECTED_RULES]
    assert set(current_rules) - set(target_rules) == {"bone_deficit_solution"}
    assert "patient_situations" not in _load_yaml(TARGET_STRATEGY)

    changed_from_four = 0
    for rule_id, target in target_rules.items():
        current = current_rules[rule_id]
        assert target["service_priorities"] == {
            option["service_id"]: option["priority"]
            for option in current["options"]
        }
        if current["max_options"] == 4:
            changed_from_four += 1
            assert target["max_options"] == 3
        else:
            assert target["max_options"] == current["max_options"]

    assert changed_from_four == 4


def test_exact_positive_recommendations_become_equal_baseline_priority() -> None:
    recommended: set[str] = set()
    all_current_variants: set[str] = set()
    for path in sorted(CURRENT_OFFERS.glob("*.json")):
        for variant in _load_json(path).get("variants", []):
            all_current_variants.add(variant["offer_id"])
            if variant.get("recommended") is True:
                recommended.add(variant["offer_id"])

    priorities = _load_yaml(TARGET_STRATEGY)["default_offer_priorities"]
    target_offer_ids = {offer["offer_id"] for offer in _target_offer_records()}

    assert recommended == EXPECTED_RECOMMENDED_OFFERS
    assert priorities == {offer_id: 1 for offer_id in sorted(recommended)}
    assert set(priorities) <= target_offer_ids
    assert not ((all_current_variants - recommended) & set(priorities))


def test_real_contexts_resolve_specific_rules_before_general_rules() -> None:
    strategy = _strategy()

    installed = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(
            extent="full_arch",
            stage="implant_placed",
            jaw="upper",
            reported_context="reported_bone_deficit",
        ),
        service_ids=[
            "temporary_teeth",
            "implant_supported_prosthetics",
            "zirconia_crowns",
        ],
    )
    extraction = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(
            extent="one_tooth",
            stage="extraction_context",
            reported_context="reported_bone_deficit",
        ),
        service_ids=["tooth_extraction", "classic", "one_stage"],
    )
    full_arch_extraction = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(extent="full_arch", stage="extraction_context"),
        service_ids=["removable_dentures", "all_on_6", "all_on_4"],
    )
    upper_bone = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(
            extent="full_arch",
            jaw="upper",
            reported_context="reported_bone_deficit",
        ),
        service_ids=[
            "removable_dentures",
            "all_on_6",
            "all_on_4",
            "zygomatic_implants",
        ],
    )

    assert installed.matched_rule_id == "existing_implant_prosthetic_stage"
    assert installed.service_ids[0] == "implant_supported_prosthetics"
    assert extraction.matched_rule_id == "extraction_then_implant_restore"
    assert extraction.service_ids == ("one_stage", "classic", "tooth_extraction")
    assert full_arch_extraction.matched_rule_id == "full_arch_restore"
    assert full_arch_extraction.service_ids == (
        "all_on_4",
        "all_on_6",
        "removable_dentures",
    )
    assert upper_bone.matched_rule_id == "upper_full_arch_with_bone_deficit"
    assert upper_bone.service_ids == (
        "zygomatic_implants",
        "all_on_4",
        "all_on_6",
    )


def test_real_shortlists_cap_without_adding_candidates() -> None:
    strategy = _strategy()

    few_teeth = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(extent="few_teeth"),
        service_ids=[
            "removable_dentures",
            "clasp_dentures",
            "classic",
            "implant_supported_prosthetics",
        ],
    )
    offers = resolve_target_strategy(
        strategy,
        TargetStrategyMatch(),
        offer_ids=["all_on_4.jaw.nobel", "all_on_4.jaw.impro"],
    )

    assert few_teeth.service_ids == (
        "implant_supported_prosthetics",
        "classic",
        "clasp_dentures",
    )
    assert "removable_dentures" not in few_teeth.service_ids
    assert offers.offer_ids == (
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    assert set(offers.offer_ids) == {
        "all_on_4.jaw.nobel",
        "all_on_4.jaw.impro",
    }


def test_sources_are_read_only_and_test_has_no_product_wiring() -> None:
    paths = [
        CURRENT_PLAYBOOK,
        TARGET_SERVICES,
        TARGET_BRANDS,
        TARGET_FACTS,
        *sorted(CURRENT_OFFERS.glob("*.json")),
        *sorted(TARGET_OFFERS.glob("*.json")),
    ]
    before = {path: _sha256(path) for path in paths}

    _strategy()
    _real_bundle()

    assert {path: _sha256(path) for path in paths} == before

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module.startswith(
            (
                "app",
                "config",
                "handlers",
                "orchestration",
                "routes",
                "telegram",
            )
        )
        for module in imported_modules
    )
