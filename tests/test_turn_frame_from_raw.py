from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from core.turn_frame_from_raw import build_turn_frame_from_raw

_TOPICS = frozenset({"clinic", "doctors", "implantation"})


def _valid_raw() -> dict:
    return {
        "route": "content",
        "aspects": ["overview", "duration"],
        "topic": "clinic",
        "topic_confidence": 0.8,
    }


def test_valid_slice_builds_expected_values_and_metadata():
    frame = build_turn_frame_from_raw(_valid_raw(), allowed_topics=_TOPICS)

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


def test_a6_empty_aspects_preserves_valid_topic_as_partial_fields():
    raw = {
        "route": "content",
        "aspects": [],
        "topic": "doctors",
        "topic_confidence": 0.95,
    }

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

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

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

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

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

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

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

    assert frame.topic is None
    assert frame.field_meta.topic.status == "missing"
    assert frame.field_meta.topic.error is None
    assert frame.field_meta.topic.confidence == 0.0


def test_non_string_topic_does_not_leak_raw_value():
    raw = _valid_raw()
    raw["topic"] = {"secret": "patient-value"}

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)
    dumped = str(frame.model_dump())

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_invalid_type"
    assert "patient-value" not in dumped


def test_out_of_taxonomy_topic_is_invalid_without_value_leak():
    raw = _valid_raw()
    raw["topic"] = "secret-other-client-topic"

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)
    dumped = str(frame.model_dump())

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_not_allowed"
    assert "secret-other-client-topic" not in dumped


@pytest.mark.parametrize("bad_confidence", [True, "0.8", -0.1, 1.1])
def test_invalid_topic_confidence_drops_topic_with_stable_error(bad_confidence):
    raw = _valid_raw()
    raw["topic_confidence"] = bad_confidence

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

    assert frame.topic is None
    assert frame.field_meta.topic.confidence == 0.0
    assert frame.field_meta.topic.status == "invalid"
    assert frame.field_meta.topic.error == "topic_confidence_invalid"


def test_positive_confidence_without_topic_is_invalid():
    raw = _valid_raw()
    raw["topic"] = None
    raw["topic_confidence"] = 0.7

    frame = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

    assert frame.topic is None
    assert frame.field_meta.topic.error == "topic_confidence_invalid"


def test_builder_does_not_mutate_raw_or_nested_unknown_values():
    raw = _valid_raw()
    raw["unknown_nested"] = {"items": [1, {"x": "y"}]}
    before = copy.deepcopy(raw)

    build_turn_frame_from_raw(raw, allowed_topics=_TOPICS)

    assert raw == before


def test_unknown_raw_fields_do_not_enter_frame_dump():
    raw = _valid_raw()
    raw["question"] = "secret question"
    raw["answer"] = "secret answer"
    raw["history"] = ["secret history"]
    raw["exception"] = "secret exception"

    dumped = build_turn_frame_from_raw(raw, allowed_topics=_TOPICS).model_dump()
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


def test_non_migrated_axes_are_defaulted_with_stable_provenance():
    frame = build_turn_frame_from_raw(_valid_raw(), allowed_topics=_TOPICS)

    for name in (
        "emotion",
        "specificity",
        "patient_scope",
        "service_id",
        "follow_up",
        "followup_of",
        "needs_clarification",
    ):
        meta = getattr(frame.field_meta, name)
        assert meta.status == "defaulted", name
        assert meta.provenance == "a7.not_migrated", name
        assert meta.confidence == 0.0, name
        assert meta.error is None, name


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
    thematic_tokens = ("doctors", "extraction", "implantation", "a6_04", "a6_05", "a6_06")
    assert [token for token in thematic_tokens if token in lower] == []
