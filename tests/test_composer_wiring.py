from __future__ import annotations

import uuid
from typing import Any

import pytest
from flask import Flask

from contracts.answer_plan import AnswerPlan
from retriever import get_chunk_by_ref
from session import mem_reset

_app = Flask(__name__)


def _composite_plan(*, aspects: list[str] | None = None) -> AnswerPlan:
    return AnswerPlan(
        aspects=aspects or ["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
        plan_reason="composite",
    )


def _pain_chunk() -> dict:
    chunk = get_chunk_by_ref("implantation__faq__pain.md#korotko", client_id="demo")
    assert isinstance(chunk, dict)
    chunk = dict(chunk)
    chunk.setdefault("_score", 0.95)
    return chunk


def _respond(
    *,
    sid: str,
    plan: AnswerPlan,
    monkeypatch: pytest.MonkeyPatch,
    chunk: dict | None = None,
    route: str = "price_lookup",
    matched_service_id: str = "all_on_4",
    **mocks: Any,
) -> dict:
    from chunk_responder import respond_from_chunk

    chunk = chunk or _pain_chunk()
    calls: dict[str, int] = {
        "empathy": 0,
        "composer": 0,
        "slots": 0,
        "numeric_gate": 0,
    }

    def _empathy(*_a, **_k):
        calls["empathy"] += 1
        return "single-source answer", {"empathy": True}

    def _composer(q, materialized, meta, session_id):
        calls["composer"] += 1
        fn = mocks.get("composer_fn")
        if fn is not None:
            return fn(q, materialized, meta, session_id)
        return "composed answer", {"composer_used": True}

    def _slots(**_k):
        calls["slots"] += 1
        return _k["answer"], None, "", None

    real_numeric = mocks.get("numeric_gate_real", True)
    from chunk_responder import _apply_numeric_fact_gate as _real_numeric_gate

    def _numeric(**kwargs):
        calls["numeric_gate"] += 1
        if real_numeric:
            return _real_numeric_gate(**kwargs)
        return kwargs["answer"], None

    monkeypatch.setattr("chunk_responder.generate_answer_with_empathy", _empathy)
    monkeypatch.setattr("chunk_responder.generate_answer_from_packet", _composer)
    monkeypatch.setattr("chunk_responder._apply_answer_slots_and_price_append", _slots)
    monkeypatch.setattr("chunk_responder._apply_numeric_fact_gate", _numeric)
    monkeypatch.setattr(
        "chunk_responder._apply_response_policy_compat",
        lambda payload, *_a, **_k: payload,
    )
    monkeypatch.setattr("chunk_responder.schedule_verifier_shadow_if_needed", lambda **_k: None)

    def _finalize(payload, *_a, **_k):
        return payload

    with _app.test_request_context():
        from flask import request

        request.ctx = {"answer_plan": plan.model_dump()}
        resp = respond_from_chunk(
            chunk=chunk,
            q="Сколько стоит all-on-4 и не больно ли?",
            sid=sid,
            client_id="demo",
            finalize_ask=_finalize,
            safe_jsonify=lambda x: x,
            logger=type("L", (), {"info": lambda *a, **k: None, "warning": lambda *a, **k: None})(),
            route=route,
            matched_service_id=matched_service_id,
        )
    out = resp.get_json() if hasattr(resp, "get_json") else resp
    assert isinstance(out, dict)
    out["_calls"] = calls
    return out


@pytest.fixture
def sid():
    s = f"composer-wiring-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


def test_composer_path_when_flag_on_and_composite_packet(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)
    out = _respond(sid=sid, plan=_composite_plan(), monkeypatch=monkeypatch)
    assert out["meta"]["answer_path"] == "composer"
    assert out["_calls"]["composer"] == 1
    assert out["_calls"]["empathy"] == 0
    assert out["_calls"]["slots"] == 0
    assert out["_calls"]["numeric_gate"] == 1


def test_single_source_when_flag_off(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", False)
    out = _respond(sid=sid, plan=_composite_plan(), monkeypatch=monkeypatch)
    assert out["meta"]["answer_path"] == "single_source"
    assert out["_calls"]["composer"] == 0
    assert out["_calls"]["empathy"] == 1
    assert out["_calls"]["slots"] == 1


def test_single_source_for_price_only_despite_promo_cards(sid, monkeypatch):
    """Price-only plan materializes price + promos (3 cards) but must stay single-source."""
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)
    out = _respond(
        sid=sid,
        plan=AnswerPlan(
            aspects=["price"],
            primary_aspect="price",
            service_id="all_on_4",
            topic="implantation",
            append=["price_offer"],
        ),
        monkeypatch=monkeypatch,
        route="price_lookup",
    )
    assert out["meta"]["answer_path"] == "single_source"
    assert out["_calls"]["composer"] == 0
    assert out["_calls"]["empathy"] == 1
    assert out["_calls"]["slots"] == 1
    assert out["meta"].get("composer_skip_reason") == "single_aspect"


def test_single_source_when_only_one_materialized_card(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)
    out = _respond(
        sid=sid,
        plan=AnswerPlan(
            aspects=["pain"],
            primary_aspect="pain",
            service_id="all_on_4",
            topic="implantation",
        ),
        monkeypatch=monkeypatch,
        route="retrieval_chunk",
    )
    assert out["meta"]["answer_path"] == "single_source"
    assert out["_calls"]["composer"] == 0
    assert out["_calls"]["empathy"] == 1
    assert out["_calls"]["slots"] == 1


def test_fail_open_when_composer_raises(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)

    def _boom(*_a, **_k):
        raise RuntimeError("composer down")

    out = _respond(
        sid=sid,
        plan=_composite_plan(),
        monkeypatch=monkeypatch,
        composer_fn=_boom,
    )
    assert out["meta"]["answer_path"] == "single_source"
    assert out["_calls"]["empathy"] == 1
    assert out["_calls"]["slots"] == 1
    assert out["answer"] == "single-source answer"


def test_fail_open_when_composer_returns_not_used(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)

    def _unused(*_a, **_k):
        return "fallback", {"composer_used": False}

    out = _respond(
        sid=sid,
        plan=_composite_plan(),
        monkeypatch=monkeypatch,
        composer_fn=_unused,
    )
    assert out["meta"]["answer_path"] == "single_source"
    assert out["_calls"]["empathy"] == 1


def test_forbidden_claim_falls_back_to_single_source(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)

    def _forbidden(*_a, **_k):
        return "Операция пройдёт безболезненно.", {"composer_used": True}

    out = _respond(
        sid=sid,
        plan=_composite_plan(),
        monkeypatch=monkeypatch,
        composer_fn=_forbidden,
    )
    assert out["meta"]["answer_path"] == "single_source"
    assert out["meta"].get("composer_skip_reason") == "forbidden_claim"
    assert out["_calls"]["empathy"] == 1
    assert out["_calls"]["slots"] == 1
    assert "bezbolesnenno" in (out["meta"].get("forbidden_claim_hits") or [])


def test_clean_composer_answer_stays_on_composer_path(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)

    def _clean(*_a, **_k):
        return (
            "Стоимость зависит от бренда импланта. Обычно дискомфорт минимальный.",
            {"composer_used": True},
        )

    out = _respond(
        sid=sid,
        plan=_composite_plan(),
        monkeypatch=monkeypatch,
        composer_fn=_clean,
    )
    assert out["meta"]["answer_path"] == "composer"
    assert out["_calls"]["composer"] == 1
    assert out["_calls"]["empathy"] == 0


def test_numeric_gate_strips_hallucinated_price_on_composer_path(sid, monkeypatch):
    monkeypatch.setattr("chunk_responder.COMPOSER_ON", True)
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )

    def _bad_composer(_q, materialized, _meta, _sid):
        allowed = " ".join(c.text for c in materialized)
        assert "318 000" in allowed
        return (
            "Стоимость all-on-4 около 999 999 ₽ за челюсть. Также 318 000 ₽ по прайсу.",
            {"composer_used": True},
        )

    out = _respond(
        sid=sid,
        plan=_composite_plan(),
        monkeypatch=monkeypatch,
        composer_fn=_bad_composer,
        numeric_gate_real=True,
    )
    assert out["meta"]["answer_path"] == "composer"
    gate = out["meta"].get("numeric_fact_gate") or {}
    assert gate.get("action") in {"remove_fact", "blocked"}
    assert "999 999" not in out["answer"]
    assert "318 000" in out["answer"]
