"""Verifier-style live harness for A9R2 patient-scope planner eval."""

from __future__ import annotations

import subprocess
import types
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from contracts.planner_attempt import PlannerAttempt
from evals.v5 import a9r2_patient_scope_live_contract as _default_contract
from evals.v5.a9r2_patient_scope_live_scoring import (
    aggregate_call_results,
    evaluate_automated_verdict,
    evaluate_proposed_gates,
    map_automated_to_final_verdict,
    score_planner_call,
)
from evals.v5.fullcontext_response_eval_contract import (
    HarnessConfigError,
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
from session import mem_add_bot, mem_add_user, mem_reset

_REPO_ROOT = Path(__file__).resolve().parents[2]

PlannerFn = Callable[[str, str | None, str | None], PlannerAttempt]
LiveContract = types.ModuleType


def _resolve_contract(contract: LiveContract | None) -> LiveContract:
    return contract or _default_contract


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def _contract_requires_model_pin(contract: LiveContract) -> bool:
    return bool(getattr(contract, "REQUIRES_PLANNER_MODEL_PIN", False))


def _sid_prefix_for_contract(contract: LiveContract) -> str:
    measurement_id = str(getattr(contract, "MEASUREMENT_ID", "a9r2"))
    if measurement_id.startswith("a9r2d"):
        return "a9r2d"
    if measurement_id.startswith("a9r2c"):
        return "a9r2c"
    if measurement_id.startswith("a9r2b"):
        return "a9r2b"
    return "a9r2"


def configure_live_env(*, contract: LiveContract | None = None) -> None:
    """Pin planner model env for owner-approved patient-scope live attempt."""

    import os

    c = _resolve_contract(contract)
    os.environ["TURN_PLANNER_LLM_MODEL"] = c.OWNER_APPROVED_PLANNER_MODEL
    if _contract_requires_model_pin(c):
        from evals.v5.patient_scope_live_model_pin import assert_planner_model_pin_before_marker

        assert_planner_model_pin_before_marker(c.OWNER_APPROVED_PLANNER_MODEL)


def prepare_live_run(
    *,
    contract: LiveContract | None = None,
    attempt_marker_path: Path | None = None,
    call_ledger_path: Path | None = None,
    raw_path: Path | None = None,
    result_path: Path | None = None,
    manifest_path: Path | None = None,
    manual_review_path: Path | None = None,
    owner_override_attempt_marker: bool = False,
) -> None:
    c = _resolve_contract(contract)
    attempt_marker_path = attempt_marker_path or c.LIVE_ATTEMPT_MARKER_PATH
    call_ledger_path = call_ledger_path or c.LIVE_CALL_LEDGER_PATH
    raw_path = raw_path or c.LIVE_RAW_ARTIFACT_PATH
    result_path = result_path or c.LIVE_RESULT_ARTIFACT_PATH
    manifest_path = manifest_path or c.LIVE_MANIFEST_ARTIFACT_PATH
    manual_review_path = manual_review_path or c.LIVE_MANUAL_REVIEW_ARTIFACT_PATH
    if hasattr(c, "load_frozen_matrix_v3"):
        c.assert_matrix_v3_frozen()
        c.load_frozen_matrix_v3()
    else:
        c.load_frozen_matrix_v2()
    c.assert_attempt_marker_absent(
        attempt_marker_path,
        owner_override=owner_override_attempt_marker,
    )
    excluded = {
        attempt_marker_path.resolve(),
        call_ledger_path.resolve(),
        raw_path.resolve(),
        result_path.resolve(),
        manifest_path.resolve(),
        manual_review_path.resolve(),
    }
    using_custom_outputs = any(
        path.resolve() != default.resolve()
        for path, default in (
            (attempt_marker_path, c.LIVE_ATTEMPT_MARKER_PATH),
            (call_ledger_path, c.LIVE_CALL_LEDGER_PATH),
            (raw_path, c.LIVE_RAW_ARTIFACT_PATH),
            (result_path, c.LIVE_RESULT_ARTIFACT_PATH),
            (manifest_path, c.LIVE_MANIFEST_ARTIFACT_PATH),
            (manual_review_path, c.LIVE_MANUAL_REVIEW_ARTIFACT_PATH),
        )
    )
    if using_custom_outputs:
        excluded |= {path.resolve() for path in c.DEFAULT_LIVE_ARTIFACT_PATHS}
    c.assert_live_artifacts_absent(exclude_paths=excluded)
    marker_payload = c.build_attempt_marker_payload()
    if _contract_requires_model_pin(c):
        from evals.v5.patient_scope_live_model_pin import assert_planner_model_pin_before_marker

        provenance = assert_planner_model_pin_before_marker(c.OWNER_APPROVED_PLANNER_MODEL)
        marker_payload["model_provenance"] = provenance
    c.create_attempt_marker_exclusive(
        attempt_marker_path,
        marker_payload,
    )


def _execute_planner_call(
    *,
    planner_fn: PlannerFn,
    call_spec: dict[str, Any],
    sid: str,
    contract: LiveContract,
    attempt_marker_path: Path,
    call_ledger_path: Path,
) -> dict[str, Any]:
    call_id = str(call_spec["call_id"])
    contract.append_call_ledger_entry(
        call_ledger_path,
        {
            "event": "planner_call_started",
            "call_id": call_id,
            "question": call_spec["question"],
            "retry_count": contract.RETRY_COUNT_MAX,
        },
    )
    contract.record_provider_call_started(attempt_marker_path)
    attempt = planner_fn(call_spec["question"], sid, contract.CLIENT_ID)
    contract.append_call_ledger_entry(
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
    contract: LiveContract | None = None,
    attempt_marker_path: Path | None = None,
    call_ledger_path: Path | None = None,
    raw_path: Path | None = None,
    result_path: Path | None = None,
    manifest_path: Path | None = None,
    manual_review_path: Path | None = None,
    owner_override_attempt_marker: bool = False,
    record_dialog_history: bool = False,
) -> dict[str, Any]:
    c = _resolve_contract(contract)
    attempt_marker_path = attempt_marker_path or c.LIVE_ATTEMPT_MARKER_PATH
    call_ledger_path = call_ledger_path or c.LIVE_CALL_LEDGER_PATH
    raw_path = raw_path or c.LIVE_RAW_ARTIFACT_PATH
    result_path = result_path or c.LIVE_RESULT_ARTIFACT_PATH
    manifest_path = manifest_path or c.LIVE_MANIFEST_ARTIFACT_PATH
    manual_review_path = manual_review_path or c.LIVE_MANUAL_REVIEW_ARTIFACT_PATH

    prepare_live_run(
        contract=c,
        attempt_marker_path=attempt_marker_path,
        call_ledger_path=call_ledger_path,
        raw_path=raw_path,
        result_path=result_path,
        manifest_path=manifest_path,
        manual_review_path=manual_review_path,
        owner_override_attempt_marker=owner_override_attempt_marker,
    )
    load_matrix = (
        c.load_frozen_matrix_v3 if hasattr(c, "load_frozen_matrix_v3") else c.load_frozen_matrix_v2
    )
    matrix = load_matrix()
    call_specs = c.iter_live_planner_calls(matrix)
    sid = f"{_sid_prefix_for_contract(c)}-{uuid.uuid4().hex[:12]}"
    prior_session: SessionPatientFacts | None = None
    prev_case_id: str | None = None
    raw_calls: list[dict[str, Any]] = []
    scored_calls: list[dict[str, Any]] = []
    aborted = False
    abort_reason: str | None = None
    model_pin_required = _contract_requires_model_pin(c)
    provider_observed_models: list[str] = []
    model_provenance: dict[str, Any] | None = None
    if model_pin_required:
        from evals.v5.patient_scope_live_model_pin import (
            assert_planner_model_pin_before_marker,
            assert_provider_model_matches,
            build_model_provenance,
            make_model_tracked_planner,
        )

        model_provenance = assert_planner_model_pin_before_marker(c.OWNER_APPROVED_PLANNER_MODEL)
        planner_fn = make_model_tracked_planner(planner_fn, provider_observed_models)

    try:
        for index, call_spec in enumerate(call_specs, start=1):
            if index > c.MAX_PLANNER_CALLS:
                aborted = True
                abort_reason = "planner_call_budget_exceeded"
                break
            if call_spec["case_id"] != prev_case_id:
                if record_dialog_history:
                    mem_reset(sid)
                prior_session = None
                prev_case_id = call_spec["case_id"]
            execution = _execute_planner_call(
                planner_fn=planner_fn,
                call_spec=call_spec,
                sid=sid,
                contract=c,
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

            if model_pin_required and index == 1 and provider_observed_models:
                assert_provider_model_matches(
                    owner_requested_model=c.OWNER_APPROVED_PLANNER_MODEL,
                    configured_model=str(model_provenance["configured_model"]),
                    observed_model=provider_observed_models[0],
                )
                model_provenance = build_model_provenance(
                    owner_requested_model=c.OWNER_APPROVED_PLANNER_MODEL,
                    configured_model=str(model_provenance["configured_model"]),
                    provider_observed_models=provider_observed_models,
                )

            if record_dialog_history:
                mem_add_user(sid, call_spec["question"])
                mem_add_bot(sid, "Понял.")

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
        summary["retry_count"] = c.RETRY_COUNT_MAX
        proposed_gates = evaluate_proposed_gates(summary, gates=c.PROPOSED_GATES)
        automated_verdict = evaluate_automated_verdict(summary, gates=c.PROPOSED_GATES)
        final_verdict = map_automated_to_final_verdict(automated_verdict)
        ledger_ok = c.ledger_entries_balanced(call_ledger_path)

        raw_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": c.MEASUREMENT_ID,
                "matrix_blob": c.MATRIX_V3_BLOB if hasattr(c, "MATRIX_V3_BLOB") else c.MATRIX_V2_BLOB,
                **(
                    {
                        "model_provenance": build_model_provenance(
                            owner_requested_model=c.OWNER_APPROVED_PLANNER_MODEL,
                            configured_model=str(model_provenance["configured_model"]),
                            provider_observed_models=provider_observed_models,
                        )
                    }
                    if model_pin_required and model_provenance is not None
                    else {"planner_model": c.OWNER_APPROVED_PLANNER_MODEL}
                ),
                "calls": raw_calls,
                "aborted": aborted,
                "abort_reason": abort_reason,
            }
        )
        result_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": c.MEASUREMENT_ID,
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
                "measurement_id": c.MEASUREMENT_ID,
                "git_head": _git_head_commit(),
                "matrix_blob": c.MATRIX_V3_BLOB if hasattr(c, "MATRIX_V3_BLOB") else c.MATRIX_V2_BLOB,
                **(
                    {
                        "model_provenance": build_model_provenance(
                            owner_requested_model=c.OWNER_APPROVED_PLANNER_MODEL,
                            configured_model=str(model_provenance["configured_model"]),
                            provider_observed_models=provider_observed_models,
                        )
                    }
                    if model_pin_required and model_provenance is not None
                    else {"planner_model": c.OWNER_APPROVED_PLANNER_MODEL}
                ),
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
        manual_seed = c.build_manual_review_seed(automated_verdict=automated_verdict)  # type: ignore[arg-type]

        c.write_json_exclusive(raw_path, raw_artifact)
        c.write_json_exclusive(result_path, result_artifact)
        c.write_json_exclusive(manifest_path, manifest_artifact)
        c.write_json_exclusive(manual_review_path, manual_seed)

        c.finalize_attempt_marker(
            attempt_marker_path,
            status="completed" if not aborted else "aborted",
            automated_verdict=automated_verdict,  # type: ignore[arg-type]
        )
        return {
            "measurement_id": c.MEASUREMENT_ID,
            "summary": summary,
            "automated_verdict": automated_verdict,
            "final_verdict": final_verdict,
            "artifact_paths": [str(path) for path in c.DEFAULT_LIVE_ARTIFACT_PATHS],
            "ledger_sha256": sha256_file_hex(call_ledger_path),
        }
    except Exception as error:
        from evals.v5.patient_scope_live_model_pin import ProviderModelMismatchError, build_model_provenance

        if isinstance(error, ProviderModelMismatchError):
            aborted = True
            abort_reason = error.code
            if model_pin_required and model_provenance is not None:
                model_provenance = build_model_provenance(
                    owner_requested_model=c.OWNER_APPROVED_PLANNER_MODEL,
                    configured_model=str(model_provenance["configured_model"]),
                    provider_observed_models=provider_observed_models,
                )
            summary = aggregate_call_results(scored_calls) if scored_calls else {"planner_calls": 0}
            summary["retry_count"] = c.RETRY_COUNT_MAX
            proposed_gates = evaluate_proposed_gates(summary, gates=c.PROPOSED_GATES)
            automated_verdict = "AUTOMATED_FAIL"
            final_verdict = map_automated_to_final_verdict(automated_verdict)
            raw_artifact = prepare_json_artifact_payload(
                {
                    "measurement_id": c.MEASUREMENT_ID,
                    "matrix_blob": c.MATRIX_V3_BLOB if hasattr(c, "MATRIX_V3_BLOB") else c.MATRIX_V2_BLOB,
                    "model_provenance": model_provenance,
                    "calls": raw_calls,
                    "aborted": True,
                    "abort_reason": abort_reason,
                }
            )
            result_artifact = prepare_json_artifact_payload(
                {
                    "measurement_id": c.MEASUREMENT_ID,
                    "summary": summary,
                    "automated_verdict": automated_verdict,
                    "final_verdict": final_verdict,
                    "proposed_gates": proposed_gates,
                    "call_results": scored_calls,
                    "ledger_balanced": c.ledger_entries_balanced(call_ledger_path),
                    "authority_enabled": False,
                    "abort_reason": abort_reason,
                }
            )
            manifest_artifact = prepare_json_artifact_payload(
                {
                    "measurement_id": c.MEASUREMENT_ID,
                    "git_head": _git_head_commit(),
                    "matrix_blob": c.MATRIX_V3_BLOB if hasattr(c, "MATRIX_V3_BLOB") else c.MATRIX_V2_BLOB,
                    "model_provenance": model_provenance,
                    "planner_calls": summary.get("planner_calls", 0),
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
                    "abort_reason": abort_reason,
                }
            )
            manual_seed = c.build_manual_review_seed(automated_verdict=automated_verdict)  # type: ignore[arg-type]
            c.write_json_exclusive(raw_path, raw_artifact)
            c.write_json_exclusive(result_path, result_artifact)
            c.write_json_exclusive(manifest_path, manifest_artifact)
            c.write_json_exclusive(manual_review_path, manual_seed)
            c.finalize_attempt_marker(
                attempt_marker_path,
                status="aborted_model_mismatch",
                automated_verdict=automated_verdict,
            )
            raise HarnessConfigError(
                f"{c.MEASUREMENT_ID} aborted after provider model mismatch; "
                "retry requires new owner approval"
            ) from error
        c.finalize_attempt_marker(
            attempt_marker_path,
            status="aborted",
            automated_verdict="AUTOMATED_FAIL",
        )
        raise HarnessConfigError(
            f"{c.MEASUREMENT_ID} harness aborted after provider call start; "
            "retry requires new owner approval"
        ) from error


__all__ = [
    "configure_live_env",
    "prepare_live_run",
    "run_planner_harness",
]
