from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import get_args

import pytest

from contracts.answer_plan import AspectKind
from contracts.turn_frame import (
    FieldMeta,
    PatientCareStage,
    PatientExtent,
    PatientJaw,
    PatientScopeFrame,
    PatientScopeFrameMeta,
    PatientScopeModifier,
)
from contracts.turn_plan import TurnPlan


FIXTURE_PATH = Path("tests/fixtures/patient_scope_native_contract_a9_v2.json")
SCOPE_FIELDS = ("extent", "jaw", "stage", "modifiers")

PROJECTION_IDS = (
    "projection_valid_native_valid_legacy",
    "projection_native_plus_unknown_top_level",
    "projection_invalid_native_valid_legacy",
    "projection_valid_native_invalid_legacy",
    "projection_input_immutability",
)
PRECEDENCE_IDS = (
    "precedence_absent_uses_bridge",
    "precedence_present_object_uses_native",
    "precedence_present_invalid_container_no_bridge",
    "precedence_present_invalid_member_no_backfill",
)
PARSER_IDS = (
    "container_valid_object",
    "container_null_invalid_type",
    "container_non_object_invalid_type",
    "container_extra_field_preserves_neighbors",
    "members_valid_composite",
    "members_explicit_unknown_empty",
    "members_all_missing",
    "extent_invalid_type",
    "extent_not_allowed",
    "jaw_invalid_type",
    "jaw_not_allowed",
    "stage_invalid_type",
    "stage_not_allowed",
    "modifiers_invalid_type_non_list",
    "modifiers_invalid_type_item",
    "modifier_not_allowed",
    "modifiers_duplicate_canonical",
    "invalid_member_preserves_neighbors",
)
PROMPT_EXAMPLE_IDS = (
    "meaning_one_tooth",
    "meaning_full_upper_reported_bone",
    "meaning_implant_placed",
    "meaning_informational_no_patient_facts",
    "meaning_vague_followup_no_current_scope",
)
REQUIRED_PROMPT_SEMANTICS = (
    "object_with_exact_four_keys",
    "current_message_explicit_only",
    "unknown_or_empty_without_guess",
    "history_referent_without_scope_carry",
    "legacy_patient_situation_separate",
    "no_service_protocol_price_document_evidence_diagnosis_selection",
    "urgency_and_pain_outside_scope",
    "reported_bone_is_context_not_confirmation",
    "json_only_no_extra_fields",
)
FORBIDDEN_PROMPT_SEMANTICS = (
    "service_protocol_mapping",
    "diagnosis_inference",
    "old_scope_value_carry",
    "frozen_live_case_ids",
    "exhaustive_phrase_classifier",
    "second_llm_call",
    "scope_retry",
)
EXPECTED_NATIVE_ERRORS = {
    "patient_scope_invalid_type",
    "patient_scope_extra_field",
    "patient_extent_invalid_type",
    "patient_extent_not_allowed",
    "patient_jaw_invalid_type",
    "patient_jaw_not_allowed",
    "patient_stage_invalid_type",
    "patient_stage_not_allowed",
    "patient_modifiers_invalid_type",
    "patient_modifier_not_allowed",
}
SAFE_SCOPE = {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
VALID_STATUSES = {field: "valid" for field in SCOPE_FIELDS}
NO_ERRORS = {field: None for field in SCOPE_FIELDS}
EXPECTED_METADATA_CONTRACT = {
    "confidence": 0.0,
    "container_present_provenance": "turn_plan.raw.patient_scope",
    "container_absent_provenance": "turn_plan.schema_default",
    "schema_default_provenance": "turn_plan.schema_default",
    "native_field_provenance": {
        field: f"turn_plan.raw.patient_scope.{field}" for field in SCOPE_FIELDS
    },
    "bridge_field_provenance": {
        field: f"turn_plan.patient_situation.{field}" for field in SCOPE_FIELDS
    },
}


def _parser_expected(
    raw_container: object,
    *,
    scope: dict | None = None,
    container_status: str = "valid",
    container_error: str | None = None,
    statuses: dict | None = None,
    errors: dict | None = None,
    shadow_status: str = "ok",
) -> dict:
    return {
        "raw_container": raw_container,
        "expected_scope": SAFE_SCOPE if scope is None else scope,
        "expected_container": {"status": container_status, "error": container_error},
        "expected_field_status": VALID_STATUSES if statuses is None else statuses,
        "expected_field_error": NO_ERRORS if errors is None else errors,
        "expected_shadow_status": shadow_status,
    }


PARSER_EXPECTATIONS = {
    "container_valid_object": _parser_expected(
        {"extent": "one_tooth", "jaw": "upper", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
        scope={"extent": "one_tooth", "jaw": "upper", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
    ),
    "container_null_invalid_type": _parser_expected(
        None,
        container_status="invalid",
        container_error="patient_scope_invalid_type",
        statuses={field: "defaulted" for field in SCOPE_FIELDS},
        shadow_status="partial",
    ),
    "container_non_object_invalid_type": _parser_expected(
        42,
        container_status="invalid",
        container_error="patient_scope_invalid_type",
        statuses={field: "defaulted" for field in SCOPE_FIELDS},
        shadow_status="partial",
    ),
    "container_extra_field_preserves_neighbors": _parser_expected(
        {"extent": "few_teeth", "jaw": "lower", "stage": "extraction_context", "modifiers": [], "synthetic_extra": "must_not_serialize"},
        scope={"extent": "few_teeth", "jaw": "lower", "stage": "extraction_context", "modifiers": []},
        container_status="invalid",
        container_error="patient_scope_extra_field",
        shadow_status="partial",
    ),
    "members_valid_composite": _parser_expected(
        {"extent": "full_arch", "jaw": "both", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
        scope={"extent": "full_arch", "jaw": "both", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
    ),
    "members_explicit_unknown_empty": _parser_expected(dict(SAFE_SCOPE)),
    "members_all_missing": _parser_expected(
        {},
        statuses={field: "missing" for field in SCOPE_FIELDS},
        shadow_status="partial",
    ),
    "extent_invalid_type": _parser_expected(
        {"extent": 42, "jaw": "unknown", "stage": "unknown", "modifiers": []},
        statuses={**VALID_STATUSES, "extent": "invalid"},
        errors={**NO_ERRORS, "extent": "patient_extent_invalid_type"},
        shadow_status="partial",
    ),
    "extent_not_allowed": _parser_expected(
        {"extent": "synthetic_many_teeth", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        statuses={**VALID_STATUSES, "extent": "invalid"},
        errors={**NO_ERRORS, "extent": "patient_extent_not_allowed"},
        shadow_status="partial",
    ),
    "jaw_invalid_type": _parser_expected(
        {"extent": "unknown", "jaw": 42, "stage": "unknown", "modifiers": []},
        statuses={**VALID_STATUSES, "jaw": "invalid"},
        errors={**NO_ERRORS, "jaw": "patient_jaw_invalid_type"},
        shadow_status="partial",
    ),
    "jaw_not_allowed": _parser_expected(
        {"extent": "unknown", "jaw": "synthetic_left", "stage": "unknown", "modifiers": []},
        statuses={**VALID_STATUSES, "jaw": "invalid"},
        errors={**NO_ERRORS, "jaw": "patient_jaw_not_allowed"},
        shadow_status="partial",
    ),
    "stage_invalid_type": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": 42, "modifiers": []},
        statuses={**VALID_STATUSES, "stage": "invalid"},
        errors={**NO_ERRORS, "stage": "patient_stage_invalid_type"},
        shadow_status="partial",
    ),
    "stage_not_allowed": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": "synthetic_healed", "modifiers": []},
        statuses={**VALID_STATUSES, "stage": "invalid"},
        errors={**NO_ERRORS, "stage": "patient_stage_not_allowed"},
        shadow_status="partial",
    ),
    "modifiers_invalid_type_non_list": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": "reported_bone_deficit"},
        statuses={**VALID_STATUSES, "modifiers": "invalid"},
        errors={**NO_ERRORS, "modifiers": "patient_modifiers_invalid_type"},
        shadow_status="partial",
    ),
    "modifiers_invalid_type_item": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": [42]},
        statuses={**VALID_STATUSES, "modifiers": "invalid"},
        errors={**NO_ERRORS, "modifiers": "patient_modifiers_invalid_type"},
        shadow_status="partial",
    ),
    "modifier_not_allowed": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": ["reported_bone_deficit", "synthetic_unsupported"]},
        statuses={**VALID_STATUSES, "modifiers": "invalid"},
        errors={**NO_ERRORS, "modifiers": "patient_modifier_not_allowed"},
        shadow_status="partial",
    ),
    "modifiers_duplicate_canonical": _parser_expected(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": ["reported_bone_deficit", "reported_bone_deficit"]},
        scope={"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": ["reported_bone_deficit"]},
    ),
    "invalid_member_preserves_neighbors": _parser_expected(
        {"extent": 42, "jaw": "upper", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
        scope={"extent": "unknown", "jaw": "upper", "stage": "implant_placed", "modifiers": ["reported_bone_deficit"]},
        statuses={**VALID_STATUSES, "extent": "invalid"},
        errors={**NO_ERRORS, "extent": "patient_extent_invalid_type"},
        shadow_status="partial",
    ),
}

PRECEDENCE_EXPECTATIONS = {
    "precedence_absent_uses_bridge": {
        "synthetic_input": {"patient_situation": "one_tooth_missing"},
        "expected_source": "scalar_bridge",
        "expected_scope": {"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        "expected_container": {"status": "defaulted", "error": None, "provenance": "turn_plan.schema_default"},
        "expected_field_status": {"extent": "valid", "jaw": "defaulted", "stage": "defaulted", "modifiers": "defaulted"},
        "expected_field_provenance": {"extent": "turn_plan.patient_situation.extent", "jaw": "turn_plan.schema_default", "stage": "turn_plan.schema_default", "modifiers": "turn_plan.schema_default"},
        "forbid_scalar_backfill": False,
    },
    "precedence_present_object_uses_native": {
        "synthetic_input": {
            "patient_situation": "one_tooth_missing",
            "patient_scope": {"extent": "full_arch", "jaw": "both", "stage": "unknown", "modifiers": []},
        },
        "expected_source": "native",
        "expected_scope": {"extent": "full_arch", "jaw": "both", "stage": "unknown", "modifiers": []},
        "expected_container": {"status": "valid", "error": None, "provenance": "turn_plan.raw.patient_scope"},
        "expected_field_status": {"extent": "valid", "jaw": "valid", "stage": "valid", "modifiers": "valid"},
        "expected_field_provenance": {field: f"turn_plan.raw.patient_scope.{field}" for field in SCOPE_FIELDS},
        "forbid_scalar_backfill": True,
    },
    "precedence_present_invalid_container_no_bridge": {
        "synthetic_input": {"patient_situation": "one_tooth_missing", "patient_scope": None},
        "expected_source": "native_invalid_container",
        "expected_scope": SAFE_SCOPE,
        "expected_container": {"status": "invalid", "error": "patient_scope_invalid_type", "provenance": "turn_plan.raw.patient_scope"},
        "expected_field_status": {field: "defaulted" for field in SCOPE_FIELDS},
        "expected_field_provenance": {field: "turn_plan.schema_default" for field in SCOPE_FIELDS},
        "forbid_scalar_backfill": True,
    },
    "precedence_present_invalid_member_no_backfill": {
        "synthetic_input": {
            "patient_situation": "one_tooth_missing",
            "patient_scope": {"extent": 42, "jaw": "upper", "stage": "unknown", "modifiers": []},
        },
        "expected_source": "native",
        "expected_scope": {"extent": "unknown", "jaw": "upper", "stage": "unknown", "modifiers": []},
        "expected_container": {"status": "valid", "error": None, "provenance": "turn_plan.raw.patient_scope"},
        "expected_field_status": {**VALID_STATUSES, "extent": "invalid"},
        "expected_field_provenance": {field: f"turn_plan.raw.patient_scope.{field}" for field in SCOPE_FIELDS},
        "forbid_scalar_backfill": True,
    },
}

PROMPT_SCOPE_EXPECTATIONS = {
    "meaning_one_tooth": {"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []},
    "meaning_full_upper_reported_bone": {"extent": "full_arch", "jaw": "upper", "stage": "unknown", "modifiers": ["reported_bone_deficit"]},
    "meaning_implant_placed": {"extent": "unknown", "jaw": "unknown", "stage": "implant_placed", "modifiers": []},
    "meaning_informational_no_patient_facts": SAFE_SCOPE,
    "meaning_vague_followup_no_current_scope": SAFE_SCOPE,
}


def _load() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _ids(rows: list[dict]) -> tuple[str, ...]:
    return tuple(row["id"] for row in rows)


def _compact_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def test_exact_top_level_schema_and_value_contract() -> None:
    spec = _load()
    assert tuple(spec) == (
        "schema_version",
        "purpose",
        "implementation_enabled",
        "live_allowed",
        "authority_decision_allowed",
        "raw_contract",
        "projection_cases",
        "precedence_cases",
        "parser_cases",
        "prompt_contract",
        "completion_size_sample",
    )
    assert spec["schema_version"] == "a9.patient_scope_native_contract.v2"
    assert spec["implementation_enabled"] is False
    assert spec["live_allowed"] is False
    assert spec["authority_decision_allowed"] is False

    raw = spec["raw_contract"]
    assert tuple(raw["legacy_keys"]) == tuple(TurnPlan.model_fields)
    assert raw["shadow_sibling"] == "patient_scope"
    assert tuple(raw["patient_scope_keys"]) == tuple(PatientScopeFrame.model_fields)
    assert raw["allowed_values"] == {
        "extent": list(get_args(PatientExtent)),
        "jaw": list(get_args(PatientJaw)),
        "stage": list(get_args(PatientCareStage)),
        "modifiers": list(get_args(PatientScopeModifier)),
    }
    assert raw["safe_values"] == PatientScopeFrame().model_dump()
    assert raw["metadata_contract"] == EXPECTED_METADATA_CONTRACT


def test_required_case_manifest_is_exact_ordered_and_unique() -> None:
    spec = _load()
    groups = (
        (spec["projection_cases"], PROJECTION_IDS),
        (spec["precedence_cases"], PRECEDENCE_IDS),
        (spec["parser_cases"], PARSER_IDS),
        (spec["prompt_contract"]["examples"], PROMPT_EXAMPLE_IDS),
    )
    all_ids: list[str] = []
    for rows, expected in groups:
        assert _ids(rows) == expected
        all_ids.extend(_ids(rows))
    assert len(all_ids) == len(set(all_ids)) == 32
    assert tuple(PRECEDENCE_EXPECTATIONS) == PRECEDENCE_IDS
    assert tuple(PARSER_EXPECTATIONS) == PARSER_IDS
    assert tuple(PROMPT_SCOPE_EXPECTATIONS) == PROMPT_EXAMPLE_IDS


@pytest.mark.parametrize("case_id", PROJECTION_IDS)
def test_exact_one_key_projection_preserves_everything_else_and_input(case_id: str) -> None:
    row = next(row for row in _load()["projection_cases"] if row["id"] == case_id)
    original = copy.deepcopy(row["synthetic_planner_object"])
    projected = {
        key: value
        for key, value in row["synthetic_planner_object"].items()
        if key != "patient_scope"
    }
    assert projected == row["expected_legacy_object"]
    assert row["synthetic_planner_object"] == original

    if row["expected_legacy_valid"]:
        TurnPlan.model_validate(projected)
    else:
        with pytest.raises(ValueError):
            TurnPlan.model_validate(projected)


def test_projection_keeps_unknown_extra_and_native_invalidity_is_independent() -> None:
    rows = {row["id"]: row for row in _load()["projection_cases"]}
    extra = rows["projection_native_plus_unknown_top_level"]["expected_legacy_object"]
    assert extra["synthetic_unknown_top_level"] == "must_survive_projection"
    assert rows["projection_invalid_native_valid_legacy"]["synthetic_planner_object"]["patient_scope"] is None
    assert rows["projection_invalid_native_valid_legacy"]["expected_legacy_valid"] is True
    assert rows["projection_valid_native_invalid_legacy"]["expected_legacy_valid"] is False


def test_precedence_contract_freezes_bridge_native_and_no_backfill() -> None:
    rows = {row["id"]: row for row in _load()["precedence_cases"]}
    assert {
        case_id: {key: value for key, value in row.items() if key != "id"}
        for case_id, row in rows.items()
    } == PRECEDENCE_EXPECTATIONS
    absent = rows["precedence_absent_uses_bridge"]
    assert "patient_scope" not in absent["synthetic_input"]
    assert absent["expected_source"] == "scalar_bridge"
    assert absent["expected_scope"]["extent"] == "one_tooth"
    assert absent["expected_container"] == {
        "status": "defaulted",
        "error": None,
        "provenance": "turn_plan.schema_default",
    }

    present = rows["precedence_present_object_uses_native"]
    assert present["synthetic_input"]["patient_situation"] == "one_tooth_missing"
    assert present["expected_scope"]["extent"] == "full_arch"
    assert present["forbid_scalar_backfill"] is True

    invalid_container = rows["precedence_present_invalid_container_no_bridge"]
    assert invalid_container["expected_scope"] == PatientScopeFrame().model_dump()
    assert invalid_container["expected_container"]["error"] == "patient_scope_invalid_type"
    assert set(invalid_container["expected_field_status"].values()) == {"defaulted"}

    invalid_member = rows["precedence_present_invalid_member_no_backfill"]
    assert invalid_member["expected_scope"]["extent"] == "unknown"
    assert invalid_member["expected_scope"]["jaw"] == "upper"
    assert invalid_member["expected_field_status"]["extent"] == "invalid"


@pytest.mark.parametrize("case_id", PARSER_IDS)
def test_parser_fixture_expected_values_and_metadata_validate(case_id: str) -> None:
    spec = _load()
    row = next(row for row in spec["parser_cases"] if row["id"] == case_id)
    assert {key: value for key, value in row.items() if key != "id"} == PARSER_EXPECTATIONS[case_id]
    PatientScopeFrame.model_validate(row["expected_scope"])

    metadata = spec["raw_contract"]["metadata_contract"]
    container = FieldMeta(
        confidence=metadata["confidence"],
        provenance=metadata["container_present_provenance"],
        status=row["expected_container"]["status"],
        error=row["expected_container"]["error"],
    )
    children: dict[str, FieldMeta] = {}
    for field in SCOPE_FIELDS:
        status = row["expected_field_status"][field]
        provenance = (
            metadata["schema_default_provenance"]
            if status == "defaulted"
            else metadata["native_field_provenance"][field]
        )
        children[field] = FieldMeta(
            confidence=metadata["confidence"],
            provenance=provenance,
            status=status,
            error=row["expected_field_error"][field],
        )
    PatientScopeFrameMeta(container=container, **children)

    has_issue = container.status in {"missing", "invalid"} or any(
        meta.status in {"missing", "invalid"} for meta in children.values()
    )
    assert row["expected_shadow_status"] == ("partial" if has_issue else "ok")


def test_parser_manifest_covers_exact_error_taxonomy_and_special_rules() -> None:
    rows = {row["id"]: row for row in _load()["parser_cases"]}
    observed_errors = {
        error
        for row in rows.values()
        for error in [row["expected_container"]["error"], *row["expected_field_error"].values()]
        if error is not None
    }
    assert observed_errors == EXPECTED_NATIVE_ERRORS

    for case_id in ("container_null_invalid_type", "container_non_object_invalid_type"):
        assert set(rows[case_id]["expected_field_status"].values()) == {"defaulted"}

    extra = rows["container_extra_field_preserves_neighbors"]
    assert extra["expected_container"]["error"] == "patient_scope_extra_field"
    assert set(extra["expected_field_status"].values()) == {"valid"}
    assert "synthetic_extra" not in json.dumps(extra["expected_scope"])

    mixed = rows["modifier_not_allowed"]
    assert mixed["raw_container"]["modifiers"] == [
        "reported_bone_deficit",
        "synthetic_unsupported",
    ]
    assert mixed["expected_scope"]["modifiers"] == []
    assert mixed["expected_field_error"]["modifiers"] == "patient_modifier_not_allowed"

    duplicate = rows["modifiers_duplicate_canonical"]
    assert duplicate["expected_scope"]["modifiers"] == ["reported_bone_deficit"]


def test_prompt_contract_is_semantic_abstract_and_unknown_safe() -> None:
    prompt = _load()["prompt_contract"]
    assert tuple(prompt["required_semantics"]) == REQUIRED_PROMPT_SEMANTICS
    assert tuple(prompt["forbidden_semantics"]) == FORBIDDEN_PROMPT_SEMANTICS
    assert _ids(prompt["examples"]) == PROMPT_EXAMPLE_IDS
    for row in prompt["examples"]:
        assert set(row) == {"id", "expected_scope"}
        assert row["expected_scope"] == PROMPT_SCOPE_EXPECTATIONS[row["id"]]
        PatientScopeFrame.model_validate(row["expected_scope"])


def test_fixture_contains_only_synthetic_governed_objects_without_live_payload_keys() -> None:
    spec = _load()
    forbidden_keys = {"question", "q", "answer", "history", "sid", "session_id", "response"}

    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(spec)
    serialized = json.dumps(spec, ensure_ascii=False)
    assert "patient_scope_a9_live_" not in serialized
    assert "patient_scope_a9_multi_" not in serialized


def test_representative_completion_size_and_native_delta_are_reproducible() -> None:
    spec = _load()
    sample = spec["completion_size_sample"]
    planner_object = sample["planner_object"]
    without_scope = {key: value for key, value in planner_object.items() if key != "patient_scope"}
    without_bytes = len(_compact_bytes(without_scope))
    with_bytes = len(_compact_bytes(planner_object))

    assert sample["classification"] == "representative_upper_size_not_worst_case"
    assert tuple(planner_object) == (*spec["raw_contract"]["legacy_keys"], "patient_scope")
    assert tuple(planner_object["aspects"]) == get_args(AspectKind)
    PatientScopeFrame.model_validate(planner_object["patient_scope"])
    TurnPlan.model_validate(without_scope)
    assert without_bytes == sample["without_patient_scope_utf8_bytes"] == 465
    assert with_bytes == sample["with_patient_scope_utf8_bytes"] == 585
    assert with_bytes - without_bytes == sample["native_sibling_delta_utf8_bytes"] == 120
    assert sample["tokenizer_exact_tokens"] is None
    assert sample["current_max_completion_tokens"] == 300
    assert sample["budget_verdict"] == "implementation_decision_required"


def test_frozen_contract_is_bound_to_native_implementation_seams() -> None:
    planner_path = Path("core/turn_planner_llm.py")
    planner_source = planner_path.read_text(encoding="utf-8")
    assert "_PATIENT_SCOPE_PROMPT" in planner_source
    assert "patient_situation, patient_scope, brand_filter" in planner_source
    assert 'key != "patient_scope"' in planner_source
    assert "_project_legacy_turn_plan_raw(obj)" in planner_source

    builder_source = Path("core/turn_frame_from_raw.py").read_text(encoding="utf-8")
    assert 'if "patient_scope" not in raw' in builder_source
    assert 'raw["patient_scope"]' in builder_source
    assert "_patient_scope_from_scalar(raw)" in builder_source
    assert "_patient_scope_from_native" in builder_source
