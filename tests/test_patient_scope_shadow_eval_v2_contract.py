from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from evals.v5 import run_patient_scope_shadow_eval_v2 as harness


_V1_MATRIX = Path("evals/v5/demo/patient_scope_shadow_matrix.json")
_V2_MATRIX = Path("evals/v5/demo/patient_scope_shadow_matrix_v2.json")
_RAW = Path("eval_patient_scope_a9_last.txt")
_PURPOSE = (
    "Frozen A9 v2 patient-scope shadow expectations with live-only scoring "
    "and harness-owned manual-contact applicability."
)
_SCORING = {
    "scope_match": "per_field_exact_normalized",
    "metadata_match": "per_field_status_and_stable_error",
    "observation_priority": [
        "transport_error",
        "scoreable_shadow",
        "runtime_not_available_or_degraded",
        "pre_planner_manual_contact",
        "extraction_error",
    ],
    "planner_availability_live_only": True,
    "manual_contact_not_applicable": {
        "service_route": "ingress_manual_contact",
        "status": "not_applicable",
        "reason": "pre_planner_manual_contact",
    },
    "not_applicable_retained_in_frozen_total": True,
    "not_applicable_excluded_from_scoreable_denominators": [
        "scope",
        "exact",
        "positive",
        "composite",
    ],
    "live_quality_separate_from_deterministic_fixtures": True,
    "current_frame_is_current_turn_only": True,
    "legacy_session_carry_scored_separately": True,
    "one_live_call_per_live_turn": True,
    "retry_failed_case": False,
    "confidence_is_descriptive_only": True,
    "confidence_pass_threshold": None,
    "authority_decision_allowed": False,
    "product_parity_source": "existing_regression_suites",
}
_NULL_ERRORS = {axis: None for axis in ("extent", "jaw", "stage", "modifiers")}
_MANUAL_IDS = {
    "patient_scope_a9_live_17_urgent_only",
    "patient_scope_a9_live_20_booking_complaint",
}


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _patient_meta(
    statuses: dict[str, str],
    errors: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    errors = errors or dict(_NULL_ERRORS)
    result: dict[str, Any] = {
        "container": {
            "confidence": 0.0,
            "provenance": "test.fixture.patient_scope",
            "status": "valid",
            "error": None,
        }
    }
    for axis in harness.AXES:
        result[axis] = {
            "confidence": 0.0,
            "provenance": f"test.fixture.patient_scope.{axis}",
            "status": statuses[axis],
            "error": errors[axis],
        }
    return result


def _scoreable_response(
    scope: dict[str, Any],
    statuses: dict[str, str],
    *,
    shadow_status: str = "ok",
    service_route: str | None = None,
    carried: bool = False,
    carry_age: int | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "metadata_first": {
            "turn_frame_shadow_status": shadow_status,
            "turn_frame_shadow": {
                "patient_scope": copy.deepcopy(scope),
                "field_meta": {"patient_scope": _patient_meta(statuses)},
            },
            "patient_situation_carried": carried,
            "patient_situation_carry_age": carry_age,
        }
    }
    if service_route is not None:
        meta["service_route"] = service_route
    return {"meta": meta}


def _manual_response() -> dict[str, Any]:
    return {"meta": {"service_route": "ingress_manual_contact"}}


def _fake_bundle(
    spec: dict[str, Any],
    overrides: dict[str, dict[str, Any]] | None = None,
):
    overrides = overrides or {}
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
            if row["id"] in overrides:
                return copy.deepcopy(overrides[row["id"]])
            if row["id"] in _MANUAL_IDS:
                return _manual_response()
            return _scoreable_response(row["expected_scope"], row["expected_field_status"])
        scenario_index = int(sid.split("_multi_", 1)[1].split("_", 1)[0])
        scenario = spec["multi_turn_cases"][scenario_index - 1]
        turn_index = multi_counts.get(sid, 0)
        multi_counts[sid] = turn_index + 1
        row = scenario["turns"][turn_index]
        carried = scenario_index == 1 and row["turn"] == 2
        return _scoreable_response(
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


def _run_fake(
    *,
    overrides: dict[str, dict[str, Any]] | None = None,
    age_fn=None,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    spec = harness.load_and_validate_spec()
    post, reset, age, read, calls, _, _ = _fake_bundle(spec, overrides)
    output = io.StringIO()
    result = harness.run_harness(
        post_turn_fn=post,
        reset_session_fn=reset,
        age_snapshot_fn=age_fn or age,
        read_snapshot_fn=read,
        output=output,
    )
    return result, output.getvalue(), calls


def _default_expected() -> tuple[dict[str, Any], dict[str, str]]:
    return (
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        {axis: "defaulted" for axis in harness.AXES},
    )


def test_v2_matrix_uses_independent_literal_oracle_and_preserves_v1_cases() -> None:
    v1_text = _V1_MATRIX.read_text(encoding="utf-8")
    v2_text = _V2_MATRIX.read_text(encoding="utf-8")
    v1 = json.loads(v1_text)
    v2 = json.loads(v2_text)

    assert v2["schema_version"] == "a9.patient_scope_shadow_matrix.v2"
    assert v2["purpose"] == _PURPOSE
    assert v2["scoring_contract"] == _SCORING
    assert v2["authority_decision_allowed"] is False
    assert v1_text.split('  "bridge_cases":', 1)[1] == v2_text.split('  "bridge_cases":', 1)[1]
    for key in ("bridge_cases", "field_isolation_cases", "single_turn_cases", "multi_turn_cases"):
        assert v2[key] == v1[key]


def test_frozen_hashes_counts_and_order_are_exact() -> None:
    assert _git_blob_hash(_V2_MATRIX) == "8de7698266bb61f237618f39b18a8b984e8ea5cd"
    assert _git_blob_hash(Path("evals/v5/run_patient_scope_shadow_eval.py")) == "2898ff1d56dba3319f4121158ba98e2879cdb579"
    assert _git_blob_hash(Path("tests/test_patient_scope_shadow_eval_contract.py")) == "c2ed5f0655ab8e1dddda1a865ab95c50ffc797b3"
    assert _git_blob_hash(_V1_MATRIX) == "d459073bbf8767f7ff590ece2958f7aa8cb18b25"
    assert _git_blob_hash(Path("tests/fixtures/patient_scope_native_contract_a9_v2.json")) == "c7458e4481489895320ea3de1dec1a81b8da5f50"
    assert hashlib.sha256(_RAW.read_bytes()).hexdigest().upper() == "478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21"

    spec = harness.load_and_validate_spec()
    ids = [
        row["id"]
        for group in ("bridge_cases", "field_isolation_cases", "single_turn_cases", "multi_turn_cases")
        for row in spec[group]
    ]
    assert len(ids) == len(set(ids)) == 39
    assert len(spec["single_turn_cases"]) == 20
    assert sum(len(row["turns"]) for row in spec["multi_turn_cases"]) == 10


def test_strict_preflight_rejects_version_scoring_and_hash_drift(monkeypatch) -> None:
    spec = copy.deepcopy(harness.load_and_validate_spec())
    spec["scoring_contract"]["authority_decision_allowed"] = True
    with pytest.raises(harness.HarnessConfigError, match="scoring contract mismatch"):
        harness._validate_frozen_spec(spec)

    monkeypatch.setattr(harness, "MATRIX_HASH", "0" * 40)
    with pytest.raises(harness.HarnessConfigError, match="hash mismatch"):
        harness.run_harness(post_turn_fn=lambda _: {}, output=io.StringIO())


def test_real_deterministic_builder_paths_are_fourteen_exact_passes() -> None:
    spec = harness.load_and_validate_spec()
    rows = [*harness.run_bridge_cases(spec), *harness.run_field_isolation_cases(spec)]
    assert len(rows) == 14
    assert {row["status"] for row in rows} == {"PASS"}
    assert {row["availability_status"] for row in rows} == {"available"}
    assert all(row["reason"] == "exact" for row in rows)


def test_perfect_fake_run_has_honest_live_denominators_and_green_exit() -> None:
    result, output, calls = _run_fake()
    summary = result["summary"]

    assert len(calls) == 30
    assert len(result["case_results"]) == 34
    assert len(result["turn_results"]) == 10
    assert len(result["boundary_results"]) == 5
    assert summary["planned_live_calls"] == summary["executed_live_calls"] == 30
    assert summary["planner_availability"] == {
        "available": 28,
        "not_available": 0,
        "degraded": 0,
        "not_applicable": 2,
        "transport_error": 0,
        "extraction_error": 0,
    }
    assert sum(summary["planner_availability"].values()) == 30
    assert summary["live_current_scope"] == {
        "total": 30,
        "scoreable": 28,
        "exact_complete": 28,
        "not_applicable": 2,
    }
    assert summary["single_turn"] == {
        "total": 20,
        "passed": 18,
        "failed": 0,
        "errors": 0,
        "not_applicable": 2,
    }
    assert summary["multi_turn"]["passed"] == 10
    assert summary["field_isolation"]["passed"] == 4
    assert summary["boundaries"]["passed"] == 5
    assert summary["overall_exit_code"] == 0
    manual_rows = [row for row in result["case_results"] if row["status"] == "NOT_APPLICABLE"]
    assert {row["case_id"] for row in manual_rows} == _MANUAL_IDS
    assert {row["reason"] for row in manual_rows} == {"pre_planner_manual_contact"}
    assert {row["shadow_status"] for row in manual_rows} == {"not_applicable"}
    assert all(row["observed_scope"] is None for row in manual_rows)
    for group in ("bridge", "field_isolation", "single_turn", "multi_turn", "boundaries"):
        counts = summary[group]
        assert counts["total"] == sum(
            counts[key] for key in ("passed", "failed", "errors", "not_applicable")
        )
    assert output.count("A9_SCOPE_V2_CASE ") == 34
    assert output.count("A9_SCOPE_V2_TURN ") == 10
    assert output.count("A9_SCOPE_V2_BOUNDARY ") == 5
    assert output.count("A9_SCOPE_V2_SUMMARY ") == 1


def test_positive_and_composite_denominators_are_recomputed_from_live_matrix() -> None:
    spec = harness.load_and_validate_spec()
    live_scopes = [row["expected_scope"] for row in spec["single_turn_cases"]]
    live_scopes.extend(
        turn["expected_current_scope"]
        for scenario in spec["multi_turn_cases"]
        for turn in scenario["turns"]
    )
    positive = {
        "extent": sum(row["extent"] != "unknown" for row in live_scopes),
        "jaw": sum(row["jaw"] != "unknown" for row in live_scopes),
        "stage": sum(row["stage"] != "unknown" for row in live_scopes),
        "modifiers": sum(bool(row["modifiers"]) for row in live_scopes),
    }
    composite = sum(
        sum(
            (
                row["extent"] != "unknown",
                row["jaw"] != "unknown",
                row["stage"] != "unknown",
                bool(row["modifiers"]),
            )
        )
        >= 2
        for row in live_scopes
    )
    assert positive == {"extent": 13, "jaw": 9, "stage": 4, "modifiers": 3}
    assert composite == 7

    summary = _run_fake()[0]["summary"]
    for axis, expected in positive.items():
        metric = summary["live_per_axis"][axis]
        assert metric["scoreable"] == 28
        assert metric["all_value_exact"] == 28
        assert metric["positive_expected"] == expected
        assert metric["positive_available"] == expected
        assert metric["positive_exact"] == expected
    assert summary["live_composite"] == {"total": 7, "scoreable": 7, "exact": 7}


@pytest.mark.parametrize("runtime_status", ["not_available", "degraded"])
def test_scoreable_frame_wins_manual_route_and_runtime_status(runtime_status: str) -> None:
    scope, statuses = _default_expected()
    response = _scoreable_response(
        scope,
        statuses,
        shadow_status=runtime_status,
        service_route="ingress_manual_contact",
    )
    result = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert result[:4] == ("PASS", "exact", runtime_status, "available")


@pytest.mark.parametrize("runtime_status", ["not_available", "degraded"])
def test_runtime_status_wins_manual_contact_when_frame_is_absent(runtime_status: str) -> None:
    scope, statuses = _default_expected()
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": {"turn_frame_shadow_status": runtime_status},
        }
    }
    result = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert result[:4] == ("ERROR", runtime_status, runtime_status, runtime_status)


@pytest.mark.parametrize(
    "frame",
    [
        None,
        {},
        {"patient_scope": {"extent": "unknown"}, "field_meta": {}},
        {
            "patient_scope": {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
            "field_meta": {"patient_scope": {}},
        },
    ],
)
def test_present_malformed_manual_frame_is_extraction_error(frame: Any) -> None:
    scope, statuses = _default_expected()
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": {"turn_frame_shadow_status": "ok", "turn_frame_shadow": frame},
        }
    }
    result = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert result[0] == "ERROR"
    assert result[1] == result[3] == "extraction_error"


