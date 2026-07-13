"""Unit contract for A7 attempt-aware topic shadow re-audit (no live LLM)."""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from contracts.planner_attempt import PlannerAttempt
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5 import run_topic_shadow_attempt_eval as harness

_A6_RUNNER_HASH = "23150c7d47950a5b7127a44120963632bc230b00"
_A6_TEST_HASH = "e1153a4e11ed22978fa3ac644f436bc26c30f17e"
_TAXONOMY = frozenset(harness.a6_harness.FROZEN_TAXONOMY_ORDERED)


def _spec() -> dict:
    return harness.a6_harness.load_and_validate_spec()


def _case_by_question() -> dict[str, dict]:
    return {case["question"]: case for case in _spec()["cases"]}


def _frame(
    topic: str | None,
    *,
    confidence: object = 0.9,
    aspects: list[str] | None = None,
):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["overview"] if aspects is None else aspects,
            "topic": topic,
            "topic_confidence": confidence,
        },
        allowed_topics=_TAXONOMY,
    )


def _attempt(
    topic: str | None,
    *,
    confidence: object = 0.9,
    aspects: list[str] | None = None,
    shadow_status: str | None = None,
    legacy_available: bool = True,
):
    frame = _frame(topic, confidence=confidence, aspects=aspects)
    if shadow_status is None:
        shadow_status = "partial" if topic is None or aspects == [] else "ok"
    return SimpleNamespace(
        legacy_plan=object() if legacy_available else None,
        shadow_frame=frame,
        shadow_status=shadow_status,
    )


def _perfect_attempt(question: str, _sid, client_id: str):
    assert client_id == "demo"
    expected = _case_by_question()[question]["expected_topic"]
    return _attempt(
        expected,
        confidence=0.9 if expected is not None else 0.0,
    )


def _case_lines(output: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("A7_CASE "))
        for line in output.splitlines()
        if line.startswith("A7_CASE ")
    ]


def _summary(output: str) -> dict:
    lines = [line for line in output.splitlines() if line.startswith("A7_SUMMARY ")]
    assert len(lines) == 1
    return json.loads(lines[0].removeprefix("A7_SUMMARY "))


def test_old_a6_harness_and_tests_keep_frozen_hashes() -> None:
    a6 = harness.a6_harness
    assert a6.git_blob_hash(a6.canonical_git_blob_bytes("evals/v5/run_topic_shadow_eval.py")) == _A6_RUNNER_HASH
    assert a6.git_blob_hash(a6.canonical_git_blob_bytes("tests/test_topic_shadow_eval_contract.py")) == _A6_TEST_HASH
    assert a6.git_blob_hash(a6.canonical_git_blob_bytes(a6.FROZEN_MATRIX_PATH)) == a6.FROZEN_MATRIX_HASH
    assert a6.git_blob_hash(a6.canonical_git_blob_bytes(a6.FROZEN_PRESERVATION_PATH)) == a6.FROZEN_PRESERVATION_HASH


def test_perfect_fake_is_called_33_times_in_frozen_order() -> None:
    calls: list[tuple[str, None, str]] = []

    def _fake(question, sid, client_id):
        calls.append((question, sid, client_id))
        return _perfect_attempt(question, sid, client_id)

    out = io.StringIO()
    code = harness.run_harness(plan_turn_attempt_fn=_fake, stdout=out)

    cases = _spec()["cases"]
    assert code == 0
    assert calls == [(case["question"], None, "demo") for case in cases]
    assert [row["case_id"] for row in _case_lines(out.getvalue())] == [
        case["id"] for case in cases
    ]


def test_partial_doctors_with_empty_aspects_is_scoreable_without_legacy() -> None:
    frame = _frame("doctors", confidence=0.95, aspects=[])
    attempt = PlannerAttempt(
        legacy_plan=None,
        shadow_frame=frame,
        shadow_status="partial",
    )

    result = harness.classify_attempt_result(
        expected_topic="doctors",
        attempt=attempt,
        taxonomy=_TAXONOMY,
    )

    assert result == {
        "observed_topic": "doctors",
        "topic_confidence": 0.95,
        "topic_field_status": "valid",
        "topic_field_error": None,
        "shadow_status": "partial",
        "legacy_plan_available": False,
        "status": "PASS",
        "reason": "exact_match",
    }


def test_missing_topic_with_zero_confidence_is_scoreable_null() -> None:
    result = harness.classify_attempt_result(
        expected_topic=None,
        attempt=_attempt(None, confidence=0.0, legacy_available=False),
        taxonomy=_TAXONOMY,
    )
    assert result["status"] == "PASS"
    assert result["reason"] == "exact_match"
    assert result["observed_topic"] is None
    assert result["topic_confidence"] == 0.0
    assert result["topic_field_status"] == "missing"


