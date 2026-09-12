from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, get_args

import yaml

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import (
    MarketingScenario,
    ResponseSchemaBundle,
    TargetMarketingPolicy,
)
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
CURRENT_MARKETING = Path(
    "docs/evidence/client_pack/fixtures/demo_legacy_marketing.yaml"
)
CURRENT_TONE = DEMO_ROOT / "tone.yaml"
TARGET_OFFERS = TARGET_ROOT / "pricebook/services"
CURRENT_PRICE_SERVICES = TARGET_OFFERS
MD_ROOT = DEMO_ROOT / "md"
TARGET_SERVICES = TARGET_ROOT / "service_catalog.json"
TARGET_BRANDS = TARGET_ROOT / "brand_catalog.json"
TARGET_FACTS = TARGET_ROOT / "pricebook/facts.json"
TARGET_STRATEGY = TARGET_ROOT / "clinic_strategy.yaml"
DOCTOR_CATALOG = DEMO_ROOT / "doctor_catalog.json"
AUDIT_DOC = Path("docs/MARKETING_TARGET_MIGRATION_AUDIT.md")

EXPECTED_MARKETING_KEYS = [
    "classic",
    "one_stage",
    "all_on_4",
    "all_on_6",
    "temporary_teeth",
    "benefits",
    "what_included",
    "sinus_lift",
    "pterygoid_implants",
    "zygomatic_implants",
    "teeth_whitening",
    "tooth_extraction",
    "periodontitis",
]
EXPECTED_FACT_IDS = [
    "tax_deduction",
    "installment_12",
    "free_implant_consult",
    "implant_warranty",
    "implant_same_day_discount",
    "professional_whitening_discount",
    "payment_stages",
    "fixed_price",
    "sv_3d_diagnocat",
    "sv_aprf",
]
EXPECTED_PROMO_IDS = [
    "free_implant_consult",
    "implant_same_day_discount",
    "professional_whitening_discount",
]
EXPECTED_TONE_CTA_KEYS = [
    "booking",
    "consult",
    "callback",
    "plan",
    "price",
    "doctor",
]
EXPECTED_SCENARIOS = (
    "pain_fear",
    "cost",
    "time",
    "doctor_trust",
    "result_reliability",
)
CANDIDATE_REFS = {
    "pain_fear": [
        "kb:implantation__faq__pain.md#korotko",
        "kb:implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut",
    ],
    "cost": [
        "fact:installment_12",
        "fact:implant_same_day_discount",
        "fact:tax_deduction",
        "kb:implantation__faq__cost.md#kak-sdelat-implantatsiyu-dostupnee",
    ],
    "time": [
        "kb:implantation__faq__duration.md#korotko",
        "kb:implantation__faq__duration.md#mozhno-li-uskorit-implantatsiyu",
        "kb:implantation__faq__tooth_one_day.md#korotko",
        "kb:implantation__info__steps.md#korotko",
    ],
    "doctor_trust": [
        "doctor:doctors__doctor__volkov",
        "doctor:doctors__doctor__orlov",
        "kb:doctors__doctor__overview.md#korotko",
        "kb:clinic__info__technology.md#korotko",
    ],
    "result_reliability": [
        "fact:implant_warranty",
        "kb:implantation__faq__osseointegration.md#korotko",
        "kb:implantation__faq__osseointegration.md#ot-chego-zavisit-prizhivlenie",
        "kb:clinic__info__warranty.md#korotko",
    ],
}


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("yaml_top_level_must_be_mapping")
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("json_top_level_must_be_mapping")
    return raw


def _target_offer_records() -> list[dict[str, Any]]:
    return [_load_json(path) for path in sorted(TARGET_OFFERS.glob("*.json"))]


def _candidate_marketing() -> dict[str, Any]:
    return {
        "version": 1,
        "limits": {
            "max_marketing_facts_per_turn": 3,
            "max_amplifiers_per_turn": 2,
            "max_scenarios_per_turn": 2,
        },
        "initial_commercial_blocks": {},
        "scenario_rules": {
            scenario: {
                "ordered_amplifier_refs": refs,
                "allowed_semantic_contexts": ["audit_candidate_only"],
            }
            for scenario, refs in CANDIDATE_REFS.items()
        },
        "cta_contexts": {"default": "audit_validation_only"},
    }


