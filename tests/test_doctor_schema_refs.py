from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import TypeAdapter, ValidationError

from contracts import doctor_schema_refs
from contracts.doctor_schema import TargetDoctorCatalog
from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    DoctorCatalogExternalRefError,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import SourceRef


def _doctor(
    *,
    name: str,
    services: list[str],
    profile_ref: str,
) -> dict[str, object]:
    return {
        "name": name,
        "position": "Врач-имплантолог",
        "experience_years": 12,
        "service_ids": services,
        "profile_ref": profile_ref,
    }


def _catalog() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_z": _doctor(
                    name="Doctor Z",
                    services=["service_two", "Service_Case"],
                    profile_ref="kb:doctors/z.md#Profile_Z",
                ),
                "doctor_a": _doctor(
                    name="Doctor A",
                    services=["service_one", "service_two"],
                    profile_ref="kb:doctors/a.md#profile_a",
                ),
            }
        }
    )


def _full_index() -> DoctorCatalogExternalIndex:
    return DoctorCatalogExternalIndex.model_validate(
        {
            "service_ids": (
                "unused_service",
                "service_one",
                "Service_Case",
                "service_two",
            ),
            "kb_refs": (
                "kb:unused.md#profile",
                "kb:doctors/a.md#profile_a",
                "kb:doctors/z.md#Profile_Z",
            ),
        }
    )


def test_full_exact_index_validates_and_extras_are_allowed() -> None:
    assert validate_doctor_catalog_external_refs(_catalog(), _full_index()) is None


def test_all_missing_refs_are_aggregated_sorted_and_unique() -> None:
    catalog = TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_z": _doctor(
                    name="Z",
                    services=["missing_z", "missing_shared"],
                    profile_ref="kb:shared.md#profile",
                ),
                "doctor_a": _doctor(
                    name="A",
                    services=["missing_a", "missing_shared"],
                    profile_ref="kb:a.md#profile",
                ),
                "doctor_m": _doctor(
                    name="M",
                    services=["missing_shared"],
                    profile_ref="kb:shared.md#profile",
                ),
            }
        }
    )

    with pytest.raises(DoctorCatalogExternalRefError) as exc_info:
        validate_doctor_catalog_external_refs(catalog, DoctorCatalogExternalIndex())

    error = exc_info.value
    assert isinstance(error, ValueError)
    assert error.code == "doctor_catalog_external_refs_missing"
    assert error.missing_service_ids == (
        "missing_a",
        "missing_shared",
        "missing_z",
    )
    assert error.missing_profile_refs == (
        "kb:a.md#profile",
        "kb:shared.md#profile",
    )


def test_case_mismatch_is_missing_without_normalization() -> None:
    catalog = TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_one": _doctor(
                    name="One",
                    services=["Service_Case"],
                    profile_ref="kb:doctor.md#Profile",
                )
            }
        }
    )
    index = DoctorCatalogExternalIndex(
        service_ids=("service_case",),
        kb_refs=("kb:doctor.md#profile",),
    )

    with pytest.raises(DoctorCatalogExternalRefError) as exc_info:
        validate_doctor_catalog_external_refs(catalog, index)

    assert exc_info.value.missing_service_ids == ("Service_Case",)
    assert exc_info.value.missing_profile_refs == ("kb:doctor.md#Profile",)


def test_empty_catalog_and_index_are_valid() -> None:
    catalog = TargetDoctorCatalog(doctors={})
    index = DoctorCatalogExternalIndex()

    assert validate_doctor_catalog_external_refs(catalog, index) is None
    assert build_doctor_source_refs(catalog) == ()


@pytest.mark.parametrize("field", ["service_ids", "kb_refs"])
@pytest.mark.parametrize("value", [[], {"one"}, "one"])
def test_index_is_tuple_only(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        DoctorCatalogExternalIndex.model_validate({field: value})


@pytest.mark.parametrize(
    ("payload", "token"),
    [
        ({"extra": ()}, "extra_forbidden"),
        ({"service_ids": ("",)}, "string_must_not_be_blank"),
        ({"service_ids": ("one", "one")}, "doctor_external_service_id_duplicate"),
        ({"kb_refs": ("fact:one",)}, "doctor_profile_ref_requires_kb_prefix"),
        ({"kb_refs": ("doctor:one",)}, "doctor_profile_ref_requires_kb_prefix"),
        ({"kb_refs": ("kb:profile.txt#one",)}, "doctor_profile_ref_requires_md_document"),
        ({"kb_refs": ("kb:profile.md",)}, "kb_ref_requires_doc_and_chunk"),
        (
            {"kb_refs": ("kb:profile.md#one", "kb:profile.md#one")},
            "doctor_external_kb_ref_duplicate",
        ),
    ],
)
def test_index_rejects_invalid_values(payload: dict[str, object], token: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        DoctorCatalogExternalIndex.model_validate(payload)
    assert token in str(exc_info.value)


def test_index_config_is_strict_frozen_forbid_and_preserves_order() -> None:
    index = _full_index()

    assert DoctorCatalogExternalIndex.model_config["strict"] is True
    assert DoctorCatalogExternalIndex.model_config["frozen"] is True
    assert DoctorCatalogExternalIndex.model_config["extra"] == "forbid"
    assert index.service_ids == (
        "unused_service",
        "service_one",
        "Service_Case",
        "service_two",
    )
    with pytest.raises(ValidationError):
        index.service_ids = ()  # type: ignore[misc]


def test_validation_is_stateless_and_does_not_mutate_inputs() -> None:
    catalog = _catalog()
    complete = _full_index()
    incomplete = DoctorCatalogExternalIndex(
        service_ids=("service_one",),
        kb_refs=("kb:doctors/a.md#profile_a",),
    )
    catalog_before = catalog.model_dump()
    complete_before = complete.model_dump()
    incomplete_before = incomplete.model_dump()

    assert validate_doctor_catalog_external_refs(catalog, complete) is None
    with pytest.raises(DoctorCatalogExternalRefError):
        validate_doctor_catalog_external_refs(catalog, incomplete)
    assert validate_doctor_catalog_external_refs(catalog, complete) is None

    assert catalog.model_dump() == catalog_before
    assert complete.model_dump() == complete_before
    assert incomplete.model_dump() == incomplete_before


def test_builder_returns_sorted_exact_s1_source_refs() -> None:
    refs = build_doctor_source_refs(_catalog())

    assert refs == ("doctor:doctor_a", "doctor:doctor_z")
    adapter = TypeAdapter(SourceRef)
    assert tuple(adapter.validate_python(ref) for ref in refs) == refs


def test_builder_itself_uses_frozen_s1_source_ref_adapter() -> None:
    tree = ast.parse(inspect.getsource(build_doctor_source_refs))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "TypeAdapter"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "SourceRef"
        for call in calls
    )
    assert any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "validate_python"
        for call in calls
    )


def test_source_has_only_foundation_imports_and_no_side_effect_calls() -> None:
    source = inspect.getsource(doctor_schema_refs)
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

    assert imported_modules <= {
        "__future__",
        "contracts.doctor_schema",
        "contracts.response_schema",
        "pydantic",
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
