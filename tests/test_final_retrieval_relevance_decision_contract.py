from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evals" / "v5"
GOLD_PATH = EVAL_DIR / "perf8_retrieval_relevance_gold_v2.json"
QUERY_PATH = EVAL_DIR / "perf8_retrieval_relevance_query_index.json"
RESULT_PATH = EVAL_DIR / "perf8_retrieval_relevance_comparison_result.json"
PERF7_MATRIX_PATH = EVAL_DIR / "perf7c_local_evidence_package_eval_matrix.json"
PROTOTYPES_PATH = EVAL_DIR / "perf8_retrieval_relevance_prototypes.py"
RUNNER_PATH = EVAL_DIR / "run_perf8_retrieval_relevance_comparison.py"
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "FINAL_RETRIEVAL_RELEVANCE_DECISION_AUDIT.md"
)

KNOWN_DEFECT_PREFIXES = {
    "s051",
    "s053",
    "s054",
    "s055",
    "s056",
    "s083",
    "s084",
    "s099",
    "s100",
    "s101",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prefix(scenario_id: str) -> str:
    return scenario_id.split("_", 1)[0]


def test_gold_and_query_indexes_have_the_same_49_unique_scenarios() -> None:
    gold = _json(GOLD_PATH)
    queries = _json(QUERY_PATH)
    gold_ids = [row["scenario_id"] for row in gold["scenarios"]]
    query_ids = [row["scenario_id"] for row in queries["scenarios"]]
    assert gold["scenario_count"] == 49
    assert len(gold_ids) == len(set(gold_ids)) == 49
    assert set(gold_ids) == set(query_ids)


def test_query_wording_matches_the_original_perf7c_matrix() -> None:
    original = _json(PERF7_MATRIX_PATH)
    queries = _json(QUERY_PATH)
    original_queries = {
        row["scenario_id"]: row["synthetic_query"] for row in original["scenarios"]
    }
    for row in queries["scenarios"]:
        assert row["synthetic_query"] == original_queries[row["scenario_id"]]


def test_gold_references_exist_and_relevance_sets_do_not_overlap() -> None:
    gold = _json(GOLD_PATH)
    md_refs = {
        path.relative_to(ROOT / "clients" / "demo" / "md").as_posix()
        for path in (ROOT / "clients" / "demo" / "md").rglob("*.md")
    }
    for row in gold["scenarios"]:
        required = set(row["required_md_refs"])
        allowed = set(row["allowed_retrieval_md_refs"])
        forbidden = set(row["forbidden_retrieval_md_refs"])
        assert required | allowed | forbidden <= md_refs
        assert not (required & allowed)
        assert not (allowed & forbidden)
        assert row["rationale"].strip()
        if row["fallback_required"]:
            assert not allowed
        else:
            assert allowed


def test_broad_single_document_contract_does_not_accept_collective_sets() -> None:
    rows = {row["scenario_id"]: row for row in _json(GOLD_PATH)["scenarios"]}
    assert rows["s011_broad_service"]["fallback_required"] is True
    assert rows["s013_broad_service"]["fallback_required"] is True
    assert rows["s015_broad_service"]["allowed_retrieval_md_refs"] == [
        "treatment__service__teeth_treatment.md"
    ]
    assert rows["s081_cross_topic"]["allowed_retrieval_md_refs"] == [
        "implantation__info__contraindications.md"
    ]


def test_external_plan_claims_are_not_inferred_from_generic_consultation() -> None:
    rows = _json(GOLD_PATH)["scenarios"]
    external_plan_rows = [
        row
        for row in rows
        if _prefix(row["scenario_id"]) in {"s051", "s053", "s054", "s055", "s056"}
    ]
    assert len(external_plan_rows) == 5
    for row in external_plan_rows:
        assert row["fallback_required"] is True
        assert "clinic__info__consultation.md" in row["forbidden_retrieval_md_refs"]


def test_result_pins_unchanged_binding_inputs() -> None:
    result = _json(RESULT_PATH)
    methodology = result["methodology"]
    assert methodology["gold_unchanged_during_run"] is True
    assert methodology["query_index_unchanged_during_run"] is True
    assert methodology["gold_sha256_before"] == methodology["gold_sha256_after"] == _sha256(GOLD_PATH)
    assert (
        methodology["query_index_sha256_before"]
        == methodology["query_index_sha256_after"]
        == _sha256(QUERY_PATH)
    )


def test_result_is_exploratory_and_does_not_authorize_runtime() -> None:
    result = _json(RESULT_PATH)
    assert result["decision"]["verdict"] == "EMBEDDINGS_EVALUATION_JUSTIFIED"
    assert result["decision"]["runtime_candidate"] is None
    assert result["methodology"]["evaluation_scope"] == "exploratory_development_set"
    assert "same development matrix" in result["methodology"]["candidate_b_c_threshold_status"]
    assert "not topics produced by a measured Planner" in result["methodology"]["topic_hint_limitation"]


def test_candidate_metrics_reconcile_with_per_scenario_verdicts() -> None:
    result = _json(RESULT_PATH)
    rows = result["per_scenario"]
    assert len(rows) == 49
    for candidate in ("A", "B", "C"):
        verdicts = [row[candidate]["verdict"] for row in rows]
        summary = result["candidates"][candidate]
        assert summary["critical_false_narrow_count"] == verdicts.count(
            "critical_false_narrow_irrelevant_retrieval"
        )
        assert summary["match_correct_count"] == verdicts.count("match_correct")
        assert summary["safe_over_fallback_count"] == verdicts.count("safe_over_fallback")
        assert (
            summary["critical_false_narrow_count"]
            + summary["match_correct_count"]
            + summary["safe_over_fallback_count"]
            == 49
        )


def test_known_perf7c_defects_are_critical_for_a_and_safe_fallbacks_for_b_c() -> None:
    rows = {
        _prefix(row["scenario_id"]): row
        for row in _json(RESULT_PATH)["per_scenario"]
        if _prefix(row["scenario_id"]) in KNOWN_DEFECT_PREFIXES
    }
    assert set(rows) == KNOWN_DEFECT_PREFIXES
    for row in rows.values():
        assert row["A"]["verdict"] == "critical_false_narrow_irrelevant_retrieval"
        for candidate in ("B", "C"):
            assert row[candidate]["decision"] == "fallback"
            assert row[candidate]["verdict"] == "match_correct"


def test_conservative_candidates_are_not_misrepresented_as_useful_passes() -> None:
    candidates = _json(RESULT_PATH)["candidates"]
    assert candidates["A"]["critical_false_narrow_count"] > 0
    for candidate in ("B", "C"):
        assert candidates[candidate]["critical_false_narrow_count"] == 0
        assert candidates[candidate]["fallback_rate"] >= 0.85
        assert candidates[candidate]["recall_at_1"] < 0.25
    assert candidates["D"] == "NOT_EVALUATED"


def test_estimated_tokens_are_document_characters_divided_by_four() -> None:
    result = _json(RESULT_PATH)
    for candidate in ("A", "B", "C"):
        token_lengths = []
        for row in result["per_scenario"]:
            decision = row[candidate]["decision"]
            if decision != "fallback":
                chars = len(
                    (ROOT / "clients" / "demo" / "md" / decision).read_text(
                        encoding="utf-8-sig"
                    )
                )
                token_lengths.append(chars // 4)
        expected_average = sum(token_lengths) / len(token_lengths)
        assert result["candidates"][candidate]["estimated_avg_tokens"] == expected_average


def test_build_timings_are_measured_and_explicitly_non_binding() -> None:
    build = _json(RESULT_PATH)["one_time_build_ms"]
    assert build["paragraph_index"] >= 0
    assert build["weighted_lexical_tables"] >= 0
    assert build["fts5"] >= 0
    assert "non-binding" in build["note"]


def test_research_code_discloses_test_set_tuning_and_has_no_network_transport() -> None:
    source = PROTOTYPES_PATH.read_text(encoding="utf-8")
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    assert "same 49-scenario development matrix" in source
    assert "not independent" in source
    forbidden_transport_markers = (
        "requests.",
        "httpx.",
        "urllib.request",
        "chat_completions_create",
        "OpenAI(",
    )
    for marker in forbidden_transport_markers:
        assert marker not in source
        assert marker not in runner


def test_perf8_research_is_not_imported_by_runtime_modules() -> None:
    runtime_roots = [ROOT / "core", ROOT / "orchestration", ROOT / "app.py"]
    markers = (
        "perf8_retrieval_relevance_prototypes",
        "run_perf8_retrieval_relevance_comparison",
    )
    for runtime_root in runtime_roots:
        paths = [runtime_root] if runtime_root.is_file() else runtime_root.rglob("*.py")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                assert marker not in text, f"runtime import/reference in {path}: {marker}"


def test_audit_withdraws_runtime_switch_and_speedup_claims() -> None:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    assert "EMBEDDINGS_EVALUATION_JUSTIFIED" in text
    assert "NO runtime wiring" in text
    assert "NO speedup claim" in text
    assert "STOP before embeddings evaluation" in text
