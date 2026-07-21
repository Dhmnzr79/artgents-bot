from __future__ import annotations

import ast
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs


_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _ROOT / "clients" / "demo"
_MD_ROOT = _DEMO_ROOT / "md"
_DOCTOR_CATALOG_PATH = _DEMO_ROOT / "doctor_catalog.json"
_SERVICE_CATALOG_PATH = _DEMO_ROOT / "service_catalog.json"
_OVERVIEW_NAME = "doctors__doctor__overview.md"
_DOCTOR_FIELDS = {
    "experience_years",
    "name",
    "position",
    "profile_ref",
    "service_ids",
}
_FORBIDDEN_FIELDS = {
    "active",
    "aliases",
    "availability",
    "card",
    "certificates",
    "cta",
    "education",
    "photo",
    "priority",
    "rating",
    "roles",
    "schedule",
    "slots",
    "ui",
}

_EXPECTED_CATALOG = {
    "doctors": {
        "doctors__doctor__fedorova": {
            "name": "Фёдорова Ирина Михайловна",
            "position": "Врач-стоматолог-терапевт",
            "experience_years": 16,
            "service_ids": [
                "caries",
                "pulpitis",
                "teeth_treatment",
                "professional_whitening",
                "veneers",
                "zirconia_crowns",
            ],
            "profile_ref": "kb:doctors__doctor__fedorova.md#korotko",
        },
        "doctors__doctor__grigoriev": {
            "name": "Григорьев Павел Игоревич",
            "position": "Врач-пародонтолог",
            "experience_years": 12,
            "service_ids": ["periodontitis"],
            "profile_ref": "kb:doctors__doctor__grigoriev.md#korotko",
        },
        "doctors__doctor__kuznetsov": {
            "name": "Кузнецов Дмитрий Андреевич",
            "position": "Врач-стоматолог-ортопед",
            "experience_years": 19,
            "service_ids": [
                "zirconia_crowns",
                "veneers",
                "all_on_4",
                "all_on_6",
                "temporary_teeth",
                "classic",
                "implant_supported_prosthetics",
                "clasp_dentures",
                "removable_dentures",
            ],
            "profile_ref": "kb:doctors__doctor__kuznetsov.md#korotko",
        },
        "doctors__doctor__morozova": {
            "name": "Морозова Анна Сергеевна",
            "position": "Врач-ортодонт",
            "experience_years": 11,
            "service_ids": ["aligners"],
            "profile_ref": "kb:doctors__doctor__morozova.md#korotko",
        },
        "doctors__doctor__orlov": {
            "name": "Орлов Никита Владимирович",
            "position": "Врач-имплантолог",
            "experience_years": 16,
            "service_ids": [
                "classic",
                "one_stage",
                "sinus_lift",
                "all_on_4",
                "all_on_6",
                "temporary_teeth",
                "implant_supported_prosthetics",
            ],
            "profile_ref": "kb:doctors__doctor__orlov.md#korotko",
        },
        "doctors__doctor__volkov": {
            "name": "Волков Александр Сергеевич",
            "position": "Главный врач, стоматолог-хирург, имплантолог",
            "experience_years": 13,
            "service_ids": [
                "classic",
                "one_stage",
                "sinus_lift",
                "zygomatic_implants",
                "pterygoid_implants",
                "all_on_4",
                "all_on_6",
                "temporary_teeth",
                "tooth_extraction",
            ],
            "profile_ref": "kb:doctors__doctor__volkov.md#korotko",
        },
    }
}


class _StrictSafeLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        key: list(resolvers)
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"duplicate_mapping_key:{key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _personal_md_paths() -> list[Path]:
    return [
        path
        for path in sorted(
            _MD_ROOT.glob("doctors__doctor__*.md"), key=lambda item: item.name
        )
        if path.name != _OVERVIEW_NAME
    ]


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3
    assert not parts[0].strip()
    raw = yaml.load(parts[1], Loader=_StrictSafeLoader)
    assert isinstance(raw, dict)
    return raw


def _md_projection() -> dict[str, object]:
    doctors: dict[str, object] = {}
    for path in _personal_md_paths():
        frontmatter = _read_frontmatter(path)
        doctors[frontmatter["doc_id"]] = {
            "name": frontmatter["name_full"],
            "position": frontmatter["position"],
            "experience_years": frontmatter["experience_years"],
            "service_ids": frontmatter["services"],
            "profile_ref": f"kb:{path.name}#korotko",
        }
    return {"doctors": doctors}


def _hashes(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_real_demo_catalog_loads_as_exact_owner_approved_s5_data() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    raw = json.loads(_DOCTOR_CATALOG_PATH.read_text(encoding="utf-8"))

    assert isinstance(catalog, TargetDoctorCatalog)
    assert catalog.model_dump() == _EXPECTED_CATALOG
    assert list(catalog.doctors) == list(_EXPECTED_CATALOG["doctors"])
    assert set(raw) == {"doctors"}
    assert len(catalog.doctors) == 6
    for doctor in raw["doctors"].values():
        assert set(doctor) == _DOCTOR_FIELDS
        assert not (_FORBIDDEN_FIELDS & set(doctor))


def test_target_catalog_exactly_matches_transitional_md_projection() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)

    assert len(_personal_md_paths()) == 6
    assert catalog.model_dump() == _md_projection()


def test_real_demo_catalog_passes_external_integrity_and_service_coverage() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    raw_services = json.loads(_SERVICE_CATALOG_PATH.read_text(encoding="utf-8"))
    index = DoctorCatalogExternalIndex(
        service_ids=tuple(raw_services),
        kb_refs=build_response_schema_kb_refs(_MD_ROOT),
    )

    assert validate_doctor_catalog_external_refs(catalog, index) is None
    assert build_doctor_source_refs(catalog) == tuple(
        f"doctor:{doctor_id}" for doctor_id in sorted(catalog.doctors)
    )

    covered = {
        service_id
        for doctor in catalog.doctors.values()
        for service_id in doctor.service_ids
    }
    assert set(raw_services) - covered == {"tomography"}
    assert covered - set(raw_services) == set()


def test_key_demo_services_have_the_approved_doctors() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)

    def doctors_for(service_id: str) -> set[str]:
        return {
            doctor_id
            for doctor_id, doctor in catalog.doctors.items()
            if service_id in doctor.service_ids
        }

    assert {
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    } <= doctors_for("all_on_4")
    assert doctors_for("professional_whitening") == {
        "doctors__doctor__fedorova"
    }
    assert doctors_for("aligners") == {"doctors__doctor__morozova"}
    assert doctors_for("periodontitis") == {"doctors__doctor__grigoriev"}


def test_real_demo_catalog_acceptance_is_read_only() -> None:
    paths = [_DOCTOR_CATALOG_PATH, _SERVICE_CATALOG_PATH, *_personal_md_paths()]
    before = _hashes(paths)

    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    assert catalog.model_dump() == _md_projection()
    assert build_response_schema_kb_refs(_MD_ROOT)

    assert _hashes(paths) == before


def test_acceptance_test_has_no_runtime_price_loader_or_write_dependencies() -> None:
    source = inspect.getsource(sys.modules[__name__])
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported_modules.isdisjoint(
        {
            "core.answer_planner",
            "core.pricebook_loader",
            "doctors_lookup",
            "orchestration",
            "session",
            "source_routing",
        }
    )
    assert called_attributes.isdisjoint(
        {
            "mkdir",
            "open",
            "rename",
            "replace",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
    )
