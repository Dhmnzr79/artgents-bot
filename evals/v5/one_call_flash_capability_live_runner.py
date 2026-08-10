"""Windows-safe process-isolated LIVE runner for ONE_CALL Flash capability (Stage 3B)."""

from __future__ import annotations

import multiprocessing
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import llm as llm_module
from evals.v5.fullcontext_response_eval_contract import AttemptMarkerExistsError
from evals.v5.one_call_flash_capability_contract import (
    FROZEN_CAPABILITY_CASES,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_CALLS,
    MEASUREMENT_ID,
    MODEL_SNAPSHOT,
    PROPOSED_LIVE_ATTEMPT_ID,
    case_by_id,
)
from evals.v5.one_call_flash_capability_harness import (
    FakeProviderResponse,
    FakeProviderTransport,
    sample_offline_fake_responses,
)
from evals.v5.one_call_flash_capability_live_artifacts import (
    CapabilityArtifactPaths,
    CapabilityLiveCaseRecord,
    append_ledger_event,
    artifact_paths_for_attempt,
    create_attempt_marker_exclusive,
    write_json_atomic,
)
from evals.v5.one_call_flash_capability_live_transport import (
    CapabilityLiveTransportResult,
    default_live_transport,
    execute_live_capability_transport,
)
from evals.v5.one_call_flash_capability_plan import (
    cache_stable_prefix_sha256,
    excerpt_text,
    frozen_capability_plan_sha256,
)


class CapabilityLiveGovernanceError(RuntimeError):
    """LIVE gate/attempt governance failure before spawn or transport."""

    def __init__(self, code: str, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail!r}")


class CapabilityChildTimeoutError(RuntimeError):
    """Child process exceeded wall timeout and was terminated."""


_INFRASTRUCTURE_IPC_STATUSES = frozenset({"timeout", "error"})


def assert_live_governance(attempt_id: str) -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is None:
        raise CapabilityLiveGovernanceError("live_gate_closed")
    if attempt_id != LIVE_AUTHORIZED_ATTEMPT_ID:
        raise CapabilityLiveGovernanceError(
            "attempt_id_mismatch",
            {"requested": attempt_id, "authorized": LIVE_AUTHORIZED_ATTEMPT_ID},
        )


def build_attempt_marker_payload(attempt_id: str) -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "model_snapshot": MODEL_SNAPSHOT,
        "live_authorized_attempt_id": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "max_calls": MAX_CALLS,
        "frozen_plan_sha256": frozen_capability_plan_sha256(),
        "case_ids": [case.case_id for case in FROZEN_CAPABILITY_CASES],
        "max_retries_configured": llm_module.chat_client.max_retries,
        "status": "attempt_started",
    }


def _record_from_transport(
    case_id: str,
    case: Any,
    transport_result: CapabilityLiveTransportResult,
    *,
    stable_prefix_sha256: str | None = None,
    ledger_event: str,
) -> CapabilityLiveCaseRecord:
    return CapabilityLiveCaseRecord(
        case_id=case_id,
        outcome=transport_result.outcome,
        requested_model=case.requested_model,
        observed_model=transport_result.observed_model,
        provider_model_verified=(
            transport_result.observed_model == case.requested_model
            if transport_result.observed_model
            else False
        ),
        stream=case.stream,
        response_format_strategy=case.response_format_strategy,
        prompt_tokens=transport_result.prompt_tokens,
        completion_tokens=transport_result.completion_tokens,
        cached_tokens=transport_result.cached_tokens,
        transport_attempts=transport_result.transport_attempts,
        ttft_ms=transport_result.ttft_ms,
        total_ms=transport_result.total_ms,
        first_delta_excerpt=transport_result.first_delta_excerpt,
        response_excerpt=excerpt_text(transport_result.content),
        error_code=transport_result.error_code,
        provider_kind=transport_result.provider_kind,
        provider_region=transport_result.provider_region,
        stable_prefix_sha256=stable_prefix_sha256,
        ledger_event=ledger_event,
    )


