from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import response_schema_refs
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    ResponseSchemaExternalRefError,
    validate_response_schema_external_refs,
)


def _bundle(*, scenario_rules: dict[str, dict[str, object]]) -> ResponseSchemaBundle:
    return ResponseSchemaBundle.model_validate(
        {
            "services": {},
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": {
                "fact_one": {
                    "id": "fact_one",
                    "kind": "proof",
                    "text_fact": "Exact fact text.",
                    "render_mode": "strict",
                    "active": True,
                    "allowed_service_ids": [],
                    "incompatible_with": [],
                }
            },
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 3,
                    "max_amplifiers_per_turn": 2,
                    "max_scenarios_per_turn": 2,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": scenario_rules,
                "cta_contexts": {"default": "callback"},
            },
        }
    )


def _mixed_bundle() -> ResponseSchemaBundle:
    return _bundle(
        scenario_rules={
            "cost": {
                "ordered_amplifier_refs": [
                    "fact:fact_one",
                    "kb:service.md#Approved_Chunk",
                    "doctor:doctor_one",
                ],
                "allowed_semantic_contexts": ["service_context"],
            }
        }
    )


def test_complete_exact_index_validates_and_returns_none() -> None:
    index = ResponseSchemaExternalIndex(
        kb_refs=("kb:service.md#Approved_Chunk",),
        doctor_refs=("doctor:doctor_one",),
    )

    result = validate_response_schema_external_refs(_mixed_bundle(), index)

    assert result is None


def test_missing_kb_and_doctor_refs_are_one_typed_sorted_error() -> None:
    bundle = _bundle(
        scenario_rules={
            "cost": {
                "ordered_amplifier_refs": [
                    "kb:z.md#chunk",
                    "doctor:z_doctor",
                    "kb:a.md#chunk",
                ]
            },
            "time": {
                "ordered_amplifier_refs": [
                    "kb:z.md#chunk",
                    "doctor:a_doctor",
                    "doctor:z_doctor",
                ]
            },
        }
    )

    with pytest.raises(ResponseSchemaExternalRefError) as exc_info:
        validate_response_schema_external_refs(bundle, ResponseSchemaExternalIndex())

    error = exc_info.value
    assert isinstance(error, ValueError)
    assert error.code == "external_refs_missing"
    assert error.missing_kb_refs == ("kb:a.md#chunk", "kb:z.md#chunk")
    assert error.missing_doctor_refs == ("doctor:a_doctor", "doctor:z_doctor")


@pytest.mark.parametrize("value", [[], {"kb:doc.md#chunk"}, "kb:doc.md#chunk"])
def test_index_requires_exact_tuple_container(value: object) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResponseSchemaExternalIndex.model_validate({"kb_refs": value, "doctor_refs": ()})

    assert "tuple_type" in str(exc_info.value)


