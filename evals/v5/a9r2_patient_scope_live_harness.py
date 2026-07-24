"""Verifier-style live harness for A9R2 patient-scope planner eval."""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from contracts.planner_attempt import PlannerAttempt
from evals.v5.a9r2_patient_scope_live_contract import (
    CLIENT_ID,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MATRIX_V2_BLOB,
    MAX_PLANNER_CALLS,
    MEASUREMENT_ID,
    OWNER_APPROVED_PLANNER_MODEL,
    RETRY_COUNT_MAX,
    assert_attempt_marker_absent,
    assert_live_artifacts_absent,
    append_call_ledger_entry,
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    iter_live_planner_calls,
    ledger_entries_balanced,
    load_frozen_matrix_v2,
    record_provider_call_started,
    write_json_exclusive,
)
from evals.v5.a9r2_patient_scope_live_scoring import (
    aggregate_call_results,
    evaluate_automated_verdict,
    evaluate_proposed_gates,
    map_automated_to_final_verdict,
    score_planner_call,
)
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)
from core.target_effective_scope import SessionPatientFacts
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
    simulate_session_patient_facts_after_turn,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame

_REPO_ROOT = Path(__file__).resolve().parents[2]

PlannerFn = Callable[[str, str | None, str | None], PlannerAttempt]


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def prepare_live_run(
    *,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    owner_override_attempt_marker: bool = False,
) -> None:
    load_frozen_matrix_v2()
    assert_attempt_marker_absent(
        attempt_marker_path,
        owner_override=owner_override_attempt_marker,
    )
    excluded = {attempt_marker_path.resolve()}
    assert_live_artifacts_absent(exclude_paths=excluded)
    create_attempt_marker_exclusive(
        attempt_marker_path,
        build_attempt_marker_payload(),
    )


def _execute_planner_call(
    *,
    planner_fn: PlannerFn,
    call_spec: dict[str, Any],
    sid: str,
    attempt_marker_path: Path,
    call_ledger_path: Path,
) -> dict[str, Any]:
    call_id = str(call_spec["call_id"])
    append_call_ledger_entry(
        call_ledger_path,
        {
            "event": "planner_call_started",
            "call_id": call_id,
            "question": call_spec["question"],
            "retry_count": RETRY_COUNT_MAX,
        },
    )
    record_provider_call_started(attempt_marker_path)
    attempt = planner_fn(call_spec["question"], sid, CLIENT_ID)
    append_call_ledger_entry(
        call_ledger_path,
        {
            "event": "planner_call_completed",
            "call_id": call_id,
            "planner_status": attempt.status,
            "has_frame": attempt.frame is not None,
        },
    )
    return {
        "call_id": call_id,
        "planner_status": attempt.status,
        "frame": attempt.frame,
        "raw_turn_plan": attempt.frame.model_dump(mode="json") if attempt.frame else None,
    }


