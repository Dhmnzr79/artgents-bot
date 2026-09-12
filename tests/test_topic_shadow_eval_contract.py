"""Unit contract for A6 direct topic shadow harness (no live LLM)."""

from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.v5 import run_topic_shadow_eval as harness

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _frozen_spec() -> dict:
    return harness.load_and_validate_spec()


def _frozen_spec_without_client_check() -> dict:
    harness.validate_frozen_file_hash(
        path=harness.FROZEN_MATRIX_PATH,
        expected_hash=harness.FROZEN_MATRIX_HASH,
        label="matrix",
    )
    harness.validate_frozen_file_hash(
        path=harness.FROZEN_PRESERVATION_PATH,
        expected_hash=harness.FROZEN_PRESERVATION_HASH,
        label="preservation",
    )
    spec = json.loads(Path(harness.FROZEN_MATRIX_PATH).read_text(encoding="utf-8"))
    taxonomy = frozenset(harness.FROZEN_TAXONOMY_ORDERED)
    harness._validate_top_level(spec)
    harness._validate_cases(spec["cases"], taxonomy=taxonomy)
    return spec


def _case(case_id: str) -> dict:
    for row in _frozen_spec()["cases"]:
        if row["id"] == case_id:
            return dict(row)
    raise KeyError(case_id)


def _plan(topic: object | None, confidence: object = 0.0):
    return SimpleNamespace(topic=topic, topic_confidence=confidence)


_EMPTY_DESCRIPTIVE_BUCKET = {
    "count": 0,
    "values": [],
    "min": None,
    "max": None,
    "mean": None,
}


def _write_demo_md(*, md_dir: Path, filename: str, doc_id: str, topic: str = "clinic") -> None:
    md_dir.mkdir(parents=True, exist_ok=True)
    md_dir.joinpath(filename).write_text(
        f"---\ndoc_id: {doc_id}\ntopic: {topic}\n---\nbody\n",
        encoding="utf-8",
    )


def _install_duplicate_doc_id_pack(monkeypatch, tmp_path: Path) -> Path:
    md_dir = tmp_path / "clients" / "demo" / "md"
    _write_demo_md(md_dir=md_dir, filename="dup_a.md", doc_id="dup_doc_id")
    _write_demo_md(md_dir=md_dir, filename="dup_b.md", doc_id="dup_doc_id")
    monkeypatch.setattr(harness, "_REPO_ROOT", str(tmp_path))
    return md_dir


def test_frozen_spec_passes_strict_validation() -> None:
    spec = _frozen_spec()
    assert spec["suite_id"] == "a6_topic_shadow_quality_matrix"
    assert len(spec["cases"]) == 33


def test_git_blob_hash_matches_frozen_matrix() -> None:
    data = harness.canonical_git_blob_bytes(harness.FROZEN_MATRIX_PATH)
    assert harness.git_blob_hash(data) == harness.FROZEN_MATRIX_HASH


def test_matrix_hash_mismatch_stops_before_planner(monkeypatch, tmp_path) -> None:
    bad_path = tmp_path / "bad_matrix.json"
    bad_path.write_bytes(b"{}")
    monkeypatch.setattr(harness, "FROZEN_MATRIX_PATH", str(bad_path))
    with pytest.raises(harness.HarnessConfigError, match="hash mismatch"):
        harness.load_and_validate_spec()


def test_preservation_hash_mismatch_stops_before_planner(monkeypatch, tmp_path) -> None:
    matrix_copy = tmp_path / "matrix.json"
    matrix_copy.write_bytes(Path(harness.FROZEN_MATRIX_PATH).read_bytes())
    bad_preservation = tmp_path / "bad_preservation.json"
    bad_preservation.write_bytes(b"{}")
    monkeypatch.setattr(harness, "FROZEN_MATRIX_PATH", str(matrix_copy))
    monkeypatch.setattr(harness, "FROZEN_PRESERVATION_PATH", str(bad_preservation))
    with pytest.raises(harness.HarnessConfigError, match="hash mismatch"):
        harness.load_and_validate_spec()


def test_unknown_top_level_key_is_config_error() -> None:
    spec = json.loads(Path(harness.FROZEN_MATRIX_PATH).read_text(encoding="utf-8"))
    spec["extra"] = True
    with pytest.raises(harness.HarnessConfigError, match="top-level"):
        harness._validate_top_level(spec)


