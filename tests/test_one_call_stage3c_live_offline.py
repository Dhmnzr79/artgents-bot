"""Stage 3C LIVE runner offline tests (fake transport, gate patched in tests)."""

from __future__ import annotations

import json
import multiprocessing
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import app as app_module
import config
from evals.v5.one_call_stage3c_speed_gate_contract import (
    FROZEN_BASELINE_COMMIT,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_PROVIDER_CALLS_LIVE,
    MODEL_SNAPSHOT,
    PROPOSED_LIVE_ATTEMPT_ID,
    SPEED_GATE_ENDPOINT,
)
from evals.v5.one_call_stage3c_speed_gate_harness import build_frozen_turn_plan
from evals.v5.one_call_stage3c_speed_gate_live_artifacts import (
    artifact_paths_for_attempt,
    ledger_events_balanced,
)
from evals.v5.one_call_stage3c_speed_gate_live_runner import (
    SpeedGateLiveGovernanceError,
    assert_live_governance,
    assert_live_preflight,
    build_wrapped_real_create,
    run_live_attempt,
    run_preflight_blocked,
    spawn_measurement_worker,
)
from evals.v5.one_call_stage3c_speed_gate_live_transport import (
    MeasurementProviderBudget,
    MeasurementProviderBudgetExceeded,
    SpeedGateLiveTransport,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import FROZEN_MATRIX_SHA256, frozen_matrix_sha256
from evals.v5.run_one_call_stage3c_speed_gate_live import main as live_cli_main


def _patch_live_gate(monkeypatch: pytest.MonkeyPatch, attempt_id: str = PROPOSED_LIVE_ATTEMPT_ID) -> None:
    monkeypatch.setattr(
        "evals.v5.one_call_stage3c_speed_gate_contract.LIVE_AUTHORIZED_ATTEMPT_ID",
        attempt_id,
    )
    monkeypatch.setattr(
        "evals.v5.one_call_stage3c_speed_gate_live_runner.LIVE_AUTHORIZED_ATTEMPT_ID",
        attempt_id,
    )


def _patch_preflight_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CHAT_BASE_URL", SPEED_GATE_ENDPOINT)
    monkeypatch.setattr(config, "CHAT_API_KEY", "sk-prodkeyabcdef1234567890")


def _patch_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight_endpoint(monkeypatch)
    monkeypatch.setattr(
        "evals.v5.one_call_stage3c_speed_gate_live_runner._git_head_commit",
        lambda: FROZEN_BASELINE_COMMIT,
    )


def _ledger_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]


def test_live_cli_gate_none_exit() -> None:
    assert live_cli_main(["--attempt-id", PROPOSED_LIVE_ATTEMPT_ID]) == 3


def test_preflight_blocked_zero_spawn() -> None:
    summary = run_preflight_blocked(PROPOSED_LIVE_ATTEMPT_ID)
    assert summary["spawned_child_count"] == 0
    assert summary["consumed_provider_calls"] == 0
    assert summary["status"] == "live_blocked"


def test_wrong_attempt_id_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gate(monkeypatch, PROPOSED_LIVE_ATTEMPT_ID)
    with pytest.raises(SpeedGateLiveGovernanceError):
        assert_live_governance("wrong_attempt_id")


def test_existing_marker_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    paths["attempt_json"].parent.mkdir(parents=True, exist_ok=True)
    paths["attempt_json"].write_text("{}", encoding="utf-8")
    with pytest.raises(Exception, match="ATTEMPT_MARKER_EXISTS"):
        run_live_attempt(
            PROPOSED_LIVE_ATTEMPT_ID,
            artifact_root=paths,
            use_fake_transport=True,
        )


def test_one_spawned_measurement_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    assert result["spawned_child_count"] == 1
    assert result["completed_turns"] == len(build_frozen_turn_plan())


def test_alternating_arms_and_old_new_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    latency = result["latency_runs"]
    arms = [row["arm"] for row in latency]
    assert "OLD" in arms and "NEW" in arms
    new_calls = [row for row in latency if row["arm"] == "NEW"]
    for row in new_calls:
        for provider in row["provider_calls"]:
            assert provider["requested_model"] == MODEL_SNAPSHOT
    old_calls = [row for row in latency if row["arm"] == "OLD"]
    for row in old_calls:
        assert row["observed_models"]


def test_global_provider_ceiling_and_new_one_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    assert result["consumed_provider_calls"] <= MAX_PROVIDER_CALLS_LIVE
    assert result["max_provider_calls_live"] == 36
    new_latency = [
        row for row in result["latency_runs"] if row["arm"] == "NEW"
    ]
    assert all(row["provider_call_count"] <= 1 for row in new_latency)
    assert all(row["provider_call_count"] == 0 for row in result["admin_runs"])


