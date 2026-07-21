from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import yaml

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.marketing_cta_refs import MarketingCtaIndex, validate_marketing_cta_refs
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG = DEMO_ROOT / "doctor_catalog.json"
TONE = DEMO_ROOT / "tone.yaml"
CURRENT_MARKETING = DEMO_ROOT / "marketing.yaml"
CURRENT_PLAYBOOK = DEMO_ROOT / "patient_playbook.yaml"

EXPECTED_INITIAL_REFS = [
    "fact:free_implant_consult",
    "fact:installment_12",
    "fact:implant_same_day_discount",
    "fact:professional_whitening_discount",
]
EXPECTED_SCENARIOS = {
    "pain_fear": {
        "ordered_amplifier_refs": [
            "kb:implantation__faq__pain.md#korotko",
            "kb:implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut",
        ],
        "allowed_semantic_contexts": ["service"],
    },
    "cost": {
        "ordered_amplifier_refs": [
            "fact:installment_12",
            "fact:implant_same_day_discount",
            "fact:tax_deduction",
            "kb:implantation__faq__cost.md#kak-sdelat-implantatsiyu-dostupnee",
            "kb:clinic__info__payment_terms.md#korotko",
        ],
        "allowed_semantic_contexts": ["service", "price"],
    },
    "time": {
        "ordered_amplifier_refs": [
            "kb:implantation__faq__duration.md#korotko",
            "kb:implantation__faq__duration.md#mozhno-li-uskorit-implantatsiyu",
            "kb:implantation__faq__tooth_one_day.md#korotko",
            "kb:implantation__info__steps.md#korotko",
        ],
        "allowed_semantic_contexts": ["service"],
    },
    "doctor_trust": {
        "ordered_amplifier_refs": [
            "doctor:doctors__doctor__volkov",
            "doctor:doctors__doctor__orlov",
            "kb:doctors__doctor__overview.md#korotko",
            "kb:clinic__info__technology.md#korotko",
        ],
        "allowed_semantic_contexts": ["service", "doctors"],
    },
    "result_reliability": {
        "ordered_amplifier_refs": [
            "fact:implant_warranty",
            "kb:implantation__faq__osseointegration.md#korotko",
            "kb:implantation__faq__osseointegration.md#ot-chego-zavisit-prizhivlenie",
            "kb:clinic__info__warranty.md#korotko",
        ],
        "allowed_semantic_contexts": ["service"],
    },
}
EXPECTED_CURRENT_HASHES = {
    CURRENT_MARKETING: "e958fcd14be057a3e9867ec133175f4024f90178fbfedec8d3d1421f8e2c1eae",
    TONE: "cec4449df24e7e322b334c7365f839280dc6aa58e423615513c5872dc8f2ada5",
    CURRENT_PLAYBOOK: "c015633bcc5465af17faeda29937f4ad64c44a54724266970355dc8391f53c7e",
}
EXPECTED_PREEXISTING_TARGET_DIGEST = (
    "7ed9d417453a4181b67df11160089c1ff3bba145ed4f499f2de8d585fd17c73c"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("yaml_top_level_must_be_mapping")
    return raw


def _tone_cta_keys() -> tuple[str, ...]:
    tone = _load_yaml(TONE)
    keys = tuple(variant["key"] for variant in tone["lead"]["cta_variants"])
    if len(keys) != len(set(keys)):
        raise ValueError("tone_cta_key_duplicate")
    return keys


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preexisting_target_digest() -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in TARGET_ROOT.rglob("*")
        if path.is_file() and path.name != "marketing.yaml"
    )
    assert len(paths) == 35
    for path in paths:
        digest.update(path.relative_to(TARGET_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_real_demo_target_pack_loads_with_exact_marketing_policy() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    policy = bundle.marketing

    assert policy.version == 1
    assert policy.limits.model_dump() == {
        "max_marketing_facts_per_turn": 3,
        "max_amplifiers_per_turn": 2,
        "max_scenarios_per_turn": 2,
    }
    assert list(policy.initial_commercial_blocks) == ["service"]
    assert policy.initial_commercial_blocks["service"].ordered_fact_refs == (
        EXPECTED_INITIAL_REFS
    )
    assert list(policy.scenario_rules) == list(EXPECTED_SCENARIOS)
    assert {
        scenario: rule.model_dump()
        for scenario, rule in policy.scenario_rules.items()
    } == EXPECTED_SCENARIOS
    assert policy.cta_contexts == {
        "service": "plan",
        "price": "price",
        "doctors": "doctor",
        "default": "callback",
    }
    assert len(bundle.services) == 21
    assert len(bundle.offers) == 31
    assert len(bundle.facts) == 6


def test_real_demo_source_and_cta_owner_boundaries_cover_every_policy_ref() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )

    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    doctor_refs = build_doctor_source_refs(doctors)
    assert validate_response_schema_external_refs(
        bundle,
        ResponseSchemaExternalIndex(kb_refs=kb_refs, doctor_refs=doctor_refs),
    ) is None

    fact_refs = {
        ref
        for block in bundle.marketing.initial_commercial_blocks.values()
        for ref in block.ordered_fact_refs
    }
    fact_refs.update(
        ref
        for rule in bundle.marketing.scenario_rules.values()
        for ref in rule.ordered_amplifier_refs
        if ref.startswith("fact:")
    )
    assert {ref.removeprefix("fact:") for ref in fact_refs} <= set(bundle.facts)

    cta_keys = _tone_cta_keys()
    assert cta_keys == ("booking", "consult", "callback", "plan", "price", "doctor")
    assert validate_marketing_cta_refs(
        bundle.marketing,
        MarketingCtaIndex(cta_keys=cta_keys),
    ) is None


def test_materialization_preserves_current_and_preexisting_target_sources() -> None:
    paths = sorted(
        {
            *EXPECTED_CURRENT_HASHES,
            *(path for path in TARGET_ROOT.rglob("*") if path.is_file()),
            DOCTOR_CATALOG,
        }
    )
    before = {path: _sha256(path) for path in paths}

    load_response_schema_bundle(TARGET_ROOT)
    build_response_schema_kb_refs(MD_ROOT)
    load_doctor_catalog(DOCTOR_CATALOG)
    _tone_cta_keys()

    assert {path: _sha256(path) for path in paths} == before
    assert {path: _sha256(path) for path in EXPECTED_CURRENT_HASHES} == (
        EXPECTED_CURRENT_HASHES
    )
    assert _preexisting_target_digest() == EXPECTED_PREEXISTING_TARGET_DIGEST


def test_acceptance_has_no_product_runtime_writes_skip_xfail_or_live_dependencies() -> None:
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
