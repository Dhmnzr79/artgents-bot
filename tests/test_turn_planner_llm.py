from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from contracts.turn_plan import TurnPlan
from core.turn_planner_llm import (
    _SYSTEM,
    _sanitize_topic_fields,
    _validate_plan,
    plan_turn,
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
