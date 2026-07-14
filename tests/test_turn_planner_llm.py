from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_plan import TurnPlan
from core.turn_frame_from_raw import build_turn_frame_from_raw as _real_build_turn_frame_from_raw
from core.turn_planner_llm import (
    _SYSTEM,
    _sanitize_topic_fields,
    _validate_plan,
    plan_turn,
    plan_turn_attempt,
    turn_plan_to_decision_frame,
)

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


def test_validate_turn_plan_rejects_unknown_service_id():
    with pytest.raises(ValueError):
        _validate_plan(
            {
                "route": "price_lookup",
                "aspects": ["price"],
                "service_id": "not_in_catalog",
                "followup_of": None,
                "needs_clarify": False,
                "patient_situation": None,
                "brand_filter": None,
            },
            allowed_service_ids=frozenset({"classic"}),
            allowed_brand_groups=frozenset({"korean"}),
            allowed_brands=frozenset({"implantium"}),
            allowed_topics=_DEMO_TOPICS,
        )


def test_plan_turn_composite_question_returns_aspects(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"},
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset({"korean"}), frozenset({"implantium"})),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price", "pain", "duration"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("Сколько стоит all-on-4, это больно и долго ли заживает?", "tp-1", "demo")

    assert isinstance(plan, TurnPlan)
    assert plan.route == "price_lookup"
    assert set(plan.aspects) == {"price", "pain", "duration"}
    assert plan.service_id == "all_on_4"


def test_plan_turn_followup_price_uses_history(monkeypatch):
    from session import mem_add_bot, mem_add_user, mem_reset

    sid = "turn-planner-followup"
    mem_reset(sid)
    mem_add_user(sid, "Делаете all-on-4?")
    mem_add_bot(sid, "Да, выполняем протокол All-on-4.")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"},
        {"service_id": "veneers", "title": "Виниры", "about": "эстетическая реставрация"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )
    captured = _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": "all_on_4",
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("а сколько стоит?", sid, "demo")

    assert plan is not None
    assert plan.followup_of == "all_on_4"
    assert plan.service_id == "all_on_4"
    user = captured["messages"][1]["content"]
    assert "Контекст диалога" in user
    assert "не источник фактов" in user
    assert "all-on-4" in user.lower()
    assert user.count("а сколько стоит?") == 1


def test_plan_turn_includes_pending_clarify_context(monkeypatch):
    from core.clarify_state import TURN_PLANNER_PENDING_CLARIFY_INSTRUCTION
    from session import mem_reset, set_pending_clarify

    sid = "turn-planner-pending-clarify"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Уточню: коронка на свой зуб или на имплант?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    monkeypatch.setattr("core.turn_planner_llm.CLARIFY_STATE_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "zirconia_crowns", "title": "Коронки из диоксида циркония", "about": "на свой зуб"},
        {"service_id": "implant_supported_prosthetics", "title": "Протезирование на имплантах", "about": "на имплант"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )
    captured = _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "implant_supported_prosthetics",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("на имплант", sid, "demo")

    assert plan is not None
    assert plan.service_id == "implant_supported_prosthetics"
    user = captured["messages"][1]["content"]
    assert TURN_PLANNER_PENDING_CLARIFY_INSTRUCTION.split("{question}", 1)[0] in user
    assert "zirconia_crowns" in user
    assert "implant_supported_prosthetics" in user


def test_plan_turn_topic_switch_after_focus_splits_followup_and_service(monkeypatch):
    from session import mem_add_bot, mem_add_user, mem_reset

    sid = "turn-planner-topic-switch"
    mem_reset(sid)
    mem_add_user(sid, "Расскажите про All-on-4")
    mem_add_bot(sid, "All-on-4 помогает восстановить зубной ряд на одной челюсти.")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть"},
        {"service_id": "veneers", "title": "Виниры", "about": "эстетика улыбки"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "veneers",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("а виниры сколько?", sid, "demo")

    assert plan is not None
    assert plan.followup_of is None
    assert plan.service_id == "veneers"


def test_plan_turn_bad_json_fail_open(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )

    def _bad(**_kwargs):
        class _Msg:
            content = "not json"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _bad)

    assert plan_turn("сколько стоит имплантация", "tp-bad", "demo") is None


def test_plan_turn_validates_brand_filter(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset({"korean"}), frozenset({"implantium"})),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "classic",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": {"brand_group": "korean", "brand": None},
        },
    )

    plan = plan_turn("сколько стоят корейские импланты", "tp-brand", "demo")

    assert plan is not None
    assert plan.brand_filter is not None
    assert plan.brand_filter.brand_group == "korean"


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


