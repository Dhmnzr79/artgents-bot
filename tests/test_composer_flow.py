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


def _overlay_mocks(monkeypatch: pytest.MonkeyPatch, *, composer_fn=None, forbidden_hits=None):
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

    def _gen(q, materialized, meta, session_id):
        fn = composer_fn
        if fn is not None:
            return fn(q, materialized, meta, session_id)
        return "composed answer", {"composer_used": True}

    monkeypatch.setattr(composer_flow, "generate_answer_from_packet", _gen)
    monkeypatch.setattr(
        composer_flow,
        "detect_forbidden_claims",
        lambda _text: list(forbidden_hits or []),
    )


def _try_overlay(
    *,
    plan: AnswerPlan,
    monkeypatch: pytest.MonkeyPatch,
    intent: str = "price_lookup",
    composer_on: bool = True,
    **mock_kw: Any,
):
    from orchestration.composer_flow import try_composer_overlay

    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", composer_on)
    _overlay_mocks(monkeypatch, **mock_kw)
    return try_composer_overlay(
        q="тестовый вопрос",
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


def test_single_aspect_returns_none(monkeypatch):
    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    result = _try_overlay(plan=plan, monkeypatch=monkeypatch)
    assert result is None


def test_forbidden_claim_returns_none(monkeypatch):
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
    )

    def _forbidden(*_a, **_k):
        return "Операция пройдёт безболезненно.", {"composer_used": True}

    result = _try_overlay(
        plan=plan,
        monkeypatch=monkeypatch,
        composer_fn=_forbidden,
        forbidden_hits=["bezbolesnenno"],
    )
    assert result is None


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
