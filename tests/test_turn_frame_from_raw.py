from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from contracts.planner_attempt import turn_frame_has_invalid_or_missing
from contracts.turn_frame import PatientScopeFrame, PatientScopeFrameMeta
from core.turn_frame_from_raw import _PATIENT_SCOPE_BRIDGE, build_turn_frame_from_raw

_TOPICS = frozenset({"clinic", "doctors", "implantation"})
_SERVICE_IDS = frozenset({"all_on_4", "classic", "veneers"})


def _valid_raw() -> dict:
    return {
        "route": "content",
        "aspects": ["overview", "duration"],
        "service_id": None,
        "followup_of": None,
        "needs_clarify": False,
        "topic": "clinic",
        "topic_confidence": 0.8,
    }


def _build(raw: dict):
    return build_turn_frame_from_raw(
        raw,
        allowed_topics=_TOPICS,
        allowed_service_ids=_SERVICE_IDS,
    )


_SCOPE_PROVENANCE = {
    "extent": "turn_plan.patient_situation.extent",
    "jaw": "turn_plan.patient_situation.jaw",
    "stage": "turn_plan.patient_situation.stage",
    "modifiers": "turn_plan.patient_situation.modifiers",
}
_NATIVE_FIXTURE = Path("tests/fixtures/patient_scope_native_contract_a9_v2.json")


def _native_spec() -> dict:
    return json.loads(_NATIVE_FIXTURE.read_text(encoding="utf-8"))


def _assert_patient_scope_meta(frame, mapped_fields: set[str]) -> None:
    for name in PatientScopeFrameMeta.model_fields:
        meta = getattr(frame.field_meta.patient_scope, name)
        if name in mapped_fields:
            assert meta.model_dump() == {
                "confidence": 0.0,
                "provenance": _SCOPE_PROVENANCE[name],
                "status": "valid",
                "error": None,
            }
        else:
            assert meta.model_dump() == {
                "confidence": 0.0,
                "provenance": "turn_plan.schema_default",
                "status": "defaulted",
                "error": None,
            }


def test_valid_slice_builds_expected_values_and_metadata():
    frame = _build(_valid_raw())

    assert frame.intent == "content"
    assert frame.topic == "clinic"
    assert frame.aspects == ["overview", "duration"]
    assert frame.primary_aspect == "overview"
    assert frame.field_meta.intent.status == "valid"
    assert frame.field_meta.intent.provenance == "turn_plan.raw.route"
    assert frame.field_meta.topic.status == "valid"
    assert frame.field_meta.topic.confidence == 0.8
    assert frame.field_meta.topic.provenance == "turn_plan.raw.topic"
    assert frame.field_meta.aspects.status == "valid"
    assert frame.field_meta.primary_aspect.status == "valid"
    assert frame.field_meta.primary_aspect.provenance == "turn_plan.raw.aspects[0]"
    assert frame.service_id is None
    assert frame.field_meta.service_id.status == "valid"
    assert frame.field_meta.service_id.provenance == "turn_plan.raw.service_id"
    assert frame.followup_of is None
    assert frame.follow_up is False
    assert frame.field_meta.followup_of.status == "valid"
    assert frame.field_meta.follow_up.status == "valid"
    assert frame.needs_clarification is False
    assert frame.field_meta.needs_clarification.status == "valid"


def test_valid_service_id_is_stripped_without_case_conversion():
    raw = _valid_raw()
    raw["service_id"] = " classic "

    frame = _build(raw)

    assert frame.service_id == "classic"
    assert frame.field_meta.service_id.status == "valid"
    assert frame.field_meta.service_id.error is None
    assert frame.field_meta.service_id.confidence == 0.0
    assert frame.field_meta.service_id.provenance == "turn_plan.raw.service_id"


def test_service_id_explicit_null_and_missing_key_are_distinct():
    explicit = _build(_valid_raw())
    missing_raw = _valid_raw()
    missing_raw.pop("service_id")
    missing = _build(missing_raw)

    assert explicit.service_id is None
    assert explicit.field_meta.service_id.status == "valid"
    assert explicit.field_meta.service_id.provenance == "turn_plan.raw.service_id"
    assert missing.service_id is None
    assert missing.field_meta.service_id.status == "defaulted"
    assert missing.field_meta.service_id.provenance == "turn_plan.schema_default"


