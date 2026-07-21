from __future__ import annotations

import ast
import inspect
from copy import deepcopy

import pytest
from pydantic import ValidationError

from contracts import doctor_schema
from contracts.doctor_schema import TargetDoctorCatalog


def _doctor_payload() -> dict[str, object]:
    return {
        "name": " Волков Александр Сергеевич ",
        "position": "Главный врач, хирург-имплантолог",
        "experience_years": 13,
        "service_ids": ["veneers", "Classic_Implant"],
        "profile_ref": "kb:doctors/volkov.md#Sales_Profile",
    }


def _catalog_payload() -> dict[str, object]:
    return {
        "doctors": {
            "doctor_z": _doctor_payload(),
            "doctor_a": {
                **_doctor_payload(),
                "name": "Другой врач",
                "service_ids": ["service_two"],
                "profile_ref": "kb:doctors/other.md#profile",
            },
        }
    }


def _error_text(payload: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as exc_info:
        TargetDoctorCatalog.model_validate(payload)
    return str(exc_info.value)


def test_valid_catalog_preserves_exact_authored_data_and_order() -> None:
    payload = _catalog_payload()
    before = deepcopy(payload)

    catalog = TargetDoctorCatalog.model_validate(payload)

    assert list(catalog.doctors) == ["doctor_z", "doctor_a"]
    assert catalog.doctors["doctor_z"].name == " Волков Александр Сергеевич "
    assert catalog.doctors["doctor_z"].service_ids == ["veneers", "Classic_Implant"]
    assert catalog.doctors["doctor_z"].profile_ref == (
        "kb:doctors/volkov.md#Sales_Profile"
    )
    assert payload == before


def test_empty_catalog_is_valid() -> None:
    catalog = TargetDoctorCatalog.model_validate({"doctors": {}})
    assert catalog.doctors == {}


@pytest.mark.parametrize(
    "missing_field",
    ["name", "position", "experience_years", "service_ids", "profile_ref"],
)
def test_all_doctor_fields_are_required(missing_field: str) -> None:
    doctor = _doctor_payload()
    doctor.pop(missing_field)

    assert "Field required" in _error_text({"doctors": {"doctor_one": doctor}})


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("name", "   ", "string_must_not_be_blank"),
        ("position", "\t", "string_must_not_be_blank"),
        ("service_ids", [], "doctor_service_ids_empty"),
        ("service_ids", ["service_one", "service_one"], "doctor_service_id_duplicate"),
        ("service_ids", ["service_one", " "], "string_must_not_be_blank"),
    ],
)
def test_rejects_invalid_local_doctor_fields(field: str, value: object, token: str) -> None:
    doctor = _doctor_payload()
    doctor[field] = value

    assert token in _error_text({"doctors": {"doctor_one": doctor}})


@pytest.mark.parametrize("value", [0, 1, 25])
def test_experience_accepts_non_negative_strict_integer(value: int) -> None:
    doctor = _doctor_payload()
    doctor["experience_years"] = value

    catalog = TargetDoctorCatalog.model_validate({"doctors": {"doctor_one": doctor}})
    assert catalog.doctors["doctor_one"].experience_years == value


@pytest.mark.parametrize("value", [-1, True, 1.5, "13"])
def test_experience_rejects_invalid_or_coerced_values(value: object) -> None:
    doctor = _doctor_payload()
    doctor["experience_years"] = value

    assert "experience_years" in _error_text({"doctors": {"doctor_one": doctor}})


@pytest.mark.parametrize(
    "doctor_id",
    ["doctor_one", "doctors__doctor__volkov", "a", "1_doctor", "doctor-2"],
)
def test_accepts_exact_doctor_id_boundaries(doctor_id: str) -> None:
    catalog = TargetDoctorCatalog.model_validate(
        {"doctors": {doctor_id: _doctor_payload()}}
    )
    assert list(catalog.doctors) == [doctor_id]


@pytest.mark.parametrize(
    "doctor_id",
    ["", " doctor", "doctor ", "Doctor", "doctor.one", "doctor:one", "a/b"],
)
def test_rejects_invalid_doctor_ids_without_normalization(doctor_id: str) -> None:
    assert "doctor_id_invalid" in _error_text(
        {"doctors": {doctor_id: _doctor_payload()}}
    )


@pytest.mark.parametrize(
    "profile_ref",
    [
        "fact:profile",
        "doctor:doctor_one",
        "kb:doctors/profile.txt#sales",
        "kb:doctors/profile.MD#sales",
        "kb:doctors/profile.md",
        "kb:#sales",
        "kb:doctors/profile.md#",
    ],
)
def test_rejects_invalid_profile_refs(profile_ref: str) -> None:
    doctor = _doctor_payload()
    doctor["profile_ref"] = profile_ref

    assert "profile_ref" in _error_text({"doctors": {"doctor_one": doctor}})


@pytest.mark.parametrize(
    "extra_field",
    [
        "active",
        "aliases",
        "education",
        "certificates",
        "photo",
        "schedule",
        "slots",
        "card",
        "ui",
        "rating",
        "priority",
        "cta",
    ],
)
def test_rejects_forbidden_doctor_extras(extra_field: str) -> None:
    doctor = _doctor_payload()
    doctor[extra_field] = "forbidden"

    assert "extra_forbidden" in _error_text({"doctors": {"doctor_one": doctor}})


def test_catalog_extra_and_missing_doctors_mapping_are_rejected() -> None:
    assert "extra_forbidden" in _error_text({"doctors": {}, "version": 1})
    assert "Field required" in _error_text({})


def test_sequential_validations_do_not_share_state() -> None:
    first_payload = {"doctors": {"first": _doctor_payload()}}
    second_doctor = _doctor_payload()
    second_doctor["service_ids"] = ["second_service"]
    second_payload = {"doctors": {"second": second_doctor}}

    first = TargetDoctorCatalog.model_validate(first_payload)
    second = TargetDoctorCatalog.model_validate(second_payload)

    assert list(first.doctors) == ["first"]
    assert first.doctors["first"].service_ids == ["veneers", "Classic_Implant"]
    assert list(second.doctors) == ["second"]
    assert second.doctors["second"].service_ids == ["second_service"]


def test_schema_exposes_only_required_owner_approved_fields() -> None:
    assert set(doctor_schema.TargetDoctor.model_fields) == {
        "name",
        "position",
        "experience_years",
        "service_ids",
        "profile_ref",
    }
    assert all(
        field.is_required() for field in doctor_schema.TargetDoctor.model_fields.values()
    )
    assert set(TargetDoctorCatalog.model_fields) == {"doctors"}
    assert TargetDoctorCatalog.model_fields["doctors"].is_required()
    assert doctor_schema.TargetDoctor.model_config["extra"] == "forbid"
    assert TargetDoctorCatalog.model_config["extra"] == "forbid"


def test_contract_imports_only_frozen_foundation_and_has_no_side_effect_calls() -> None:
    source = inspect.getsource(doctor_schema)
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
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

    assert imported_modules <= {
        "__future__",
        "contracts.response_schema",
        "pydantic",
        "re",
        "typing",
    }
    assert called_attributes.isdisjoint(
        {
            "mkdir",
            "open",
            "read_bytes",
            "read_text",
            "rename",
            "replace",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
    )
