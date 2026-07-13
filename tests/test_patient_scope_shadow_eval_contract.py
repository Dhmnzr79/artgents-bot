from __future__ import annotations

import ast
import copy
import io
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from evals.v5 import run_patient_scope_shadow_eval as harness


def _patient_meta(statuses: dict[str, str], errors: dict[str, str | None] | None = None) -> dict[str, Any]:
    errors = errors or {axis: None for axis in harness.AXES}
    return {
        axis: {
            "confidence": 0.0,
            "provenance": "test.fixture",
            "status": statuses[axis],
            "error": errors[axis],
        }
        for axis in harness.AXES
    }


def _response(
    scope: dict[str, Any],
    statuses: dict[str, str],
    *,
    shadow_status: str = "ok",
    carried: bool = False,
    carry_age: int | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "turn_frame_shadow_status": shadow_status,
        "patient_situation_carried": carried,
        "patient_situation_carry_age": carry_age,
    }
    if shadow_status in {"ok", "partial"}:
        metadata["turn_frame_shadow"] = {
            "patient_scope": copy.deepcopy(scope),
            "field_meta": {"patient_scope": _patient_meta(statuses)},
        }
    return {"meta": {"metadata_first": metadata}}


def _perfect_fake_bundle(spec: dict[str, Any]):
    calls: list[dict[str, Any]] = []
    resets: list[str] = []
    ages: list[str] = []
    multi_counts: dict[str, int] = {}
    singles = {row["question"]: row for row in spec["single_turn_cases"]}

    def post(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(copy.deepcopy(payload))
        sid = payload["sid"]
        if "_single_" in sid:
            row = singles[payload["q"]]
            return _response(row["expected_scope"], row["expected_field_status"])
        scenario_index = int(sid.split("_multi_", 1)[1].split("_", 1)[0])
        scenario = spec["multi_turn_cases"][scenario_index - 1]
        turn_index = multi_counts.get(sid, 0)
        multi_counts[sid] = turn_index + 1
        row = scenario["turns"][turn_index]
        carried = scenario_index == 1 and row["turn"] == 2
        return _response(
            row["expected_current_scope"],
            row["expected_current_field_status"],
            carried=carried,
            carry_age=1 if carried else None,
        )

    def reset(sid: str) -> None:
        resets.append(sid)

    def age(sid: str) -> dict[str, Any]:
        ages.append(sid)
        return {"prepared": True, "reason": "exact"}

    def read(sid: str) -> dict[str, Any] | None:
        scenario_index = int(sid.split("_multi_", 1)[1].split("_", 1)[0])
        kinds = {
            1: "one_tooth_missing",
            2: None,
            3: None,
            4: "few_teeth_missing",
            5: "few_teeth_missing",
        }
        kind = kinds[scenario_index]
        return {"kind": kind} if kind else None

    return post, reset, age, read, calls, resets, ages


def test_frozen_spec_hashes_and_strict_validation() -> None:
    spec = harness.load_and_validate_spec()
    assert harness.git_blob_hash(harness.canonical_git_blob_bytes(harness.MATRIX_PATH)) == harness.MATRIX_HASH
    assert (
        harness.git_blob_hash(harness.canonical_git_blob_bytes(harness.PRESERVATION_PATH))
        == harness.PRESERVATION_HASH
    )
    assert (
        harness.git_blob_hash(harness.canonical_git_blob_bytes(harness.TOPIC_MATRIX_PATH))
        == harness.TOPIC_MATRIX_HASH
    )
    assert len(spec["bridge_cases"]) == 10
    assert len(spec["field_isolation_cases"]) == 4
    assert len(spec["single_turn_cases"]) == 20
    assert len(spec["multi_turn_cases"]) == 5
    assert sum(len(row["turns"]) for row in spec["multi_turn_cases"]) == 10


def test_frozen_ids_are_39_unique_and_ordered() -> None:
    spec = harness.load_and_validate_spec()
    ids = [
        row["id"]
        for group in ("bridge_cases", "field_isolation_cases", "single_turn_cases", "multi_turn_cases")
        for row in spec[group]
    ]
    assert len(ids) == len(set(ids)) == 39
    assert ids[0] == "patient_scope_a9_bridge_01_one_tooth"
    assert ids[-1] == "patient_scope_a9_multi_05_jaw_arrives_second"


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda spec: spec.update({"unexpected": True}), "top-level key mismatch"),
        (lambda spec: spec["bridge_cases"].pop(), "bridge_cases count mismatch"),
        (
            lambda spec: spec["bridge_cases"].reverse(),
            "bridge_cases order mismatch",
        ),
        (
            lambda spec: spec["bridge_cases"][0].update({"raw_patient_situation": "unknown"}),
            "bridge kinds mismatch",
        ),
        (
            lambda spec: spec["scoring_contract"].update({"authority_decision_allowed": True}),
            "scoring contract mismatch",
        ),
        (lambda spec: spec["single_turn_cases"][0].update({"evidence_refs": ["missing.md"]}), "evidence missing"),
    ],
)
def test_strict_preflight_rejects_schema_drift(mutator, message: str) -> None:
    spec = copy.deepcopy(harness.load_and_validate_spec())
    mutator(spec)
    with pytest.raises(harness.HarnessConfigError, match=message):
        harness._validate_frozen_spec(spec)


