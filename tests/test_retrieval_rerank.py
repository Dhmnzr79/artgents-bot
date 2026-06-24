from __future__ import annotations

import pytest

from core.retrieval_rerank import (
    evaluate_rerank_trigger,
    maybe_rerank_top,
    pool_top_when_alias_rerank_skipped,
    strong_alias_blocks_rerank,
)


def _cands(scores: list[float]) -> list[dict]:
    return [{"file": f"a{i}.md", "h3_id": "korotko", "_score": s, "text": "x"} for i, s in enumerate(scores)]


def _cands_with_sources(rows: list[tuple[float, list[str]]]) -> list[dict]:
    out: list[dict] = []
    for i, (score, sources) in enumerate(rows):
        out.append(
            {
                "file": f"a{i}.md",
                "h3_id": "korotko",
                "_score": score,
                "_pool_sources": sources,
                "text": "x",
            }
        )
    return out


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


def test_rerank_skipped_on_strong_alias_in_gray_zone() -> None:
    cands = _cands_with_sources(
        [
            (0.64, ["semantic"]),
            (0.64, ["semantic", "alias"]),
            (0.55, ["semantic"]),
        ]
    )
    ok, reason = evaluate_rerank_trigger(
        cands, point_literal=False, alias_strong=False, alias_decision="embed_high"
    )
    assert ok is False
    assert reason == "strong_alias_in_pool"


def test_pool_top_prefers_alias_on_score_tie() -> None:
    cands = _cands_with_sources(
        [
            (0.64, ["semantic"]),
            (0.64, ["semantic", "alias"]),
        ]
    )
    top = pool_top_when_alias_rerank_skipped(cands)
    assert top is cands[1]


def test_maybe_rerank_skips_llm_for_strong_alias_tie(monkeypatch: pytest.MonkeyPatch) -> None:
    cands = _cands_with_sources(
        [
            (0.64, ["semantic"]),
            (0.64, ["semantic", "alias"]),
            (0.55, ["semantic"]),
        ]
    )

    def _boom(*_a, **_k):
        raise RuntimeError("should not call rerank")

    monkeypatch.setattr("core.retrieval_rerank.chat_completions_create", _boom)
    top, tel = maybe_rerank_top(
        "вопрос", cands, point_literal=False, alias_strong=False, alias_decision="embed_high"
    )
    assert top is cands[1]
    assert tel["rerank_applied"] is False
    assert tel["rerank_trigger_reason"] == "strong_alias_in_pool"


def test_strong_alias_guard_off_when_alias_not_strong() -> None:
    cands = _cands_with_sources([(0.64, ["semantic"]), (0.64, ["semantic", "alias"])])
    assert strong_alias_blocks_rerank(cands, alias_strong=False) is False
    ok, reason = evaluate_rerank_trigger(cands, point_literal=False, alias_strong=False)
    assert ok is True
    assert reason == "triggered"