def test_unknown_case_key_is_config_error() -> None:
    spec = _frozen_spec()
    cases = [dict(row) for row in spec["cases"]]
    cases[0]["observed_topic"] = "clinic"
    with pytest.raises(harness.HarnessConfigError, match="key mismatch"):
        harness._validate_cases(cases, taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_scoring_contract_change_is_config_error() -> None:
    spec = json.loads(Path(harness.FROZEN_MATRIX_PATH).read_text(encoding="utf-8"))
    spec["scoring_contract"] = dict(spec["scoring_contract"])
    spec["scoring_contract"]["retry_failed_case"] = True
    with pytest.raises(harness.HarnessConfigError, match="scoring_contract"):
        harness._validate_top_level(spec)


def test_duplicate_case_id_is_config_error() -> None:
    spec = _frozen_spec()
    cases = [dict(row) for row in spec["cases"]]
    cases[1]["id"] = cases[0]["id"]
    with pytest.raises(harness.HarnessConfigError, match="duplicate"):
        harness._validate_cases(cases, taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_per_topic_distribution_mismatch_is_config_error() -> None:
    spec = _frozen_spec()
    cases = [dict(row) for row in spec["cases"]]
    cases[0]["expected_topic"] = "doctors"
    with pytest.raises(harness.HarnessConfigError, match="per-topic"):
        harness._validate_cases(cases, taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_taxonomy_mismatch_is_config_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.topic_taxonomy.load_client_topic_taxonomy",
        lambda _cid: frozenset({"clinic"}),
    )
    spec = _frozen_spec_without_client_check()
    with pytest.raises(harness.HarnessConfigError, match="taxonomy mismatch"):
        harness._validate_client_sources(spec["cases"], taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_missing_source_doc_is_config_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.topic_taxonomy.load_client_topic_taxonomy",
        lambda _cid: frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    monkeypatch.setattr(harness, "_demo_doc_topics_by_doc_id", lambda: {})
    spec = _frozen_spec_without_client_check()
    with pytest.raises(harness.HarnessConfigError, match="missing source doc_id"):
        harness._validate_client_sources(spec["cases"], taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_source_doc_topic_mismatch_is_config_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.topic_taxonomy.load_client_topic_taxonomy",
        lambda _cid: frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    doc_topics = harness._demo_doc_topics_by_doc_id()
    first = next(
        row
        for row in _frozen_spec_without_client_check()["cases"]
        if row["id"] == "topic_a6_01_clinic_payment"
    )
    doc_topics[str(first["source_doc_id"])] = "doctors"
    monkeypatch.setattr(harness, "_demo_doc_topics_by_doc_id", lambda: doc_topics)
    spec = _frozen_spec_without_client_check()
    with pytest.raises(harness.HarnessConfigError, match="source doc topic mismatch"):
        harness._validate_client_sources(spec["cases"], taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED))


def test_duplicate_client_frontmatter_doc_id_stops_before_planner(monkeypatch, tmp_path) -> None:
    _install_duplicate_doc_id_pack(monkeypatch, tmp_path)

    with pytest.raises(harness.HarnessConfigError, match="duplicate doc_id"):
        harness._demo_doc_topics_by_doc_id()

    planner_calls = {"count": 0}

    def _boom(*_args, **_kwargs):
        planner_calls["count"] += 1
        return _plan("clinic", 0.5)

    with pytest.raises(harness.HarnessConfigError, match="duplicate doc_id"):
        harness.load_and_validate_spec()
    assert planner_calls["count"] == 0

    with pytest.raises(harness.HarnessConfigError, match="duplicate doc_id"):
        harness.run_harness(plan_turn_fn=_boom)
    assert planner_calls["count"] == 0


def test_fake_planner_called_33_times_in_order_with_none_sid() -> None:
    spec = _frozen_spec()
    calls: list[tuple[str, str | None, str]] = []

    def _fake(question: str, sid: str | None, client_id: str):
        calls.append((question, sid, client_id))
        return _plan("clinic", 0.5)

    out = io.StringIO()
    code = harness.run_harness(plan_turn_fn=_fake, stdout=out)
    assert code == 1
    assert len(calls) == 33
    assert [q for q, _sid, _cid in calls] == [case["question"] for case in spec["cases"]]
    assert all(sid is None for _q, sid, _cid in calls)
    assert all(client_id == "demo" for _q, _sid, client_id in calls)


def test_planner_none_is_unavailable_without_retry() -> None:
    calls = {"count": 0}

    def _fake(_question: str, _sid: str | None, _client_id: str):
        calls["count"] += 1
        return None

    out = io.StringIO()
    harness.run_harness(plan_turn_fn=_fake, stdout=out)
    assert calls["count"] == 33


def test_planner_exception_continues_remaining_cases() -> None:
    seen: list[int] = []

    def _fake(_question: str, _sid: str | None, _client_id: str):
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError("secret planner failure")
        return _plan("clinic", 0.5)

    out = io.StringIO()
    harness.run_harness(plan_turn_fn=_fake, stdout=out)
    assert len(seen) == 33
    rows = [json.loads(line.removeprefix("A6_CASE ")) for line in out.getvalue().splitlines() if line.startswith("A6_CASE ")]
    assert rows[0]["status"] == "ERROR"
    assert rows[0]["reason"] == "planner_exception"
    assert rows[1]["status"] in {"PASS", "FAIL", "ERROR"}


def test_exact_match_pass() -> None:
    result = harness.classify_plan_result(
        expected_topic="clinic",
        plan=_plan("clinic", 0.8),
        taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    assert result == {
        "observed_topic": "clinic",
        "topic_confidence": 0.8,
        "status": "PASS",
        "reason": "exact_match",
    }


def test_null_exact_match_pass() -> None:
    result = harness.classify_plan_result(
        expected_topic=None,
        plan=_plan(None, 0.0),
        taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    assert result["status"] == "PASS"
    assert result["reason"] == "exact_match"


def test_valid_mismatch_is_fail_with_confusion_cell() -> None:
    def _fake(question: str, _sid: str | None, _client_id: str) -> object:
        if question == _case("topic_a6_01_clinic_payment")["question"]:
            return _plan("doctors", 0.7)
        return _plan(None, 0.0)

    out = io.StringIO()
    harness.run_harness(plan_turn_fn=_fake, stdout=out)
    summary = json.loads(out.getvalue().strip().splitlines()[-1].removeprefix("A6_SUMMARY "))
    assert summary["failed"] >= 1
    assert summary["confusion_matrix"]["clinic"]["doctors"] >= 1


def test_out_of_taxonomy_is_invalid_error() -> None:
    result = harness.classify_plan_result(
        expected_topic="clinic",
        plan=_plan("not_a_real_topic", 0.5),
        taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    assert result["status"] == "ERROR"
    assert result["reason"] == "invalid_or_out_of_taxonomy"


def test_invalid_confidence_is_invalid_error() -> None:
    result = harness.classify_plan_result(
        expected_topic="clinic",
        plan=_plan("clinic", 1.5),
        taxonomy=frozenset(harness.FROZEN_TAXONOMY_ORDERED),
    )
    assert result["reason"] == "invalid_or_out_of_taxonomy"


def test_summary_denominator_and_confusion_total_remain_33_with_errors() -> None:
    out = io.StringIO()
    harness.run_harness(plan_turn_fn=lambda *_a, **_k: None, stdout=out)
    summary = json.loads(out.getvalue().strip().splitlines()[-1].removeprefix("A6_SUMMARY "))
    assert summary["total"] == 33
    total_cells = sum(
        summary["confusion_matrix"][row][col]
        for row in harness.CONFUSION_ROWS
        for col in harness.CONFUSION_COLS
    )
    assert total_cells == 33


def test_per_topic_and_ambiguous_metrics() -> None:
    spec = _frozen_spec()

    def _planner(question: str, _sid: str | None, _client_id: str):
        case = next(row for row in spec["cases"] if row["question"] == question)
        if case["case_kind"] == "ambiguous_null":
            return _plan(None, 0.0)
        return _plan(case["expected_topic"], 0.6)

    out = io.StringIO()
    code = harness.run_harness(plan_turn_fn=_planner, stdout=out)
    summary = json.loads(out.getvalue().strip().splitlines()[-1].removeprefix("A6_SUMMARY "))
    assert code == 0
    assert summary["ambiguous_null_exact_match"] == {"matched": 6, "total": 6, "rate": 1.0}
    for topic in harness.FROZEN_TAXONOMY_ORDERED:
        assert summary["per_topic_exact_match"][topic] == {"matched": 3, "total": 3, "rate": 1.0}


def test_build_summary_rejects_partial_case_results() -> None:
    with pytest.raises(ValueError, match="33 entries"):
        harness.build_summary(
            spec=_frozen_spec(),
            case_results=[
                {
                    "index": 1,
                    "case_id": "a",
                    "case_kind": "grounded_single_topic",
                    "expected_topic": "clinic",
                    "observed_topic": "clinic",
                    "topic_confidence": 0.5,
                    "status": "PASS",
                    "reason": "exact_match",
                }
            ],
        )


def test_descriptive_bucket_empty_list_semantics() -> None:
    assert harness._descriptive_bucket([]) == _EMPTY_DESCRIPTIVE_BUCKET


def test_summary_empty_incorrect_and_invalid_confidence_buckets() -> None:
    spec = _frozen_spec()

    def _perfect(question: str, _sid: str | None, _client_id: str):
        case = next(row for row in spec["cases"] if row["question"] == question)
        return _plan(case["expected_topic"], 0.4 if case["expected_topic"] else 0.0)

    out = io.StringIO()
    code = harness.run_harness(plan_turn_fn=_perfect, stdout=out)
    assert code == 0
    summary = json.loads(out.getvalue().strip().splitlines()[-1].removeprefix("A6_SUMMARY "))
    buckets = summary["confidence_by_correctness_descriptive"]
    assert buckets["incorrect"] == _EMPTY_DESCRIPTIVE_BUCKET
    assert buckets["invalid"] == _EMPTY_DESCRIPTIVE_BUCKET
    assert buckets["correct"]["count"] == 33


def test_confidence_bucket_values() -> None:
    def _row(i: int) -> dict:
        if i == 1:
            return {
                "index": 1,
                "case_id": "c1",
                "case_kind": "grounded_single_topic",
                "expected_topic": "clinic",
                "observed_topic": "clinic",
                "topic_confidence": 0.5,
                "status": "PASS",
                "reason": "exact_match",
            }
        if i == 2:
            return {
                "index": 2,
                "case_id": "c2",
                "case_kind": "grounded_single_topic",
                "expected_topic": "clinic",
                "observed_topic": "doctors",
                "topic_confidence": 0.25,
                "status": "FAIL",
                "reason": "topic_mismatch",
            }
        if i == 3:
            return {
                "index": 3,
                "case_id": "c3",
                "case_kind": "grounded_single_topic",
                "expected_topic": "clinic",
                "observed_topic": None,
                "topic_confidence": None,
                "status": "ERROR",
                "reason": "invalid_or_out_of_taxonomy",
            }
        return {
            "index": i,
            "case_id": f"c{i}",
            "case_kind": "grounded_single_topic",
            "expected_topic": "clinic",
            "observed_topic": "clinic",
            "topic_confidence": 0.5,
            "status": "PASS",
            "reason": "exact_match",
        }

    summary = harness.build_summary(
        spec=_frozen_spec(),
        case_results=[_row(i) for i in range(1, 34)],
    )
    buckets = summary["confidence_by_correctness_descriptive"]
    assert buckets["correct"]["count"] == 31
    assert buckets["incorrect"]["mean"] == 0.25
    assert buckets["invalid"]["count"] == 0


def test_exit_codes_are_distinct() -> None:
    assert harness.main(["--unexpected-argument"]) == 2

    out = io.StringIO()
    spec = _frozen_spec()

    def _perfect(question: str, _sid: str | None, _client_id: str):
        case = next(row for row in spec["cases"] if row["question"] == question)
        return _plan(case["expected_topic"], 0.4 if case["expected_topic"] else 0.0)

    assert harness.run_harness(plan_turn_fn=_perfect, stdout=out) == 0

    out = io.StringIO()
    assert harness.run_harness(plan_turn_fn=lambda *_a, **_k: _plan("doctors", 0.1), stdout=out) == 1


def test_cli_rejects_unknown_arguments_without_planner(monkeypatch) -> None:
    def _boom(**_kwargs):
        raise AssertionError("run_harness should not be called")

    monkeypatch.setattr(harness, "run_harness", _boom)
    assert harness.main(["--unexpected-argument"]) == 2


def test_production_default_uses_real_plan_turn_symbol() -> None:
    import core.turn_planner_llm

    source = Path(harness.__file__).read_text(encoding="utf-8")
    assert "from core.turn_planner_llm import plan_turn" in source
    assert core.turn_planner_llm.plan_turn is not None


def test_runner_does_not_import_app_resolver_or_http() -> None:
    source = Path("evals/v5/run_topic_shadow_eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    assert "app" not in imported
    assert "orchestration.resolver_turn" not in imported
    assert "urllib" not in imported
    assert "requests" not in imported


def test_frozen_hashes_unchanged() -> None:
    matrix = harness.canonical_git_blob_bytes(harness.FROZEN_MATRIX_PATH)
    preservation = harness.canonical_git_blob_bytes(harness.FROZEN_PRESERVATION_PATH)
    assert harness.git_blob_hash(matrix) == harness.FROZEN_MATRIX_HASH
    assert harness.git_blob_hash(preservation) == harness.FROZEN_PRESERVATION_HASH


def test_case_result_keys_contains_exactly_eight_task_fields() -> None:
    expected = {
        "index",
        "case_id",
        "case_kind",
        "expected_topic",
        "observed_topic",
        "topic_confidence",
        "status",
        "reason",
    }
    assert harness.CASE_RESULT_KEYS == expected
    assert len(harness.CASE_RESULT_KEYS) == 8


def test_case_output_schema_has_no_exception_or_question_leaks() -> None:
    out = io.StringIO()
    harness.run_harness(plan_turn_fn=lambda *_a, **_k: _plan("clinic", 0.5), stdout=out)
    for line in out.getvalue().splitlines():
        if not line.startswith("A6_CASE "):
            continue
        payload = json.loads(line.removeprefix("A6_CASE "))
        assert set(payload.keys()) == harness.CASE_RESULT_KEYS
        assert "exception" not in json.dumps(payload)
        assert "secret" not in json.dumps(payload).lower()