@pytest.mark.parametrize(
    ("raw_service_id", "expected_error"),
    [
        (42, "service_id_invalid_type"),
        ({"secret": "patient-service"}, "service_id_invalid_type"),
        ("   ", "service_id_not_allowed"),
        ("secret-other-client-service", "service_id_not_allowed"),
    ],
)
def test_invalid_service_id_is_isolated_with_stable_error(
    raw_service_id,
    expected_error,
):
    raw = _valid_raw()
    raw["service_id"] = raw_service_id

    frame = _build(raw)
    assert frame.service_id is None
    assert frame.field_meta.service_id.status == "invalid"
    assert frame.field_meta.service_id.error == expected_error


def test_followup_explicit_id_null_and_missing_key_are_consistent():
    active_raw = _valid_raw()
    active_raw["followup_of"] = " classic "
    active = _build(active_raw)
    explicit_null = _build(_valid_raw())
    missing_raw = _valid_raw()
    missing_raw.pop("followup_of")
    missing = _build(missing_raw)

    assert active.followup_of == "classic"
    assert active.follow_up is True
    assert active.field_meta.followup_of.status == "valid"
    assert active.field_meta.follow_up.status == "valid"
    assert active.field_meta.follow_up.provenance == "derived.followup_of"
    assert explicit_null.followup_of is None
    assert explicit_null.follow_up is False
    assert explicit_null.field_meta.followup_of.status == "valid"
    assert explicit_null.field_meta.follow_up.status == "valid"
    assert missing.followup_of is None
    assert missing.follow_up is False
    assert missing.field_meta.followup_of.status == "defaulted"
    assert missing.field_meta.follow_up.status == "defaulted"
    assert missing.field_meta.follow_up.provenance == "turn_plan.schema_default"


@pytest.mark.parametrize(
    ("raw_followup", "expected_error"),
    [
        (42, "followup_of_invalid_type"),
        ({"secret": "patient-followup"}, "followup_of_invalid_type"),
        ("", "followup_of_not_allowed"),
        ("secret-followup", "followup_of_not_allowed"),
    ],
)
def test_invalid_followup_invalidates_derived_axis_with_stable_errors(
    raw_followup,
    expected_error,
):
    raw = _valid_raw()
    raw["followup_of"] = raw_followup

    frame = _build(raw)
    assert frame.followup_of is None
    assert frame.follow_up is False
    assert frame.field_meta.followup_of.status == "invalid"
    assert frame.field_meta.followup_of.error == expected_error
    assert frame.field_meta.follow_up.status == "invalid"
    assert frame.field_meta.follow_up.error == "follow_up_unavailable"
    assert frame.field_meta.follow_up.provenance == "derived.followup_of"


def test_invalid_catalog_raw_values_do_not_leak_into_frame_dump():
    raw = _valid_raw()
    raw["service_id"] = {"secret": "patient-service"}
    raw["followup_of"] = "secret-followup"

    dumped = str(_build(raw).model_dump())

    assert "patient-service" not in dumped
    assert "secret-followup" not in dumped


def test_needs_clarification_exact_bool_and_schema_default():
    true_raw = _valid_raw()
    true_raw["needs_clarify"] = True
    explicit_true = _build(true_raw)
    explicit_false = _build(_valid_raw())
    missing_raw = _valid_raw()
    missing_raw.pop("needs_clarify")
    missing = _build(missing_raw)

    assert explicit_true.needs_clarification is True
    assert explicit_true.field_meta.needs_clarification.status == "valid"
    assert explicit_false.needs_clarification is False
    assert explicit_false.field_meta.needs_clarification.status == "valid"
    assert missing.needs_clarification is False
    assert missing.field_meta.needs_clarification.status == "defaulted"
    assert missing.field_meta.needs_clarification.provenance == "turn_plan.schema_default"


@pytest.mark.parametrize("raw_value", [None, 0, 1, "false", [], {}])
def test_needs_clarification_rejects_non_bool_without_coercion(raw_value):
    raw = _valid_raw()
    raw["needs_clarify"] = raw_value

    frame = _build(raw)

    assert frame.needs_clarification is False
    assert frame.field_meta.needs_clarification.status == "invalid"
    assert (
        frame.field_meta.needs_clarification.error
        == "needs_clarification_invalid_type"
    )
    assert frame.field_meta.needs_clarification.provenance == "turn_plan.raw.needs_clarify"


def test_invalid_new_field_does_not_erase_other_valid_axes():
    raw = _valid_raw()
    raw["service_id"] = "secret-other-client-service"

    frame = _build(raw)

    assert frame.intent == "content"
    assert frame.field_meta.intent.status == "valid"
    assert frame.topic == "clinic"
    assert frame.field_meta.topic.status == "valid"
    assert frame.aspects == ["overview", "duration"]
    assert frame.field_meta.aspects.status == "valid"
    assert frame.service_id is None
    assert frame.field_meta.service_id.error == "service_id_not_allowed"


