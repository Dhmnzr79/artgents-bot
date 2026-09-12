from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from contracts.response_schema import TargetService
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs


DEMO_ROOT = Path("clients/demo")
TARGET_PATH = DEMO_ROOT / "target_response/service_catalog.json"
DOCTOR_PATH = DEMO_ROOT / "doctor_catalog.json"
MD_ROOT = DEMO_ROOT / "md"

SERVICE_IDS = (
    "tomography",
    "professional_whitening",
    "classic",
    "one_stage",
    "all_on_4",
    "all_on_6",
    "temporary_teeth",
    "implant_supported_prosthetics",
    "caries",
    "pulpitis",
    "teeth_treatment",
    "tooth_extraction",
    "periodontitis",
    "aligners",
    "bone_graft",
    "veneers",
    "zirconia_crowns",
    "clasp_dentures",
    "sinus_lift",
    "zygomatic_implants",
    "pterygoid_implants",
    "removable_dentures",
)

KNOWN_INACTIVE_SERVICE_IDS = ("braces",)

ALL_CATALOG_SERVICE_IDS = SERVICE_IDS + KNOWN_INACTIVE_SERVICE_IDS

INACTIVE_SERVICE_INVENTORY: dict[str, tuple[str, list[str], dict[str, object]]] = {
    "braces": ("orthodontics", [], {"mode": "context"}),
}

INVENTORY: dict[str, tuple[str, list[str], dict[str, object]]] = {
    "tomography": ("diagnostics", ["supporting"], {"mode": "direct"}),
    "professional_whitening": ("aesthetics", [], {"mode": "context"}),
    "classic": (
        "implantology",
        ["protocol"],
        {"mode": "scope", "extent": ["one_tooth", "few_teeth"]},
    ),
    "one_stage": (
        "implantology",
        ["protocol"],
        {
            "mode": "context",
            "extent": ["one_tooth", "few_teeth"],
            "stage": ["extraction_context"],
        },
    ),
    "all_on_4": (
        "implantology",
        ["protocol"],
        {"mode": "scope", "extent": ["full_arch"]},
    ),
    "all_on_6": (
        "implantology",
        ["protocol"],
        {"mode": "scope", "extent": ["full_arch"]},
    ),
    "temporary_teeth": (
        "prosthodontics",
        ["supporting"],
        {
            "mode": "direct",
            "stage": ["extraction_context", "implant_placed"],
        },
    ),
    "implant_supported_prosthetics": (
        "prosthodontics",
        [],
        {
            "mode": "scope",
            "extent": ["one_tooth", "few_teeth", "full_arch"],
            "stage": ["implant_placed"],
        },
    ),
    "caries": ("therapy", [], {"mode": "direct"}),
    "pulpitis": ("endodontics", [], {"mode": "direct"}),
    "teeth_treatment": ("therapy", [], {"mode": "context"}),
    "tooth_extraction": ("surgery", [], {"mode": "direct"}),
    "periodontitis": ("periodontology", [], {"mode": "direct"}),
    "aligners": ("orthodontics", [], {"mode": "context"}),
    "bone_graft": ("implantology", [], {"mode": "direct"}),
    "veneers": ("aesthetics", [], {"mode": "context"}),
    "zirconia_crowns": (
        "prosthodontics",
        [],
        {
            "mode": "scope",
            "extent": ["one_tooth", "few_teeth"],
            "stage": ["natural_tooth_present", "implant_placed"],
        },
    ),
    "clasp_dentures": (
        "prosthodontics",
        [],
        {
            "mode": "scope",
            "extent": ["few_teeth"],
            "stage": ["natural_tooth_present"],
        },
    ),
    "sinus_lift": (
        "implantology",
        [],
        {
            "mode": "context",
            "jaw": ["upper"],
            "reported_context": ["reported_bone_deficit"],
        },
    ),
    "zygomatic_implants": (
        "implantology",
        ["advanced_protocol"],
        {
            "mode": "context",
            "extent": ["full_arch"],
            "jaw": ["upper"],
            "reported_context": ["reported_bone_deficit"],
        },
    ),
    "pterygoid_implants": (
        "implantology",
        ["advanced_protocol"],
        {
            "mode": "context",
            "extent": ["few_teeth", "full_arch"],
            "jaw": ["upper"],
            "reported_context": ["reported_bone_deficit"],
        },
    ),
    "removable_dentures": (
        "prosthodontics",
        [],
        {"mode": "scope", "extent": ["few_teeth", "full_arch"]},
    ),
}

EXPECTED_OPTIONS: dict[str, list[dict[str, object]]] = {
    "sinus_lift": [
        {"option_id": "closed", "name": "Закрытый синус-лифтинг", "aliases": []},
        {"option_id": "open", "name": "Открытый синус-лифтинг", "aliases": []},
    ],
    "removable_dentures": [
        {
            "option_id": "partial",
            "name": "Частичный съёмный протез",
            "aliases": [],
            "selection": {"extent": ["few_teeth"]},
        },
        {
            "option_id": "full",
            "name": "Полный съёмный протез",
            "aliases": [],
            "selection": {"extent": ["full_arch"]},
        },
    ],
}


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_mapping_key:{key}")
        result[key] = value
    return result


