"""Frame-first planner LLM tests (C2b)."""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path
from typing import get_args

import pytest

from contracts.answer_plan import AspectKind
from contracts.decision_frame import RouteIntent
from contracts.patient_situation import PatientSituationKind
from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import PatientCareStage, PatientExtent, PatientJaw, PatientScopeModifier
from contracts.turn_plan import TurnPlan
from core.target_client_data import allowed_brand_filters, build_compact_service_catalog
from core.turn_frame_from_raw import build_turn_frame_from_raw as _real_build_turn_frame_from_raw
from core.turn_planner_llm import (
    _PATIENT_SCOPE_PROMPT,
    _SYSTEM,
    _TURN_PLANNER_MAX_COMPLETION_TOKENS,
    _planner_chat_completions_create,
    _planner_completion_controls,
    plan_turn_attempt,
)
from core.topic_taxonomy import load_client_topic_taxonomy

_DEMO_TOPICS = frozenset(
    {
        "clinic",
        "doctors",
        "extraction",
        "implantation",
        "orthodontics",
        "periodontology",
        "prosthetics",
        "treatment",
        "whitening",
    }
)
_NATIVE_FIXTURE = Path("tests/fixtures/patient_scope_native_contract_a9_v2.json")


def _native_spec() -> dict:
    return json.loads(_NATIVE_FIXTURE.read_text(encoding="utf-8"))


def _mock_llm(monkeypatch, payload):
    captured: dict = {}

    def _fake(**kwargs):
        captured["_call_count"] = captured.get("_call_count", 0) + 1
        captured.update(kwargs)

        class _Msg:
            content = json.dumps(payload)

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _fake)
    return captured


def _planner_catalog():
    return [{"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"}]


def _planner_filters():
    return (frozenset(), frozenset())


def _prepare_attempt(monkeypatch, payload):
    monkeypatch.setattr(
        "core.turn_planner_llm.build_compact_service_catalog",
        lambda _cid: _planner_catalog(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.allowed_brand_filters",
        lambda _cid: _planner_filters(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.load_client_topic_taxonomy",
        lambda _cid: _DEMO_TOPICS,
    )
    return _mock_llm(monkeypatch, payload)


def _valid_attempt_payload() -> dict:
    return {
        "route": "content",
        "aspects": ["overview"],
        "service_id": None,
        "followup_of": None,
        "needs_clarify": False,
        "patient_situation": None,
        "brand_filter": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }


def test_turn_plan_model_accepts_legacy_planner_payload_without_topic():
    plan = TurnPlan.model_validate(
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        }
    )
    assert plan.topic is None
    assert plan.topic_confidence == 0.0


def test_plan_turn_attempt_user_content_includes_dynamic_client_topics(monkeypatch):
    captured = _prepare_attempt(
        monkeypatch,
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": "implantation",
            "topic_confidence": 0.8,
        },
    )
    plan_turn_attempt("расскажите про имплантацию", "tp-topics", "demo")
    user = captured["messages"][1]["content"]
    assert "Разрешенные topics" in user
    assert "implantation" in user
    assert "prosthetics" in user


def test_plan_turn_attempt_survives_topic_taxonomy_loader_failure(monkeypatch):
    captured_events: list[dict] = []

    def _taxonomy_boom(_cid):
        raise RuntimeError("secret path clients/demo/md/broken.md frontmatter leaked")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm.allowed_brand_filters", lambda _cid: _planner_filters())
    monkeypatch.setattr("core.turn_planner_llm.load_client_topic_taxonomy", _taxonomy_boom)
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured_events.append({"event": event, **fields}),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
    )
    attempt = plan_turn_attempt("сколько стоит all-on-4?", "tp-taxonomy-fail", "demo")
    assert attempt.shadow_status == "partial"
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic is None
    assert captured_events[0]["reason"] == "topic_taxonomy_unavailable"
    payload = json.dumps(captured_events, ensure_ascii=False)
    assert "secret path" not in payload