def test_partial_valid_topic_mismatch_is_fail_not_error() -> None:
    result = harness.classify_attempt_result(
        expected_topic="doctors",
        attempt=_attempt("extraction", shadow_status="partial", legacy_available=False),
        taxonomy=_TAXONOMY,
    )
    assert result["status"] == "FAIL"
    assert result["reason"] == "topic_mismatch"
    assert result["observed_topic"] == "extraction"


def test_invalid_topic_metadata_is_error_with_stable_reason() -> None:
    attempt = SimpleNamespace(
        legacy_plan=None,
        shadow_frame=build_turn_frame_from_raw(
            {
                "route": "content",
                "aspects": ["overview"],
                "topic": "secret-unknown-topic",
                "topic_confidence": 0.9,
            },
            allowed_topics=_TAXONOMY,
        ),
        shadow_status="partial",
    )
    result = harness.classify_attempt_result(
        expected_topic=None,
        attempt=attempt,
        taxonomy=_TAXONOMY,
    )
    assert result["status"] == "ERROR"
    assert result["reason"] == "invalid_or_out_of_taxonomy"
    assert result["topic_field_status"] == "invalid"
    assert result["topic_field_error"] == "topic_not_allowed"
    assert "secret-unknown-topic" not in str(result)


def test_invalid_topic_confidence_keeps_stable_field_error() -> None:
    attempt = SimpleNamespace(
        legacy_plan=None,
        shadow_frame=_frame("doctors", confidence="not-a-number"),
        shadow_status="partial",
    )
    result = harness.classify_attempt_result(
        expected_topic="doctors",
        attempt=attempt,
        taxonomy=_TAXONOMY,
    )
    assert result["status"] == "ERROR"
    assert result["reason"] == "invalid_or_out_of_taxonomy"
    assert result["topic_field_error"] == "topic_confidence_invalid"


@pytest.mark.parametrize(
    ("attempt", "error", "reason", "shadow_status"),
    [
        (None, None, "planner_unavailable", "not_available"),
        (
            SimpleNamespace(legacy_plan=None, shadow_frame=None, shadow_status="not_available"),
            None,
            "planner_unavailable",
            "not_available",
        ),
        (
            SimpleNamespace(legacy_plan=object(), shadow_frame=None, shadow_status="degraded"),
            None,
            "shadow_degraded",
            "degraded",
        ),
        (None, RuntimeError("secret exception and question"), "planner_exception", "not_available"),
    ],
)
def test_technical_unavailable_reasons_are_distinct(attempt, error, reason, shadow_status) -> None:
    result = harness.classify_attempt_result(
        expected_topic="clinic",
        attempt=attempt,
        taxonomy=_TAXONOMY,
        error=error,
    )
    assert result["status"] == "ERROR"
    assert result["reason"] == reason
    assert result["shadow_status"] == shadow_status
    assert "secret exception" not in str(result)


def test_valid_shadow_without_legacy_is_still_scoreable() -> None:
    result = harness.classify_attempt_result(
        expected_topic="clinic",
        attempt=_attempt("clinic", legacy_available=False, shadow_status="partial"),
        taxonomy=_TAXONOMY,
    )
    assert result["status"] == "PASS"
    assert result["legacy_plan_available"] is False


def test_perfect_summary_has_exact_attempt_status_counts() -> None:
    out = io.StringIO()
    assert harness.run_harness(plan_turn_attempt_fn=_perfect_attempt, stdout=out) == 0
    summary = _summary(out.getvalue())

    assert summary["measurement_id"] == harness.MEASUREMENT_ID
    assert summary["total"] == 33
    assert summary["passed"] == 33
    assert summary["failed"] == 0
    assert summary["errors"] == 0
    assert summary["scoreable_count"] == 33
    assert summary["shadow_status_counts"] == {
        "ok": 27,
        "partial": 6,
        "not_available": 0,
        "degraded": 0,
    }
    assert summary["topic_field_status_counts"] == {
        "valid": 27,
        "missing": 6,
        "invalid": 0,
        "defaulted": 0,
        "unavailable": 0,
    }
    assert summary["legacy_plan_available_count"] == 33
    assert summary["authority_decision_allowed"] is False
    confusion_total = sum(
        value
        for columns in summary["confusion_matrix"].values()
        for value in columns.values()
    )
    assert confusion_total == 33