def _candidate_bundle() -> ResponseSchemaBundle:
    return ResponseSchemaBundle.model_validate(
        {
            "services": _load_json(TARGET_SERVICES),
            "brands": _load_json(TARGET_BRANDS),
            "offers": _target_offer_records(),
            "facts": _load_json(TARGET_FACTS),
            "strategy": _load_yaml(TARGET_STRATEGY),
            "marketing": _candidate_marketing(),
        }
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_marketing_exact_inventory_and_service_key_split() -> None:
    marketing = _load_yaml(CURRENT_MARKETING)
    entries = marketing["service_marketing"]
    target_service_ids = set(_load_json(TARGET_SERVICES))

    assert marketing["version"] == 1
    assert marketing["blocked_aspects_for_promo"] == [
        "pain",
        "contraindications",
        "safety",
        "complications",
    ]
    assert list(entries) == EXPECTED_MARKETING_KEYS
    assert sum(len(entry.get("clinic_proof", [])) for entry in entries.values()) == 11
    assert sum(len(entry.get("consult_reasons", [])) for entry in entries.values()) == 13
    assert Counter(entry["primary_cta_key"] for entry in entries.values()) == {
        "doctor": 10,
        "consult": 3,
    }
    assert [key for key in entries if key in target_service_ids] == [
        "classic",
        "one_stage",
        "all_on_4",
        "all_on_6",
        "temporary_teeth",
        "sinus_lift",
        "pterygoid_implants",
        "zygomatic_implants",
        "tooth_extraction",
        "periodontitis",
    ]
    assert [key for key in entries if key not in target_service_ids] == [
        "benefits",
        "what_included",
        "teeth_whitening",
    ]
    assert "professional_whitening" in target_service_ids


def test_all_24_free_strings_have_zero_exact_md_matches() -> None:
    entries = _load_yaml(CURRENT_MARKETING)["service_marketing"]
    free_strings = [
        value
        for entry in entries.values()
        for field in ("clinic_proof", "consult_reasons")
        for value in entry.get(field, [])
    ]
    md_sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(MD_ROOT.glob("*.md"))
    }

    assert len(free_strings) == len(set(free_strings)) == 24
    assert {
        (value, path_name)
        for value in free_strings
        for path_name, source in md_sources.items()
        if value in source
    } == set()


def test_promo_rules_are_already_owned_by_target_facts() -> None:
    promo_rules = _load_yaml(CURRENT_MARKETING)["promo_rules"]
    facts = _load_json(TARGET_FACTS)

    assert list(promo_rules) == EXPECTED_PROMO_IDS
    assert [rule["fact_ref"] for rule in promo_rules.values()] == EXPECTED_PROMO_IDS
    assert list(facts) == EXPECTED_FACT_IDS
    assert [
        promo_id
        for promo_id, rule in promo_rules.items()
        if rule.get("cta_key") is not None
    ] == ["free_implant_consult"]
    assert promo_rules["free_implant_consult"]["cta_key"] == "consult"

    list_order_differences: list[str] = []
    for promo_id, rule in promo_rules.items():
        fact = facts[promo_id]
        assert rule["active"] == fact["active"] is True
        if promo_id == "professional_whitening_discount":
            assert fact.get("active_until") == "2026-11-30"
        else:
            assert rule.get("active_until") == fact.get("active_until")
        rule_ids = rule["allowed_service_ids"]
        fact_ids = fact["allowed_service_ids"]
        assert set(rule_ids) <= set(fact_ids)
        fact_subset = [service_id for service_id in fact_ids if service_id in set(rule_ids)]
        if rule_ids != fact_subset:
            list_order_differences.append(promo_id)
        assert set(rule) - {
            "active",
            "active_until",
            "fact_ref",
            "allowed_service_ids",
            "cta_key",
        } == {"allowed_routes", "allowed_aspects", "blocked_aspects"}

    assert list_order_differences == [
        "free_implant_consult",
        "implant_same_day_discount",
    ]