def test_a6_empty_aspects_preserves_valid_topic_as_partial_fields():
    raw = {
        "route": "content",
        "aspects": [],
        "topic": "doctors",
        "topic_confidence": 0.95,
    }

    frame = _build(raw)

    assert frame.topic == "doctors"
    assert frame.field_meta.topic.status == "valid"
    assert frame.aspects == []
    assert frame.field_meta.aspects.status == "invalid"
    assert frame.field_meta.aspects.error == "aspects_empty"
    assert frame.primary_aspect is None
    assert frame.field_meta.primary_aspect.status == "invalid"
    assert frame.field_meta.primary_aspect.error == "primary_aspect_unavailable"


@pytest.mark.parametrize(
    ("raw_aspects", "expected_error"),
    [
        (None, "aspects_invalid_type"),
        (("overview",), "aspects_invalid_type"),
        (["not_allowed"], "aspect_not_allowed"),
        (["overview", 42], "aspect_not_allowed"),
    ],
)
def test_invalid_aspects_are_not_silently_repaired(raw_aspects, expected_error):
    raw = _valid_raw()
    if raw_aspects is None:
        raw.pop("aspects")
    else:
        raw["aspects"] = raw_aspects

    frame = _build(raw)

    assert frame.aspects == []
    assert frame.primary_aspect is None
    assert frame.field_meta.aspects.status == "invalid"
    assert frame.field_meta.aspects.error == expected_error
    assert frame.field_meta.primary_aspect.error == "primary_aspect_unavailable"


@pytest.mark.parametrize("bad_route", [None, 42, "not_a_route", " content "])
def test_invalid_route_maps_to_unknown_with_stable_error(bad_route):
    raw = _valid_raw()
    if bad_route is None:
        raw.pop("route")
    else:
        raw["route"] = bad_route

    frame = _build(raw)

    assert frame.intent == "unknown"
    assert frame.field_meta.intent.status == "invalid"
    assert frame.field_meta.intent.error == "route_invalid"


@pytest.mark.parametrize(
    "topic_patch",
    [
        {},
        {"topic": None, "topic_confidence": 0.0},
        {"topic": "   ", "topic_confidence": None},
    ],
)
def test_missing_topic_is_explicitly_missing(topic_patch):
    raw = _valid_raw()
    raw.pop("topic")
    raw.pop("topic_confidence")
    raw.update(topic_patch)

    frame = _build(raw)

    assert frame.topic is None
    assert frame.field_meta.topic.status == "missing"
    assert frame.field_meta.topic.error is None
    assert frame.field_meta.topic.confidence == 0.0


def test_non_string_topic_does_not_leak_raw_value():
    raw = _valid_raw()
    raw["topic"] = {"secret": "patient-value"}

    frame = _build(raw)
    dumped = str(frame.model_dump())

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_invalid_type"
    assert "patient-value" not in dumped


def test_out_of_taxonomy_topic_is_invalid_without_value_leak():
    raw = _valid_raw()
    raw["topic"] = "secret-other-client-topic"

    frame = _build(raw)
    dumped = str(frame.model_dump())

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_not_allowed"
    assert "secret-other-client-topic" not in dumped


@pytest.mark.parametrize("bad_confidence", [True, "0.8", -0.1, 1.1])
def test_invalid_topic_confidence_drops_topic_with_stable_error(bad_confidence):
    raw = _valid_raw()
    raw["topic_confidence"] = bad_confidence

    frame = _build(raw)

    assert frame.topic is None
    assert frame.field_meta.topic.confidence == 0.0
    assert frame.field_meta.topic.status == "invalid"
    assert frame.field_meta.topic.error == "topic_confidence_invalid"


def test_positive_confidence_without_topic_is_invalid():
    raw = _valid_raw()
    raw["topic"] = None
    raw["topic_confidence"] = 0.7

    frame = _build(raw)

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_confidence_invalid"


def test_builder_does_not_mutate_raw_or_nested_unknown_values():
    raw = _valid_raw()
    raw["unknown_nested"] = {"items": [1, {"x": "y"}]}
    before = copy.deepcopy(raw)

    _build(raw)

    assert raw == before


def test_unknown_raw_fields_do_not_enter_frame_dump():
    raw = _valid_raw()
    raw["question"] = "secret question"
    raw["answer"] = "secret answer"
    raw["history"] = ["secret history"]
    raw["exception"] = "secret exception"

    dumped = _build(raw).model_dump()
    text = str(dumped)

    assert "secret question" not in text
    assert "secret answer" not in text
    assert "secret history" not in text
    assert "secret exception" not in text
    assert set(dumped) == {
        "intent",
        "topic",
        "aspects",
        "primary_aspect",
        "emotion",
        "specificity",
        "patient_scope",
        "service_id",
        "follow_up",
        "followup_of",
        "needs_clarification",
        "field_meta",
    }


