from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.doctor_schema import TargetDoctorCatalog
from core import doctor_schema_loader
from core.doctor_schema_loader import (
    DoctorCatalogLoadError,
    DuplicateDoctorCatalogKeyError,
    load_doctor_catalog,
)


def _doctor_payload(*, name: str = " Exact Doctor Name ") -> dict[str, object]:
    return {
        "name": name,
        "position": "Хирург-имплантолог",
        "experience_years": 13,
        "service_ids": ["all_on_4", "Classic_Implant"],
        "profile_ref": "kb:doctors/volkov.md#Sales_Profile",
    }


def _catalog_payload() -> dict[str, object]:
    return {
        "doctors": {
            "doctor_z": _doctor_payload(),
            "doctor_a": {
                **_doctor_payload(name="Другой врач"),
                "service_ids": ["veneers"],
                "profile_ref": "kb:doctors/fedorova.md#profile",
            },
        }
    }


def _write_catalog(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _captured_error(catalog_path: object) -> DoctorCatalogLoadError:
    with pytest.raises(DoctorCatalogLoadError) as exc_info:
        load_doctor_catalog(catalog_path)  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None
    return exc_info.value


def test_complete_catalog_preserves_exact_values_order_and_mapping_ids(
    tmp_path: Path,
) -> None:
    path = _write_catalog(tmp_path / "filename-is-not-a-doctor-id.json", _catalog_payload())

    catalog = load_doctor_catalog(path)

    assert isinstance(catalog, TargetDoctorCatalog)
    assert list(catalog.doctors) == ["doctor_z", "doctor_a"]
    assert catalog.doctors["doctor_z"].name == " Exact Doctor Name "
    assert catalog.doctors["doctor_z"].service_ids == [
        "all_on_4",
        "Classic_Implant",
    ]
    assert catalog.doctors["doctor_z"].profile_ref == (
        "kb:doctors/volkov.md#Sales_Profile"
    )
    assert "filename-is-not-a-doctor-id" not in catalog.doctors


def test_empty_catalog_is_valid(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path / "empty.json", {"doctors": {}})
    assert load_doctor_catalog(path).doctors == {}


def test_non_path_is_not_coerced() -> None:
    error = _captured_error("doctor_catalog.json")

    assert error.code == "catalog_path_invalid"
    assert error.path == Path(".")
    assert isinstance(error.__cause__, TypeError)


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_invalid_filesystem_path_keeps_original_path(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / kind
    cause_type: type[BaseException]
    if kind == "directory":
        path.mkdir()
        cause_type = IsADirectoryError
    else:
        cause_type = FileNotFoundError

    error = _captured_error(path)

    assert error.code == "catalog_path_invalid"
    assert error.path == path
    assert isinstance(error.__cause__, cause_type)


def test_invalid_utf8_is_file_read_failure(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_bytes(b"\xff\xfe")

    error = _captured_error(path)

    assert error.code == "file_read_failed"
    assert error.path == path
    assert isinstance(error.__cause__, UnicodeDecodeError)


def test_malformed_json_is_typed(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")

    error = _captured_error(path)

    assert error.code == "json_invalid"
    assert error.path == path
    assert isinstance(error.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "content",
    [
        '{"doctors": {}, "doctors": {}}',
        (
            '{"doctors": {"doctor_one": {'
            '"name": "A", "name": "B", "position": "P", '
            '"experience_years": 1, "service_ids": ["service"], '
            '"profile_ref": "kb:doctor.md#profile"}}}'
        ),
    ],
)
def test_duplicate_keys_fail_before_schema(tmp_path: Path, content: str) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(content, encoding="utf-8")

    error = _captured_error(path)

    assert error.code == "duplicate_key"
    assert error.path == path
    assert isinstance(error.__cause__, DuplicateDoctorCatalogKeyError)


@pytest.mark.parametrize("content", ["[]", '"doctor"', "null"])
def test_top_level_must_be_mapping(tmp_path: Path, content: str) -> None:
    path = tmp_path / "wrong-shape.json"
    path.write_text(content, encoding="utf-8")

    error = _captured_error(path)

    assert error.code == "top_level_type_invalid"
    assert error.path == path
    assert isinstance(error.__cause__, TypeError)


def _schema_error(tmp_path: Path, doctor: dict[str, object]) -> DoctorCatalogLoadError:
    path = _write_catalog(
        tmp_path / "schema-invalid.json",
        {"doctors": {"doctor_one": doctor}},
    )
    error = _captured_error(path)
    assert error.code == "schema_invalid"
    assert error.path == path
    assert isinstance(error.__cause__, ValidationError)
    return error


def test_transitional_legacy_fields_are_not_mapped(tmp_path: Path) -> None:
    doctor = _doctor_payload()
    doctor["name_full"] = doctor.pop("name")
    doctor["services"] = doctor.pop("service_ids")

    error = _schema_error(tmp_path, doctor)
    text = str(error.__cause__)

    assert "name" in text
    assert "service_ids" in text
    assert "extra_forbidden" in text


def test_owner_rejected_active_field_is_schema_error(tmp_path: Path) -> None:
    doctor = {**_doctor_payload(), "active": True}
    error = _schema_error(tmp_path, doctor)
    assert "extra_forbidden" in str(error.__cause__)


@pytest.mark.parametrize(
    ("mutation", "token"),
    [
        ("missing_position", "Field required"),
        ("duplicate_service", "doctor_service_id_duplicate"),
    ],
)
def test_invalid_s5_payload_keeps_validation_cause(
    tmp_path: Path, mutation: str, token: str
) -> None:
    doctor = _doctor_payload()
    if mutation == "missing_position":
        doctor.pop("position")
    else:
        doctor["service_ids"] = ["all_on_4", "all_on_4"]

    error = _schema_error(tmp_path, doctor)
    assert token in str(error.__cause__)


def test_second_load_observes_changed_source_without_cache(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path / "catalog.json", _catalog_payload())
    first = load_doctor_catalog(path)
    changed = _catalog_payload()
    changed["doctors"]["doctor_z"]["name"] = "Changed Doctor Name"  # type: ignore[index]
    _write_catalog(path, changed)
    second = load_doctor_catalog(path)

    assert first.doctors["doctor_z"].name == " Exact Doctor Name "
    assert second.doctors["doctor_z"].name == "Changed Doctor Name"


def test_loader_source_has_one_s5_validation_and_no_runtime_or_write_dependencies() -> None:
    source_path = Path(doctor_schema_loader.__file__)
    source = source_path.read_text(encoding="utf-8")
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
    model_validate_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "model_validate"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "TargetDoctorCatalog"
    ]

    assert imported_modules <= {
        "__future__",
        "contracts.doctor_schema",
        "json",
        "pathlib",
        "pydantic",
        "typing",
    }
    assert len(model_validate_calls) == 1
    assert called_attributes.isdisjoint(
        {
            "getenv",
            "model_construct",
            "open",
            "write_bytes",
            "write_text",
        }
    )
    assert "name_full" not in source
    assert "compatibility" not in source.lower()