def test_matrix_hash_mismatch_stops_before_transport(monkeypatch) -> None:
    monkeypatch.setattr(harness, "MATRIX_HASH", "0" * 40)
    calls = 0

    def post(_: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("must not run")

    with pytest.raises(harness.HarnessConfigError, match="hash mismatch"):
        harness.run_harness(post_turn_fn=post, output=io.StringIO())
    assert calls == 0


def test_bridge_uses_real_builder_and_all_ten_pass() -> None:
    results = harness.run_bridge_cases(harness.load_and_validate_spec())
    assert len(results) == 10
    assert {row["status"] for row in results} == {"PASS"}
    assert all(row["reason"] == "exact" for row in results)
    assert all(set(row) == harness.CASE_RESULT_KEYS for row in results)


def test_bridge_builder_failure_is_error_without_exception_leak(monkeypatch) -> None:
    secret = "SECRET-BRIDGE-PATH"

    def boom(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(harness, "build_turn_frame_from_raw", boom)
    results = harness.run_bridge_cases(harness.load_and_validate_spec())
    encoded = json.dumps(results)
    assert {row["status"] for row in results} == {"ERROR"}
    assert {row["reason"] for row in results} == {"bridge_builder_error"}
    assert secret not in encoded


def test_field_isolation_real_current_gap_is_four_fails_not_errors() -> None:
    results = harness.run_field_isolation_cases(harness.load_and_validate_spec())
    assert len(results) == 4
    assert [row["status"] for row in results] == ["FAIL"] * 4
    assert [row["shadow_status"] for row in results] == ["partial"] * 4
    assert all(row["reason"].startswith("scope_value_mismatch:") for row in results)


def test_perfect_fake_full_run_has_exact_calls_results_and_target_red_exit() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, calls, resets, ages = _perfect_fake_bundle(spec)
    output = io.StringIO()
    result = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read,
        output=output,
    )
    assert len(calls) == 30
    assert len(resets) == 25
    assert len(set(resets)) == 25
    assert len(ages) == 1
    assert len(result["case_results"]) == 34
    assert len(result["turn_results"]) == 10
    assert len(result["boundary_results"]) == 5
    assert {row["status"] for row in result["turn_results"]} == {"PASS"}
    assert {row["status"] for row in result["boundary_results"]} == {"PASS"}
    assert result["summary"]["executed_live_calls"] == 30
    assert result["summary"]["field_isolation"] == {"total": 4, "passed": 0, "failed": 4, "errors": 0}
    assert result["summary"]["overall_exit_code"] == 1
    lines = output.getvalue().splitlines()
    assert sum(line.startswith("A9_SCOPE_CASE ") for line in lines) == 34
    assert sum(line.startswith("A9_SCOPE_TURN ") for line in lines) == 10
    assert sum(line.startswith("A9_SCOPE_BOUNDARY ") for line in lines) == 5
    assert sum(line.startswith("A9_SCOPE_SUMMARY ") for line in lines) == 1


def test_fake_full_run_preserves_multi_order_and_one_call_per_turn() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, calls, _, _ = _perfect_fake_bundle(spec)
    harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read,
        output=io.StringIO(),
    )
    multi_calls = [row for row in calls if "_multi_" in row["sid"]]
    expected = [turn["question"] for scenario in spec["multi_turn_cases"] for turn in scenario["turns"]]
    assert [row["q"] for row in multi_calls] == expected
    assert all(row["client_id"] == "demo" for row in calls)


