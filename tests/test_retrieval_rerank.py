from __future__ import annotations

import pytest

from core.retrieval_rerank import evaluate_rerank_trigger, maybe_rerank_top


def _cands(scores: list[float]) -> list[dict]:
    return [{"file": f"a{i}.md", "h3_id": "korotko", "_score": s, "text": "x"} for i, s in enumerate(scores)]


def test_rerank_trigger_gray_zone() -> None:
    ok, reason = evaluate_rerank_trigger(_cands([0.5, 0.48]), point_literal=False)
    assert ok is True
    assert reason == "triggered"


def test_rerank_trigger_below_min() -> None:
    ok, reason = evaluate_rerank_trigger(_cands([0.3, 0.28]), point_literal=False)
    assert ok is False
    assert reason == "below_score_min"


def test_rerank_trigger_above_max() -> None:
    ok, reason = evaluate_rerank_trigger(_cands([0.8, 0.79]), point_literal=False)
    assert ok is False
    assert reason == "above_score_max"


def test_rerank_trigger_gap_too_wide() -> None:
    ok, reason = evaluate_rerank_trigger(_cands([0.5, 0.2]), point_literal=False)
    assert ok is False
    assert reason == "gap_too_wide"


def test_rerank_trigger_point_literal() -> None:
    ok, reason = evaluate_rerank_trigger(_cands([0.5, 0.48]), point_literal=True)
    assert ok is False
    assert reason == "point_literal_query"


def test_maybe_rerank_skips_without_llm() -> None:
    cands = _cands([0.8, 0.79])
    top, tel = maybe_rerank_top("вопрос", cands, point_literal=False)
    assert top is cands[0]
    assert tel["rerank_applied"] is False
    assert tel["rerank_trigger_reason"] == "above_score_max"


def test_maybe_rerank_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    cands = _cands([0.5, 0.48])

    def _boom(*_a, **_k):
        raise RuntimeError("api down")

    monkeypatch.setattr("core.retrieval_rerank.chat_completions_create", _boom)
    top, tel = maybe_rerank_top("сколько длится имплантация", cands, point_literal=False)
    assert top is cands[0]
    assert tel["rerank_applied"] is True
    assert tel["rerank_fallback_used"] is True
    assert tel["rerank_fallback_reason"] == "api_error"
