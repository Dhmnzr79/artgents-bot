"""LIVE runner for Stage 3C Speed Gate (one spawn child, fake or real transport)."""

from __future__ import annotations

import multiprocessing
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import config
import llm as llm_module
from evals.v5.fullcontext_response_eval_contract import AttemptMarkerExistsError
from evals.v5.one_call_stage3c_speed_gate_call_plan import (
    build_frozen_call_plan,
    prove_old_max_for_matrix_cases,
)
from evals.v5.one_call_stage3c_speed_gate_contract import (
    CLIENT_ID,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_PROVIDER_CALLS_LIVE,
    MAX_RETRIES,
    MEASUREMENT_ID,
    MODEL_SNAPSHOT,
    NEW_MAX_PROVIDER_CALLS_ADMIN,
    NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
    PROPOSED_LIVE_ATTEMPT_ID,
    SPEED_GATE_ENDPOINT,
    STAGE3C_GATE_CONTRACT_REL_PATH,
    STAGE3C_OFFLINE_BASELINE_COMMIT,
    ArmLabel,
    build_attempt_marker_payload,
)
from evals.v5.one_call_stage3c_speed_gate_fake_transport import SpeedGateFakeTransport
from evals.v5.one_call_stage3c_speed_gate_harness import (
    build_frozen_turn_plan,
    canned_answer_for_case,
    configure_arm_flags,
    evaluate_turn_quality,
    run_offline_dry_run,
    stable_prefix_sha256,
)
from evals.v5.one_call_stage3c_speed_gate_live_artifacts import (
    append_ledger_event,
    artifact_paths_for_attempt,
    create_attempt_marker_exclusive,
    ledger_events_balanced,
    write_json_atomic,
)
from evals.v5.one_call_stage3c_speed_gate_live_transport import (
    InstrumentedProviderCall,
    MeasurementProviderBudget,
    MeasurementProviderBudgetExceeded,
    SpeedGateLiveTransport,
    instrumented_call_to_record,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import (
    assert_frozen_matrix_unchanged,
    frozen_matrix_sha256,
)
from evals.v5.one_call_stage3c_speed_gate_patient_ttft import execute_stream_turn
from evals.v5.one_call_stage3c_speed_gate_speed_gate import evaluate_speed_gate
from session import mem_reset

_REPO_ROOT = Path(__file__).resolve().parents[2]

_FATAL_ATTEMPT_ERROR_CODES: frozenset[str] = frozenset(
    {
        "AuthenticationError",
        "PermissionDeniedError",
        "PermissionDenied",
        "InvalidAPIKeyError",
    }
)

_PLACEHOLDER_KEY_MARKERS = (
    "placeholder",
    "your-api-key",
    "sk-test",
    "sk-fake",
    "changeme",
)

_FULL_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class SpawnMeasurementOutcome:
    events: list[dict[str, Any]]
    cleanup_verified: bool
    timed_out: bool
    timeout_failure_kind: str | None
    worker_ready_received: bool


class SpeedGateLiveGovernanceError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def _git_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=_REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def _git_tracked_dirty_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def _git_diff_against_head(rel_path: str) -> str:
    return subprocess.check_output(
        ["git", "diff", "HEAD", "--", rel_path],
        cwd=_REPO_ROOT,
        text=True,
    )


def normalize_speed_gate_endpoint(url: str) -> str:
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise SpeedGateLiveGovernanceError("endpoint_mismatch", f"endpoint={raw}")
    if parsed.query or parsed.fragment:
        raise SpeedGateLiveGovernanceError(
            "endpoint_mismatch",
            f"endpoint_has_query_or_fragment={raw}",
        )
    if parsed.username or parsed.password:
        raise SpeedGateLiveGovernanceError(
            "endpoint_mismatch",
            f"endpoint_has_credentials={raw}",
        )
    path = parsed.path or ""
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def validate_expected_live_head(expected_live_head: str) -> str:
    value = str(expected_live_head or "").strip()
    if not value:
        raise SpeedGateLiveGovernanceError(
            "expected_live_head_missing",
            "stage3c_expected_live_head_missing",
        )
    if not _FULL_COMMIT_SHA_RE.match(value):
        raise SpeedGateLiveGovernanceError(
            "expected_live_head_invalid",
            f"expected_live_head={expected_live_head}",
        )
    return value


def _gate_authorization_diff_only(diff: str) -> bool:
    if not diff.strip():
        return True
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@", "diff ", "index ")):
            continue
        if line.startswith("-") or line.startswith("+"):
            if "LIVE_AUTHORIZED_ATTEMPT_ID" not in line:
                return False
    return True


def assert_tracked_code_clean() -> None:
    dirty_paths = _git_tracked_dirty_paths()
    if not dirty_paths:
        return
    gate_path = STAGE3C_GATE_CONTRACT_REL_PATH
    non_gate_dirty = [path for path in dirty_paths if path != gate_path]
    if non_gate_dirty:
        raise SpeedGateLiveGovernanceError(
            "tracked_code_dirty",
            f"dirty_paths={non_gate_dirty}",
        )
    diff = _git_diff_against_head(gate_path)
    if not _gate_authorization_diff_only(diff):
        raise SpeedGateLiveGovernanceError(
            "tracked_code_dirty",
            "gate_contract_diff_not_authorization_only",
        )


def _is_fatal_attempt_error(error_code: str | None) -> bool:
    if not error_code:
        return False
    if error_code in _FATAL_ATTEMPT_ERROR_CODES:
        return True
    lowered = error_code.lower()
    return (
        "authentication" in lowered
        or "permissiondenied" in lowered
        or "invalidapikey" in lowered
        or lowered == "accessdenied"
    )


def assert_live_governance(attempt_id: str) -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is None:
        raise SpeedGateLiveGovernanceError("live_gate_closed", "stage3c_live_gate_closed")
    if LIVE_AUTHORIZED_ATTEMPT_ID != attempt_id:
        raise SpeedGateLiveGovernanceError(
            "attempt_id_mismatch",
            f"stage3c_attempt_id_mismatch:{attempt_id}",
        )


def assert_live_preflight(
    attempt_id: str,
    *,
    paths: dict[str, Path],
    expected_live_head: str,
) -> tuple[str, str]:
    assert_live_governance(attempt_id)
    assert_frozen_matrix_unchanged()
    validated_expected = validate_expected_live_head(expected_live_head)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise SpeedGateLiveGovernanceError("ci_forbidden", "stage3c_ci_forbidden")
    if llm_module.chat_client.max_retries != MAX_RETRIES:
        raise SpeedGateLiveGovernanceError(
            "max_retries_nonzero",
            f"max_retries={llm_module.chat_client.max_retries}",
        )
    configured_endpoint = normalize_speed_gate_endpoint(str(config.CHAT_BASE_URL or ""))
    pinned_endpoint = normalize_speed_gate_endpoint(SPEED_GATE_ENDPOINT)
    if configured_endpoint != pinned_endpoint:
        raise SpeedGateLiveGovernanceError(
            "endpoint_mismatch",
            f"endpoint={configured_endpoint} expected={pinned_endpoint}",
        )
    api_key = str(config.CHAT_API_KEY or "").strip()
    if not api_key:
        raise SpeedGateLiveGovernanceError("api_key_missing", "stage3c_api_key_missing")
    lowered_key = api_key.lower()
    if any(marker in lowered_key for marker in _PLACEHOLDER_KEY_MARKERS):
        raise SpeedGateLiveGovernanceError("api_key_placeholder", "stage3c_api_key_placeholder")
    assert_tracked_code_clean()
    observed_live_head = _git_head_commit()
    if not _git_is_ancestor(STAGE3C_OFFLINE_BASELINE_COMMIT, observed_live_head):
        raise SpeedGateLiveGovernanceError(
            "offline_baseline_not_ancestor",
            (
                f"offline_baseline={STAGE3C_OFFLINE_BASELINE_COMMIT} "
                f"head={observed_live_head}"
            ),
        )
    if observed_live_head != validated_expected:
        raise SpeedGateLiveGovernanceError(
            "expected_live_head_mismatch",
            f"head={observed_live_head} expected={validated_expected}",
        )
    if paths["attempt_json"].exists():
        raise AttemptMarkerExistsError("ATTEMPT_MARKER_EXISTS")
    return observed_live_head, validated_expected


def run_dry_run_attempt(
    *,
    attempt_id: str = "stage3c_offline_dry_run",
    observed_live_head: str,
) -> dict[str, Any]:
    """Fake-transport dry-run via offline harness; no LIVE gate required."""

    paths = artifact_paths_for_attempt(attempt_id)
    if paths["attempt_json"].exists():
        raise RuntimeError(f"artifact already exists: {paths['attempt_json']}")

    matrix_sha = frozen_matrix_sha256()
    create_attempt_marker_exclusive(
        paths["attempt_json"],
        build_attempt_marker_payload(
            attempt_id=attempt_id,
            frozen_matrix_sha256=matrix_sha,
            stage3c_offline_baseline_commit=STAGE3C_OFFLINE_BASELINE_COMMIT,
            expected_live_head=observed_live_head,
            observed_live_head=observed_live_head,
        ),
    )
    append_ledger_event(
        paths["calls_jsonl"],
        event="START",
        case_id="dry_run",
        attempt_id=attempt_id,
    )

    from pytest import MonkeyPatch

    with MonkeyPatch.context() as monkeypatch:
        result = run_offline_dry_run(
            monkeypatch,
            attempt_id=attempt_id,
            write_artifacts=False,
        )

    paths["raw_json"].write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["result_json"].write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_ledger_event(
        paths["calls_jsonl"],
        event="FINISH",
        case_id="dry_run",
        attempt_id=attempt_id,
        extra={"verdict": result.get("speed_gate", {}).get("verdict")},
    )
    return result


def _cleanup_process(proc: multiprocessing.Process) -> bool:
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
    if proc.is_alive():
        proc.kill()
        proc.join()
    return not proc.is_alive()


def build_wrapped_real_create(
    underlying_create: Callable[..., Any],
    *,
    before_call: Callable[[], None] | None = None,
) -> Callable[..., Any]:
    """Wrap captured underlying transport once; never lookup llm_module after patch."""

    def wrapped(**kwargs: Any) -> Any:
        if before_call is not None:
            before_call()
        return underlying_create(**kwargs)

    return wrapped


def _turn_ledger_key(case_id: str, arm: str) -> tuple[str, str]:
    return case_id, arm


def _record_turn_timeout_ledger(
    *,
    state: dict[str, Any],
    paths: dict[str, Path],
    attempt_id: str,
    planned_turns: list[dict[str, object]],
    failure_kind: str,
) -> None:
    completed = int(state.get("completed_turns") or 0)
    current = state.get("current_turn")

    if failure_kind == "turn_wall_timeout" and current is not None:
        case_id = str(current.get("case_id") or "")
        arm = str(current.get("arm") or "")
    elif completed < len(planned_turns):
        expected = planned_turns[completed]
        case_id = str(expected["case_id"])
        arm = str(expected["arm"])
    else:
        return

    key = _turn_ledger_key(case_id, arm)
    if state.get("turn_ledger_open_key") != key:
        append_ledger_event(
            paths["turns_jsonl"],
            event="START",
            case_id=case_id,
            attempt_id=attempt_id,
            extra={"arm": arm, "source": "parent_timeout"},
        )
        state["turn_ledger_open_key"] = key

    if not state.get("turn_ledger_closed"):
        append_ledger_event(
            paths["turns_jsonl"],
            event="ERROR",
            case_id=case_id,
            attempt_id=attempt_id,
            extra={
                "arm": arm,
                "error_code": failure_kind,
                "failure_kind": failure_kind,
            },
        )
        state["turn_ledger_closed"] = True
        state["failure_kind"] = failure_kind

    state["current_turn"] = None
    state["current_case_id"] = case_id
    state["current_arm"] = arm


def _measurement_child_worker(job: dict[str, Any], conn: Any) -> None:
    try:
        _run_measurement_in_child(job, conn)
    except Exception as exc:  # noqa: BLE001
        conn.send(
            {
                "type": "measurement_error",
                "error_code": type(exc).__name__,
                "message": str(exc),
            }
        )
    finally:
        conn.close()


def _run_measurement_in_child(job: dict[str, Any], conn: Any) -> None:
    attempt_id = str(job["attempt_id"])
    use_fake = bool(job.get("use_fake_transport"))
    turns = list(job.get("turns") or [])
    hang_turn_index: int | None = job.get("hang_turn_index")
    hang_sleep_seconds = float(job.get("hang_sleep_seconds") or 30.0)
    hang_before_worker_ready = bool(job.get("hang_before_worker_ready"))
    bootstrap_sleep_seconds = job.get("bootstrap_sleep_seconds")

    import ingress_gate
    import app as app_module
    from core import sales_one_plus_live_backend, target_runtime_llm_backends, turn_planner_llm

    current_case_id = ""
    current_arm: ArmLabel = "OLD"

    def _on_provider_start(call: InstrumentedProviderCall) -> None:
        conn.send(
            _provider_event(
                "provider_start",
                call,
                attempt_id,
                case_id=current_case_id,
                arm=current_arm,
            )
        )

    def _on_provider_finish(call: InstrumentedProviderCall) -> None:
        conn.send(
            _provider_event(
                "provider_finish",
                call,
                attempt_id,
                case_id=current_case_id,
                arm=current_arm,
            )
        )

    def _on_provider_error(call: InstrumentedProviderCall) -> None:
        conn.send(
            _provider_event(
                "provider_error",
                call,
                attempt_id,
                case_id=current_case_id,
                arm=current_arm,
            )
        )

    fail_error = job.get("fail_first_provider_error")
    fail_once = bool(fail_error)

    def _maybe_fail() -> None:
        if fail_error == "AuthenticationError":
            AuthenticationError = type("AuthenticationError", (RuntimeError,), {})
            raise AuthenticationError(str(fail_error))
        nonlocal fail_once
        if fail_once and fail_error:
            fail_once = False
            raise RuntimeError(str(fail_error))

    underlying_create = llm_module.chat_completions_create
    wrapped_real_create = build_wrapped_real_create(underlying_create, before_call=_maybe_fail)

    budget = MeasurementProviderBudget()
    fake = SpeedGateFakeTransport(answer_text="placeholder")
    transport = SpeedGateLiveTransport(
        budget=budget,
        use_fake_transport=use_fake,
        fake_transport=fake,
        real_create=wrapped_real_create if not use_fake else None,
        on_provider_start=_on_provider_start,
        on_provider_finish=_on_provider_finish,
        on_provider_error=_on_provider_error,
    )

    measurement_aborted = False

    def _instrumented_create(**kwargs: Any) -> Any:
        nonlocal measurement_aborted
        if measurement_aborted:
            raise RuntimeError("measurement_aborted")
        try:
            _maybe_fail()
            return transport.chat_completions_create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if fail_error == "AuthenticationError" or _is_fatal_attempt_error(type(exc).__name__):
                conn.send(
                    {
                        "type": "measurement_error",
                        "error_code": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                measurement_aborted = True
            raise

    for module in (
        llm_module,
        ingress_gate,
        turn_planner_llm,
        target_runtime_llm_backends,
        sales_one_plus_live_backend,
    ):
        setattr(module, "chat_completions_create", _instrumented_create)

    client = app_module.app.test_client()
    prefix_sha = stable_prefix_sha256()

    if bootstrap_sleep_seconds is not None:
        time.sleep(float(bootstrap_sleep_seconds))

    if hang_before_worker_ready:
        time.sleep(hang_sleep_seconds)
        return

    conn.send(
        {
            "type": "worker_ready",
            "event": "worker_ready",
            "attempt_id": attempt_id,
        }
    )

    latency_runs: list[dict[str, Any]] = []
    admin_runs: list[dict[str, Any]] = []
    old_calls_by_case: dict[str, int] = {}

    for turn_index, turn in enumerate(turns):
        if measurement_aborted:
            break

        case_id = str(turn["case_id"])
        arm = str(turn["arm"])
        current_case_id = case_id
        current_arm = arm
        kind = str(turn["kind"])
        sid = str(turn["sid"])
        user_message = str(turn["user_message"])

        conn.send(
            {
                "type": "turn_start",
                "attempt_id": attempt_id,
                "case_id": case_id,
                "arm": arm,
                "kind": kind,
                "turn_index": turn_index,
            }
        )

        if hang_turn_index is not None and turn_index == hang_turn_index:
            time.sleep(hang_sleep_seconds)
            return

        fake.answer_text = canned_answer_for_case(case_id)
        transport.reset_turn_calls()
        configure_arm_flags(arm)
        mem_reset(sid)

        try:
            http_result = execute_stream_turn(
                client,
                sid=sid,
                client_id=CLIENT_ID,
                body={"q": user_message},
            )
            provider_count = transport.turn_call_count()
            quality = evaluate_turn_quality(
                case_id,
                arm=arm,
                http_result=http_result,
                provider_call_count=provider_count,
            )
            observed_models = [call.observed_model for call in transport.calls]
            record = {
                "case_id": case_id,
                "arm": arm,
                "kind": kind,
                "sid": sid,
                "latency_category": turn.get("latency_category"),
                "arm_order_index": turn.get("arm_order_index"),
                "requested_model": MODEL_SNAPSHOT if arm == "NEW" else None,
                "observed_models": observed_models,
                "provider_call_count": provider_count,
                "provider_calls": [instrumented_call_to_record(call) for call in transport.calls],
                "patient_ttft_ms": http_result.get("patient_ttft_ms"),
                "total_ms": http_result.get("total_ms"),
                "patient_text_kind": http_result.get("patient_text_kind"),
                "widget_payload_ready": http_result.get("widget_payload_ready"),
                "quality": quality,
                "stable_prefix_sha256": prefix_sha if arm == "NEW" else None,
            }
            if arm == "OLD" and kind == "latency":
                old_calls_by_case[case_id] = provider_count
            if kind == "admin":
                admin_runs.append(record)
            else:
                latency_runs.append(record)

            violation = _new_arm_budget_violation(arm=arm, kind=kind, provider_count=provider_count)
            if violation:
                conn.send(
                    {
                        "type": "turn_error",
                        "attempt_id": attempt_id,
                        "case_id": case_id,
                        "arm": arm,
                        "error_code": violation,
                        "record": record,
                    }
                )
                conn.send(
                    {
                        "type": "measurement_error",
                        "error_code": violation,
                        "message": violation,
                    }
                )
                return

            conn.send(
                {
                    "type": "turn_finish",
                    "attempt_id": attempt_id,
                    "case_id": case_id,
                    "arm": arm,
                    "record": record,
                    "consumed_provider_calls": budget.consumed,
                    "completed_provider_calls": budget.completed,
                }
            )
        except MeasurementProviderBudgetExceeded as exc:
            conn.send(
                {
                    "type": "turn_error",
                    "attempt_id": attempt_id,
                    "case_id": case_id,
                    "arm": arm,
                    "error_code": type(exc).__name__,
                }
            )
            conn.send(
                {
                    "type": "measurement_error",
                    "error_code": "MeasurementProviderBudgetExceeded",
                    "message": str(exc),
                }
            )
            return
        except Exception as exc:  # noqa: BLE001
            conn.send(
                {
                    "type": "turn_error",
                    "attempt_id": attempt_id,
                    "case_id": case_id,
                    "arm": arm,
                    "error_code": type(exc).__name__,
                }
            )
            if _is_fatal_attempt_error(type(exc).__name__):
                conn.send(
                    {
                        "type": "measurement_error",
                        "error_code": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                return

    peak_old, old_proved = prove_old_max_for_matrix_cases(old_calls_by_case)
    conn.send(
        {
            "type": "measurement_complete",
            "attempt_id": attempt_id,
            "latency_runs": latency_runs,
            "admin_runs": admin_runs,
            "consumed_provider_calls": budget.consumed,
            "completed_provider_calls": budget.completed,
            "stable_prefix_sha256": prefix_sha,
            "observed_old_peak_per_case": peak_old,
            "old_max_proved_offline": old_proved,
        }
    )


def _provider_event(
    event_type: str,
    call: InstrumentedProviderCall,
    attempt_id: str,
    *,
    case_id: str = "",
    arm: str = "",
) -> dict[str, Any]:
    return {
        "type": event_type,
        "attempt_id": attempt_id,
        "case_id": case_id,
        "arm": arm,
        "call_index": call.call_index,
        "call_source": call.call_source,
        "requested_model": call.requested_model,
        "observed_model": call.observed_model,
        "verified": call.verified,
        "stream": call.stream,
        "prompt_tokens": call.prompt_tokens,
        "completion_tokens": call.completion_tokens,
        "cached_tokens": call.cached_tokens,
        "provider_ttft_ms": call.provider_ttft_ms,
        "duration_ms": call.duration_ms,
        "outcome": call.outcome,
        "error_code": call.error_code,
    }


def _new_arm_budget_violation(*, arm: str, kind: str, provider_count: int) -> str | None:
    if arm != "NEW":
        return None
    if kind == "admin" and provider_count > NEW_MAX_PROVIDER_CALLS_ADMIN:
        return "new_admin_provider_calls_nonzero"
    if kind != "admin" and provider_count > NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT:
        return "new_free_text_more_than_one_call"
    return None


def spawn_measurement_worker(
    job: dict[str, Any],
    *,
    worker_startup_timeout_seconds: float = 60.0,
    turn_timeout_seconds: float = 120.0,
    attempt_wall_timeout_seconds: float = 600.0,
) -> SpawnMeasurementOutcome:
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_measurement_child_worker, args=(job, child_conn), daemon=False)
    proc.start()
    child_conn.close()

    events: list[dict[str, Any]] = []
    timed_out = False
    timeout_failure_kind: str | None = None
    worker_ready_received = False
    turn_deadline: float | None = None
    started = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            elapsed = now - started

            if elapsed >= attempt_wall_timeout_seconds:
                timed_out = True
                timeout_failure_kind = "attempt_wall_timeout"
                break

            if not worker_ready_received:
                if elapsed >= worker_startup_timeout_seconds:
                    timed_out = True
                    timeout_failure_kind = "worker_startup_timeout"
                    break
                poll_timeout = min(
                    worker_startup_timeout_seconds - elapsed,
                    attempt_wall_timeout_seconds - elapsed,
                    0.1,
                )
            else:
                if turn_deadline is not None and now >= turn_deadline:
                    timed_out = True
                    timeout_failure_kind = "turn_wall_timeout"
                    break
                poll_timeout = attempt_wall_timeout_seconds - elapsed
                if turn_deadline is not None:
                    poll_timeout = min(poll_timeout, turn_deadline - now)
                poll_timeout = max(0.01, min(poll_timeout, 1.0))

            if not proc.is_alive() and not parent_conn.poll():
                break

            if parent_conn.poll(timeout=poll_timeout):
                event = parent_conn.recv()
                events.append(event)
                event_type = str(event.get("type") or "")
                if event_type == "worker_ready":
                    worker_ready_received = True
                elif event_type == "turn_start":
                    turn_deadline = time.monotonic() + turn_timeout_seconds
                elif event_type in {"turn_finish", "turn_error"}:
                    turn_deadline = None
                elif event_type in {"measurement_complete", "measurement_error"}:
                    break
            else:
                continue
    finally:
        parent_conn.close()

    cleanup_verified = _cleanup_process(proc) if proc.is_alive() or timed_out else True
    if not proc.is_alive():
        proc.join(timeout=0)
    return SpawnMeasurementOutcome(
        events=events,
        cleanup_verified=cleanup_verified,
        timed_out=timed_out,
        timeout_failure_kind=timeout_failure_kind,
        worker_ready_received=worker_ready_received,
    )


def _build_speed_summary(
    latency_runs: list[dict[str, Any]],
    admin_runs: list[dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    warm_new_ttft = [
        int(row["patient_ttft_ms"])
        for row in latency_runs
        if row["arm"] == "NEW"
        and row.get("latency_category") == "warm"
        and row.get("patient_ttft_ms") is not None
    ]
    warm_old_ttft = [
        int(row["patient_ttft_ms"])
        for row in latency_runs
        if row["arm"] == "OLD"
        and row.get("latency_category") == "warm"
        and row.get("patient_ttft_ms") is not None
    ]
    warm_new_total = [
        int(row["total_ms"])
        for row in latency_runs
        if row["arm"] == "NEW" and row.get("latency_category") == "warm"
    ]
    warm_old_total = [
        int(row["total_ms"])
        for row in latency_runs
        if row["arm"] == "OLD" and row.get("latency_category") == "warm"
    ]
    all_quality = [row["quality"] for row in latency_runs] + [row["quality"] for row in admin_runs]
    quality_pass = all(item.get("pass") for item in all_quality)
    new_calls_ok = all(
        int(row["provider_call_count"]) <= 1
        for row in latency_runs
        if row["arm"] == "NEW"
    ) and all(int(row["provider_call_count"]) == 0 for row in admin_runs)

    summary = evaluate_speed_gate(
        warm_new_ttft_ms=warm_new_ttft,
        warm_old_ttft_ms=warm_old_ttft,
        warm_new_total_ms=warm_new_total,
        warm_old_total_ms=warm_old_total,
        new_provider_calls_ok=new_calls_ok,
        quality_pass=quality_pass,
    )
    if status != "completed":
        summary["verdict"] = "inconclusive"
        summary["speed_pass"] = False
    return summary


def _handle_ipc_event(
    event: dict[str, Any],
    *,
    state: dict[str, Any],
    paths: dict[str, Path],
    attempt_id: str,
    on_partial: Callable[[], None] | None = None,
) -> None:
    event_type = str(event.get("type") or event.get("event") or "")
    case_id = str(event.get("case_id") or "")
    arm = str(event.get("arm") or "")

    if event_type == "worker_ready":
        state["worker_ready"] = True
    elif event_type == "turn_start":
        state["current_turn"] = {"case_id": case_id, "arm": arm}
        key = _turn_ledger_key(case_id, arm)
        if state.get("turn_ledger_open_key") != key:
            append_ledger_event(
                paths["turns_jsonl"],
                event="START",
                case_id=case_id,
                attempt_id=attempt_id,
                extra={"arm": arm},
            )
            state["turn_ledger_open_key"] = key
        state["turn_ledger_closed"] = False
    elif event_type == "provider_start":
        state["consumed_provider_calls"] = int(state.get("consumed_provider_calls") or 0) + 1
        append_ledger_event(
            paths["calls_jsonl"],
            event="START",
            case_id=case_id or "provider",
            attempt_id=attempt_id,
            extra={
                "arm": arm,
                "call_index": event.get("call_index"),
                "call_source": event.get("call_source"),
                "requested_model": event.get("requested_model"),
            },
        )
    elif event_type == "provider_finish":
        append_ledger_event(
            paths["calls_jsonl"],
            event="FINISH",
            case_id=case_id or "provider",
            attempt_id=attempt_id,
            extra={
                "arm": arm,
                "call_index": event.get("call_index"),
                "observed_model": event.get("observed_model"),
                "duration_ms": event.get("duration_ms"),
                "provider_ttft_ms": event.get("provider_ttft_ms"),
            },
        )
        state["completed_provider_calls"] = int(state.get("completed_provider_calls") or 0) + 1
    elif event_type == "provider_error":
        append_ledger_event(
            paths["calls_jsonl"],
            event="ERROR",
            case_id=case_id or "provider",
            attempt_id=attempt_id,
            extra={
                "arm": arm,
                "call_index": event.get("call_index"),
                "error_code": event.get("error_code"),
            },
        )
    elif event_type == "turn_finish":
        record = dict(event.get("record") or {})
        if record.get("kind") == "admin":
            state.setdefault("admin_runs", []).append(record)
        else:
            state.setdefault("latency_runs", []).append(record)
        state["completed_turns"] = int(state.get("completed_turns") or 0) + 1
        state["consumed_provider_calls"] = event.get("consumed_provider_calls")
        state["completed_provider_calls"] = event.get("completed_provider_calls")
        append_ledger_event(
            paths["turns_jsonl"],
            event="FINISH",
            case_id=case_id,
            attempt_id=attempt_id,
            extra={"arm": arm},
        )
        state["current_turn"] = None
        state["turn_ledger_closed"] = True
        state["turn_ledger_open_key"] = None
    elif event_type == "turn_error":
        append_ledger_event(
            paths["turns_jsonl"],
            event="ERROR",
            case_id=case_id,
            attempt_id=attempt_id,
            extra={"arm": arm, "error_code": event.get("error_code")},
        )
        state["current_turn"] = None
        state["turn_ledger_closed"] = True
        state["turn_ledger_open_key"] = None
    elif event_type == "measurement_complete":
        state["latency_runs"] = list(event.get("latency_runs") or [])
        state["admin_runs"] = list(event.get("admin_runs") or [])
        state["consumed_provider_calls"] = event.get("consumed_provider_calls")
        state["completed_provider_calls"] = event.get("completed_provider_calls")
        state["stable_prefix_sha256"] = event.get("stable_prefix_sha256")
        state["observed_old_peak_per_case"] = event.get("observed_old_peak_per_case")
        state["old_max_proved_offline"] = event.get("old_max_proved_offline")
        state["status"] = "completed"
    elif event_type == "measurement_error":
        state["status"] = "error"
        state["failure_kind"] = event.get("error_code")
        state["failure_message"] = event.get("message")

    if on_partial is not None:
        on_partial()


def run_live_attempt(
    attempt_id: str,
    *,
    expected_live_head: str,
    artifact_root: dict[str, Path] | None = None,
    artifacts_root: Path | None = None,
    worker_startup_timeout_seconds: float = 60.0,
    turn_timeout_seconds: float = 120.0,
    attempt_wall_timeout_seconds: float = 600.0,
    wall_timeout_seconds: float | None = None,
    use_fake_transport: bool = False,
    hang_turn_index: int | None = None,
    hang_sleep_seconds: float = 30.0,
    fail_first_provider_error: str | None = None,
    hang_before_worker_ready: bool = False,
    bootstrap_sleep_seconds: float | None = None,
) -> dict[str, Any]:
    if wall_timeout_seconds is not None:
        attempt_wall_timeout_seconds = wall_timeout_seconds
    paths = artifact_root or artifact_paths_for_attempt(
        attempt_id,
        artifacts_root=artifacts_root,
    )
    observed_live_head, validated_expected = assert_live_preflight(
        attempt_id,
        paths=paths,
        expected_live_head=expected_live_head,
    )

    matrix_sha = frozen_matrix_sha256()
    create_attempt_marker_exclusive(
        paths["attempt_json"],
        build_attempt_marker_payload(
            attempt_id=attempt_id,
            frozen_matrix_sha256=matrix_sha,
            stage3c_offline_baseline_commit=STAGE3C_OFFLINE_BASELINE_COMMIT,
            expected_live_head=validated_expected,
            observed_live_head=observed_live_head,
        ),
    )

    call_plan = build_frozen_call_plan()
    turns = build_frozen_turn_plan()
    state: dict[str, Any] = {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "mode": "live_fake_transport" if use_fake_transport else "live",
        "model_snapshot": MODEL_SNAPSHOT,
        "frozen_matrix_sha256": matrix_sha,
        "stage3c_offline_baseline_commit": STAGE3C_OFFLINE_BASELINE_COMMIT,
        "expected_live_head": validated_expected,
        "observed_live_head": observed_live_head,
        "status": "in_progress",
        "spawned_child_count": 1,
        "completed_turns": 0,
        "consumed_provider_calls": 0,
        "completed_provider_calls": 0,
        "current_case_id": None,
        "current_arm": None,
        "latency_runs": [],
        "admin_runs": [],
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "turn_ledger_open_key": None,
        "turn_ledger_closed": False,
        "worker_ready": False,
    }
    turns_path = paths["turns_jsonl"]
    calls_path = paths["calls_jsonl"]

    def _write_partial() -> None:
        artifact_state = {k: v for k, v in state.items() if not str(k).startswith("_")}
        partial_result = _assemble_result_payload(
            state,
            call_plan=call_plan,
            turns_path=turns_path,
            calls_path=calls_path,
        )
        write_json_atomic(paths["raw_json"], artifact_state)
        write_json_atomic(paths["result_json"], partial_result)

    write_json_atomic(paths["raw_json"], {k: v for k, v in state.items() if not str(k).startswith("_")})

    job: dict[str, Any] = {
        "attempt_id": attempt_id,
        "use_fake_transport": use_fake_transport,
        "turns": turns,
        "hang_turn_index": hang_turn_index,
        "hang_sleep_seconds": hang_sleep_seconds,
        "fail_first_provider_error": fail_first_provider_error,
        "hang_before_worker_ready": hang_before_worker_ready,
        "bootstrap_sleep_seconds": bootstrap_sleep_seconds,
    }
    spawn_outcome = spawn_measurement_worker(
        job,
        worker_startup_timeout_seconds=worker_startup_timeout_seconds,
        turn_timeout_seconds=turn_timeout_seconds,
        attempt_wall_timeout_seconds=attempt_wall_timeout_seconds,
    )

    for event in spawn_outcome.events:
        state["current_case_id"] = event.get("case_id")
        state["current_arm"] = event.get("arm")
        _handle_ipc_event(
            event,
            state=state,
            paths=paths,
            attempt_id=attempt_id,
            on_partial=_write_partial,
        )

    if spawn_outcome.timed_out:
        failure_kind = spawn_outcome.timeout_failure_kind or "attempt_wall_timeout"
        _record_turn_timeout_ledger(
            state=state,
            paths=paths,
            attempt_id=attempt_id,
            planned_turns=turns,
            failure_kind=failure_kind,
        )
        state["status"] = "aborted"
        if failure_kind == "attempt_wall_timeout":
            state["wall_timeout_occurred"] = True
        _write_partial()
    elif state.get("status") == "in_progress":
        state["status"] = "aborted"

    state["child_cleanup_verified"] = spawn_outcome.cleanup_verified
    if spawn_outcome.worker_ready_received:
        state["worker_ready"] = True
    final_payload = _assemble_result_payload(
        state,
        call_plan=call_plan,
        turns_path=turns_path,
        calls_path=calls_path,
    )
    artifact_state = {k: v for k, v in state.items() if not str(k).startswith("_")}
    write_json_atomic(paths["raw_json"], artifact_state)
    write_json_atomic(paths["result_json"], final_payload)
    return final_payload


def _assemble_result_payload(
    state: dict[str, Any],
    *,
    call_plan: Any,
    turns_path: Path,
    calls_path: Path,
) -> dict[str, Any]:
    status = str(state.get("status") or "aborted")
    latency_runs = list(state.get("latency_runs") or [])
    admin_runs = list(state.get("admin_runs") or [])
    speed_gate = _build_speed_summary(latency_runs, admin_runs, status=status)
    payload: dict[str, Any] = {
        "measurement_id": state.get("measurement_id"),
        "attempt_id": state.get("attempt_id"),
        "mode": state.get("mode"),
        "model_snapshot": state.get("model_snapshot"),
        "frozen_matrix_sha256": state.get("frozen_matrix_sha256"),
        "stable_fullcontext_prefix_sha256": state.get("stable_prefix_sha256"),
        "stage3c_offline_baseline_commit": state.get("stage3c_offline_baseline_commit"),
        "expected_live_head": state.get("expected_live_head"),
        "observed_live_head": state.get("observed_live_head"),
        "status": status,
        "spawned_child_count": state.get("spawned_child_count", 0),
        "completed_turns": state.get("completed_turns", 0),
        "consumed_provider_calls": state.get("consumed_provider_calls", 0),
        "completed_provider_calls": state.get("completed_provider_calls", 0),
        "max_provider_calls_live": MAX_PROVIDER_CALLS_LIVE,
        "current_case_id": state.get("current_case_id"),
        "current_arm": state.get("current_arm"),
        "latency_runs": latency_runs,
        "admin_runs": admin_runs,
        "call_plan": {
            "old_max_per_turn": call_plan.old_max_per_turn,
            "new_max_per_free_text": call_plan.new_max_per_free_text,
            "new_max_admin": call_plan.new_max_admin,
            "max_provider_calls_live": call_plan.max_provider_calls_live,
            "observed_old_peak_per_case": state.get("observed_old_peak_per_case"),
            "old_max_proved_offline": state.get("old_max_proved_offline"),
            "derivation_notes": list(call_plan.derivation_notes),
        },
        "speed_gate": speed_gate,
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "child_cleanup_verified": state.get("child_cleanup_verified"),
        "ledger_balanced": {
            "turns": ledger_events_balanced(turns_path),
            "calls": ledger_events_balanced(calls_path),
        },
    }
    if state.get("wall_timeout_occurred"):
        payload["wall_timeout_occurred"] = True
    if state.get("worker_ready"):
        payload["worker_ready"] = True
    if state.get("failure_kind"):
        payload["failure_kind"] = state.get("failure_kind")
        payload["failure_message"] = state.get("failure_message")
    return payload


def run_preflight_blocked(attempt_id: str) -> dict[str, Any]:
    if LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        raise SpeedGateLiveGovernanceError(
            "preflight_expected_gate_closed",
            LIVE_AUTHORIZED_ATTEMPT_ID,
        )
    return {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "status": "live_blocked",
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "consumed_provider_calls": 0,
        "completed_provider_calls": 0,
        "spawned_child_count": 0,
        "frozen_matrix_sha256": frozen_matrix_sha256(),
        "max_provider_calls_live": MAX_PROVIDER_CALLS_LIVE,
        "reason": "live_gate_closed",
    }
