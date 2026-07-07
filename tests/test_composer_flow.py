"""Composer overlay at ask_turn + dispatch (phase 3a). LLM/gates mocked — path/structure only."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from flask import Flask

from contracts.answer_packet import MaterializedCard
from contracts.answer_plan import AnswerPlan
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.source_route_result import SourceRouteResult
from session import mem_reset

_app = Flask(__name__)


def _sr(*, service_id: str | None = "all_on_4", ref: str | None = None) -> SourceRouteResult:
    return SourceRouteResult(
        source="price_card",
        service_id=service_id,
        ref=ref,
        match_score=0.9,
        match_method="catalog_containment",
    )


def _two_cards() -> list[MaterializedCard]:
    return [
        MaterializedCard(aspect="price", kind="price", text="318 000 ₽ за челюсть."),
        MaterializedCard(
            aspect="pain",
            kind="content",
            text="Обычно дискомфорт минимальный.",
            source_ref="implantation__faq__pain.md#korotko",
        ),
    ]


def _overlay_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    composer_fn=None,
    price_route_mode: str = "matched",
):
    from orchestration import composer_flow

    monkeypatch.setattr(composer_flow, "publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        composer_flow,
        "assemble_answer_packet",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        composer_flow,
        "materialize_cards",
        lambda *a, **k: _two_cards(),
    )
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": price_route_mode},
    )

    def _gen(q, materialized, meta, session_id):
        fn = composer_fn
        if fn is not None:
            return fn(q, materialized, meta, session_id)
        return "composed answer", {"composer_used": True}

    monkeypatch.setattr(composer_flow, "generate_answer_from_packet", _gen)


def _try_overlay(
    *,
    plan: AnswerPlan,
    monkeypatch: pytest.MonkeyPatch,
    intent: str = "price_lookup",
    composer_on: bool = True,
    q: str = "тестовый вопрос",
    **mock_kw: Any,
):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", composer_on)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", False)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", False)
    _overlay_mocks(monkeypatch, **mock_kw)
    return try_composer_overlay(
        q=q,
        sid="composer-flow-test",
        client_id="demo",
        intent=intent,
        plan=plan,
        sr=_sr(service_id=plan.service_id),
        decision=None,
        decision_frame={},
    )


@pytest.fixture
def sid():
    s = f"composer-flow-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


def test_composite_price_returns_composer(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(plan=plan, monkeypatch=monkeypatch, intent="price_lookup")
    assert result is not None
    assert result.kind == "composer"
    assert result.composed_answer == "composed answer"
    assert len(result.materialized_cards or []) >= 2
    assert result.matched_service_id == "all_on_4"


def test_composite_content_returns_composer(monkeypatch):
    plan = AnswerPlan(
        aspects=["pain", "duration"],
        primary_aspect="pain",
        service_id="all_on_4",
        topic="implantation",
    )
    result = _try_overlay(plan=plan, monkeypatch=monkeypatch, intent="content")
    assert result is not None
    assert result.kind == "composer"


def test_composite_ambiguous_group_price_defers_to_price_path(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "payment"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(
        plan=plan,
        monkeypatch=monkeypatch,
        q="Сколько стоит имплантация и есть ли рассрочка?",
        price_route_mode="group_overview",
    )
    assert result is None


def test_composite_named_protocol_still_composes_on_group_overview(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "warranty"],
        primary_aspect="price",
        service_id="classic",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(
        plan=plan,
        monkeypatch=monkeypatch,
        q="Сколько стоит классическая имплантация и какая гарантия?",
        price_route_mode="group_overview",
    )
    assert result is not None
    assert result.kind == "composer"


def test_composite_specific_service_still_composes(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(
        plan=plan,
        monkeypatch=monkeypatch,
        q="Сколько стоит all-on-4 и не больно ли?",
        price_route_mode="matched",
    )
    assert result is not None
    assert result.kind == "composer"


def test_single_aspect_returns_none_without_fullctx(monkeypatch):
    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(plan=plan, monkeypatch=monkeypatch)
    assert result is None


def test_single_aspect_fullctx_composes(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", False)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow.assemble_answer_packet",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": "matched"},
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.assemble_client_knowledge_base",
        lambda _cid: "kb",
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.materialize_deterministic_cards",
        lambda *a, **k: [
            MaterializedCard(aspect="price", kind="price", text="318 000 ₽ за челюсть.")
        ],
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("single price composed", {"composer_used": True}),
    )

    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит all-on-4?",
        sid="composer-flow-single-fullctx",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is not None
    assert result.kind == "composer"
    assert result.composed_answer == "single price composed"


def test_jaw_scope_upper_jaw_defer_before_service_selector(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    selector_called = {"value": False}

    def _selector(*_a, **_k):
        selector_called["value"] = True
        return None

    monkeypatch.setattr("orchestration.composer_flow.classify_service", _selector)
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("should not run", {"composer_used": True}),
    )

    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит имплантация всей верхней челюсти?",
        sid="composer-flow-jaw-defer",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert selector_called["value"] is False


def test_jaw_scope_all_teeth_defer_before_service_selector(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    selector_called = {"value": False}

    def _selector(*_a, **_k):
        selector_called["value"] = True
        return None

    monkeypatch.setattr("orchestration.composer_flow.classify_service", _selector)

    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит вставить все зубы под ключ?",
        sid="composer-flow-all-teeth-defer",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert selector_called["value"] is False


def test_jaw_scope_named_protocol_on_jaw_does_not_defer(monkeypatch):
    from contracts.service_selection import ServiceSelection
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *a, **k: ServiceSelection(service_id="all_on_4", confidence=0.9),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("all-on-4 upper jaw", {"composer_used": True}),
    )

    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит all-on-4 на верхнюю челюсть?",
        sid="composer-flow-named-jaw",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is not None
    assert result.kind == "composer"


def test_single_aspect_generic_implant_defers_with_fullctx(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", False)
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": "group_overview"},
    )
    composer_called = {"value": False}

    def _fullctx(*_a, **_k):
        composer_called["value"] = True
        return "x", {"composer_used": True}

    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        _fullctx,
    )

    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит имплантация?",
        sid="composer-flow-defer-fullctx",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert composer_called["value"] is False


def test_composer_off_returns_none(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
    )
    result = _try_overlay(plan=plan, monkeypatch=monkeypatch, composer_on=False)
    assert result is None


def test_respond_from_composer_numeric_gate_whitelist(sid, monkeypatch):
    from chunk_responder import respond_from_composer

    cards = _two_cards()
    captured: dict[str, Any] = {}

    def _numeric(**kwargs):
        captured.update(kwargs)
        return kwargs["answer"], None

    monkeypatch.setattr("chunk_responder._apply_numeric_fact_gate", _numeric)
    monkeypatch.setattr(
        "chunk_responder._apply_response_policy_compat",
        lambda payload, *_a, **_k: payload,
    )
    monkeypatch.setattr("chunk_responder.schedule_verifier_shadow_if_needed", lambda **_k: None)

    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
    )

    def _finalize(payload, *_a, **_k):
        return payload

    with _app.test_request_context():
        from flask import request

        request.ctx = {"answer_plan": plan.model_dump()}
        out = respond_from_composer(
            composed_answer="Стоимость и комфорт.",
            materialized_cards=cards,
            q="Сколько стоит all-on-4 и больно ли?",
            sid=sid,
            client_id="demo",
            matched_service_id="all_on_4",
            route="price_lookup",
            primary_chunk_ref=None,
            finalize_ask=_finalize,
            logger=type("L", (), {"info": lambda *a, **k: None, "warning": lambda *a, **k: None})(),
        )

    assert out["meta"]["answer_path"] == "composer"
    allowed = str(captured.get("deterministic_append") or "")
    assert "318 000" in allowed
    assert "дискомфорт" in allowed.lower()


def test_respond_from_composer_fullctx_whitelist_includes_knowledge_base(sid, monkeypatch):
    from chunk_responder import respond_from_composer

    monkeypatch.setattr("chunk_responder.FULLCTX_ON", True)
    kb = "Гарантия на имплантаты — 99,8% приживаемость."
    monkeypatch.setattr(
        "chunk_responder.assemble_client_knowledge_base",
        lambda _cid: kb,
    )
    captured: dict[str, Any] = {}

    def _numeric(**kwargs):
        captured.update(kwargs)
        return kwargs["answer"], None

    monkeypatch.setattr("chunk_responder._apply_numeric_fact_gate", _numeric)
    monkeypatch.setattr(
        "chunk_responder._apply_response_policy_compat",
        lambda payload, *_a, **_k: payload,
    )
    monkeypatch.setattr("chunk_responder.schedule_verifier_shadow_if_needed", lambda **_k: None)

    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
    )

    def _finalize(payload, *_a, **_k):
        return payload

    with _app.test_request_context():
        from flask import request

        request.ctx = {"answer_plan": plan.model_dump()}
        respond_from_composer(
            composed_answer="Приживаемость высокая.",
            materialized_cards=_two_cards(),
            q="Какая приживаемость?",
            sid=sid,
            client_id="demo",
            matched_service_id="all_on_4",
            route="price_lookup",
            primary_chunk_ref=None,
            finalize_ask=_finalize,
            logger=type("L", (), {"info": lambda *a, **k: None, "warning": lambda *a, **k: None})(),
        )

    allowed = str(captured.get("deterministic_append") or "")
    assert "99,8%" in allowed
    assert "318 000" in allowed


def _parse_sse_ui_payload(body: str) -> dict[str, Any]:
    event_name: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            event_name = line[7:].strip()
        elif line.startswith("data: ") and event_name == "ui":
            raw = json.loads(line[6:])
            if not isinstance(raw, dict):
                raise ValueError("ui payload is not a dict")
            return raw
    raise ValueError("no ui event in SSE body")


def test_composer_should_defer_group_price_helpers():
    from orchestration.composer_flow import _composer_should_defer_group_price

    assert _composer_should_defer_group_price(
        "Сколько стоит имплантация и есть ли рассрочка?",
        {"mode": "group_overview"},
    )
    assert not _composer_should_defer_group_price(
        "Сколько стоит классическая имплантация и какая гарантия?",
        {"mode": "group_overview"},
    )
    assert _composer_should_defer_group_price("q", {"mode": "unit_clarify"})
    assert _composer_should_defer_group_price("q", {"mode": "matched"}) is False


def test_defer_group_price_exception_logs_fail_open(monkeypatch):
    from orchestration.composer_flow import _defer_group_price_via_price_route

    calls: list[dict[str, Any]] = []

    def _route(*_a, **_k):
        raise RuntimeError("route exploded")

    def _log(_logger, message, **fields):
        calls.append({"message": message, **fields})

    monkeypatch.setattr("query_selector.select_price_service_route", _route)
    monkeypatch.setattr("orchestration.composer_flow.log_json", _log)

    assert (
        _defer_group_price_via_price_route(q="q", client_id="demo", sid="sid-1")
        is False
    )
    assert calls == [
        {
            "message": "composer_defer_group_price_failed",
            "client_id": "demo",
            "sid": "sid-1",
            "err": "route exploded",
        }
    ]


def test_composer_overlay_exception_logs_fail_open(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    calls: list[dict[str, Any]] = []

    def _packet(*_a, **_k):
        raise RuntimeError("packet exploded")

    def _log(_logger, message, **fields):
        calls.append({"message": message, **fields})

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", False)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", False)
    monkeypatch.setattr(
        "orchestration.composer_flow._defer_group_price_via_price_route",
        lambda **_k: False,
    )
    monkeypatch.setattr("orchestration.composer_flow.assemble_answer_packet", _packet)
    monkeypatch.setattr("orchestration.composer_flow.log_json", _log)

    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="q",
        sid="sid-2",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert calls == [
        {
            "message": "composer_overlay_failed",
            "client_id": "demo",
            "sid": "sid-2",
            "err": "packet exploded",
        }
    ]


def test_telemetry_answer_path_for_chunk_route():
    from chunk_responder import _telemetry_answer_path_for_chunk

    assert _telemetry_answer_path_for_chunk(route="contacts_chunk") == "contacts"
    assert _telemetry_answer_path_for_chunk(route="retrieval_chunk") == "single_source"
    assert _telemetry_answer_path_for_chunk(route="retrieval_chunk", composer=True) == "composer"


def test_stamp_service_answer_path_price():
    from app import _stamp_service_answer_path

    payload: dict = {"meta": {}}
    _stamp_service_answer_path(payload, "price_lookup")
    assert payload["meta"]["answer_path"] == "price"

    payload2: dict = {"meta": {}}
    _stamp_service_answer_path(payload2, "catalog_facts")
    assert "answer_path" not in payload2["meta"]


def test_group_c_whitening_fullctx_triggers_composer(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": "matched"},
    )

    captured: dict = {}

    def _fullctx(q, kb, aspects, cards, meta, sid):
        captured["kb"] = kb
        captured["aspects"] = aspects
        captured["cards"] = cards
        return "composed whitening", {"composer_used": True}

    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        _fullctx,
    )

    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="professional_whitening",
        topic="whitening",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит отбеливание и не больно ли?",
        sid="composer-flow-fullctx",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="professional_whitening"),
        decision=None,
        decision_frame={},
    )
    assert result is not None
    assert result.kind == "composer"
    assert result.composed_answer == "composed whitening"
    assert captured["aspects"] == ["price", "pain"]
    assert "отбеливание" in captured["kb"].lower()
    price_cards = [c for c in captured["cards"] if c.kind == "price"]
    assert len(price_cards) == 1
    assert "18 000" in price_cards[0].text


def test_group_c_whitening_without_fullctx_fail_open_on_single_card(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", False)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": "matched"},
    )

    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="professional_whitening",
        topic="whitening",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит отбеливание и не больно ли?",
        sid="composer-flow-no-fullctx",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="professional_whitening"),
        decision=None,
        decision_frame={},
    )
    assert result is None


def test_extraction_composer_uses_llm_service_selection(monkeypatch):
    from contracts.service_selection import ServiceSelection
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *a, **k: ServiceSelection(service_id="tooth_extraction", confidence=0.9),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("composed extraction", {"composer_used": True}),
    )

    plan = AnswerPlan(
        aspects=["pain", "price"],
        primary_aspect="pain",
        service_id="pulpitis",
        topic="treatment",
    )
    result = try_composer_overlay(
        q="Больно ли удалять зуб и сколько это стоит?",
        sid="composer-flow-extraction",
        client_id="demo",
        intent="content",
        plan=plan,
        sr=_sr(service_id="pulpitis"),
        decision=None,
        decision_frame={},
    )
    assert result is not None
    assert result.kind == "composer"
    assert result.matched_service_id == "tooth_extraction"
    price_cards = [c for c in (result.materialized_cards or []) if c.kind == "price"]
    assert len(price_cards) == 1
    assert "4 500" in price_cards[0].text


def test_generic_implant_llm_null_defers_composer(monkeypatch):
    from contracts.service_selection import ServiceSelection
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *a, **k: ServiceSelection(service_id=None, confidence=0.85),
    )
    composer_called = {"value": False}

    def _composer(*_a, **_k):
        composer_called["value"] = True
        return "x", {"composer_used": True}

    monkeypatch.setattr("orchestration.composer_flow.generate_answer_from_packet", _composer)

    plan = AnswerPlan(
        aspects=["price", "payment"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит имплантация и есть ли рассрочка?",
        sid="composer-flow-defer",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert composer_called["value"] is False


def test_service_select_off_keeps_marker_defer(monkeypatch):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", False)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "query_selector.select_price_service_route",
        lambda *a, **k: {"mode": "group_overview"},
    )
    selector_called = {"value": False}

    def _selector(*_a, **_k):
        selector_called["value"] = True
        return None

    monkeypatch.setattr("orchestration.composer_flow.classify_service", _selector)

    plan = AnswerPlan(
        aspects=["price", "payment"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = try_composer_overlay(
        q="Сколько стоит имплантация и есть ли рассрочка?",
        sid="composer-flow-off",
        client_id="demo",
        intent="price_lookup",
        plan=plan,
        sr=_sr(service_id="all_on_4"),
        decision=None,
        decision_frame={},
    )
    assert result is None
    assert selector_called["value"] is False


def test_sse_composer_dispatch(monkeypatch):
    ensure = pytest.importorskip("app")
    _ = ensure
    from app import _dispatch_orchestration_sse, app

    def _composer_payload(**_kw):
        return {"answer": "composed via sse", "meta": {"answer_path": "composer"}}

    monkeypatch.setattr("app.respond_from_composer", _composer_payload)

    orch_r = AskOrchestrationResult(
        kind="composer",
        q="вопрос",
        sid="sse-composer",
        client_id="demo",
        composed_answer="composed via sse",
        materialized_cards=_two_cards(),
        matched_service_id="all_on_4",
        chunk_route="price_lookup",
    )

    with app.test_request_context():
        resp = _dispatch_orchestration_sse(orch_r)

    body = resp.get_data(as_text=True)
    assert "event: typing" in body
    assert "event: ui" in body
    assert "event: done" in body
    assert "text_delta" not in body

    ui = _parse_sse_ui_payload(body)
    meta = ui.get("meta") if isinstance(ui.get("meta"), dict) else {}
    assert meta.get("answer_path") == "composer"