def _planner_catalog():
    return [{"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"}]


def _planner_filters():
    return (frozenset(), frozenset())


def _planner_topics():
    return _DEMO_TOPICS


def test_plan_turn_user_content_includes_dynamic_client_topics(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm._allowed_pricebook_filters", lambda _cid: _planner_filters())
    monkeypatch.setattr("core.turn_planner_llm.load_client_topic_taxonomy", lambda _cid: _DEMO_TOPICS)
    captured = _mock_llm(
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

    plan = plan_turn("расскажите про имплантацию", "tp-topics", "demo")

    assert plan is not None
    user = captured["messages"][1]["content"]
    assert "Разрешенные topics" in user
    assert "implantation" in user
    assert "prosthetics" in user


def test_plan_turn_survives_topic_taxonomy_loader_failure(monkeypatch):
    captured_events: list[dict] = []

    def _taxonomy_boom(_cid):
        raise RuntimeError("secret path clients/demo/md/broken.md frontmatter leaked")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm._allowed_pricebook_filters", lambda _cid: _planner_filters())
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

    plan = plan_turn("сколько стоит all-on-4?", "tp-taxonomy-fail", "demo")

    assert plan is not None
    assert plan.route == "price_lookup"
    assert plan.service_id == "all_on_4"
    assert plan.topic is None
    assert plan.topic_confidence == 0.0
    assert captured_events[0] == {
        "event": "turn_plan_topic_sanitized",
        "client_id": "demo",
        "sid": "tp-taxonomy-fail",
        "reason": "topic_taxonomy_unavailable",
    }
    payload = json.dumps(captured_events, ensure_ascii=False)
    assert "secret path" not in payload
    assert "broken.md" not in payload
    assert "frontmatter" not in payload
    assert "сколько стоит" not in payload


def test_plan_turn_prompt_requires_null_topic_when_taxonomy_empty(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: _planner_catalog())
    monkeypatch.setattr("core.turn_planner_llm._allowed_pricebook_filters", lambda _cid: _planner_filters())
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

    plan = plan_turn("сколько стоит all-on-4?", "tp-taxonomy-empty", "demo")

    assert plan is not None
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


def test_validate_plan_accepts_valid_native_topic(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    plan = _validate_plan(
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": "implantation",
            "topic_confidence": 0.75,
        },
        allowed_service_ids=frozenset({"all_on_4"}),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
    )

    assert plan is not None
    assert plan.topic == "implantation"
    assert plan.topic_confidence == 0.75
    assert captured == []


def test_validate_plan_sanitizes_unknown_topic_without_dropping_legacy_fields(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    plan = _validate_plan(
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": "other_client_topic",
            "topic_confidence": 0.9,
        },
        allowed_service_ids=frozenset({"all_on_4"}),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
        client_id="demo",
        sid="sanitize-unknown",
    )

    assert plan is not None
    assert plan.route == "price_lookup"
    assert plan.service_id == "all_on_4"
    assert plan.topic is None
    assert plan.topic_confidence == 0.0
    assert captured == [
        {
            "event": "turn_plan_topic_sanitized",
            "client_id": "demo",
            "sid": "sanitize-unknown",
            "reason": "topic_not_allowed",
        }
    ]


@pytest.mark.parametrize(
    "bad_topic",
    [["implantation"], {"name": "implantation"}, 42, True],
    ids=["list", "dict", "int", "bool"],
)
def test_validate_plan_sanitizes_non_string_topic(bad_topic, monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    plan = _validate_plan(
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": bad_topic,
            "topic_confidence": 0.5,
        },
        allowed_service_ids=frozenset(),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
    )

    assert plan is not None
    assert plan.topic is None
    assert plan.topic_confidence == 0.0
    assert captured[0]["reason"] == "topic_invalid_type"


def test_validate_plan_keeps_valid_topic_when_confidence_invalid(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    plan = _validate_plan(
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": "implantation",
            "topic_confidence": 1.5,
        },
        allowed_service_ids=frozenset(),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
    )

    assert plan is not None
    assert plan.topic == "implantation"
    assert plan.topic_confidence == 0.0
    assert captured[0]["reason"] == "topic_confidence_invalid"


def test_validate_plan_zeros_confidence_without_topic(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    plan = _validate_plan(
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": None,
            "topic_confidence": 0.7,
        },
        allowed_service_ids=frozenset(),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
    )

    assert plan is not None
    assert plan.topic is None
    assert plan.topic_confidence == 0.0
    assert captured[0]["reason"] == "topic_confidence_without_topic"


def test_sanitize_topic_fields_does_not_mutate_raw_dict():
    raw = {
        "route": "content",
        "aspects": ["overview"],
        "topic": "unknown_topic",
        "topic_confidence": 0.9,
    }
    before = json.loads(json.dumps(raw))

    topic, confidence, reason = _sanitize_topic_fields(raw, allowed_topics=_DEMO_TOPICS)

    assert raw == before
    assert topic is None
    assert confidence == 0.0
    assert reason == "topic_not_allowed"


def test_topic_sanitization_event_has_only_stable_reason(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: captured.append({"event": event, **fields}),
    )
    _validate_plan(
        {
            "route": "content",
            "aspects": ["overview"],
            "service_id": None,
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
            "topic": ["implantation"],
            "topic_confidence": 0.9,
        },
        allowed_service_ids=frozenset(),
        allowed_brand_groups=frozenset(),
        allowed_brands=frozenset(),
        allowed_topics=_DEMO_TOPICS,
        client_id="demo",
        sid="sanitize-event",
    )

    assert len(captured) == 1
    event = captured[0]
    assert set(event.keys()) == {"event", "client_id", "sid", "reason"}
    assert event["reason"] == "topic_invalid_type"
    payload = json.dumps(event, ensure_ascii=False)
    assert "implantation" not in payload


def test_turn_plan_to_decision_frame_ignores_native_topic():
    plan = TurnPlan(
        route="price_lookup",
        aspects=["price"],
        service_id="all_on_4",
        topic="clinic",
        topic_confidence=0.99,
    )

    decision = turn_plan_to_decision_frame(plan, client_id="demo")

    assert decision.service_topic == "implantation"
    assert decision.confidence.topic == 0.85


def _iter_firewall_py_files() -> list[Path]:
    roots = (
        Path("orchestration"),
        Path("core"),
    )
    skip_names = {
        "turn_planner_llm.py",
        "turn_frame_adapter.py",
        "topic_taxonomy.py",
        "turn_frame_shadow.py",
    }
    paths: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.name in skip_names:
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
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and node.slice.value == "topic":
                if isinstance(node.value, ast.Name) and node.value.id in {"turn_plan", "plan"}:
                    hits.append(f"{node.value.id}['topic']")
    return hits


def _imports_turn_plan(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "contracts.turn_plan":
            if any(alias.name == "TurnPlan" for alias in node.names):
                return True
    return False


def test_downstream_modules_do_not_read_turn_plan_topic():
    patterns = ("routing", "composer", "orchestration")
    offenders: dict[str, list[str]] = {}
    for path in _iter_firewall_py_files():
        text_path = str(path).replace("\\", "/")
        if not any(token in text_path for token in patterns):
            continue
        if not _imports_turn_plan(path):
            continue
        hits = _reads_turn_plan_topic(path)
        if hits:
            offenders[str(path)] = hits
    assert offenders == {}


def _prepare_attempt(monkeypatch, payload):
    monkeypatch.setattr(
        "core.turn_planner_llm.build_compact_service_catalog",
        lambda _cid: _planner_catalog(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
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


def test_plan_turn_attempt_valid_payload_returns_ok(monkeypatch):
    _prepare_attempt(monkeypatch, _valid_attempt_payload())

    attempt = plan_turn_attempt("Расскажите про имплантацию", "attempt-ok", "demo")

    assert isinstance(attempt, PlannerAttempt)
    assert attempt.shadow_status == "ok"
    assert attempt.legacy_plan is not None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "implantation"
    assert attempt.shadow_frame.field_meta.service_id.status == "valid"
    assert attempt.shadow_frame.field_meta.followup_of.status == "valid"
    assert attempt.shadow_frame.field_meta.follow_up.status == "valid"
    assert attempt.shadow_frame.field_meta.needs_clarification.status == "valid"


def test_plan_turn_attempt_known_patient_kind_stays_ok_with_mapped_scope(monkeypatch):
    payload = _valid_attempt_payload()
    payload["patient_situation"] = "one_tooth_missing"
    captured = _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Нет одного зуба", "attempt-scope-contract", "demo")

    assert captured["_call_count"] == 1
    assert attempt.shadow_status == "ok"
    assert attempt.legacy_plan is not None
    assert attempt.legacy_plan.patient_situation == "one_tooth_missing"
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.patient_scope.model_dump() == {
        "extent": "one_tooth",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": [],
    }
    scope_meta = attempt.shadow_frame.field_meta.patient_scope.model_dump()
    assert scope_meta["extent"] == {
        "confidence": 0.0,
        "provenance": "turn_plan.patient_situation.extent",
        "status": "valid",
        "error": None,
    }
    for name in ("container", "jaw", "stage", "modifiers"):
        assert scope_meta[name] == {
            "confidence": 0.0,
            "provenance": "turn_plan.schema_default",
            "status": "defaulted",
            "error": None,
        }


def test_plan_turn_attempt_malformed_patient_kind_is_partial_without_scope_leak(monkeypatch):
    payload = _valid_attempt_payload()
    payload["patient_situation"] = {"secret-kind": "one_tooth_missing"}
    captured = _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Пациентский секрет", "attempt-scope-malformed", "demo")

    assert captured["_call_count"] == 1
    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.patient_scope.model_dump() == {
        "extent": "unknown",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": [],
    }
    for field_meta in attempt.shadow_frame.field_meta.patient_scope.model_dump().values():
        assert field_meta == {
            "confidence": 0.0,
            "provenance": "turn_plan.schema_default",
            "status": "defaulted",
            "error": None,
        }
    assert attempt.shadow_frame.topic == "implantation"
    assert attempt.shadow_frame.aspects == ["overview"]
    assert "secret-kind" not in str(attempt.shadow_frame.model_dump())


def test_plan_turn_attempt_missing_optional_raw_keys_uses_schema_defaults(monkeypatch):
    payload = _valid_attempt_payload()
    payload.pop("service_id")
    payload.pop("followup_of")
    payload.pop("needs_clarify")
    _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Общий вопрос", "attempt-defaults", "demo")

    assert attempt.shadow_status == "ok"
    assert attempt.legacy_plan is not None
    assert attempt.shadow_frame is not None
    for name in ("service_id", "followup_of", "follow_up", "needs_clarification"):
        meta = getattr(attempt.shadow_frame.field_meta, name)
        assert meta.status == "defaulted", name
        assert meta.provenance == "turn_plan.schema_default", name
        assert meta.error is None, name


@pytest.mark.parametrize(
    ("field", "bad_value", "meta_field", "expected_error"),
    [
        ("service_id", "other-client-service", "service_id", "service_id_not_allowed"),
        ("followup_of", "other-client-service", "followup_of", "followup_of_not_allowed"),
    ],
)
def test_unknown_catalog_field_keeps_other_shadow_axes_and_strict_failure(
    monkeypatch,
    field,
    bad_value,
    meta_field,
    expected_error,
):
    payload = _valid_attempt_payload()
    payload[field] = bad_value
    _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Общий вопрос", f"attempt-bad-{field}", "demo")

    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "implantation"
    assert attempt.shadow_frame.aspects == ["overview"]
    assert getattr(attempt.shadow_frame.field_meta, meta_field).error == expected_error
    assert bad_value not in str(attempt.shadow_frame.model_dump())


def test_non_bool_clarify_is_invalid_only_in_shadow_strict_coercion_unchanged(monkeypatch):
    payload = _valid_attempt_payload()
    payload["needs_clarify"] = 1
    _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Общий вопрос", "attempt-clarify-coercion", "demo")

    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is not None
    assert attempt.legacy_plan.needs_clarify is True
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.needs_clarification is False
    assert (
        attempt.shadow_frame.field_meta.needs_clarification.error
        == "needs_clarification_invalid_type"
    )


def test_plan_turn_wrapper_returns_attempt_legacy_plan(monkeypatch):
    payload = _valid_attempt_payload()
    _prepare_attempt(monkeypatch, payload)
    attempt = plan_turn_attempt("Расскажите про имплантацию", "attempt-wrapper", "demo")

    _prepare_attempt(monkeypatch, payload)
    plan = plan_turn("Расскажите про имплантацию", "attempt-wrapper", "demo")

    assert plan == attempt.legacy_plan


def test_plan_turn_attempt_empty_aspects_keeps_topic_in_partial_frame(monkeypatch):
    payload = _valid_attempt_payload()
    payload["topic"] = "doctors"
    payload["topic_confidence"] = 0.95
    payload["aspects"] = []
    _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Кто занимается лечением?", "attempt-partial", "demo")

    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "doctors"
    assert attempt.shadow_frame.field_meta.topic.status == "valid"
    assert attempt.shadow_frame.field_meta.aspects.error == "aspects_empty"
    assert attempt.shadow_frame.field_meta.primary_aspect.error == "primary_aspect_unavailable"


def test_plan_turn_wrapper_keeps_a6_empty_aspects_fail_open(monkeypatch):
    payload = _valid_attempt_payload()
    payload["topic"] = "doctors"
    payload["topic_confidence"] = 0.95
    payload["aspects"] = []
    _prepare_attempt(monkeypatch, payload)

    plan = plan_turn("Кто занимается лечением?", "wrapper-a6-fail-open", "demo")

    assert plan is None


def test_plan_turn_attempt_invalid_topic_preserves_valid_legacy_semantics(monkeypatch):
    payload = _valid_attempt_payload()
    payload["topic"] = "other-client-secret-topic"
    _prepare_attempt(monkeypatch, payload)

    attempt = plan_turn_attempt("Общий вопрос", "attempt-topic-invalid", "demo")

    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is not None
    assert attempt.legacy_plan.route == "content"
    assert attempt.legacy_plan.aspects == ["overview"]
    assert attempt.legacy_plan.topic is None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic is None
    assert attempt.shadow_frame.field_meta.topic.error == "topic_not_allowed"
    assert "other-client-secret-topic" not in str(attempt.shadow_frame.model_dump())


def test_plan_turn_attempt_bad_json_is_not_available(monkeypatch):
    monkeypatch.setattr(
        "core.turn_planner_llm.build_compact_service_catalog",
        lambda _cid: _planner_catalog(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: _planner_filters(),
    )

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
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is None


def test_plan_turn_attempt_non_object_json_is_not_available(monkeypatch):
    _prepare_attempt(monkeypatch, ["content", "overview"])

    attempt = plan_turn_attempt("Вопрос", "attempt-list-json", "demo")

    assert attempt.shadow_status == "not_available"
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is None


def test_builder_failure_does_not_destroy_valid_legacy_plan(monkeypatch):
    events: list[dict] = []
    _prepare_attempt(monkeypatch, _valid_attempt_payload())
    monkeypatch.setattr(
        "core.turn_planner_llm.build_turn_frame_from_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("secret question and exception text")
        ),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.log_json",
        lambda _logger, event, **fields: events.append({"event": event, **fields}),
    )

    attempt = plan_turn_attempt("Пациентский секрет", "attempt-builder-fail", "demo")

    assert attempt.shadow_status == "degraded"
    assert attempt.shadow_frame is None
    assert attempt.legacy_plan is not None
    degraded = [event for event in events if event["event"] == "turn_planner_shadow_degraded"]
    assert degraded == [
        {
            "event": "turn_planner_shadow_degraded",
            "client_id": "demo",
            "sid": "attempt-builder-fail",
            "reason": "turn_frame_build_failed",
        }
    ]
    assert "secret question" not in json.dumps(events, ensure_ascii=False)


def test_builder_failure_and_strict_failure_returns_degraded(monkeypatch):
    payload = _valid_attempt_payload()
    payload["aspects"] = []
    _prepare_attempt(monkeypatch, payload)
    monkeypatch.setattr(
        "core.turn_planner_llm.build_turn_frame_from_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("builder failed")),
    )

    attempt = plan_turn_attempt("Вопрос", "attempt-both-fail", "demo")

    assert attempt.shadow_status == "degraded"
    assert attempt.shadow_frame is None
    assert attempt.legacy_plan is None


def test_builder_failure_survives_shadow_telemetry_failure(monkeypatch):
    _prepare_attempt(monkeypatch, _valid_attempt_payload())
    monkeypatch.setattr(
        "core.turn_planner_llm.build_turn_frame_from_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("builder failed")),
    )

    def _log_json(_logger, event, **_fields):
        if event == "turn_planner_shadow_degraded":
            raise RuntimeError("telemetry failed")

    monkeypatch.setattr("core.turn_planner_llm.log_json", _log_json)

    attempt = plan_turn_attempt("Вопрос", "attempt-telemetry-fail", "demo")

    assert attempt.shadow_status == "degraded"
    assert attempt.shadow_frame is None
    assert attempt.legacy_plan is not None


def test_strict_failure_does_not_destroy_valid_shadow_frame(monkeypatch):
    _prepare_attempt(monkeypatch, _valid_attempt_payload())
    monkeypatch.setattr(
        "core.turn_planner_llm._validate_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("strict failed")),
    )

    attempt = plan_turn_attempt("Вопрос", "attempt-strict-fail", "demo")

    assert attempt.shadow_status == "partial"
    assert attempt.legacy_plan is None
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.topic == "implantation"


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


@pytest.mark.parametrize("entrypoint", ["attempt", "wrapper"])
def test_planner_entrypoint_makes_exactly_one_llm_call(monkeypatch, entrypoint):
    calls = {"count": 0}
    payload = _valid_attempt_payload()
    monkeypatch.setattr(
        "core.turn_planner_llm.build_compact_service_catalog",
        lambda _cid: _planner_catalog(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: _planner_filters(),
    )
    monkeypatch.setattr(
        "core.turn_planner_llm.load_client_topic_taxonomy",
        lambda _cid: _DEMO_TOPICS,
    )

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

    if entrypoint == "attempt":
        result = plan_turn_attempt("Вопрос", "attempt-one-call", "demo")
        assert result.legacy_plan is not None
    else:
        result = plan_turn("Вопрос", "wrapper-one-call", "demo")
        assert result is not None
    assert calls["count"] == 1


def test_raw_values_are_unchanged_between_shadow_and_strict_branches(monkeypatch):
    payload = _valid_attempt_payload()
    _prepare_attempt(monkeypatch, payload)
    snapshots: dict[str, dict] = {}

    def _builder(raw, *, allowed_topics, allowed_service_ids):
        snapshots["builder_before"] = json.loads(json.dumps(raw))
        snapshots["allowed_service_ids"] = allowed_service_ids
        frame = _real_build_turn_frame_from_raw(
            raw,
            allowed_topics=allowed_topics,
            allowed_service_ids=allowed_service_ids,
        )
        snapshots["builder_after"] = json.loads(json.dumps(raw))
        return frame

    def _strict(raw, **kwargs):
        snapshots["strict"] = json.loads(json.dumps(raw))
        return _validate_plan(raw, **kwargs)

    monkeypatch.setattr("core.turn_planner_llm.build_turn_frame_from_raw", _builder)
    monkeypatch.setattr("core.turn_planner_llm._validate_plan", _strict)

    attempt = plan_turn_attempt("Вопрос", "attempt-immutable", "demo")

    assert attempt.legacy_plan is not None
    assert snapshots["builder_before"] == payload
    assert snapshots["builder_after"] == payload
    assert snapshots["strict"] == payload
    assert snapshots["allowed_service_ids"] == frozenset({"all_on_4"})


def test_protocol_guard_changes_only_legacy_plan(monkeypatch):
    payload = _valid_attempt_payload()
    _prepare_attempt(monkeypatch, payload)
    calls = {"count": 0}

    def _guard(plan, **_kwargs):
        calls["count"] += 1
        return plan.model_copy(update={"service_id": "all_on_4"})

    monkeypatch.setattr("core.turn_planner_llm._apply_protocol_choice_guard", _guard)

    attempt = plan_turn_attempt("Вопрос", "attempt-guard", "demo")

    assert calls["count"] == 1
    assert attempt.legacy_plan is not None
    assert attempt.legacy_plan.service_id == "all_on_4"
    assert attempt.shadow_frame is not None
    assert attempt.shadow_frame.service_id is None
    assert attempt.shadow_frame.field_meta.service_id.status == "valid"
    assert attempt.shadow_frame.field_meta.service_id.provenance == "turn_plan.raw.service_id"


def test_partial_shadow_is_not_read_by_downstream_modules():
    recorder = Path("core/turn_frame_shadow.py").read_text(encoding="utf-8")
    assert "PlannerAttempt" in recorder
    assert "attempt.shadow_frame" in recorder

    paths = [Path("app.py"), Path("llm.py")]
    paths.extend(sorted(Path("orchestration").rglob("*.py")))
    offenders: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if "PlannerAttempt" in source or ".shadow_frame" in source:
            offenders.append(str(path))
    assert offenders == []