def test_plan_turn_attempt_prompt_requires_null_topic_when_taxonomy_empty(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm.allowed_brand_filters", lambda _cid: _planner_filters())
    monkeypatch.setattr("core.turn_planner_llm.load_client_topic_taxonomy", lambda _cid: frozenset())
    captured = _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": None,
            "topic_confidence": 0.0,
        },
    )
    plan_turn_attempt("сколько стоит all-on-4?", "tp-taxonomy-empty", "demo")
    user = captured["messages"][1]["content"]
    assert "topic=null" in user
    assert "topic_confidence=0.0" in user
    assert "Разрешенные topics" in user
    assert "недоступны" in user


def test_system_prompt_has_no_hardcoded_topic_names():
    banned = (
        "implantation",
        "prosthetics",
        "clinic",
        "doctors",
        "orthodontics",
        "periodontology",
        "extraction",
        "whitening",
        "treatment",
    )
    hits = [name for name in banned if re.search(rf'["\']{re.escape(name)}["\']', _SYSTEM.lower())]
    assert hits == []


def _iter_firewall_py_files() -> list[Path]:
    paths: list[Path] = []
    for root in (Path("orchestration"), Path("core")):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.name in {"turn_planner_llm.py", "topic_taxonomy.py", "turn_frame_shadow.py"}:
                continue
            paths.append(path)
    return paths