def test_jsonl_does_not_leak_questions_raw_answers_sids_or_exception_text() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, _, _, _ = _perfect_fake_bundle(spec)
    output = io.StringIO()
    harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read,
        output=output,
    )
    text = output.getvalue()
    assert spec["single_turn_cases"][0]["question"] not in text
    assert spec["multi_turn_cases"][0]["turns"][0]["question"] not in text
    assert '"question"' not in text
    assert '"answer"' not in text
    assert '"raw_payload"' not in text
    assert '"sid"' not in text


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        ({}, "metadata_first_missing"),
        (
            {"meta": {"metadata_first": {"turn_frame_shadow_status": "not_available"}}},
            "shadow_not_available",
        ),
        (
            {"meta": {"metadata_first": {"turn_frame_shadow_status": "degraded"}}},
            "shadow_degraded",
        ),
        (
            {"meta": {"metadata_first": {"turn_frame_shadow_status": "ok"}}},
            "shadow_frame_missing",
        ),
    ],
)
def test_live_extraction_errors_are_not_semantic_fails(response, reason: str) -> None:
    scope = {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    statuses = {axis: "defaulted" for axis in harness.AXES}
    status, got_reason, *_ = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert status == "ERROR"
    assert got_reason == reason


def test_transport_exception_is_privacy_safe() -> None:
    def boom(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("SECRET-QUESTION-AND-PATH")

    scope = {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    statuses = {axis: "defaulted" for axis in harness.AXES}
    result = harness._run_live_turn(
        post_turn_fn=boom,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert result[0:3] == ("ERROR", "transport_error", "transport_error")
    assert "SECRET" not in repr(result)


def test_compare_reports_value_status_and_error_separately() -> None:
    scope = {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    statuses = {axis: "defaulted" for axis in harness.AXES}
    errors = {axis: None for axis in harness.AXES}
    got = copy.deepcopy(scope)
    got["jaw"] = "upper"
    assert harness._compare_observation(
        expected_scope=scope,
        observed_scope=got,
        expected_status=statuses,
        observed_status=statuses,
        expected_errors=errors,
        observed_errors=errors,
    ) == ("FAIL", "scope_value_mismatch:jaw")
    got_status = copy.deepcopy(statuses)
    got_status["jaw"] = "valid"
    assert harness._compare_observation(
        expected_scope=scope,
        observed_scope=scope,
        expected_status=statuses,
        observed_status=got_status,
        expected_errors=errors,
        observed_errors=errors,
    ) == ("FAIL", "scope_status_mismatch:jaw")
    expected_invalid = copy.deepcopy(statuses)
    expected_invalid["jaw"] = "invalid"
    expected_errors = copy.deepcopy(errors)
    expected_errors["jaw"] = "patient_jaw_not_allowed"
    observed_errors = copy.deepcopy(expected_errors)
    observed_errors["jaw"] = "patient_jaw_invalid_type"
    assert harness._compare_observation(
        expected_scope=scope,
        observed_scope=scope,
        expected_status=expected_invalid,
        observed_status=expected_invalid,
        expected_errors=expected_errors,
        observed_errors=observed_errors,
    ) == ("FAIL", "scope_error_mismatch:jaw")


def test_stale_default_age_uses_public_blank_ticks_without_history_pollution() -> None:
    from session import mem_reset, recent_dialog_history, set_last_patient_situation

    sid = f"a9-age-{uuid.uuid4().hex}"
    mem_reset(sid)
    set_last_patient_situation(sid, {"kind": "one_tooth_missing"})
    result = harness._default_age_snapshot(sid)
    assert result == {"prepared": True, "reason": "exact"}
    assert harness._default_read_snapshot(sid) is None
    assert recent_dialog_history(sid) == ""
    mem_reset(sid)


def test_stale_precondition_error_still_executes_second_turn() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, _, read, calls, _, _ = _perfect_fake_bundle(spec)
    result = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=lambda _: {"prepared": False, "reason": "snapshot_missing_after_turn_1"},
        read_snapshot_fn=read,
        output=io.StringIO(),
    )
    assert len(calls) == 30
    stale = result["boundary_results"][1]
    assert stale["status"] == "ERROR"
    assert stale["reason"] == "snapshot_missing_after_turn_1"


def test_boundary_result_schema_is_exact_for_all_five() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, _, _, _ = _perfect_fake_bundle(spec)
    result = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read,
        output=io.StringIO(),
    )
    assert len(result["boundary_results"]) == 5
    assert all(set(row) == harness.BOUNDARY_RESULT_KEYS for row in result["boundary_results"])


def test_snapshot_read_failure_is_visible_boundary_error() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, _, calls, _, _ = _perfect_fake_bundle(spec)

    def read_boom(_: str):
        raise RuntimeError("SECRET-SNAPSHOT-PATH")

    result = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read_boom,
        output=io.StringIO(),
    )
    assert len(calls) == 30
    assert {row["status"] for row in result["boundary_results"]} == {"ERROR"}
    assert {row["reason"] for row in result["boundary_results"]} == {"boundary_snapshot_read_error"}
    assert "SECRET" not in json.dumps(result["boundary_results"])


def test_summary_denominators_metrics_and_schema() -> None:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, _, _, _ = _perfect_fake_bundle(spec)
    summary = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age,
        read_snapshot_fn=read,
        output=io.StringIO(),
    )["summary"]
    assert set(summary) == harness.SUMMARY_KEYS
    assert summary["bridge"] == {"total": 10, "passed": 10, "failed": 0, "errors": 0}
    assert summary["single_turn"] == {"total": 20, "passed": 20, "failed": 0, "errors": 0}
    assert summary["multi_turn"] == {"total": 10, "passed": 10, "failed": 0, "errors": 0}
    assert summary["boundaries"] == {"total": 5, "passed": 5, "failed": 0, "errors": 0}
    assert set(summary["per_axis"]) == set(harness.AXES)
    assert all("confusion" in summary["per_axis"][axis] for axis in harness.AXES)
    assert summary["planner_availability"]["available"] == 44
    assert summary["authority_decision_allowed"] is False
    assert summary["product_parity_source"] == "existing_regression_suites"


def test_build_summary_rejects_partial_results() -> None:
    with pytest.raises(ValueError, match="denominator"):
        harness.build_summary(
            case_results=[],
            turn_results=[],
            boundary_results=[],
            executed_live_calls=0,
        )


def test_cli_unknown_argument_exits_two_before_harness(monkeypatch, capsys) -> None:
    def boom(**kwargs):
        raise AssertionError("run_harness must not be called")

    monkeypatch.setattr(harness, "run_harness", boom)
    assert harness.main(["--unexpected"]) == 2
    assert "unexpected CLI arguments" in capsys.readouterr().err


def test_cli_config_error_is_stable_without_details(monkeypatch, capsys) -> None:
    def fail(**kwargs):
        raise harness.HarnessConfigError("SECRET-PATH")

    monkeypatch.setattr(harness, "run_harness", fail)
    assert harness.main([]) == 2
    captured = capsys.readouterr().err
    assert "harness configuration error" in captured
    assert "SECRET" not in captured


def test_production_default_requires_same_process_e2e_test_client(monkeypatch) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    with pytest.raises(harness.HarnessConfigError, match="E2E test client required"):
        harness.run_harness(output=io.StringIO())


def test_production_default_uses_existing_stream_helper_and_public_session_api() -> None:
    source = Path(harness.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "post_ask_stream" in source
    assert "mem_reset" in source
    assert "get_last_patient_situation" in source
    assert 'mem_add_user(sid, "")' in source
    assert "_persist_unlocked" not in source
    assert "_lock" not in source
    forbidden = ("turn_planner_llm", "resolver_turn", "composer_flow", "patient_situation_llm")
    assert not any(any(item in imported for item in forbidden) for imported in imports)


def test_result_key_constants_match_task_contract() -> None:
    assert len(harness.CASE_RESULT_KEYS) == 12
    assert len(harness.TURN_RESULT_KEYS) == 12
    assert len(harness.BOUNDARY_RESULT_KEYS) == 8
    assert len(harness.SUMMARY_KEYS) == 16