@pytest.mark.parametrize(
    ("payload", "token"),
    [
        (
            {"kb_refs": ("kb:doc.md#chunk",), "doctor_refs": (), "extra": True},
            "extra_forbidden",
        ),
        (
            {"kb_refs": ("kb:doc.md#chunk", "kb:doc.md#chunk"), "doctor_refs": ()},
            "external_index_kb_ref_duplicate",
        ),
        (
            {"kb_refs": (), "doctor_refs": ("doctor:one", "doctor:one")},
            "external_index_doctor_ref_duplicate",
        ),
        (
            {"kb_refs": ("doctor:one",), "doctor_refs": ()},
            "external_index_kb_prefix_invalid",
        ),
        (
            {"kb_refs": (), "doctor_refs": ("kb:doc.md#chunk",)},
            "external_index_doctor_prefix_invalid",
        ),
        (
            {"kb_refs": ("kb:doc-without-chunk",), "doctor_refs": ()},
            "kb_ref_requires_doc_and_chunk",
        ),
    ],
)
def test_index_rejects_extra_duplicates_wrong_prefix_and_malformed_refs(
    payload: dict[str, object], token: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResponseSchemaExternalIndex.model_validate(payload)

    assert token in str(exc_info.value)


def test_index_model_is_strict_frozen_and_preserves_order_and_case() -> None:
    raw_kb = ("kb:Z.md#Chunk", "kb:a.md#chunk")
    raw_doctors = ("doctor:Doctor_Z", "doctor:doctor_a")
    index = ResponseSchemaExternalIndex(kb_refs=raw_kb, doctor_refs=raw_doctors)

    assert index.model_config.get("strict") is True
    assert index.model_config.get("frozen") is True
    assert index.model_config.get("extra") == "forbid"
    assert index.kb_refs == raw_kb
    assert index.doctor_refs == raw_doctors
    with pytest.raises(ValidationError) as exc_info:
        index.kb_refs = ()
    assert "frozen_instance" in str(exc_info.value)


def test_empty_index_and_extra_available_refs_are_allowed() -> None:
    fact_only = _bundle(
        scenario_rules={
            "cost": {"ordered_amplifier_refs": ["fact:fact_one"]},
        }
    )
    assert validate_response_schema_external_refs(fact_only, ResponseSchemaExternalIndex()) is None

    index = ResponseSchemaExternalIndex(
        kb_refs=("kb:unused.md#chunk",),
        doctor_refs=("doctor:unused",),
    )
    assert validate_response_schema_external_refs(fact_only, index) is None


def test_case_mismatch_is_missing_without_normalization() -> None:
    index = ResponseSchemaExternalIndex(
        kb_refs=("kb:Service.md#approved_chunk",),
        doctor_refs=("doctor:Doctor_One",),
    )

    with pytest.raises(ResponseSchemaExternalRefError) as exc_info:
        validate_response_schema_external_refs(_mixed_bundle(), index)

    assert exc_info.value.missing_kb_refs == ("kb:service.md#Approved_Chunk",)
    assert exc_info.value.missing_doctor_refs == ("doctor:doctor_one",)


def test_calls_with_different_indexes_share_no_state() -> None:
    bundle = _mixed_bundle()
    complete = ResponseSchemaExternalIndex(
        kb_refs=("kb:service.md#Approved_Chunk",),
        doctor_refs=("doctor:doctor_one",),
    )
    missing = ResponseSchemaExternalIndex()

    assert validate_response_schema_external_refs(bundle, complete) is None
    with pytest.raises(ResponseSchemaExternalRefError):
        validate_response_schema_external_refs(bundle, missing)
    assert validate_response_schema_external_refs(bundle, complete) is None


def test_validation_does_not_mutate_bundle_index_or_pool_order() -> None:
    bundle = _mixed_bundle()
    index = ResponseSchemaExternalIndex(
        kb_refs=("kb:service.md#Approved_Chunk", "kb:unused.md#chunk"),
        doctor_refs=("doctor:doctor_one", "doctor:unused"),
    )
    bundle_before = bundle.model_dump()
    index_before = index.model_dump()

    validate_response_schema_external_refs(bundle, index)

    assert bundle.model_dump() == bundle_before
    assert index.model_dump() == index_before
    assert bundle.marketing.scenario_rules["cost"].ordered_amplifier_refs == [
        "fact:fact_one",
        "kb:service.md#Approved_Chunk",
        "doctor:doctor_one",
    ]
    assert index.kb_refs == ("kb:service.md#Approved_Chunk", "kb:unused.md#chunk")


def test_source_has_no_io_loader_client_runtime_session_or_a9_dependencies() -> None:
    source_path = Path(response_schema_refs.__file__)
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
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert imported_modules <= {
        "__future__",
        "pydantic",
        "contracts.response_schema",
    }
    assert not ({"open", "read_text", "write_text", "getenv"} & called_attributes)
    assert not (
        {
            "client_id",
            "DEFAULT_CLIENT_ID",
            "session",
            "patient_scope",
            "requests",
            "environ",
        }
        & identifiers
    )