def test_only_deferred_scalar_axes_keep_not_migrated_provenance():
    frame = _build(_valid_raw())

    for name in (
        "emotion",
        "specificity",
    ):
        meta = getattr(frame.field_meta, name)
        assert meta.status == "defaulted", name
        assert meta.provenance == "a7.not_migrated", name
        assert meta.confidence == 0.0, name
        assert meta.error is None, name


def test_absent_patient_scope_uses_nested_schema_defaults():
    frame = _build(_valid_raw())

    assert frame.patient_scope == PatientScopeFrame()
    assert isinstance(frame.field_meta.patient_scope, PatientScopeFrameMeta)
    _assert_patient_scope_meta(frame, set())


@pytest.mark.parametrize(
    ("patient_situation", "expected_scope", "mapped_fields"),
    [
        ("one_tooth_missing", {"extent": "one_tooth"}, {"extent"}),
        ("few_teeth_missing", {"extent": "few_teeth"}, {"extent"}),
        ("full_arch_missing", {"extent": "full_arch"}, {"extent"}),
        ("upper_jaw_missing_or_complex", {"jaw": "upper"}, {"jaw"}),
        (
            "existing_implant_prosthetic_stage",
            {"stage": "implant_placed"},
            {"stage"},
        ),
        ("extraction_then_implant", {"stage": "extraction_context"}, {"stage"}),
        (
            "bone_deficit_or_grafting",
            {"modifiers": ["reported_bone_deficit"]},
            {"modifiers"},
        ),
        ("urgent_problem", {}, set()),
        ("generic_implant_interest", {}, set()),
        ("unknown", {}, set()),
        (None, {}, set()),
    ],
)
def test_scalar_patient_situation_uses_exact_loss_aware_bridge(
    patient_situation,
    expected_scope,
    mapped_fields,
):
    raw = _valid_raw()
    raw["patient_situation"] = patient_situation
    before = copy.deepcopy(raw)

    frame = _build(raw)

    expected = {
        "extent": "unknown",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": [],
        **expected_scope,
    }
    assert frame.patient_scope.model_dump() == expected
    _assert_patient_scope_meta(frame, mapped_fields)
    assert raw == before


def test_noop_scalar_kinds_and_absent_have_same_scope_dump():
    absent = _build(_valid_raw())
    for kind in (None, "unknown", "urgent_problem", "generic_implant_interest"):
        explicit_raw = _valid_raw()
        explicit_raw["patient_situation"] = kind
        explicit = _build(explicit_raw)
        assert absent.patient_scope.model_dump() == explicit.patient_scope.model_dump()
        assert (
            absent.field_meta.patient_scope.model_dump()
            == explicit.field_meta.patient_scope.model_dump()
        )


@pytest.mark.parametrize(
    "malformed",
    [42, True, ["secret-list"], {"secret-dict": "kind"}, "secret-kind", " one_tooth_missing "],
)
def test_malformed_scalar_is_safe_default_without_synthetic_nested_errors(malformed):
    raw = _valid_raw()
    raw.update(
        {
            "patient_situation": malformed,
            "question": "secret-question",
            "answer": "secret-answer",
            "history": ["secret-history"],
        }
    )
    before = copy.deepcopy(raw)

    frame = _build(raw)
    dumped = str(frame.model_dump())

    assert frame.patient_scope == PatientScopeFrame()
    _assert_patient_scope_meta(frame, set())
    assert raw == before
    for secret in (
        "secret-list",
        "secret-dict",
        "secret-kind",
        "secret-question",
        "secret-answer",
        "secret-history",
    ):
        assert secret not in dumped
    assert frame.intent == "content"
    assert frame.topic == "clinic"
    assert frame.aspects == ["overview", "duration"]


@pytest.mark.parametrize(
    "patient_situation",
    ["one_tooth_missing", "bone_deficit_or_grafting", "extraction_then_implant"],
)
def test_patient_scope_bridge_does_not_change_other_shadow_axes(patient_situation):
    raw = _valid_raw()
    raw["patient_situation"] = patient_situation
    raw["service_id"] = "classic"

    frame = _build(raw)

    assert frame.intent == "content"
    assert frame.topic == "clinic"
    assert frame.aspects == ["overview", "duration"]
    assert frame.primary_aspect == "overview"
    assert frame.service_id == "classic"


