"""Offline tests for FINAL scope/widget E2E retry2 live harness."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from evals.v5.final_scope_widget_e2e_live_contract import (
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    OWNER_APPROVED_PLANNER_MODEL,
    create_attempt_marker_exclusive,
)
from evals.v5.final_scope_widget_e2e_live_harness import (
    configure_process_env,
    run_non_network_preflight,
    validate_runtime_seams,
    _scope_nav_refs,
)
from evals.v5.final_scope_widget_e2e_live_provider_audit import get_audit_state
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    MEASUREMENT_ID,
    RETRY_COUNT_MAX,
    S69_DELETED_LEGACY_MODULES,
    S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    build_retry2_attempt_marker_payload,
    load_frozen_turns,
)
from evals.v5.final_scope_widget_e2e_retry2_live_harness import (
    _assert_frozen_neighbors,
    prepare_retry2_live_run,
    run_http_harness,
)
from tests.test_final_scope_widget_e2e_retry1_live_harness import (
    _install_retry1_http_fakes,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

_RETRY2_HARNESS_FILES = (
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "final_scope_widget_e2e_retry2_live_harness.py",
    _REPO_ROOT / "evals" / "v5" / "run_final_scope_widget_e2e_retry2_live.py",
)


@pytest.fixture(autouse=True)
def _retry2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A9_PATIENT_SCOPE_AUTHORITY", "1")
    monkeypatch.setenv("TURN_PLANNER_LLM_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("MODEL_INGRESS_CLASSIFY", "qwen3.6-flash")
    monkeypatch.setenv("TARGET_FULLCONTEXT_BOUNDARY_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_COMPOSER_MODEL", OWNER_APPROVED_PLANNER_MODEL)
    monkeypatch.setenv("TARGET_FULLCONTEXT_VERIFIER_MODEL", OWNER_APPROVED_PLANNER_MODEL)


def test_frozen_retry1_neighbors_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()


def test_retry2_budget_constants() -> None:
    assert MAX_PROVIDER_CALLS == 40
    assert MAX_HTTP_TURNS == 8
    assert RETRY_COUNT_MAX == 0
    load_frozen_turns()


def test_s69_deleted_modules_not_importable() -> None:
    for module_name in S69_DELETED_LEGACY_MODULES:
        assert importlib.util.find_spec(module_name) is None, module_name


def test_harness_ast_firewall_forbids_deleted_s69_imports() -> None:
    patterns = [re.compile(p) for p in S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS]
    offenders: list[str] = []
    for path in _RETRY2_HARNESS_FILES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in patterns:
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}:{line.strip()}")
    assert not offenders, offenders


def test_validate_runtime_seams_exposes_target_only_client() -> None:
    configure_process_env()
    seam = validate_runtime_seams()
    assert hasattr(seam["app_module"], "_orchestrate_ask_turn")
    assert not hasattr(seam["app_module"], "orchestrate_routing_after_resolver")
    assert seam["client"] is not None


def test_fake_provider_executes_all_eight_http_turns_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))

    run_non_network_preflight(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
        assert_frozen_neighbors=_assert_frozen_neighbors,
    )
    create_attempt_marker_exclusive(
        marker,
        build_retry2_attempt_marker_payload(baseline_commit="retry2-offline"),
    )
    _install_retry1_http_fakes(monkeypatch)

    payload = run_http_harness(
        live=False,
        skip_live_prepare=True,
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
    )

    assert len(payload["turn_results"]) == MAX_HTTP_TURNS
    assert all(row["status_code"] == 200 for row in payload["turn_results"])
    assert all(row["automated_turn_verdict"] == "PASS" for row in payload["turn_results"])
    assert payload["summary"]["technical"]["turn_automated_pass"] == MAX_HTTP_TURNS
    assert payload["summary"]["technical"]["all_materialized"] is True
    assert payload["summary"]["technical"]["fullcontext_build_count"] == 1
    turn2 = payload["turn_results"][1]
    assert "terminal" not in str((turn2.get("meta") or {}).get("service_route") or "")
    turn5 = payload["turn_results"][4]
    assert len(_scope_nav_refs(list(turn5.get("quick_replies") or []))) == 3
    assert "₽" in str(turn5.get("answer_text") or "")
    stream_turns = [row for row in payload["turn_results"] if row["endpoint"] == "/ask/stream"]
    assert len(stream_turns) == 2
    assert all("event: ui" in str(row.get("stream_text") or "") for row in stream_turns)
    assert get_audit_state().total_started == 0


def test_ask_and_stream_invoke_target_only_orchestration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))
    run_non_network_preflight(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
        assert_frozen_neighbors=_assert_frozen_neighbors,
    )
    create_attempt_marker_exclusive(
        marker,
        build_retry2_attempt_marker_payload(baseline_commit="retry2-route"),
    )
    _install_retry1_http_fakes(monkeypatch)
    payload = run_http_harness(
        live=False,
        skip_live_prepare=True,
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        artifact_paths=artifacts,
        monkeypatch=monkeypatch,
    )
    ask_count = sum(1 for row in payload["turn_results"] if row["endpoint"] == "/ask")
    stream_count = sum(1 for row in payload["turn_results"] if row["endpoint"] == "/ask/stream")
    assert ask_count == 6
    assert stream_count == 2
    assert all(row["automated_turn_verdict"] == "PASS" for row in payload["turn_results"])


def test_retry2_dry_run_cli() -> None:
    from evals.v5.final_scope_widget_e2e_retry2_live_contract import LIVE_ATTEMPT_MARKER_PATH

    proc = subprocess.run(
        [sys.executable, "evals/v5/run_final_scope_widget_e2e_retry2_live.py", "--dry-run"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if LIVE_ATTEMPT_MARKER_PATH.exists():
        assert proc.returncode == 2, proc.stderr
        assert "CONFIG_ERROR" in proc.stderr
        return
    assert proc.returncode == 0, proc.stderr
    idx = proc.stdout.rfind('"measurement_id"')
    start = proc.stdout.rfind("{", 0, idx)
    payload = json.loads(proc.stdout[start:])
    assert payload["measurement_id"] == MEASUREMENT_ID
    assert payload["dry_run"] is True
    assert payload["live_blocked"] is True
    assert payload["max_http_turns"] == MAX_HTTP_TURNS
    assert payload["retry_count_max"] == 0


def test_retry2_runner_has_no_deleted_module_imports() -> None:
    source = (_REPO_ROOT / "evals/v5/run_final_scope_widget_e2e_retry2_live.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "orchestration.ask_turn" not in imported


def test_marker_created_after_seam_validation_before_provider_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "attempt.json"
    artifacts = tuple(tmp_path / f"artifact_{i}.json" for i in range(3))
    events: list[str] = []

    def tracked_validate(mp: object | None = None) -> dict[str, object]:
        events.append("seams_validated")
        return validate_runtime_seams(mp)

    def tracked_create(path: Path, payload: dict[str, object]) -> None:
        events.append("marker_created")
        create_attempt_marker_exclusive(path, payload)

    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_retry2_live_harness.assert_retry2_live_artifacts_absent",
        lambda: None,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.validate_runtime_seams",
        tracked_validate,
    )
    monkeypatch.setattr(
        "evals.v5.final_scope_widget_e2e_live_harness.create_attempt_marker_exclusive",
        tracked_create,
    )
    prepare_retry2_live_run(
        attempt_marker_path=marker,
        artifact_paths=artifacts,
        baseline_commit="retry2-test",
        monkeypatch=monkeypatch,
    )
    assert events == ["seams_validated", "marker_created"]