def _error_record(
    case: Any,
    *,
    error_code: str,
    stable_prefix_sha256: str | None = None,
) -> CapabilityLiveCaseRecord:
    return CapabilityLiveCaseRecord(
        case_id=case.case_id,
        outcome="transport_error",
        requested_model=case.requested_model,
        observed_model=None,
        provider_model_verified=False,
        stream=case.stream,
        response_format_strategy=case.response_format_strategy,
        prompt_tokens=None,
        completion_tokens=None,
        cached_tokens=None,
        transport_attempts=1,
        ttft_ms=None,
        total_ms=0,
        first_delta_excerpt=None,
        response_excerpt=None,
        error_code=error_code,
        stable_prefix_sha256=stable_prefix_sha256,
        ledger_event="ERROR",
    )


def build_capability_conclusions(
    case_records: list[CapabilityLiveCaseRecord],
    *,
    child_cleanup_verified_all_executed_cases: bool,
    wall_timeout_occurred: bool,
    max_retries_zero_configured: bool,
) -> dict[str, bool]:
    by_id = {record.case_id: record for record in case_records}
    json_blocking = by_id.get("json_mode_blocking")
    json_streaming = by_id.get("json_mode_streaming")
    legacy_blocking = by_id.get("legacy_blocking")
    legacy_streaming = by_id.get("legacy_streaming")
    cache_repeat = by_id.get("cache_repeat")

    successes = [record for record in case_records if record.outcome == "supported"]
    exact_model_verified_all_successes = bool(successes) and all(
        record.provider_model_verified for record in successes
    )
    provider_responses = [
        record for record in case_records if record.ledger_event == "FINISH"
    ]
    no_retry_verified = (
        max_retries_zero_configured
        and bool(provider_responses)
        and all(record.transport_attempts == 1 for record in provider_responses)
    )

    return {
        "json_mode_blocking_supported": bool(
            json_blocking and json_blocking.outcome == "supported"
        ),
        "json_mode_streaming_supported": bool(
            json_streaming and json_streaming.outcome == "supported"
        ),
        "legacy_blocking_supported": bool(
            legacy_blocking and legacy_blocking.outcome == "supported"
        ),
        "legacy_streaming_supported": bool(
            legacy_streaming and legacy_streaming.outcome == "supported"
        ),
        "provider_cache_hit_observed": bool(
            cache_repeat
            and cache_repeat.cached_tokens is not None
            and cache_repeat.cached_tokens > 0
            and cache_repeat.outcome == "supported"
            and cache_repeat.provider_model_verified
        ),
        "exact_model_verified_all_successes": exact_model_verified_all_successes,
        "no_retry_verified": no_retry_verified,
        "child_cleanup_verified_all_executed_cases": child_cleanup_verified_all_executed_cases,
        "wall_timeout_occurred": wall_timeout_occurred,
    }


def _child_worker(job: dict[str, Any], conn: Any) -> None:
    try:
        case = case_by_id(job["case_id"])
        attempt_id = job["attempt_id"]
        if job.get("child_sleep_seconds"):
            time.sleep(float(job["child_sleep_seconds"]))
        counter: dict[str, int] | None = None
        if job.get("use_fake_transport"):
            responses = [
                FakeProviderResponse(**row) for row in job.get("fake_responses", [])
            ]
            fake_transport = FakeProviderTransport(responses=responses)
            fake_transport.set_case(case.case_id)
            transport_fn: Callable[..., Any] = fake_transport.chat_completions_create
            counter = fake_transport.attempts_per_case
        else:
            transport_fn = default_live_transport()
        result = execute_live_capability_transport(
            case,
            attempt_id=attempt_id,
            transport=transport_fn,
            transport_attempt_counter=counter,
            validate_endpoint=not job.get("use_fake_transport"),
        )
        conn.send({"status": "ok", "result": asdict(result)})
    except Exception as exc:  # noqa: BLE001
        conn.send(
            {
                "status": "error",
                "error": {"code": type(exc).__name__, "message": str(exc)},
            }
        )
    finally:
        conn.close()


def _cleanup_process(proc: multiprocessing.Process) -> bool:
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
    if proc.is_alive():
        proc.kill()
        proc.join()
    return not proc.is_alive()