def test_patient_scope_bridge_has_no_shared_mutable_modifier_state():
    raw = _valid_raw()
    raw["patient_situation"] = "bone_deficit_or_grafting"

    first = _build(raw)
    second = _build(raw)
    first.patient_scope.modifiers.clear()

    assert first.patient_scope.modifiers == []
    assert second.patient_scope.modifiers == ["reported_bone_deficit"]


def test_patient_scope_bridge_mapping_is_immutable():
    with pytest.raises(TypeError):
        _PATIENT_SCOPE_BRIDGE["secret-kind"] = (None, None, None, ())


@pytest.mark.parametrize(
    "case_id",
    [row["id"] for row in _native_spec()["parser_cases"]],
)
def test_native_patient_scope_parser_matches_frozen_cases(case_id):
    spec = _native_spec()
    row = next(row for row in spec["parser_cases"] if row["id"] == case_id)
    raw = _valid_raw()
    raw["patient_situation"] = "one_tooth_missing"
    raw["patient_scope"] = copy.deepcopy(row["raw_container"])
    before = copy.deepcopy(raw)

    frame = _build(raw)

    assert frame.patient_scope.model_dump() == row["expected_scope"]
    scope_meta = frame.field_meta.patient_scope
    assert scope_meta.container.model_dump() == {
        "confidence": 0.0,
        "provenance": "turn_plan.raw.patient_scope",
        "status": row["expected_container"]["status"],
        "error": row["expected_container"]["error"],
    }
    native_provenance = spec["raw_contract"]["metadata_contract"]["native_field_provenance"]
    for field in ("extent", "jaw", "stage", "modifiers"):
        status = row["expected_field_status"][field]
        assert getattr(scope_meta, field).model_dump() == {
            "confidence": 0.0,
            "provenance": (
                "turn_plan.schema_default"
                if status == "defaulted"
                else native_provenance[field]
            ),
            "status": status,
            "error": row["expected_field_error"][field],
        }
    assert turn_frame_has_invalid_or_missing(frame) is (row["expected_shadow_status"] == "partial")
    assert raw == before
    if case_id == "container_extra_field_preserves_neighbors":
        dumped = str(frame.model_dump())
        assert "synthetic_extra" not in dumped
        assert "must_not_serialize" not in dumped


@pytest.mark.parametrize(
    "case_id",
    [row["id"] for row in _native_spec()["precedence_cases"]],
)
def test_native_patient_scope_precedence_matches_frozen_cases(case_id):
    row = next(row for row in _native_spec()["precedence_cases"] if row["id"] == case_id)
    raw = _valid_raw()
    raw.update(copy.deepcopy(row["synthetic_input"]))
    before = copy.deepcopy(raw)

    frame = _build(raw)

    assert frame.patient_scope.model_dump() == row["expected_scope"]
    scope_meta = frame.field_meta.patient_scope
    assert scope_meta.container.model_dump() == {
        "confidence": 0.0,
        **row["expected_container"],
    }
    for field in ("extent", "jaw", "stage", "modifiers"):
        meta = getattr(scope_meta, field)
        assert meta.status == row["expected_field_status"][field]
        assert meta.provenance == row["expected_field_provenance"][field]
        assert meta.confidence == 0.0
    expected_partial = scope_meta.container.status == "invalid" or any(
        getattr(scope_meta, field).status in {"missing", "invalid"}
        for field in ("extent", "jaw", "stage", "modifiers")
    )
    assert turn_frame_has_invalid_or_missing(frame) is expected_partial
    assert raw == before


def test_builder_has_no_runtime_or_thematic_dependencies():
    path = Path("core/turn_frame_from_raw.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_import_tokens = (
        "turn_planner_llm",
        "pricebook",
        "service_catalog",
        "topic_taxonomy",
        "patient_situation",
        "flask",
        "session",
        "resolver",
        "llm",
        "openai",
        "requests",
        "httpx",
    )
    assert [name for name in imported if any(token in name for token in forbidden_import_tokens)] == []

    lower = source.lower()
    forbidden_inference_tokens = (
        "all_on_4",
        "all_on_6",
        "classic",
        "sinus_lift",
        "zygomatic",
        "detect_patient_situation",
        "recent_dialog_history",
        "patient_situation_session",
    )
    assert [token for token in forbidden_inference_tokens if token in lower] == []
    for forbidden_key in ("question", "answer", "history", "session", "cues"):
        assert f'raw.get("{forbidden_key}")' not in source
        assert f'raw["{forbidden_key}"]' not in source