def test_call_37_blocked_before_transport() -> None:
    budget = MeasurementProviderBudget(max_calls=36, consumed=36)
    transport = SpeedGateLiveTransport(
        budget=budget,
        use_fake_transport=True,
        fake_transport=__import__(
            "evals.v5.one_call_stage3c_speed_gate_fake_transport",
            fromlist=["SpeedGateFakeTransport"],
        ).SpeedGateFakeTransport(answer_text="x"),
    )
    with pytest.raises(MeasurementProviderBudgetExceeded):
        transport.chat_completions_create(model=MODEL_SNAPSHOT, messages=[])


def test_ledgers_balanced_after_full_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
    )
    assert ledger_events_balanced(paths["turns_jsonl"])
    assert ledger_events_balanced(paths["calls_jsonl"])


def test_partial_artifacts_after_every_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
    )
    assert paths["raw_json"].exists()
    assert paths["result_json"].exists()
    raw = json.loads(paths["raw_json"].read_text(encoding="utf-8"))
    assert raw["completed_turns"] == len(build_frozen_turn_plan())


def test_timeout_aborts_and_closes_open_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    active_before = len(multiprocessing.active_children())
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        worker_startup_timeout_seconds=60.0,
        attempt_wall_timeout_seconds=120.0,
        turn_timeout_seconds=2.0,
        hang_turn_index=0,
        hang_sleep_seconds=5.0,
    )
    assert result["status"] == "aborted"
    assert result.get("failure_kind") == "turn_wall_timeout"
    assert result.get("worker_ready") is True
    assert result["consumed_provider_calls"] == 0
    assert result["completed_provider_calls"] == 0
    assert result["completed_turns"] == 0
    events = _ledger_events(paths["turns_jsonl"])
    starts = [row for row in events if row["event"] == "START"]
    errors = [row for row in events if row["event"] == "ERROR"]
    finishes = [row for row in events if row["event"] == "FINISH"]
    assert len(starts) == 1
    assert len(errors) == 1
    assert len(finishes) == 0
    assert starts[0]["case_id"] == errors[0]["case_id"]
    assert starts[0]["arm"] == errors[0]["arm"]
    assert errors[0]["error_code"] == "turn_wall_timeout"
    assert not _ledger_events(paths["calls_jsonl"])
    assert paths["raw_json"].exists()
    assert paths["result_json"].exists()
    assert len(multiprocessing.active_children()) == active_before


def test_worker_startup_timeout_records_parent_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        worker_startup_timeout_seconds=2.0,
        attempt_wall_timeout_seconds=120.0,
        turn_timeout_seconds=2.0,
        hang_before_worker_ready=True,
        hang_sleep_seconds=5.0,
    )
    assert result["status"] == "aborted"
    assert result.get("failure_kind") == "worker_startup_timeout"
    assert not result.get("worker_ready")
    assert result["consumed_provider_calls"] == 0
    events = _ledger_events(paths["turns_jsonl"])
    assert len([r for r in events if r["event"] == "START"]) == 1
    assert len([r for r in events if r["event"] == "ERROR"]) == 1
    assert len([r for r in events if r["event"] == "FINISH"]) == 0
    assert not _ledger_events(paths["calls_jsonl"])
    first_turn = build_frozen_turn_plan()[0]
    assert events[0]["case_id"] == first_turn["case_id"]
    assert events[0]["arm"] == first_turn["arm"]
    assert events[1]["error_code"] == "worker_startup_timeout"


def test_slow_bootstrap_does_not_trigger_turn_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
        worker_startup_timeout_seconds=30.0,
        turn_timeout_seconds=2.0,
        attempt_wall_timeout_seconds=120.0,
        bootstrap_sleep_seconds=3.0,
    )
    assert result["status"] == "completed"
    assert result.get("worker_ready") is True
    assert result["completed_turns"] == len(build_frozen_turn_plan())
    assert ledger_events_balanced(
        artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)["turns_jsonl"]
    )


def test_real_wrapper_calls_underlying_once_no_recursion() -> None:
    underlying_calls = 0

    def underlying_create(**kwargs: object) -> SimpleNamespace:
        nonlocal underlying_calls
        underlying_calls += 1
        return SimpleNamespace(
            model=str(kwargs.get("model") or MODEL_SNAPSHOT),
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(
                prompt_tokens=1,
                completion_tokens=1,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )

    wrapped = build_wrapped_real_create(underlying_create)
    transport = SpeedGateLiveTransport(
        budget=MeasurementProviderBudget(max_calls=36),
        use_fake_transport=False,
        real_create=wrapped,
    )

    def instrumented_create(**kwargs: object) -> object:
        return transport.chat_completions_create(**kwargs)

    instrumented_create(model=MODEL_SNAPSHOT, messages=[{"role": "user", "content": "hi"}])
    assert underlying_calls == 1

    ledger_calls: list[str] = []
    transport2 = SpeedGateLiveTransport(
        budget=MeasurementProviderBudget(max_calls=36),
        use_fake_transport=False,
        real_create=wrapped,
        on_provider_start=lambda _call: ledger_calls.append("START"),
        on_provider_finish=lambda _call: ledger_calls.append("FINISH"),
    )
    transport2.chat_completions_create(model=MODEL_SNAPSHOT, messages=[])
    assert underlying_calls == 2
    assert ledger_calls == ["START", "FINISH"]


def test_frozen_baseline_commit_pin() -> None:
    assert FROZEN_BASELINE_COMMIT == "4fe14658ebe8a454be6c4cb017c3670c7ea2f4c0"
    assert len(FROZEN_BASELINE_COMMIT) == 40
    assert all(ch in "0123456789abcdef" for ch in FROZEN_BASELINE_COMMIT)


def test_git_head_matches_frozen_baseline() -> None:
    repo = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
    ).strip()
    assert head == FROZEN_BASELINE_COMMIT