def spawn_isolated_case(
    job: dict[str, Any],
    *,
    wall_timeout_seconds: float = 60.0,
) -> tuple[dict[str, Any], bool]:
    """Spawn one child process; return IPC payload and whether cleanup verified."""

    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_worker, args=(job, child_conn), daemon=False)
    proc.start()
    child_conn.close()

    ipc_payload: dict[str, Any] | None = None
    timed_out = False
    try:
        if parent_conn.poll(timeout=wall_timeout_seconds):
            ipc_payload = parent_conn.recv()
        else:
            timed_out = True
    finally:
        parent_conn.close()

    if timed_out:
        cleanup_verified = _cleanup_process(proc)
        return {
            "status": "timeout",
            "error": {
                "code": "CapabilityChildTimeoutError",
                "message": "wall_timeout",
            },
        }, cleanup_verified

    if ipc_payload is None:
        cleanup_verified = _cleanup_process(proc)
        return {
            "status": "error",
            "error": {
                "code": "ChildExitWithoutResult",
                "message": f"exitcode={proc.exitcode}",
            },
        }, cleanup_verified

    if proc.is_alive():
        proc.join(timeout=5)
    cleanup_verified = _cleanup_process(proc) if proc.is_alive() else True
    if not proc.is_alive():
        proc.join(timeout=0)
    return ipc_payload, cleanup_verified


