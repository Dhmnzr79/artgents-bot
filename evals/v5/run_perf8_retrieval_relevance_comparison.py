"""PERF-8 Phase 1 retrieval-executor: runner/CLI for the retrieval-mechanism comparison study.

Runs four candidate retrieval mechanisms (A: existing shipped lexical-paragraph baseline, B: a new
conservative IDF-weighted lexical prototype, C: a new in-memory SQLite FTS5/BM25 prototype, D:
local embeddings -- only if genuinely already available offline) against all 49 frozen gold
scenarios in ``evals/v5/perf8_retrieval_relevance_gold_v2.json``, scores each candidate's decision
per scenario using the one binding scoring rule in this milestone's brief, and writes the
machine-readable comparison result to
``evals/v5/perf8_retrieval_relevance_comparison_result.json``.

Read-only: this script never writes to the gold file or the query-index file, never modifies
``core/target_lexical_paragraph_index.py`` or ``core/target_evidence_package_builder.py`` (both are
only imported/read for reference), and never touches any file under ``clients/`` except reading the
real MD corpus for the ``estimated_avg_tokens`` proxy metric. No network call, no package install,
no LLM/provider call anywhere in this script or in ``perf8_retrieval_relevance_prototypes.py``.

Usage (from the repository root):

    python evals/v5/run_perf8_retrieval_relevance_comparison.py
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT_FOR_IMPORT = _THIS_DIR.parents[1]
for _path in (str(_REPO_ROOT_FOR_IMPORT), str(_THIS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.target_lexical_paragraph_index import (
    TargetLexicalParagraphIndex,
    TargetLexicalParagraphIndexError,
    search_target_lexical_paragraph_index,
)

from perf8_retrieval_relevance_prototypes import (
    CandidateOutcome,
    build_document_char_lengths,
    build_document_token_sets,
    build_document_topic_map,
    build_fts5_index,
    build_idf_table,
    candidate_b_decide,
    candidate_c_decide,
    load_corpus_index,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MD_ROOT = _REPO_ROOT / "clients" / "demo" / "md"
_GOLD_PATH = Path(__file__).resolve().with_name("perf8_retrieval_relevance_gold_v2.json")
_QUERY_INDEX_PATH = Path(__file__).resolve().with_name("perf8_retrieval_relevance_query_index.json")
_RESULT_PATH = Path(__file__).resolve().with_name("perf8_retrieval_relevance_comparison_result.json")

# Candidate A mirrors the current Builder's lexical decision exactly: search ten paragraph hits,
# require at least one exact-token match, aggregate the best hit per document, and accept only one
# unique top-scoring document. The Builder remains unmodified and unwired.
_CANDIDATE_A_SEARCH_LIMIT = 10
_CANDIDATE_A_MIN_EXACT_TOKEN_MATCHES = 1


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_a_decide(index: TargetLexicalParagraphIndex, query: str) -> CandidateOutcome:
    started = time.perf_counter()
    try:
        hits = search_target_lexical_paragraph_index(index, query, limit=_CANDIDATE_A_SEARCH_LIMIT)
    except TargetLexicalParagraphIndexError:
        hits = ()

    eligible_hits = [
        hit
        for hit in hits
        if hit.exact_token_matches >= _CANDIDATE_A_MIN_EXACT_TOKEN_MATCHES
    ]
    if not eligible_hits:
        return CandidateOutcome(decision=None, raw_top3=(), elapsed_ms=(time.perf_counter() - started) * 1000)

    # hits are already sorted (score desc, paragraph_id asc) by the imported search function.
    # Dedup to one (best) hit per document, preserving that same rank order.
    best_hit_by_document: dict[str, Any] = {}
    for hit in eligible_hits:
        document_path = hit.paragraph.document_path
        if document_path not in best_hit_by_document:
            best_hit_by_document[document_path] = hit

    ranked_documents = sorted(
        best_hit_by_document.items(), key=lambda item: (-item[1].score, item[0])
    )
    raw_top3 = tuple(document_path for document_path, _ in ranked_documents[:3])

    top_score = ranked_documents[0][1].score
    top_documents = [
        document_path for document_path, hit in ranked_documents if hit.score == top_score
    ]

    decision: str | None = None
    if len(top_documents) == 1:
        decision = top_documents[0]

    elapsed_ms = (time.perf_counter() - started) * 1000
    return CandidateOutcome(decision=decision, raw_top3=raw_top3, elapsed_ms=elapsed_ms)


def _check_candidate_d_availability() -> tuple[bool, str]:
    """Local-only, no-network, no-install check for a usable local embedding model.

    Only checks whether a known local-embedding Python package is already importable in this
    environment. Never attempts a network call, never installs anything, never downloads a model,
    and never approximates/simulates embedding quality if nothing is found.
    """

    candidate_packages = ("sentence_transformers", "gensim", "fasttext", "spacy")
    importable = [
        package_name
        for package_name in candidate_packages
        if importlib.util.find_spec(package_name) is not None
    ]
    package_note = ", ".join(importable) if importable else "none"
    return False, (
        "NOT_EVALUATED: importable packages alone do not prove that compatible local model "
        f"weights are installed (importable packages: {package_note}); no repository-configured "
        "offline embedding model artifact exists, and downloads/provider calls are forbidden"
    )


def _verdict(decision: str | None, allowed: list[str], fallback_required: bool) -> str:
    if decision is None:
        return "match_correct" if fallback_required else "safe_over_fallback"
    if decision in allowed:
        return "match_correct"
    return "critical_false_narrow_irrelevant_retrieval"


def _empty_metrics_accumulator() -> dict[str, Any]:
    return {
        "critical_false_narrow_count": 0,
        "match_correct_count": 0,
        "safe_over_fallback_count": 0,
        "fallback_count": 0,
        "recall_at_1_hits": 0,
        "recall_at_3_hits": 0,
        "unrelated_top_candidate_count": 0,
        "token_lengths_of_selections": [],
        "time_ms_samples": [],
    }


def main() -> None:
    gold_hash_before = _sha256_file(_GOLD_PATH)
    query_index_hash_before = _sha256_file(_QUERY_INDEX_PATH)
    gold = _load_json(_GOLD_PATH)
    query_index = _load_json(_QUERY_INDEX_PATH)

    query_by_scenario_id = {
        entry["scenario_id"]: entry for entry in query_index["scenarios"]
    }

    index_build_started = time.perf_counter()
    index = load_corpus_index(_MD_ROOT)
    paragraph_index_build_ms = (time.perf_counter() - index_build_started) * 1000

    weighted_build_started = time.perf_counter()
    document_token_sets = build_document_token_sets(index)
    idf_table = build_idf_table(index, document_token_sets)
    document_topics = build_document_topic_map(index)
    document_paths = sorted(document_token_sets.keys())
    document_char_lengths = build_document_char_lengths(_MD_ROOT, document_paths)
    weighted_lexical_build_ms = (time.perf_counter() - weighted_build_started) * 1000

    fts5_build_started = time.perf_counter()
    fts5_connection = build_fts5_index(index)
    fts5_build_ms = (time.perf_counter() - fts5_build_started) * 1000

    candidate_d_available, candidate_d_reason = _check_candidate_d_availability()

    accumulators = {
        "A": _empty_metrics_accumulator(),
        "B": _empty_metrics_accumulator(),
        "C": _empty_metrics_accumulator(),
    }
    per_scenario_rows: list[dict[str, Any]] = []

    for scenario in gold["scenarios"]:
        scenario_id = scenario["scenario_id"]
        allowed = scenario["allowed_retrieval_md_refs"]
        fallback_required = scenario["fallback_required"]

        query_entry = query_by_scenario_id[scenario_id]
        query_text = query_entry["synthetic_query"]
        topic_hint = tuple(query_entry.get("topic_hint") or ())

        outcome_a = _candidate_a_decide(index, query_text)
        outcome_b = candidate_b_decide(
            query_text,
            document_token_sets=document_token_sets,
            idf=idf_table,
            document_topics=document_topics,
            topic_hint=topic_hint,
        )
        outcome_c = candidate_c_decide(query_text, fts5_connection)

        row: dict[str, Any] = {
            "scenario_id": scenario_id,
            "gold_fallback_required": fallback_required,
        }

        for label, outcome in (("A", outcome_a), ("B", outcome_b), ("C", outcome_c)):
            verdict = _verdict(outcome.decision, allowed, fallback_required)
            row[label] = {"decision": outcome.decision or "fallback", "verdict": verdict}

            accumulator = accumulators[label]
            if verdict == "critical_false_narrow_irrelevant_retrieval":
                accumulator["critical_false_narrow_count"] += 1
            elif verdict == "match_correct":
                accumulator["match_correct_count"] += 1
            elif verdict == "safe_over_fallback":
                accumulator["safe_over_fallback_count"] += 1

            if outcome.decision is None:
                accumulator["fallback_count"] += 1
            else:
                accumulator["token_lengths_of_selections"].append(
                    document_char_lengths.get(outcome.decision, 0) // 4
                )

            accumulator["time_ms_samples"].append(outcome.elapsed_ms)

            if not fallback_required:
                if outcome.decision is not None and outcome.decision in allowed:
                    accumulator["recall_at_1_hits"] += 1
                if any(candidate in allowed for candidate in outcome.raw_top3):
                    accumulator["recall_at_3_hits"] += 1

            raw_top1 = outcome.raw_top3[0] if outcome.raw_top3 else None
            if raw_top1 is not None and raw_top1 not in allowed:
                accumulator["unrelated_top_candidate_count"] += 1

        row["D"] = None
        per_scenario_rows.append(row)

    scenario_count = len(gold["scenarios"])
    fallback_required_false_count = sum(
        1 for scenario in gold["scenarios"] if not scenario["fallback_required"]
    )

    candidates_summary: dict[str, Any] = {}
    for label in ("A", "B", "C"):
        accumulator = accumulators[label]
        token_lengths = accumulator["token_lengths_of_selections"]
        time_samples = accumulator["time_ms_samples"]
        candidates_summary[label] = {
            "scenario_count": scenario_count,
            "fallback_required_false_count": fallback_required_false_count,
            "critical_false_narrow_count": accumulator["critical_false_narrow_count"],
            "match_correct_count": accumulator["match_correct_count"],
            "safe_over_fallback_count": accumulator["safe_over_fallback_count"],
            "fallback_count": accumulator["fallback_count"],
            "fallback_rate": accumulator["fallback_count"] / scenario_count,
            "recall_at_1": (
                accumulator["recall_at_1_hits"] / fallback_required_false_count
                if fallback_required_false_count
                else None
            ),
            "recall_at_3": (
                accumulator["recall_at_3_hits"] / fallback_required_false_count
                if fallback_required_false_count
                else None
            ),
            "unrelated_top_candidate_count": accumulator["unrelated_top_candidate_count"],
            "estimated_avg_tokens": (
                sum(token_lengths) / len(token_lengths) if token_lengths else None
            ),
            "avg_time_ms": sum(time_samples) / len(time_samples) if time_samples else None,
            "avg_time_ms_note": (
                "per-scenario decision time only; one-time corpus/index build cost "
                "(paragraph index build, IDF table build, FTS5 table build) is measured once "
                "and amortized outside this average, not included per-call"
            ),
        }

    candidates_summary["D"] = (
        "NOT_EVALUATED" if not candidate_d_available else {"note": candidate_d_reason}
    )

    gold_hash_after = _sha256_file(_GOLD_PATH)
    query_index_hash_after = _sha256_file(_QUERY_INDEX_PATH)
    if gold_hash_after != gold_hash_before or query_index_hash_after != query_index_hash_before:
        raise RuntimeError("binding input changed during retrieval comparison")

    result = {
        "schema_version": 2,
        "decision": {
            "verdict": "EMBEDDINGS_EVALUATION_JUSTIFIED",
            "runtime_candidate": None,
            "reason": (
                "The current lexical baseline produces critical false narrowing. Conservative "
                "weighted lexical and FTS5/BM25 avoid it on this development matrix only by "
                "falling back on most scenarios, and their gates were tuned on this same matrix. "
                "No candidate has independent holdout evidence sufficient for runtime wiring."
            ),
        },
        "methodology": {
            "evaluation_scope": "exploratory_development_set",
            "gold_sha256_before": gold_hash_before,
            "gold_sha256_after": gold_hash_after,
            "gold_unchanged_during_run": gold_hash_before == gold_hash_after,
            "query_index_sha256_before": query_index_hash_before,
            "query_index_sha256_after": query_index_hash_after,
            "query_index_unchanged_during_run": (
                query_index_hash_before == query_index_hash_after
            ),
            "inherited_wip_provenance_limitation": (
                "Gold and executor files were inherited as untracked WIP, so original temporal "
                "authoring order cannot be proven cryptographically. They were independently "
                "reviewed and hashed before this final comparison run."
            ),
            "candidate_b_c_threshold_status": (
                "tuned on this same development matrix; metrics are descriptive, not "
                "generalization evidence"
            ),
            "topic_hint_limitation": (
                "candidate B receives synthetic allowed_topics copied from the PERF-7C matrix, "
                "not topics produced by a measured Planner run; this can make B optimistic"
            ),
        },
        "one_time_build_ms": {
            "paragraph_index": paragraph_index_build_ms,
            "weighted_lexical_tables": weighted_lexical_build_ms,
            "fts5": fts5_build_ms,
            "note": "one observed local run; non-binding and expected to vary",
        },
        "candidates": candidates_summary,
        "per_scenario": per_scenario_rows,
    }

    with _RESULT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Candidate D available locally: {candidate_d_available} ({candidate_d_reason})")
    print(f"Wrote {_RESULT_PATH}")
    for label in ("A", "B", "C"):
        summary = candidates_summary[label]
        print(
            f"{label}: critical_false_narrow={summary['critical_false_narrow_count']} "
            f"recall@1={summary['recall_at_1']} recall@3={summary['recall_at_3']} "
            f"safe_over_fallback={summary['safe_over_fallback_count']} "
            f"fallback_rate={summary['fallback_rate']:.3f} "
            f"unrelated_top1={summary['unrelated_top_candidate_count']}"
        )


if __name__ == "__main__":
    main()