def test_preflight_baseline_blocks_wrong_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight_endpoint(monkeypatch)
    monkeypatch.setattr(
        "evals.v5.one_call_stage3c_speed_gate_live_runner._git_head_commit",
        lambda: "0000000000000000000000000000000000000000",
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    with pytest.raises(SpeedGateLiveGovernanceError) as excinfo:
        assert_live_preflight(PROPOSED_LIVE_ATTEMPT_ID, paths=paths)
    assert excinfo.value.code == "baseline_commit_mismatch"


def test_preflight_baseline_passes_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight_endpoint(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    assert_live_preflight(PROPOSED_LIVE_ATTEMPT_ID, paths=paths)


def test_auth_failure_aborts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch, "auth_abort_stage3c")
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt("auth_abort_stage3c", artifacts_root=tmp_path)
    result = run_live_attempt(
        "auth_abort_stage3c",
        artifact_root=paths,
        use_fake_transport=True,
        fail_first_provider_error="AuthenticationError",
    )
    assert result["status"] == "error"
    assert result.get("failure_kind") == "AuthenticationError"
    assert result["consumed_provider_calls"] <= 1


def test_no_active_child_after_spawn_return(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    active_before = len(multiprocessing.active_children())
    job = {
        "attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "use_fake_transport": True,
        "turns": build_frozen_turn_plan()[:1],
    }
    outcome = spawn_measurement_worker(
        job,
        worker_startup_timeout_seconds=60.0,
        attempt_wall_timeout_seconds=60.0,
    )
    assert outcome.cleanup_verified
    assert outcome.worker_ready_received
    assert len(multiprocessing.active_children()) == active_before


def test_matrix_sha_pinned() -> None:
    assert frozen_matrix_sha256() == FROZEN_MATRIX_SHA256


def test_no_tests_imports_in_live_eval_modules() -> None:
    repo = Path(__file__).resolve().parents[1]
    modules = [
        repo / "evals/v5/one_call_stage3c_speed_gate_live_runner.py",
        repo / "evals/v5/one_call_stage3c_speed_gate_matrix.py",
        repo / "evals/v5/run_one_call_stage3c_speed_gate_live.py",
    ]
    for path in modules:
        text = path.read_text(encoding="utf-8")
        assert "tests." not in text
        assert "from tests" not in text


def test_artifacts_no_prompt_corpus_key_pii(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    for path in (
        paths["raw_json"],
        paths["result_json"],
        paths["calls_jsonl"],
        paths["turns_jsonl"],
        paths["attempt_json"],
    ):
        blob = path.read_text(encoding="utf-8")
        assert "APPROVED_MD_CORPUS" not in blob
        assert "=== SYSTEM_POLICY ===" not in blob
        assert "clients/demo/md/" not in blob
        assert "sk-prodkey" not in blob
        assert SPEED_GATE_ENDPOINT not in blob


def test_quality_fail_final_fail_not_abort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    assert result["status"] == "completed"
    assert result["speed_gate"]["verdict"] in {"fail", "pass", "inconclusive"}


def test_incomplete_cannot_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_preflight(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        worker_startup_timeout_seconds=60.0,
        attempt_wall_timeout_seconds=120.0,
        turn_timeout_seconds=2.0,
        hang_turn_index=0,
        hang_sleep_seconds=5.0,
    )
    assert result["speed_gate"]["verdict"] == "inconclusive"
    assert result["speed_gate"]["speed_pass"] is False


def test_production_does_not_import_live_runner() -> None:
    text = Path(app_module.__file__).read_text(encoding="utf-8")
    assert "one_call_stage3c_speed_gate_live_runner" not in text
    assert "run_one_call_stage3c_speed_gate_live" not in text


def test_gate_none_no_artifacts(tmp_path: Path) -> None:
    assert LIVE_AUTHORIZED_ATTEMPT_ID is None
    run_preflight_blocked(PROPOSED_LIVE_ATTEMPT_ID)
    attempt_dir = tmp_path / PROPOSED_LIVE_ATTEMPT_ID
    assert not attempt_dir.exists()