def test_container_meta_is_shape_validated_but_not_a_semantic_axis() -> None:
    scope, statuses = _default_expected()
    response = _scoreable_response(scope, statuses)
    container = response["meta"]["metadata_first"]["turn_frame_shadow"]["field_meta"]["patient_scope"]["container"]
    container.update({"status": "invalid", "error": "patient_scope_invalid_type"})
    accepted = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert accepted[:4] == ("PASS", "exact", "ok", "available")

    container["error"] = "patient_extent_invalid_type"
    rejected = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert rejected[0] == "ERROR"
    assert rejected[1] == rejected[3] == "extraction_error"


def test_transport_and_generic_missing_are_distinct_privacy_safe_errors() -> None:
    scope, statuses = _default_expected()

    def boom(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("SECRET-QUESTION-AND-PATH")

    transport = harness._run_live_turn(
        post_turn_fn=boom,
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    missing = harness._run_live_turn(
        post_turn_fn=lambda _: {},
        payload={"q": "secret", "sid": "secret", "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert transport[:4] == ("ERROR", "transport_error", "transport_error", "transport_error")
    assert missing[0] == "ERROR" and missing[1] == missing[3] == "extraction_error"
    assert "SECRET" not in repr(transport)


def test_fail_error_and_boundary_error_make_exit_red_but_na_does_not() -> None:
    spec = harness.load_and_validate_spec()
    row = spec["single_turn_cases"][0]
    wrong = copy.deepcopy(row["expected_scope"])
    wrong["extent"] = "unknown"
    mismatch = _scoreable_response(wrong, row["expected_field_status"])
    result = _run_fake(overrides={row["id"]: mismatch})[0]
    assert result["summary"]["single_turn"]["failed"] == 1
    assert result["summary"]["overall_exit_code"] == 1

    missing = _run_fake(overrides={row["id"]: {}})[0]
    assert missing["summary"]["planner_availability"]["extraction_error"] == 1
    assert missing["summary"]["overall_exit_code"] == 1

    boundary = _run_fake(age_fn=lambda _: {"prepared": False, "reason": "snapshot_missing_after_turn_1"})[0]
    assert boundary["summary"]["boundaries"]["errors"] == 1
    assert boundary["summary"]["overall_exit_code"] == 1


def test_output_schema_and_recursive_privacy_are_frozen() -> None:
    result, output, _ = _run_fake()
    assert set(result["summary"]) == harness.SUMMARY_KEYS
    assert all(set(row) == harness.CASE_RESULT_KEYS for row in result["case_results"])
    assert all(set(row) == harness.TURN_RESULT_KEYS for row in result["turn_results"])
    assert all(set(row) == harness.BOUNDARY_RESULT_KEYS for row in result["boundary_results"])
    forbidden = {
        "question",
        "answer",
        "history",
        "sid",
        "session",
        "raw_payload",
        "exception",
        "recommendation",
        "diagnosis",
        "price_choice",
        "service_choice",
    }

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for child in value.values():
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)

    for line in output.splitlines():
        scan(json.loads(line.split(" ", 1)[1]))
    assert "SECRET" not in output
    assert spec_question_not_present(output)


def test_adversarial_runtime_observability_is_normalized_before_output() -> None:
    marker = "SENSITIVE_MARKER"
    scope, statuses = _default_expected()
    response = _scoreable_response(scope, statuses)
    response["meta"]["metadata_first"]["turn_frame_shadow_status"] = {
        "secret": marker
    }
    live = harness._run_live_turn(
        post_turn_fn=lambda _: response,
        payload={"q": marker, "sid": marker, "client_id": "demo"},
        expected_scope=scope,
        expected_status=statuses,
    )
    assert live[:4] == ("PASS", "exact", "unknown", "available")

    spec = harness.load_and_validate_spec()
    malformed_boundary = harness._boundary_result(
        scenario_index=1,
        scenario=spec["multi_turn_cases"][0],
        mf={
            "patient_situation_carried": {"secret": marker},
            "patient_situation_carry_age": marker,
        },
        snapshot={"kind": {"secret": marker}},
        scope=scope,
        statuses=statuses,
        stale_preparation=None,
    )
    stale_boundary = harness._boundary_result(
        scenario_index=2,
        scenario=spec["multi_turn_cases"][1],
        mf={
            "patient_situation_carried": False,
            "patient_situation_carry_age": None,
        },
        snapshot=None,
        scope=scope,
        statuses=statuses,
        stale_preparation={"prepared": False, "reason": marker},
    )
    assert malformed_boundary["status"] == "ERROR"
    assert malformed_boundary["reason"] == "boundary_observation_malformed"
    assert malformed_boundary["observed_carried"] is None
    assert malformed_boundary["observed_carry_age"] is None
    assert malformed_boundary["observed_snapshot_kind"] is None
    assert stale_boundary["reason"] == "boundary_stale_preparation_error"

    output = io.StringIO()
    harness._emit("A9_SCOPE_V2_CASE", {"shadow_status": live[2]}, output)
    harness._emit("A9_SCOPE_V2_BOUNDARY", malformed_boundary, output)
    harness._emit("A9_SCOPE_V2_BOUNDARY", stale_boundary, output)
    assert marker not in output.getvalue()
    assert '"secret"' not in output.getvalue()


def spec_question_not_present(output: str) -> bool:
    spec = harness.load_and_validate_spec()
    questions = [row["question"] for row in spec["single_turn_cases"]]
    questions.extend(turn["question"] for row in spec["multi_turn_cases"] for turn in row["turns"])
    return all(question not in output for question in questions)


def test_cli_config_exit_and_product_import_firewall(monkeypatch, capsys) -> None:
    monkeypatch.delenv("E2E_USE_TEST_CLIENT", raising=False)
    with pytest.raises(harness.HarnessConfigError, match="E2E test client required"):
        harness.run_harness(output=io.StringIO())
    assert harness.main(["--unexpected"]) == 2
    assert "unexpected CLI arguments" in capsys.readouterr().err

    def config_fail(**kwargs):
        raise harness.HarnessConfigError("SECRET-CONFIG-PATH")

    monkeypatch.setattr(harness, "run_harness", config_fail)
    assert harness.main([]) == 2
    captured = capsys.readouterr().err
    assert "harness configuration error" in captured
    assert "SECRET" not in captured

    harness_source = Path(harness.__file__).read_text(encoding="utf-8")
    harness_tree = ast.parse(harness_source)
    imports = {
        alias.name
        for node in ast.walk(harness_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        forbidden in imported
        for forbidden in ("resolver_turn", "composer_flow", "patient_situation_llm")
        for imported in imports
    )
    production_paths = [Path("app.py"), Path("llm.py"), Path("resolver.py"), Path("session.py")]
    production_paths.extend(Path("core").glob("*.py"))
    production_paths.extend(Path("contracts").glob("*.py"))
    production_paths.extend(Path("orchestration").glob("*.py"))
    production_text = "\n".join(path.read_text(encoding="utf-8") for path in production_paths if path.is_file())
    assert "run_patient_scope_shadow_eval_v2" not in production_text
    assert "patient_scope_availability_v2" not in production_text
