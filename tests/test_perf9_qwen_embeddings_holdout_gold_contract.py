from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "evals" / "v5" / "perf9_qwen_embeddings_holdout_queries_v1.json"
GOLD_PATH = ROOT / "evals" / "v5" / "perf9_qwen_embeddings_holdout_gold_v1.json"
PERF7_MATRIX_PATH = ROOT / "evals" / "v5" / "perf7c_local_evidence_package_eval_matrix.json"
PROTOCOL_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "PERF9_QWEN_EMBEDDINGS_HOLDOUT_GOLD_PROTOCOL.md"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_holdout_has_60_unique_aligned_scenarios() -> None:
    queries = _json(QUERY_PATH)
    gold = _json(GOLD_PATH)
    query_ids = [row["scenario_id"] for row in queries["scenarios"]]
    gold_ids = [row["scenario_id"] for row in gold["scenarios"]]
    assert queries["scenario_count"] == gold["scenario_count"] == 60
    assert len(query_ids) == len(set(query_ids)) == 60
    assert query_ids == gold_ids


def test_holdout_class_allocation_is_binding() -> None:
    rows = _json(QUERY_PATH)["scenarios"]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["scenario_class"]] = counts.get(row["scenario_class"], 0) + 1
    assert counts == {
        "single_doc_paraphrase": 24,
        "micro_fact": 12,
        "comparison": 8,
        "broad_requires_fallback": 6,
        "unsupported_claim": 6,
        "boundary_sensitive_relevant": 4,
    }


def test_query_index_contains_no_oracle_fields_and_gold_contains_no_query_text() -> None:
    queries = _json(QUERY_PATH)["scenarios"]
    gold = _json(GOLD_PATH)["scenarios"]
    assert all(set(row) == {"scenario_id", "scenario_class", "synthetic_query"} for row in queries)
    forbidden_query_fields = {"topic", "service_id", "expected_md_ref", "topic_hint"}
    assert all(not (set(row) & forbidden_query_fields) for row in queries)
    assert all("synthetic_query" not in row and "query" not in row for row in gold)


def test_gold_refs_exist_and_relevance_sets_do_not_overlap() -> None:
    md_refs = {
        path.relative_to(ROOT / "clients" / "demo" / "md").as_posix()
        for path in (ROOT / "clients" / "demo" / "md").rglob("*.md")
    }
    for row in _json(GOLD_PATH)["scenarios"]:
        required = set(row["required_md_refs"])
        allowed = set(row["allowed_retrieval_md_refs"])
        forbidden = set(row["forbidden_retrieval_md_refs"])
        assert required | allowed | forbidden <= md_refs
        assert not (required & allowed)
        assert not (required & forbidden)
        assert not (allowed & forbidden)
        assert row["rationale"].strip()
        if row["fallback_required"]:
            assert not allowed
        else:
            assert len(allowed) == 1


def test_gold_has_48_answerable_and_12_fallback_rows() -> None:
    rows = _json(GOLD_PATH)["scenarios"]
    assert sum(not row["fallback_required"] for row in rows) == 48
    assert sum(row["fallback_required"] for row in rows) == 12


def test_unsafe_semantic_stretches_are_explicitly_forbidden() -> None:
    rows = {row["scenario_id"]: row for row in _json(GOLD_PATH)["scenarios"]}
    assert rows["p9h051"]["fallback_required"] is True
    assert "clinic__info__consultation.md" in rows["p9h051"]["forbidden_retrieval_md_refs"]
    assert rows["p9h056"]["fallback_required"] is True
    assert "implantation__faq__pain.md" in rows["p9h056"]["forbidden_retrieval_md_refs"]
    assert rows["p9h055"]["fallback_required"] is True
    assert "diagnostics__service__tomography.md" in rows["p9h055"]["forbidden_retrieval_md_refs"]


def test_boundary_sensitive_rows_retrieve_canonical_docs_but_do_not_change_safety() -> None:
    rows = {row["scenario_id"]: row for row in _json(GOLD_PATH)["scenarios"]}
    for scenario_id in ("p9h057", "p9h058", "p9h060"):
        assert rows[scenario_id]["allowed_retrieval_md_refs"] == [
            "implantation__info__contraindications.md"
        ]
    assert rows["p9h059"]["allowed_retrieval_md_refs"] == [
        "implantation__info__aftercare.md"
    ]
    assert "never bypass" in PROTOCOL_PATH.read_text(encoding="utf-8")


def test_holdout_queries_are_not_exact_duplicates_of_perf7c_wording() -> None:
    holdout = {
        row["synthetic_query"].strip().casefold()
        for row in _json(QUERY_PATH)["scenarios"]
    }
    perf7 = {
        row["synthetic_query"].strip().casefold()
        for row in _json(PERF7_MATRIX_PATH)["scenarios"]
    }
    assert not (holdout & perf7)


def test_model_policy_is_qwen_only_and_openai_compatibility_is_transport_only() -> None:
    gold = _json(GOLD_PATH)
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    assert "Chinese models only" in gold["model_policy"]
    assert "Qwen text-embedding-v4" in gold["model_policy"]
    assert "transport syntax only" in gold["model_policy"]
    assert "Only Chinese models are allowed" in protocol
    assert "Alibaba Qwen `text-embedding-v4`" in protocol
    assert "does not authorize an OpenAI model" in protocol
    for western_candidate in (
        "text-embedding-3-small",
        "text-embedding-3-large",
        "Cohere",
        "Voyage",
        "Gemini",
        "Jina",
    ):
        assert western_candidate in protocol


def test_protocol_freezes_gold_before_any_retrieval_or_provider_run() -> None:
    text = PROTOCOL_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "Before the freeze commit, no lexical, BM25, embedding, hybrid" in normalized
    assert "must be committed before the evaluator imports or reads the query file" in normalized
    assert "gold were frozen at `27c8340` before evaluator implementation or retrieval" in normalized
    assert "Development thresholds were frozen at `9273630`; only then was the holdout run once" in normalized
    assert "The holdout must not be rerun or used for tuning" in normalized