def _load_json_mapping(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    if not isinstance(value, dict):
        raise TypeError("json_top_level_must_be_mapping")
    return value


def _load_target() -> tuple[dict[str, Any], dict[str, TargetService]]:
    raw = _load_json_mapping(TARGET_PATH)
    models = {
        service_id: TargetService.model_validate(record)
        for service_id, record in raw.items()
    }
    return raw, models


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_target_catalog_is_strict_complete_s1_wire_data() -> None:
    raw, models = _load_target()

    assert set(raw) == set(ALL_CATALOG_SERVICE_IDS)
    assert tuple(INVENTORY) == SERVICE_IDS
    assert tuple(INACTIVE_SERVICE_INVENTORY) == KNOWN_INACTIVE_SERVICE_IDS
    assert len(raw) == len(ALL_CATALOG_SERVICE_IDS)
    active_fields = {
        "name",
        "aliases",
        "family",
        "roles",
        "active",
        "selection",
        "options",
        "content_ref",
    }
    active_optional_fields = {"service_value_ref"}
    inactive_fields = {
        "name",
        "aliases",
        "family",
        "roles",
        "active",
        "selection",
        "options",
    }
    for service_id, record in raw.items():
        if service_id in KNOWN_INACTIVE_SERVICE_IDS:
            assert set(record) == inactive_fields
            assert record["active"] is False
        else:
            record_fields = set(record)
            assert active_fields <= record_fields
            assert record_fields <= active_fields | active_optional_fields
            assert record["active"] is True
        assert models[service_id].model_dump(exclude_none=True) == record


def test_duplicate_keys_are_rejected_at_nested_json_levels() -> None:
    duplicate = '{"service":{"name":"first","name":"second"}}'

    with pytest.raises(ValueError, match="duplicate_mapping_key:name"):
        json.loads(duplicate, object_pairs_hook=_reject_duplicate_pairs)


def test_family_roles_and_selection_match_normative_inventory() -> None:
    raw, _ = _load_target()

    actual = {
        service_id: (record["family"], record["roles"], record["selection"])
        for service_id, record in raw.items()
        if service_id not in KNOWN_INACTIVE_SERVICE_IDS
    }
    assert actual == INVENTORY
    inactive_actual = {
        service_id: (record["family"], record["roles"], record["selection"])
        for service_id, record in raw.items()
        if service_id in KNOWN_INACTIVE_SERVICE_IDS
    }
    assert inactive_actual == INACTIVE_SERVICE_INVENTORY


def test_only_semantic_options_exist_and_match_authored_source_labels() -> None:
    raw, _ = _load_target()
    actual = {
        service_id: record["options"]
        for service_id, record in raw.items()
        if record["options"]
    }

    assert actual == EXPECTED_OPTIONS
    for service_id, expected in EXPECTED_OPTIONS.items():
        offer_paths = sorted(
            (DEMO_ROOT / "target_response/pricebook/services").glob(f"{service_id}.*.json")
        )
        assert offer_paths, service_id
        brands = _load_json_mapping(DEMO_ROOT / "target_response/brand_catalog.json")["brands"]
        target_identity = [
            (option["option_id"], option["name"]) for option in expected
        ]
        offer_identity = []
        for path in offer_paths:
            offer = _load_json_mapping(path)
            option_id = offer.get("option_id")
            brand_id = offer.get("brand_id")
            if option_id:
                name = next(opt["name"] for opt in expected if opt["option_id"] == option_id)
                offer_identity.append((option_id, name))
            elif brand_id:
                offer_identity.append((brand_id, brands[brand_id]["canonical_name"]))
        assert sorted(target_identity) == sorted(offer_identity)
        assert all("brand" not in option and "brand_id" not in option for option in expected)


def test_content_refs_and_doctor_service_links_are_complete() -> None:
    _, services = _load_target()
    kb_refs = set(build_response_schema_kb_refs(MD_ROOT))
    without_content: list[str] = []
    for service_id, service in services.items():
        if service_id in KNOWN_INACTIVE_SERVICE_IDS:
            continue
        if service.content_ref is None:
            without_content.append(service_id)
            continue
        assert (MD_ROOT / service.content_ref).is_file()
        assert f"kb:{service.content_ref}#korotko" in kb_refs

    doctors = load_doctor_catalog(DOCTOR_PATH)
    doctor_service_ids = {
        service_id
        for doctor in doctors.doctors.values()
        for service_id in doctor.service_ids
    }
    assert without_content == []
    assert doctor_service_ids <= set(SERVICE_IDS)
    assert doctor_service_ids == set(SERVICE_IDS) - {"tomography"}


def test_real_sources_are_read_only_and_test_has_no_product_wiring() -> None:
    paths = [
        TARGET_PATH,
        DOCTOR_PATH,
        *sorted(MD_ROOT.glob("*.md")),
    ]
    before = {path: _sha256(path) for path in paths}

    _load_target()
    load_doctor_catalog(DOCTOR_PATH)
    build_response_schema_kb_refs(MD_ROOT)

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

    assert imported_modules.isdisjoint(
        {
            "app",
            "doctors_lookup",
            "core.pricebook_loader",
            "orchestration",
        }
    )
    assert called_attributes.isdisjoint(
        {"mkdir", "open", "touch", "unlink", "write_bytes", "write_text"}
    )