def test_exact_cta_sources_expose_unresolved_legacy_key() -> None:
    tone_keys = [
        variant["key"]
        for variant in _load_yaml(CURRENT_TONE)["lead"]["cta_variants"]
    ]
    md_keys: list[str] = []
    for path in sorted(MD_ROOT.glob("*.md")):
        matches = re.findall(
            r"^cta_key:\s*([^\s]+)\s*$",
            path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        assert len(matches) == 1
        md_keys.extend(matches)
    marketing_keys = [
        entry["primary_cta_key"]
        for entry in _load_yaml(CURRENT_MARKETING)["service_marketing"].values()
    ]

    assert tone_keys == EXPECTED_TONE_CTA_KEYS
    assert len(md_keys) == 54
    assert Counter(md_keys) == {
        "booking": 6,
        "callback": 1,
        "consult": 13,
        "doctor": 6,
        "plan": 26,
        "price": 2,
    }
    assert len(list(TARGET_OFFERS.glob("*.json"))) == 32
    assert Counter(marketing_keys) == {"doctor": 10, "consult": 3}
    assert "ct_consultation" not in tone_keys


def test_s17_historical_absence_and_frozen_contract_boundary_are_recorded() -> None:
    audit = AUDIT_DOC.read_text(encoding="utf-8")
    assert "S2 real demo load на момент S17 fail-closed" in audit
    assert "required_path_missing marketing.yaml" in audit

    policy = TargetMarketingPolicy.model_validate(_candidate_marketing())
    assert get_args(MarketingScenario) == EXPECTED_SCENARIOS
    assert policy.limits.model_dump() == {
        "max_marketing_facts_per_turn": 2,
        "max_amplifiers_per_turn": 2,
        "max_scenarios_per_turn": 2,
        "service": {"max_promos_per_turn": 2, "max_amplifiers_per_turn": 2},
        "price": {"max_promos_per_turn": 2, "max_amplifiers_per_turn": 2},
    }
    assert list(policy.scenario_rules) == list(EXPECTED_SCENARIOS)
    assert set(TargetMarketingPolicy.model_fields) == {
        "version",
        "limits",
        "initial_commercial_blocks",
        "service_automatic_commercial",
        "ordered_amplifier_refs",
        "priority_service_promos",
        "promotion_overview",
        "scenario_rules",
        "cta_contexts",
    }
    assert "cadence" not in TargetMarketingPolicy.model_fields
    assert policy.cta_contexts == {"default": "audit_validation_only"}


def test_candidate_refs_exist_through_their_exact_owner_boundaries() -> None:
    audit = AUDIT_DOC.read_text(encoding="utf-8")
    for scenario, refs in CANDIDATE_REFS.items():
        assert f"### `{scenario}`" in audit
        for ref in refs:
            assert f"`{ref}`" in audit

    bundle = _candidate_bundle()
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    doctor_refs = build_doctor_source_refs(doctors)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=doctor_refs,
    )

    assert validate_response_schema_external_refs(bundle, external_index) is None
    assert {
        ref.removeprefix("fact:")
        for refs in CANDIDATE_REFS.values()
        for ref in refs
        if ref.startswith("fact:")
    } <= set(bundle.facts)
    assert {
        ref
        for refs in CANDIDATE_REFS.values()
        for ref in refs
        if ref.startswith("doctor:")
    } <= set(doctor_refs)
    assert {
        ref
        for refs in CANDIDATE_REFS.values()
        for ref in refs
        if ref.startswith("kb:")
    } <= set(kb_refs)


def test_audit_is_read_only_and_has_no_new_product_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _load_yaml(CURRENT_MARKETING)
    _candidate_bundle()
    build_response_schema_kb_refs(MD_ROOT)
    load_doctor_catalog(DOCTOR_CATALOG)

    assert {path: _sha256(path) for path in paths} == before

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
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
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not any(
        module.startswith(
            ("app", "config", "handlers", "orchestration", "routes", "telegram")
        )
        for module in imported_modules
    )
    assert not (
        {"write_text", "write_bytes", "unlink", "rename", "replace", "mkdir"}
        & called_attributes
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
