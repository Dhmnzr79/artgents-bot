from __future__ import annotations

import pytest

from core.answer_planner import (
    detect_aspects,
    detect_aspects_regex,
    is_composite_question,
)
from core.aspect_planner_llm import classify_aspects_llm, order_aspects


def test_is_composite_question_multi_clause():
    q = "Сколько стоит all-on-4 и это не больно, и долго ли заживает?"
    assert is_composite_question(q)


def test_is_composite_question_short_single():
    assert not is_composite_question("Сколько стоит имплант?")


def test_detect_aspects_regex_composite_price_payment():
    aspects = detect_aspects_regex("Сколько стоит classic и есть ли рассрочка?")
    assert "price" in aspects
    assert "payment" in aspects


def test_order_aspects_priority():
    assert order_aspects(["pain", "price", "payment"]) == ["price", "payment", "pain"]


def test_classify_aspects_llm_rejects_low_confidence(monkeypatch):
    monkeypatch.setattr(
        "core.aspect_planner_llm._llm_classify_question_aspects",
        lambda *a, **k: {"aspects": ["price", "pain"], "confidence": 0.2},
    )
    assert classify_aspects_llm("тестовый вопрос про цену и боль", client_id="demo") is None


def test_classify_aspects_llm_accepts_valid(monkeypatch):
    monkeypatch.setattr(
        "core.aspect_planner_llm._llm_classify_question_aspects",
        lambda *a, **k: {"aspects": ["price", "pain", "duration"], "confidence": 0.9},
    )
    aspects = classify_aspects_llm(
        "Сколько стоит all-on-4 и долго ли заживление, это больно?",
        client_id="demo",
    )
    assert aspects == ["price", "pain", "duration"]


def test_detect_aspects_uses_llm_for_composite_when_regex_sparse(monkeypatch):
    monkeypatch.setattr("core.answer_planner.ASPECT_PLANNER_LLM_ON", True)
    q = "Сколько стоит all-on-4 и долго ли заживление после операции?"
    assert is_composite_question(q)
    regex_only = detect_aspects_regex(q)
    assert _real_aspect_count(regex_only) <= 1

    monkeypatch.setattr(
        "core.aspect_planner_llm.classify_aspects_llm",
        lambda *_a, **_k: ["price", "pain", "duration"],
    )
    aspects = detect_aspects(q, client_id="demo", sid="t-llm")
    assert set(aspects) == {"price", "pain", "duration"}


def test_detect_aspects_fail_open_to_regex(monkeypatch):
    monkeypatch.setattr("core.answer_planner.ASPECT_PLANNER_LLM_ON", True)
    q = "Сколько стоит all-on-4 и долго ли заживление после операции?"
    monkeypatch.setattr("core.aspect_planner_llm.classify_aspects_llm", lambda *_a, **_k: None)
    aspects = detect_aspects(q, client_id="demo", sid="t-fail")
    assert aspects == detect_aspects_regex(q)


def test_detect_aspects_skips_llm_when_regex_has_multiple(monkeypatch):
    monkeypatch.setattr("core.answer_planner.ASPECT_PLANNER_LLM_ON", True)

    def _boom(*_a, **_k):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr("core.aspect_planner_llm.classify_aspects_llm", _boom)
    aspects = detect_aspects(
        "Сколько по времени длится протезирование на имплантах и больно ли это?",
        client_id="demo",
        sid="t-skip",
    )
    assert "duration" in aspects
    assert "pain" in aspects


def test_detect_aspects_records_ctx_source(monkeypatch):
    app = pytest.importorskip("flask").Flask(__name__)
    monkeypatch.setattr("core.answer_planner.ASPECT_PLANNER_LLM_ON", True)
    monkeypatch.setattr(
        "core.aspect_planner_llm.classify_aspects_llm",
        lambda *_a, **_k: ["price", "pain", "duration"],
    )
    q = "Сколько стоит all-on-4 и долго ли заживление после операции?"
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        detect_aspects(q, client_id="demo", sid="t-ctx")
        assert request.ctx.get("aspect_planner_source") == "llm"
        assert request.ctx.get("aspect_planner_aspects") == ["price", "pain", "duration"]


def _real_aspect_count(aspects: list[str]) -> int:
    return len([a for a in aspects if a != "overview"])