def _reads_turn_plan_topic(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "topic":
            if isinstance(node.value, ast.Name) and node.value.id in {"turn_plan", "plan"}:
                hits.append(f"{node.value.id}.topic")
    return hits


def _imports_turn_plan(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "contracts.turn_plan":
            if any(alias.name == "TurnPlan" for alias in node.names):
                return True
    return False


def test_downstream_modules_do_not_read_turn_plan_topic():
    offenders: dict[str, list[str]] = {}
    for path in _iter_firewall_py_files():
        text_path = str(path).replace("\\", "/")
        if not any(token in text_path for token in ("routing", "composer", "orchestration")):
            continue
        if not _imports_turn_plan(path):
            continue
        hits = _reads_turn_plan_topic(path)
        if hits:
            offenders[str(path)] = hits
    assert offenders == {}


@pytest.mark.parametrize("case_id", [row["id"] for row in _native_spec()["projection_cases"]])
def test_plan_turn_attempt_binds_frozen_native_scope_cases(monkeypatch, case_id):
    row = next(row for row in _native_spec()["projection_cases"] if row["id"] == case_id)
    payload = copy.deepcopy(row["synthetic_planner_object"])
    before = copy.deepcopy(payload)
    captured = _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Синтетический contract turn", f"native-{case_id}", "demo")
    assert captured["_call_count"] == 1
    assert payload == before
    assert attempt.shadow_frame is not None
    raw_scope = row["synthetic_planner_object"].get("patient_scope")
    if isinstance(raw_scope, dict):
        expected_scope = {
            "extent": raw_scope.get("extent", "unknown"),
            "jaw": raw_scope.get("jaw", "unknown"),
            "stage": raw_scope.get("stage", "unknown"),
            "modifiers": raw_scope.get("modifiers", []),
        }
    else:
        expected_scope = {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    assert attempt.shadow_frame.patient_scope.model_dump() == expected_scope
    raw_scope = row["synthetic_planner_object"].get("patient_scope")
    if row["expected_legacy_valid"]:
        assert attempt.shadow_status == ("ok" if isinstance(raw_scope, dict) else "partial")
    elif row["id"] == "projection_native_plus_unknown_top_level":
        assert attempt.shadow_status == "ok"
    else:
        assert attempt.shadow_status == "partial"


def test_native_scope_prompt_is_frozen_semantic_block_without_product_mappings():
    assert _PATIENT_SCOPE_PROMPT in _SYSTEM
    for fragment in (
        "extent, jaw, stage, modifiers",
        "patient_situation верни отдельно",
        "Не добавляй другие ключи",
    ):
        assert fragment in _PATIENT_SCOPE_PROMPT


def test_planner_completion_controls_are_bounded_and_disable_qwen_thinking(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.TURN_PLANNER_LLM_MODEL", "qwen3.6-flash")
    assert _planner_completion_controls() == {
        "max_completion_tokens": 700,
        "extra_body": {"enable_thinking": False},
    }
    monkeypatch.setattr("core.turn_planner_llm.TURN_PLANNER_LLM_MODEL", "gpt-test")
    assert _planner_completion_controls() == {"max_completion_tokens": 700}


def test_non_qwen_planner_outgoing_kwargs_bypass_qwen_wrapper(monkeypatch):
    captured: dict = {}

    def _direct_create(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "core.turn_planner_llm.chat_completions_create",
        lambda **_kwargs: pytest.fail("non-Qwen planner must not use Qwen wrapper"),
    )
    monkeypatch.setattr("core.turn_planner_llm.chat_client.chat.completions.create", _direct_create)
    _planner_chat_completions_create(model="gpt-test", temperature=0, max_completion_tokens=700)
    assert captured["model"] == "gpt-test"
    assert "extra_body" not in captured


def test_planner_call_uses_qwen_controls_once_without_retry(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.TURN_PLANNER_LLM_MODEL", "qwen3.6-flash")
    captured = _prepare_attempt(monkeypatch, _valid_attempt_payload())
    attempt = plan_turn_attempt("Синтетический budget turn", "native-budget", "demo")
    assert attempt.shadow_status == "ok"
    assert captured["_call_count"] == 1
    assert captured["max_completion_tokens"] == 700
    assert captured["extra_body"] == {"enable_thinking": False}


def test_current_demo_compact_reference_and_catalog_drift_guard():
    spec = _native_spec()
    sample = spec["completion_size_sample"]["planner_object"]
    rows = build_compact_service_catalog("demo")
    service_ids = [row["service_id"] for row in rows]
    groups, brands = allowed_brand_filters("demo")
    brand_groups = list(groups)
    brand_tokens = list(brands)
    topics = list(load_client_topic_taxonomy("demo"))
    utf8_len = lambda value: len(str(value).encode("utf-8"))
    longest = lambda values: max(values, key=utf8_len)
    assert utf8_len(longest(service_ids)) <= utf8_len(sample["service_id"])
    derived = {
        "route": longest(get_args(RouteIntent)),
        "aspects": list(get_args(AspectKind)),
        "service_id": longest(service_ids),
        "followup_of": longest(service_ids),
        "needs_clarify": True,
        "patient_situation": longest(get_args(PatientSituationKind)),
        "brand_filter": {"brand_group": longest(brand_groups), "brand": longest(brand_tokens)},
        "topic": longest(topics),
        "topic_confidence": 1.0,
        "patient_scope": {
            "extent": longest(get_args(PatientExtent)),
            "jaw": longest(get_args(PatientJaw)),
            "stage": longest(get_args(PatientCareStage)),
            "modifiers": [longest(get_args(PatientScopeModifier))],
        },
    }
    compact_bytes = json.dumps(derived, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(compact_bytes) == 638
    assert len(compact_bytes) < _TURN_PLANNER_MAX_COMPLETION_TOKENS


def test_plan_turn_attempt_valid_payload_returns_ok(monkeypatch):
    _prepare_attempt(monkeypatch, _valid_attempt_payload())
    attempt = plan_turn_attempt("Расскажите про имплантацию", "attempt-ok", "demo")
    assert isinstance(attempt, PlannerAttempt)
    assert attempt.shadow_status == "ok"
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "implantation"


def test_plan_turn_attempt_known_patient_kind_stays_ok_with_mapped_scope(monkeypatch):
    payload = _valid_attempt_payload()
    payload["patient_situation"] = "one_tooth_missing"
    _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Нет одного зуба", "attempt-scope-contract", "demo")
    assert attempt.shadow_status == "ok"
    assert attempt.shadow_frame.patient_scope.extent == "one_tooth"


def test_plan_turn_attempt_malformed_patient_kind_does_not_leak(monkeypatch):
    payload = _valid_attempt_payload()
    payload["patient_situation"] = {"secret-kind": "one_tooth_missing"}
    _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Пациентский секрет", "attempt-scope-malformed", "demo")
    assert attempt.shadow_status == "ok"
    assert attempt.shadow_frame is not None
    assert "secret-kind" not in str(attempt.shadow_frame.model_dump())


def test_plan_turn_attempt_empty_aspects_keeps_topic_in_partial_frame(monkeypatch):
    payload = _valid_attempt_payload()
    payload["topic"] = "doctors"
    payload["topic_confidence"] = 0.95
    payload["aspects"] = []
    _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Кто занимается лечением?", "attempt-partial", "demo")
    assert attempt.shadow_status == "partial"
    assert attempt.shadow_frame.topic == "doctors"
    assert attempt.shadow_frame.field_meta.aspects.error == "aspects_empty"


def test_plan_turn_attempt_invalid_topic_is_partial(monkeypatch):
    payload = _valid_attempt_payload()
    payload["topic"] = "other-client-secret-topic"
    _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Общий вопрос", "attempt-topic-invalid", "demo")
    assert attempt.shadow_status == "partial"
    assert attempt.shadow_frame.topic is None
    assert attempt.shadow_frame.field_meta.topic.error == "topic_not_allowed"


def test_plan_turn_attempt_bad_json_is_not_available(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm.allowed_brand_filters", lambda _cid: _planner_filters())

    def _bad(**_kwargs):
        class _Msg:
            content = "not json"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _bad)
    attempt = plan_turn_attempt("Вопрос", "attempt-bad-json", "demo")
    assert attempt.shadow_status == "not_available"
    assert attempt.shadow_frame is None


def test_plan_turn_attempt_non_object_json_is_not_available(monkeypatch):
    _prepare_attempt(monkeypatch, ["content", "overview"])
    attempt = plan_turn_attempt("Вопрос", "attempt-list-json", "demo")
    assert attempt.shadow_status == "not_available"


def test_builder_failure_returns_degraded(monkeypatch):
    events: list[dict] = []
    _prepare_attempt(monkeypatch, _valid_attempt_payload())
    monkeypatch.setattr(
        "core.turn_planner_llm.build_turn_frame_from_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("builder failed")),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: events.append({"event": event, **fields}),
    )
    attempt = plan_turn_attempt("Вопрос", "attempt-builder-fail", "demo")
    assert attempt.shadow_status == "degraded"
    assert attempt.shadow_frame is None
    assert any(event["event"] == "turn_planner_frame_degraded" for event in events)


def test_empty_question_and_empty_catalog_make_no_llm_calls(monkeypatch):
    calls = {"count": 0}

    def _counted(**_kwargs):
        calls["count"] += 1
        raise AssertionError("LLM must not be called")

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _counted)
    assert plan_turn_attempt("   ", "attempt-empty", "demo").shadow_status == "not_available"
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [])
    assert plan_turn_attempt("Вопрос", "attempt-no-catalog", "demo").shadow_status == "not_available"
    assert calls["count"] == 0


def test_plan_turn_attempt_makes_exactly_one_llm_call(monkeypatch):
    calls = {"count": 0}
    payload = _valid_attempt_payload()
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm.allowed_brand_filters", lambda _cid: _planner_filters())
    monkeypatch.setattr("core.turn_planner_llm.load_client_topic_taxonomy", lambda _cid: _DEMO_TOPICS)

    def _counted(**_kwargs):
        calls["count"] += 1

        class _Msg:
            content = json.dumps(payload)

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _counted)
    result = plan_turn_attempt("Вопрос", "attempt-one-call", "demo")
    assert result.shadow_status == "ok"
    assert calls["count"] == 1


def test_raw_payload_not_mutated_during_frame_build(monkeypatch):
    payload = _valid_attempt_payload()
    _prepare_attempt(monkeypatch, payload)
    snapshots: dict[str, dict] = {}

    def _builder(raw, *, allowed_topics, allowed_service_ids):
        snapshots["before"] = json.loads(json.dumps(raw))
        frame = _real_build_turn_frame_from_raw(
            raw,
            allowed_topics=allowed_topics,
            allowed_service_ids=allowed_service_ids,
        )
        snapshots["after"] = json.loads(json.dumps(raw))
        return frame

    monkeypatch.setattr("core.turn_planner_llm.build_turn_frame_from_raw", _builder)
    attempt = plan_turn_attempt("Вопрос", "attempt-immutable", "demo")
    assert attempt.shadow_status == "ok"
    assert snapshots["before"] == payload
    assert snapshots["after"] == payload


def test_partial_shadow_is_not_read_by_downstream_modules():
    paths = [Path("app.py"), Path("llm.py")]
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    offenders: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if "PlannerAttempt" in source or ".shadow_frame" in source:
            offenders.append(str(path))
    assert offenders == []