def test_summary_separates_unavailable_degraded_and_invalid() -> None:
    spec = _spec()
    rows: list[dict] = []
    for index, case in enumerate(spec["cases"], start=1):
        classified = harness.classify_attempt_result(
            expected_topic=case["expected_topic"],
            attempt=_perfect_attempt(case["question"], None, "demo"),
            taxonomy=_TAXONOMY,
        )
        rows.append(
            {
                "index": index,
                "case_id": case["id"],
                "case_kind": case["case_kind"],
                "expected_topic": case["expected_topic"],
                **classified,
            }
        )

    rows[0].update(
        harness.classify_attempt_result(
            expected_topic=rows[0]["expected_topic"],
            attempt=None,
            taxonomy=_TAXONOMY,
        )
    )
    rows[1].update(
        harness.classify_attempt_result(
            expected_topic=rows[1]["expected_topic"],
            attempt=SimpleNamespace(
                legacy_plan=object(),
                shadow_frame=None,
                shadow_status="degraded",
            ),
            taxonomy=_TAXONOMY,
        )
    )
    rows[2].update(
        harness.classify_attempt_result(
            expected_topic=rows[2]["expected_topic"],
            attempt=SimpleNamespace(
                legacy_plan=None,
                shadow_frame=_frame("secret-invalid"),
                shadow_status="partial",
            ),
            taxonomy=_TAXONOMY,
        )
    )

    summary = harness.build_attempt_summary(spec=spec, case_results=rows)
    assert summary["total"] == 33
    assert summary["passed"] == 30
    assert summary["failed"] == 0
    assert summary["errors"] == 3
    assert summary["scoreable_count"] == 30
    assert summary["planner_unavailable_count"] == 1
    assert summary["shadow_degraded_count"] == 1
    assert summary["invalid_or_out_of_taxonomy_count"] == 1
    assert summary["technical_unavailable_count"] == 2
    assert summary["shadow_status_counts"]["not_available"] == 1
    assert summary["shadow_status_counts"]["degraded"] == 1
    assert summary["topic_field_status_counts"]["invalid"] == 1


def test_case_output_has_exact_keys_and_no_sensitive_fields() -> None:
    out = io.StringIO()
    harness.run_harness(plan_turn_attempt_fn=_perfect_attempt, stdout=out)
    rows = _case_lines(out.getvalue())
    assert len(rows) == 33
    assert harness.CASE_RESULT_KEYS == frozenset(harness.CASE_RESULT_FIELDS)
    assert len(harness.CASE_RESULT_KEYS) == 12
    for row in rows:
        assert set(row) == harness.CASE_RESULT_KEYS
        assert "question" not in row
        assert "answer" not in row
        assert "history" not in row
        assert "raw" not in row
        assert "exception" not in row


def test_one_case_exception_does_not_retry_or_shrink_denominator() -> None:
    calls: list[str] = []
    first_question = _spec()["cases"][0]["question"]

    def _fake(question, sid, client_id):
        calls.append(question)
        if question == first_question:
            raise RuntimeError("secret exception text")
        return _perfect_attempt(question, sid, client_id)

    out = io.StringIO()
    assert harness.run_harness(plan_turn_attempt_fn=_fake, stdout=out) == 1
    rows = _case_lines(out.getvalue())
    summary = _summary(out.getvalue())
    assert len(calls) == 33
    assert calls.count(first_question) == 1
    assert len(rows) == 33
    assert rows[0]["reason"] == "planner_exception"
    assert "secret exception text" not in str(rows[0])
    assert summary["passed"] == 32
    assert summary["errors"] == 1
    assert summary["scoreable_count"] == 32
    assert summary["technical_unavailable_count"] == 1


def test_internal_classifier_failure_is_not_mislabeled_as_planner_exception(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake(question, sid, client_id):
        calls["count"] += 1
        return _perfect_attempt(question, sid, client_id)

    monkeypatch.setattr(
        harness,
        "classify_attempt_result",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("harness classifier bug")),
    )
    with pytest.raises(RuntimeError, match="harness classifier bug"):
        harness.run_harness(plan_turn_attempt_fn=_fake, stdout=io.StringIO())
    assert calls["count"] == 1


def test_preflight_failure_stops_before_attempt_calls(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake(*_args):
        calls["count"] += 1
        return _attempt("clinic")

    monkeypatch.setattr(
        harness.a6_harness,
        "load_and_validate_spec",
        lambda: (_ for _ in ()).throw(harness.a6_harness.HarnessConfigError("hash mismatch")),
    )
    with pytest.raises(harness.a6_harness.HarnessConfigError, match="hash mismatch"):
        harness.run_harness(plan_turn_attempt_fn=_fake, stdout=io.StringIO())
    assert calls["count"] == 0


def test_unknown_cli_argument_exits_two_before_harness(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        harness,
        "run_harness",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("harness must not run")),
    )
    assert harness.main(["--unexpected-argument"]) == 2
    assert "A7_CONFIG_ERROR unexpected CLI arguments" in capsys.readouterr().err


def test_production_default_uses_plan_turn_attempt_not_legacy_wrapper() -> None:
    source = Path("evals/v5/run_topic_shadow_attempt_eval.py").read_text(encoding="utf-8")
    assert "from core.turn_planner_llm import plan_turn_attempt as plan_turn_attempt_fn" in source
    assert "plan_turn(" not in source
    assert source.count("plan_turn_attempt_fn(") == 1


def test_runner_has_no_product_runtime_or_http_imports() -> None:
    source = Path("evals/v5/run_topic_shadow_attempt_eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = {"app", "resolver", "orchestration", "flask", "requests", "httpx"}
    assert forbidden.isdisjoint(imported)
