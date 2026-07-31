from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "evals" / "v5" / "run_perf9_qwen_embeddings_evaluation.py"
SPEC = importlib.util.spec_from_file_location("perf9_qwen_eval", MODULE_PATH)
assert SPEC and SPEC.loader
perf9 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = perf9
SPEC.loader.exec_module(perf9)


def _vector(dense: tuple[float, ...], sparse: tuple[tuple[int, float], ...] = ((1, 1.0),)):
    padded = dense + (0.0,) * (perf9.DIMENSION - len(dense))
    return perf9.EmbeddingVector(dense=padded, sparse=sparse)


def test_qwen_model_contract_is_chinese_only() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert perf9.MODEL == "text-embedding-v4"
    assert perf9.DIMENSION == 1024
    assert perf9.OUTPUT_TYPE == "dense&sparse"
    assert "OPENAI_API_KEY" in source
    assert "no OPENAI_API_KEY fallback" in source
    assert "text-embedding-3" not in source


def test_native_endpoint_is_derived_only_from_dashscope_aliyun() -> None:
    source = "https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    assert perf9._native_endpoint(source).endswith(
        "/api/v1/services/embeddings/text-embedding/text-embedding"
    )
    with pytest.raises(perf9.Perf9EvaluationError) as error:
        perf9._native_endpoint("https://api.openai.com/v1")
    assert error.value.code == "qwen_base_url_required"


def test_document_ranking_aggregates_best_paragraph_per_document() -> None:
    corpus = (
        perf9.CorpusInput("p1", "a.md", "a"),
        perf9.CorpusInput("p2", "a.md", "a2"),
        perf9.CorpusInput("p3", "b.md", "b"),
    )
    vectors = (_vector((1.0, 0.0)), _vector((0.8, 0.2)), _vector((0.0, 1.0)))
    ranking = perf9._rank_documents(corpus, vectors, _vector((1.0, 0.0)), dense_weight=1.0)
    assert [row.document_ref for row in ranking] == ["a.md", "b.md"]
    assert ranking[0].score == pytest.approx(1.0)


def test_qwen_native_sparse_signal_can_change_hybrid_rank() -> None:
    corpus = (
        perf9.CorpusInput("p1", "dense.md", "dense"),
        perf9.CorpusInput("p2", "sparse.md", "sparse"),
    )
    vectors = (
        _vector((1.0, 0.0), ((2, 1.0),)),
        _vector((0.8, 0.2), ((1, 1.0),)),
    )
    query = _vector((1.0, 0.0), ((1, 1.0),))
    dense = perf9._rank_documents(corpus, vectors, query, dense_weight=1.0)
    hybrid = perf9._rank_documents(corpus, vectors, query, dense_weight=0.5)
    assert dense[0].document_ref == "dense.md"
    assert hybrid[0].document_ref == "sparse.md"


def test_calibration_optimizes_safety_before_usefulness() -> None:
    rankings = {
        "good": (
            perf9.RankedDocument("good.md", 0.8),
            perf9.RankedDocument("other.md", 0.2),
        ),
        "unsafe": (
            perf9.RankedDocument("wrong.md", 0.7),
            perf9.RankedDocument("other.md", 0.69),
        ),
    }
    gold = [
        {"scenario_id": "good", "fallback_required": False, "allowed_retrieval_md_refs": ["good.md"]},
        {"scenario_id": "unsafe", "fallback_required": True, "allowed_retrieval_md_refs": []},
    ]
    chosen = perf9._calibrate(rankings, gold)
    assert chosen["critical_false_narrow_count"] == 0
    assert chosen["safe_over_fallback_count"] == 0


def test_calibration_can_choose_all_fallback_when_every_accept_is_unsafe() -> None:
    rankings = {
        "unsafe": (
            perf9.RankedDocument("wrong.md", 0.9),
            perf9.RankedDocument("other.md", 0.1),
        )
    }
    gold = [
        {
            "scenario_id": "unsafe",
            "fallback_required": True,
            "allowed_retrieval_md_refs": [],
        }
    ]
    chosen = perf9._calibrate(rankings, gold)
    assert chosen["critical_false_narrow_count"] == 0
    assert chosen["fallback_count"] == 1


def test_dry_run_has_zero_calls_and_does_not_create_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(perf9, "LEDGER_ROOT", tmp_path / "ledger")
    monkeypatch.setattr(perf9, "_build_corpus_inputs", lambda: (perf9.CorpusInput("p", "a.md", "x"),))
    assert perf9.main(["--phase", "dev"]) == 0
    assert not (tmp_path / "ledger").exists()


def test_live_requires_exact_committed_attempt_before_marker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(perf9, "LEDGER_ROOT", tmp_path / "ledger")
    with pytest.raises(perf9.Perf9EvaluationError) as error:
        perf9.main(["--phase", "dev", "--live", "--attempt-id", "wrong"])
    assert error.value.code == "live_attempt_not_authorized"
    assert not (tmp_path / "ledger").exists()


def test_attempt_id_is_consumed_with_exclusive_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(perf9, "LEDGER_ROOT", tmp_path)
    perf9._create_attempt_marker("one", "dev", "hash")
    with pytest.raises(perf9.Perf9EvaluationError) as error:
        perf9._create_attempt_marker("one", "dev", "hash")
    assert error.value.code == "attempt_id_already_consumed"


def test_dev_phase_does_not_read_holdout_files(monkeypatch) -> None:
    original = perf9._json

    def guarded(path: Path):
        assert path not in {perf9.HOLDOUT_GOLD_PATH, perf9.HOLDOUT_QUERY_PATH}
        return original(path)

    monkeypatch.setattr(perf9, "_json", guarded)
    dry = perf9._dry_run("dev")
    assert dry["query_count"] == 49


def test_research_runner_is_not_imported_by_runtime() -> None:
    marker = "run_perf9_qwen_embeddings_evaluation"
    for root in (ROOT / "core", ROOT / "orchestration"):
        for path in root.rglob("*.py"):
            assert marker not in path.read_text(encoding="utf-8"), path
    for path in (ROOT / "app.py", ROOT / "llm.py"):
        assert marker not in path.read_text(encoding="utf-8"), path


def test_result_schema_never_contains_query_or_answer_text() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"contains_query_or_answer_text": False' in source
    assert '"top3"' in source