def run_planner_harness(
    *,
    planner_fn: PlannerFn,
    live: bool = False,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    call_ledger_path: Path = LIVE_CALL_LEDGER_PATH,
    raw_path: Path = LIVE_RAW_ARTIFACT_PATH,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    manifest_path: Path = LIVE_MANIFEST_ARTIFACT_PATH,
    manual_review_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    owner_override_attempt_marker: bool = False,
) -> dict[str, Any]:
    if live:
        raise HarnessConfigError(
            "A9R2 live planner calls require separate owner GO after pre-live checkpoint"
        )

    prepare_live_run(
        attempt_marker_path=attempt_marker_path,
        owner_override_attempt_marker=owner_override_attempt_marker,
    )
    matrix = load_frozen_matrix_v2()
    call_specs = iter_live_planner_calls(matrix)
    sid = f"a9r2-{uuid.uuid4().hex[:12]}"
    prior_session: SessionPatientFacts | None = None
    raw_calls: list[dict[str, Any]] = []
    scored_calls: list[dict[str, Any]] = []
    aborted = False
    abort_reason: str | None = None

    try:
        for index, call_spec in enumerate(call_specs, start=1):
            if index > MAX_PLANNER_CALLS:
                aborted = True
                abort_reason = "planner_call_budget_exceeded"
                break
            execution = _execute_planner_call(
                planner_fn=planner_fn,
                call_spec=call_spec,
                sid=sid,
                attempt_marker_path=attempt_marker_path,
                call_ledger_path=call_ledger_path,
            )
            score = score_planner_call(
                frame=execution["frame"],
                planner_status=str(execution["planner_status"]),
                call_spec=call_spec,
                prior_session=prior_session,
                session_turn_count=index,
            )
            row = {
                **call_spec,
                "planner_status": execution["planner_status"],
                "score": score,
            }
            raw_calls.append(
                {
                    "call_id": call_spec["call_id"],
                    "question": call_spec["question"],
                    "planner_status": execution["planner_status"],
                    "raw_turn_plan": execution["raw_turn_plan"],
                }
            )
            scored_calls.append(row)

            if (
                not score.get("transport_provider_error")
                and execution["frame"] is not None
                and call_spec.get("session_write") in ("write_if_confident", "optional_if_confident")
            ):
                projected = project_patient_scope_from_turn_frame(execution["frame"])
                merged = merge_effective_scope_axes(
                    EffectiveScopeMergeInputs(
                        current_topic=call_spec["topic"],
                        session_turn_count=index,
                        session_facts=prior_session,
                        projected_turn_scope=projected,
                    )
                )
                sim = simulate_session_patient_facts_after_turn(
                    merged=merged,
                    prior=prior_session,
                    current_topic=call_spec["topic"],
                    session_turn_count=index,
                )
                if sim.wrote:
                    prior_session = sim.facts

        summary = aggregate_call_results(scored_calls)
        summary["retry_count"] = RETRY_COUNT_MAX
        proposed_gates = evaluate_proposed_gates(summary)
        automated_verdict = evaluate_automated_verdict(summary)
        final_verdict = map_automated_to_final_verdict(automated_verdict)
        ledger_ok = ledger_entries_balanced(call_ledger_path)

        raw_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": MEASUREMENT_ID,
                "matrix_blob": MATRIX_V2_BLOB,
                "planner_model": OWNER_APPROVED_PLANNER_MODEL,
                "calls": raw_calls,
                "aborted": aborted,
                "abort_reason": abort_reason,
            }
        )
        result_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": MEASUREMENT_ID,
                "summary": summary,
                "automated_verdict": automated_verdict,
                "final_verdict": final_verdict,
                "proposed_gates": proposed_gates,
                "call_results": scored_calls,
                "ledger_balanced": ledger_ok,
                "authority_enabled": False,
            }
        )
        manifest_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": MEASUREMENT_ID,
                "git_head": _git_head_commit(),
                "matrix_blob": MATRIX_V2_BLOB,
                "planner_model": OWNER_APPROVED_PLANNER_MODEL,
                "planner_calls": summary["planner_calls"],
                "artifact_paths": {
                    "raw": str(raw_path),
                    "result": str(result_path),
                    "manifest": str(manifest_path),
                    "manual_review": str(manual_review_path),
                    "attempt_marker": str(attempt_marker_path),
                    "call_ledger": str(call_ledger_path),
                },
                "automated_verdict": automated_verdict,
                "final_verdict": final_verdict,
            }
        )
        manual_seed = build_manual_review_seed(automated_verdict=automated_verdict)  # type: ignore[arg-type]

        write_json_exclusive(raw_path, raw_artifact)
        write_json_exclusive(result_path, result_artifact)
        write_json_exclusive(manifest_path, manifest_artifact)
        write_json_exclusive(manual_review_path, manual_seed)

        finalize_attempt_marker(
            attempt_marker_path,
            status="completed" if not aborted else "aborted",
            automated_verdict=automated_verdict,  # type: ignore[arg-type]
        )
        return {
            "measurement_id": MEASUREMENT_ID,
            "summary": summary,
            "automated_verdict": automated_verdict,
            "final_verdict": final_verdict,
            "artifact_paths": [str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS],
            "ledger_sha256": sha256_file_hex(call_ledger_path),
        }
    except Exception as error:
        finalize_attempt_marker(
            attempt_marker_path,
            status="aborted",
            automated_verdict="AUTOMATED_FAIL",
        )
        raise HarnessConfigError(
            "A9R2 harness aborted after provider call start; "
            "retry requires new owner approval"
        ) from error


__all__ = [
    "prepare_live_run",
    "run_planner_harness",
]
