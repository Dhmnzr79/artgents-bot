from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
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
from core.response_schema_kb_index import build_response_schema_kb_refs


_ROOT = Path(__file__).resolve().parents[1]
_MD_ROOT = _ROOT / "clients" / "demo" / "md"
_CATALOG_PATH = _ROOT / "clients" / "demo" / "service_catalog.json"
_OVERVIEW_NAME = "doctors__doctor__overview.md"
_PERSONAL_GLOB = "doctors__doctor__*.md"
_TRANSITIONAL_KEYS = {
    "aliases",
    "cta_action",
    "cta_key",
    "doc_id",
    "doc_type",
    "experience_years",
    "name_full",
    "name_short",
    "position",
    "services",
    "subtopic",
    "topic",
}
_FORBIDDEN_KEYS = {
    "active",
    "card",
    "certificates",
    "education",
    "photo",
    "priority",
    "rating",
    "schedule",
    "slots",
    "ui",
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


def _doctor_paths() -> list[Path]:
    return sorted(_MD_ROOT.glob(_PERSONAL_GLOB), key=lambda path: path.name)


def _read_doctor(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3
    assert not parts[0].strip()
    frontmatter = yaml.load(parts[1], Loader=_StrictSafeLoader)
    assert isinstance(frontmatter, dict)
    return frontmatter, parts[2]


def _personal_records() -> list[tuple[Path, dict[str, Any], str]]:
    return [
        (path, *_read_doctor(path))
        for path in _doctor_paths()
        if path.name != _OVERVIEW_NAME
    ]


def _target_catalog() -> TargetDoctorCatalog:
    doctors: dict[str, dict[str, object]] = {}
    for path, frontmatter, _body in _personal_records():
        doctors[frontmatter["doc_id"]] = {
            "name": frontmatter["name_full"],
            "position": frontmatter["position"],
            "experience_years": frontmatter["experience_years"],
            "service_ids": frontmatter["services"],
            "profile_ref": f"kb:{path.name}#korotko",
        }
    return TargetDoctorCatalog.model_validate({"doctors": doctors})


def _hashes(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_demo_doctor_file_shape_and_transitional_fields_are_consistent() -> None:
    paths = _doctor_paths()
    assert len(paths) == 7
    assert sum(path.name == _OVERVIEW_NAME for path in paths) == 1

    records = _personal_records()
    assert len(records) == 6
    for path, frontmatter, body in records:
        assert set(frontmatter) == _TRANSITIONAL_KEYS
        assert not (_FORBIDDEN_KEYS & set(frontmatter))
        assert frontmatter["doc_id"] == path.stem
        assert frontmatter["doc_type"] == "doctor"
        assert frontmatter["topic"] == "doctors"
        assert frontmatter["subtopic"] == path.stem.removeprefix("doctors__doctor__")
        assert re.findall(r"^## (.+)$", body, flags=re.MULTILINE) == [
            frontmatter["name_full"]
        ]
        assert len(
            re.findall(r"^### Коротко \{#korotko\}$", body, flags=re.MULTILINE)
        ) == 1
        experience = frontmatter["experience_years"]
        assert type(experience) is int and experience > 0
        assert f"**{experience} лет**" in body
        services = frontmatter["services"]
        assert isinstance(services, list) and services
        assert all(isinstance(service_id, str) and service_id for service_id in services)
        assert len(services) == len(set(services))


def test_real_demo_materializes_through_s5_s6_and_builds_exact_doctor_refs() -> None:
    catalog = _target_catalog()
    raw_services = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    service_ids = tuple(raw_services)
    kb_refs = build_response_schema_kb_refs(_MD_ROOT)
    index = DoctorCatalogExternalIndex(service_ids=service_ids, kb_refs=kb_refs)

    assert validate_doctor_catalog_external_refs(catalog, index) is None
    assert build_doctor_source_refs(catalog) == tuple(
        sorted(f"doctor:{doctor_id}" for doctor_id in catalog.doctors)
    )
    assert len(catalog.doctors) == 6


def test_doctor_service_coverage_has_only_conscious_tomography_exception() -> None:
    catalog = _target_catalog()
    raw_services = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    covered = {
        service_id
        for doctor in catalog.doctors.values()
        for service_id in doctor.service_ids
    }

    assert set(raw_services) - covered == {"tomography"}
    assert covered - set(raw_services) == set()


def test_approved_new_links_are_explicit_in_metadata_and_selling_text() -> None:
    by_id = {
        frontmatter["doc_id"]: (frontmatter, body)
        for _path, frontmatter, body in _personal_records()
    }

    fedorova, fedorova_body = by_id["doctors__doctor__fedorova"]
    assert {
        "professional_whitening",
        "veneers",
        "zirconia_crowns",
    } <= set(fedorova["services"])
    assert "Профессиональное отбеливание" in fedorova_body
    assert "Виниры и циркониевые коронки" in fedorova_body

    orlov, orlov_body = by_id["doctors__doctor__orlov"]
    assert "sinus_lift" in orlov["services"]
    assert "Синус-лифтинг" in orlov_body

    volkov, volkov_body = by_id["doctors__doctor__volkov"]
    assert {
        "sinus_lift",
        "zygomatic_implants",
        "pterygoid_implants",
    } <= set(volkov["services"])
    assert "Синус-лифтинг" in volkov_body
    assert "скуловые" in volkov_body.lower()
    assert "птеригоидные" in volkov_body.lower()


def test_overview_is_general_kb_copy_without_derived_numeric_facts() -> None:
    overview_path = _MD_ROOT / _OVERVIEW_NAME
    frontmatter, body = _read_doctor(overview_path)

    assert frontmatter["doc_id"] == "doctors__doctor__overview"
    assert "name_full" not in frontmatter
    assert len(re.findall(r"^### Коротко \{#korotko\}$", body, re.MULTILINE)) == 1
    assert re.search(r"команда из \d+", body, flags=re.IGNORECASE) is None
    assert "суммарный стаж" not in body.lower()
    assert re.search(r"от \d+ до", body, flags=re.IGNORECASE) is None
    assert re.search(r"99[,.]8", body) is None


def test_template_validation_is_read_only() -> None:
    paths = _doctor_paths() + [_CATALOG_PATH]
    before = _hashes(paths)

    catalog = _target_catalog()
    kb_refs = build_response_schema_kb_refs(_MD_ROOT)
    assert catalog.doctors
    assert kb_refs

    assert _hashes(paths) == before


def test_template_test_does_not_import_runtime_or_call_write_apis() -> None:
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