def run_live_attempt(
    attempt_id: str,
    *,
    artifact_root: CapabilityArtifactPaths | None = None,
    artifacts_root: Path | None = None,
    wall_timeout_seconds: float = 60.0,
    use_fake_transport: bool = False,
    fake_responses: list[FakeProviderResponse] | None = None,
    child_sleep_seconds: float | None = None,
    hang_on_case_id: str | None = None,
) -> dict[str, Any]:
    """Execute frozen six-case LIVE plan with process isolation."""

    assert_live_governance(attempt_id)
    paths = artifact_root or artifact_paths_for_attempt(
        attempt_id,
        artifacts_root=artifacts_root,
    )
    if paths.attempt_json.exists():
        raise AttemptMarkerExistsError("ATTEMPT_MARKER_EXISTS")

    cache_prefix_sha = cache_stable_prefix_sha256(attempt_id)
    create_attempt_marker_exclusive(
        paths.attempt_json,
        build_attempt_marker_payload(attempt_id),
    )

    consumed_call_count = 0
    completed_call_count = 0
    case_records: list[CapabilityLiveCaseRecord] = []
    child_cleanup_verified_all = True
    wall_timeout_occurred = False
    aborted = False
    fake_payload = (
        [asdict(response) for response in fake_responses]
        if fake_responses is not None
        else None
    )
    default_fake = sample_offline_fake_responses()
    max_retries_zero = llm_module.chat_client.max_retries == 0

    raw_payload: dict[str, Any] = {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "model_snapshot": MODEL_SNAPSHOT,
        "frozen_plan_sha256": frozen_capability_plan_sha256(),
        "cache_stable_prefix_sha256": cache_prefix_sha,
        "consumed_call_count": 0,
        "completed_call_count": 0,
        "case_results": [],
        "status": "in_progress",
    }
    write_json_atomic(paths.raw_json, raw_payload)

    for case in FROZEN_CAPABILITY_CASES:
        if aborted or consumed_call_count >= MAX_CALLS:
            break

        prefix_sha = (
            cache_prefix_sha
            if case.case_id in ("cache_cold", "cache_repeat")
            else None
        )

        append_ledger_event(
            paths.calls_jsonl,
            event="START",
            case_id=case.case_id,
            attempt_id=attempt_id,
        )
        consumed_call_count += 1

        job: dict[str, Any] = {
            "case_id": case.case_id,
            "attempt_id": attempt_id,
            "use_fake_transport": use_fake_transport,
        }
        if use_fake_transport:
            index = consumed_call_count - 1
            payload = (
                fake_payload[index]
                if fake_payload is not None and index < len(fake_payload)
                else asdict(default_fake[index])
            )
            job["fake_responses"] = [payload]
        sleep_seconds = child_sleep_seconds
        if hang_on_case_id == case.case_id and sleep_seconds is None:
            sleep_seconds = 30.0
        if sleep_seconds is not None:
            job["child_sleep_seconds"] = sleep_seconds

        ipc_payload, cleanup_ok = spawn_isolated_case(
            job,
            wall_timeout_seconds=wall_timeout_seconds,
        )
        child_cleanup_verified_all = child_cleanup_verified_all and cleanup_ok

        infrastructure_failure = ipc_payload.get("status") in _INFRASTRUCTURE_IPC_STATUSES
        if ipc_payload.get("status") == "timeout":
            wall_timeout_occurred = True

        if infrastructure_failure:
            error = ipc_payload.get("error", {})
            record = _error_record(
                case,
                error_code=str(error.get("code", "infrastructure_failure")),
                stable_prefix_sha256=prefix_sha,
            )
            append_ledger_event(
                paths.calls_jsonl,
                event="ERROR",
                case_id=case.case_id,
                attempt_id=attempt_id,
                extra={"error_code": record.error_code},
            )
            case_records.append(record)
            aborted = True
        elif ipc_payload.get("status") == "ok":
            transport_result = CapabilityLiveTransportResult(**ipc_payload["result"])
            if transport_result.error_code is not None:
                record = _record_from_transport(
                    case.case_id,
                    case,
                    transport_result,
                    stable_prefix_sha256=prefix_sha,
                    ledger_event="ERROR",
                )
                append_ledger_event(
                    paths.calls_jsonl,
                    event="ERROR",
                    case_id=case.case_id,
                    attempt_id=attempt_id,
                    extra={
                        "error_code": record.error_code,
                        "outcome": record.outcome,
                    },
                )
            else:
                record = _record_from_transport(
                    case.case_id,
                    case,
                    transport_result,
                    stable_prefix_sha256=prefix_sha,
                    ledger_event="FINISH",
                )
                append_ledger_event(
                    paths.calls_jsonl,
                    event="FINISH",
                    case_id=case.case_id,
                    attempt_id=attempt_id,
                    extra={"outcome": record.outcome, "total_ms": record.total_ms},
                )
                completed_call_count += 1
            case_records.append(record)
        else:
            error = ipc_payload.get("error", {})
            record = _error_record(
                case,
                error_code=str(error.get("code", "ipc_error")),
                stable_prefix_sha256=prefix_sha,
            )
            append_ledger_event(
                paths.calls_jsonl,
                event="ERROR",
                case_id=case.case_id,
                attempt_id=attempt_id,
                extra={"error_code": record.error_code},
            )
            case_records.append(record)
            aborted = True

        raw_payload["consumed_call_count"] = consumed_call_count
        raw_payload["completed_call_count"] = completed_call_count
        raw_payload["case_results"] = [r.to_artifact_dict() for r in case_records]
        raw_payload["status"] = "aborted" if aborted else "in_progress"
        write_json_atomic(paths.raw_json, raw_payload)

        if aborted:
            break

    conclusions = build_capability_conclusions(
        case_records,
        child_cleanup_verified_all_executed_cases=child_cleanup_verified_all,
        wall_timeout_occurred=wall_timeout_occurred,
        max_retries_zero_configured=max_retries_zero,
    )
    json_mode_available_for_streaming_production = (
        conclusions["json_mode_blocking_supported"]
        and conclusions["json_mode_streaming_supported"]
    )
    final_status = "aborted" if aborted else "completed"
    result_payload = {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "model_snapshot": MODEL_SNAPSHOT,
        "requested_model": MODEL_SNAPSHOT,
        "frozen_plan_sha256": frozen_capability_plan_sha256(),
        "cache_stable_prefix_sha256": cache_prefix_sha,
        "consumed_call_count": consumed_call_count,
        "completed_call_count": completed_call_count,
        "spawned_child_count": len(case_records),
        "case_results": [record.to_artifact_dict() for record in case_records],
        **conclusions,
        "json_mode_available_for_streaming_production": json_mode_available_for_streaming_production,
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "status": final_status,
    }
    write_json_atomic(paths.result_json, result_payload)
    raw_payload["status"] = final_status
    write_json_atomic(paths.raw_json, raw_payload)
    return result_payload


def run_preflight_blocked(attempt_id: str) -> dict[str, Any]:
    """Gate-closed path: no spawn, no transport, durable blocked summary."""

    if LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        raise CapabilityLiveGovernanceError(
            "preflight_expected_gate_closed",
            LIVE_AUTHORIZED_ATTEMPT_ID,
        )
    return {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "status": "live_blocked",
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "consumed_call_count": 0,
        "completed_call_count": 0,
        "spawned_child_count": 0,
        "frozen_plan_sha256": frozen_capability_plan_sha256(),
        "reason": "live_gate_closed",
    }
