"""HTTP harness for FINAL scope/widget E2E retry2 live runtime eval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.v5.final_scope_widget_e2e_live_harness import (
    configure_process_env,
    evaluate_summary,
    evaluate_turn_gates,
    pick_scope_ref,
    pick_stage_ref,
    prepare_live_run,
    run_http_harness as _run_http_harness,
    run_non_network_preflight,
    validate_runtime_seams,
)
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_AUDIT_LOG_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    MEASUREMENT_ID,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
    assert_retry2_live_artifacts_absent,
    build_retry2_attempt_marker_payload,
)


def _assert_frozen_neighbors() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_suite_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()


def prepare_retry2_live_run(
    *,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    baseline_commit: str | None = None,
    monkeypatch: Any | None = None,
) -> None:
    assert_retry2_live_artifacts_absent()
    prepare_live_run(
        attempt_marker_path=attempt_marker_path,
        artifact_paths=artifact_paths,
        owner_override_attempt_marker=owner_override_attempt_marker,
        baseline_commit=baseline_commit,
        build_marker_payload=build_retry2_attempt_marker_payload,
        assert_frozen_neighbors=_assert_frozen_neighbors,
        monkeypatch=monkeypatch,
    )


def run_http_harness(
    *,
    live: bool,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    call_ledger_path: Path = LIVE_CALL_LEDGER_PATH,
    raw_path: Path = LIVE_RAW_ARTIFACT_PATH,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    manifest_path: Path = LIVE_MANIFEST_ARTIFACT_PATH,
    manual_review_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    audit_log_path: Path = LIVE_AUDIT_LOG_PATH,
    artifact_paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    monkeypatch: Any | None = None,
    skip_live_prepare: bool = False,
) -> dict[str, Any]:
    return _run_http_harness(
        live=live,
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
        raw_path=raw_path,
        result_path=result_path,
        manifest_path=manifest_path,
        manual_review_path=manual_review_path,
        audit_log_path=audit_log_path,
        artifact_paths=artifact_paths,
        owner_override_attempt_marker=owner_override_attempt_marker,
        monkeypatch=monkeypatch,
        skip_live_prepare=skip_live_prepare,
        measurement_id=MEASUREMENT_ID,
        build_marker_payload=build_retry2_attempt_marker_payload,
        assert_frozen_neighbors=_assert_frozen_neighbors,
    )


__all__ = [
    "MAX_HTTP_TURNS",
    "MAX_PROVIDER_CALLS",
    "MEASUREMENT_ID",
    "_assert_frozen_neighbors",
    "assert_retry2_live_artifacts_absent",
    "configure_process_env",
    "evaluate_summary",
    "evaluate_turn_gates",
    "pick_scope_ref",
    "pick_stage_ref",
    "prepare_retry2_live_run",
    "run_http_harness",
    "run_non_network_preflight",
    "validate_runtime_seams",
]
