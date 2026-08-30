"""Fake/offline runner for architecture comparison LIVE preparation."""

from __future__ import annotations

from typing import Any

from evals.v5.arch_compare.arch_compare_configs import assert_config_registry
from evals.v5.arch_compare.arch_compare_contract import MEASUREMENT_ID
from evals.v5.arch_compare.arch_compare_fake_transport import (
    ArchCompareFakeTransport,
    build_fake_envelope_json,
)
from evals.v5.arch_compare.arch_compare_harness import build_blind_variant_mapping
from evals.v5.arch_compare.arch_compare_live_capture import (
    build_dialog_history_for_session,
    build_structured_capture,
    build_structured_capture_for_provider_error,
    fake_live_patient_text,
)
from evals.v5.arch_compare.arch_compare_live_contract import (
    CAPABILITY_PREFLIGHT_BUDGET,
    FAKE_LIVE_DISCLAIMER,
    LIVE_MEASUREMENT_ID,
    LIVE_PREP_MEASUREMENT_ID,
    MEASUREMENT_PROVIDER_BUDGET,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
    ArchCompareCallBudgetPlan,
    build_config_registry_document,
    evaluate_live_readiness,
    frozen_config_digest,
)
from evals.v5.arch_compare.arch_compare_live_guard import (
    ArchCompareLiveGuardContext,
    assert_provider_budget,
    assert_single_provider_call_per_turn,
    validate_run_mode,
)
from evals.v5.arch_compare.arch_compare_live_preflight import (
    ArchComparePreflightStateMachine,
    run_capability_preflight,
    run_mock_capability_preflight,
)
from evals.v5.arch_compare.arch_compare_live_transport import ArchCompareLiveTransport
from evals.v5.arch_compare.arch_compare_live_schedule import (
    build_execution_schedule,
    config_for_job,
    scenario_for_id,
    turn_for_job,
)
from evals.v5.arch_compare.arch_compare_matrix import assert_frozen_matrix_unchanged, frozen_matrix_digest
from evals.v5.arch_compare.arch_compare_prompt_build import (
    build_composer_messages,
    build_prompt_capture,
)
from evals.v5.arch_compare.arch_compare_live_persistence import (
    ArchCompareArtifactWriteError,
    ArchCompareLiveArtifactStore,
    classify_provider_error,
)
from evals.v5.arch_compare.arch_compare_live_report import finalize_live_artifacts
from evals.v5.arch_compare.arch_compare_provider_payload import build_composer_provider_payload


class ArchCompareLiveRunnerError(RuntimeError):
    code: str
    partial_result: dict[str, Any] | None

    def __init__(
        self,
        code: str,
        message: str,
        *,
        partial_result: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.partial_result = partial_result


def _patient_text_from_envelope_json(*, envelope_json: str, turn, ctx) -> str:
    from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
    from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
    from core.one_call_envelope_protocol import parse_production_envelope_json
    from core.service_reference_catalog import ServiceReferenceCatalogSnapshot

    active_service_catalog = ActiveServiceCatalogSnapshot.from_bundle(ctx.bundle)
    service_reference_catalog = ServiceReferenceCatalogSnapshot.from_bundle(ctx.bundle)
    commercial_fact_catalog = CommercialFactCatalogSnapshot.from_bundle(ctx.bundle)
    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    return str(envelope.patient_text or "").strip()


def _execute_live_provider_turn(
    *,
    transport: ArchCompareLiveTransport,
    scenario_id: str,
    turn,
    config,
    prompt_capture,
    ctx,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    messages = build_composer_messages(prompt_capture=prompt_capture)
    payload = build_composer_provider_payload(
        config=config,
        messages=messages,
        stream=False,
    )
    response = transport.chat_completions_create(**payload)
    envelope_json = (response.choices[0].message.content or "").strip()
    if not envelope_json:
        raise ArchCompareLiveRunnerError("provider_empty_envelope", "empty provider response")
    patient_text = _patient_text_from_envelope_json(
        envelope_json=envelope_json,
        turn=turn,
        ctx=ctx,
    )
    assert_single_provider_call_per_turn(turn_calls=len(transport.calls))
    record = transport.records[-1].to_dict() if transport.records else {}
    from evals.v5.arch_compare.arch_compare_live_contract import (
        EVAL_REQUEST_TIMEOUT_SEC,
        PRODUCTION_SLA_REFERENCE_SEC,
    )

    latency_ms = record.get("latency_ms")
    record["request_timeout_sec"] = EVAL_REQUEST_TIMEOUT_SEC
    record["production_sla_sec"] = PRODUCTION_SLA_REFERENCE_SEC
    record["production_sla_breached"] = (
        latency_ms is not None and latency_ms > (PRODUCTION_SLA_REFERENCE_SEC * 1000)
    )
    return envelope_json, patient_text, payload, record
class ArchCompareTurnBudgetError(RuntimeError):
    pass


class ArchCompareProviderBudget:
    def __init__(self, *, max_calls: int) -> None:
        self.max_calls = max_calls
        self.consumed = 0

    def reserve(self) -> int:
        if self.consumed >= self.max_calls:
            raise ArchCompareTurnBudgetError("provider_budget_exhausted")
        self.consumed += 1
        return self.consumed


def build_call_budget_plan(schedule) -> ArchCompareCallBudgetPlan:
    return ArchCompareCallBudgetPlan(
        scenario_count=len({row.scenario_id for row in schedule.scenario_config_jobs}),
        turn_count=len({(row.scenario_id, row.turn_id) for row in schedule.turn_config_jobs}),
        config_count=4,
        scenario_config_jobs=len(schedule.scenario_config_jobs),
        turn_config_jobs=len(schedule.turn_config_jobs),
        provider_turn_jobs=schedule.provider_turn_jobs,
        code_only_turn_jobs=schedule.code_only_turn_jobs,
        capability_preflight_budget=CAPABILITY_PREFLIGHT_BUDGET,
        measurement_budget=MEASUREMENT_PROVIDER_BUDGET,
        total_authorized_budget=TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        max_provider_calls=TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        fake_provider_calls=0,
        optional_cache_probe_budget=4,
    )


def _execute_fake_provider_turn(
    *,
    transport: ArchCompareFakeTransport,
    scenario_id: str,
    turn,
    config,
    attempt_id: str,
) -> tuple[str, str, dict[str, Any]]:
    patient_text = fake_live_patient_text(
        attempt_id=attempt_id,
        scenario_id=scenario_id,
        turn_id=turn.turn_id,
        config_id=config.config_id,
    )
    envelope = build_fake_envelope_json(
        scenario_id=scenario_id,
        turn_id=turn.turn_id,
        route=turn.expected_route_class if turn.expected_route_class != "LOCAL" else "ANSWER",
        service_id=turn.expected_service_id,
        commercial_intent=turn.commercial_intent,
        promotion_scope=turn.promotion_scope,
        patient_text=patient_text,
    )
    transport.prepare_turn_envelopes((envelope,))
    outbound = build_composer_provider_payload(
        config=config,
        messages=({"role": "user", "content": turn.user_message},),
        stream=False,
    )
    response = transport.chat_completions_create(**outbound)
    content = response.choices[0].message.content
    if patient_text not in content:
        raise RuntimeError("fake_live_marker_missing_from_envelope")
    assert_single_provider_call_per_turn(turn_calls=len(transport.calls))
    return envelope, patient_text, outbound


def run_arch_compare_fake_full_path(
    *,
    attempt_id: str,
    guard_context: ArchCompareLiveGuardContext,
) -> dict[str, Any]:
    mode = validate_run_mode(guard_context)
    if mode != "fake":
        raise RuntimeError("fake_runner_requires_fake_mode")

    assert_config_registry()
    assert_frozen_matrix_unchanged()
    matrix_digest_value = frozen_matrix_digest()
    config_digest_value = frozen_config_digest()
    schedule = build_execution_schedule(attempt_id=attempt_id)
    budget_plan = build_call_budget_plan(schedule)

    preflight_state = ArchComparePreflightStateMachine()
    transport = ArchCompareFakeTransport()
    flash_preflight, plus_preflight = run_mock_capability_preflight(
        attempt_id=attempt_id,
        transport=transport,
        state=preflight_state,
    )
    if not preflight_state.can_start_measurement():
        raise RuntimeError("mock_preflight_failed")

    measurement_budget = ArchCompareProviderBudget(max_calls=budget_plan.measurement_budget)

    scenario_ids = tuple(dict.fromkeys(row.scenario_id for row in schedule.scenario_config_jobs))
    blind_mapping = build_blind_variant_mapping(attempt_id=attempt_id, scenario_ids=scenario_ids)

    structured_turns: list[dict[str, Any]] = []
    raw_turns: list[dict[str, Any]] = []
    session_histories: dict[str, dict[str, str]] = {}
    executed_jobs: set[tuple[str, str, str]] = set()
    outbound_payloads: list[dict[str, Any]] = []

    for job in schedule.turn_config_jobs:
        scenario = scenario_for_id(job.scenario_id)
        turn = turn_for_job(job)
        config = config_for_job(job)
        job_key = (job.scenario_id, job.turn_id, job.config_id)
        if job_key in executed_jobs:
            raise RuntimeError(f"duplicate_job:{job_key}")
        executed_jobs.add(job_key)

        prior_answers = session_histories.setdefault(job.session_id, {})
        dialog_before = build_dialog_history_for_session(
            scenario=scenario,
            turn=turn,
            prior_answers=prior_answers,
        )
        prompt_capture = build_prompt_capture(
            config=config,
            scenario=scenario,
            turn=turn,
            dialog_history=dialog_before,
        )

        envelope_json = None
        patient_text = None
        provider_calls = 0
        outbound_payload = None
        if turn.provider_turn:
            preflight_state.reserve_measurement()
            measurement_budget.reserve()
            provider_calls = 1
            envelope_json, patient_text, outbound_payload = _execute_fake_provider_turn(
                transport=transport,
                scenario_id=scenario.scenario_id,
                turn=turn,
                config=config,
                attempt_id=attempt_id,
            )
            outbound_payloads.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "turn_id": turn.turn_id,
                    "config_id": config.config_id,
                    "provider_model_id": config.provider_model_id,
                    "outbound": outbound_payload,
                }
            )
            transport.reset_calls()

        dialog_after = dialog_before
        if turn.provider_turn and patient_text:
            prior_answers[turn.turn_id] = patient_text
            dialog_after = build_dialog_history_for_session(
                scenario=scenario,
                turn=turn,
                prior_answers=prior_answers,
            )

        capture = build_structured_capture(
            attempt_id=attempt_id,
            scenario=scenario,
            turn=turn,
            config=config,
            session_id=job.session_id,
            dialog_history_before=dialog_before,
            dialog_history_after=dialog_after,
            envelope_json=envelope_json,
            patient_text=patient_text,
            prompt_capture=prompt_capture,
            provider_call_count=provider_calls,
        )
        structured_turns.append(capture.to_dict())
        raw_turns.append(
            {
                "attempt_id": attempt_id,
                "scenario_id": job.scenario_id,
                "turn_id": job.turn_id,
                "config_id": job.config_id,
                "session_id": job.session_id,
                "provider_turn": turn.provider_turn,
                "provider_model_id": config.provider_model_id if turn.provider_turn else None,
                "raw_model_envelope": envelope_json,
                "patient_text": patient_text,
                "outbound_payload": outbound_payload,
                "schedule_order_index": job.order_index,
            }
        )

    preflight_state.assert_total_budget()
    assert_provider_budget(
        consumed=preflight_state.preflight_consumed + preflight_state.measurement_consumed,
        max_calls=budget_plan.total_authorized_budget,
    )
    if preflight_state.preflight_consumed != CAPABILITY_PREFLIGHT_BUDGET:
        raise RuntimeError("preflight_budget_mismatch")
    if measurement_budget.consumed != budget_plan.measurement_budget:
        raise RuntimeError("measurement_budget_mismatch")
    if len(executed_jobs) != len(schedule.turn_config_jobs):
        raise RuntimeError("turn_job_execution_incomplete")

    readiness = evaluate_live_readiness(max_provider_calls=budget_plan.total_authorized_budget)
    preflight_state.readiness_state = "READY_FOR_AUTHORIZED_PREFLIGHT"

    return {
        "measurement_id": MEASUREMENT_ID,
        "live_prep_measurement_id": LIVE_PREP_MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "mode": "fake_full_path",
        "disclaimer": FAKE_LIVE_DISCLAIMER,
        "matrix_digest": matrix_digest_value,
        "config_digest": config_digest_value,
        "config_registry": build_config_registry_document(),
        "schedule": schedule.to_dict(),
        "call_budget": budget_plan.to_dict(),
        "preflight": {
            "flash": flash_preflight.to_dict(),
            "plus": plus_preflight.to_dict() if plus_preflight else None,
            "state_machine": preflight_state.to_dict(),
        },
        "provider_call_total": 0,
        "fake_transport_call_total": (
            preflight_state.preflight_consumed + preflight_state.measurement_consumed
        ),
        "outbound_payloads": outbound_payloads,
        "structured_turns": structured_turns,
        "raw_turns": raw_turns,
        "blind_variant_mapping": blind_mapping,
        "live_readiness": readiness.to_dict(),
        "head_sha": guard_context.head_sha,
    }


def _persist_preflight_failure(
    *,
    store: ArchCompareLiveArtifactStore,
    attempt_id: str,
    guard_context: ArchCompareLiveGuardContext,
    flash_preflight,
    plus_preflight,
    preflight_state: ArchComparePreflightStateMachine,
    matrix_digest_value: str,
    config_digest_value: str,
    budget_plan: ArchCompareCallBudgetPlan,
) -> dict[str, Any]:
    store.set_status("PREFLIGHT_FAILED")
    store.preflight = {
        "flash": flash_preflight.to_dict(),
        "plus": plus_preflight.to_dict() if plus_preflight else None,
        "state_machine": preflight_state.to_dict(),
    }
    partial = store.build_run_result(
        mode="live_preflight_failed",
        head_sha=guard_context.head_sha,
        config_registry=build_config_registry_document(),
    )
    partial.update(
        {
            "matrix_digest": matrix_digest_value,
            "config_digest": config_digest_value,
            "call_budget": budget_plan.to_dict(),
            "disclaimer": None,
            "measurement_errors": list(store.measurement_errors),
        }
    )
    store.write_error_report(
        {
            "attempt_id": attempt_id,
            "status": "PREFLIGHT_FAILED",
            "preflight": store.preflight,
            "provider_call_total": store.manifest.get("provider_call_total", 0),
        }
    )
    store.persist_core()
    finalize_live_artifacts(store=store, run_result=partial, stdout_log="status=PREFLIGHT_FAILED\n")
    return partial


def _handle_fatal_error(
    *,
    store: ArchCompareLiveArtifactStore,
    guard_context: ArchCompareLiveGuardContext,
    exc: BaseException,
) -> None:
    store.set_status("INCOMPLETE_FATAL")
    partial = store.build_run_result(
        mode="live_incomplete_fatal",
        head_sha=guard_context.head_sha,
        config_registry=build_config_registry_document(),
    )
    partial["fatal_error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    store.write_error_report(partial["fatal_error"])
    try:
        finalize_live_artifacts(store=store, run_result=partial, stdout_log="status=INCOMPLETE_FATAL\n")
    except Exception:
        store.persist_core()


def run_arch_compare_live_full_path(
    *,
    attempt_id: str,
    guard_context: ArchCompareLiveGuardContext,
    transport: ArchCompareLiveTransport,
) -> dict[str, Any]:
    mode = validate_run_mode(guard_context)
    if mode != "live":
        raise RuntimeError("live_runner_requires_live_mode")
    if guard_context.artifact_dir is None:
        raise ArchCompareLiveRunnerError("artifact_dir_missing", "artifact directory required for LIVE")

    assert_config_registry()
    assert_frozen_matrix_unchanged()
    matrix_digest_value = frozen_matrix_digest()
    config_digest_value = frozen_config_digest()
    schedule = build_execution_schedule(attempt_id=attempt_id)
    budget_plan = build_call_budget_plan(schedule)
    authorization_payload = (
        guard_context.authorization.to_dict() if guard_context.authorization is not None else None
    )
    store = ArchCompareLiveArtifactStore.initialize(
        artifact_dir=guard_context.artifact_dir,
        attempt_id=attempt_id,
        schedule=schedule.to_dict(),
        budget_plan=budget_plan.to_dict(),
        head_sha=guard_context.head_sha,
        matrix_digest=matrix_digest_value,
        config_digest=config_digest_value,
        measurement_id=LIVE_MEASUREMENT_ID,
        authorization=authorization_payload,
    )

    preflight_state = ArchComparePreflightStateMachine()
    try:
        flash_preflight, plus_preflight = run_capability_preflight(
            attempt_id=attempt_id,
            transport=transport,
            state=preflight_state,
            use_fake_queue=False,
            ledger=store.ledger,
            store=store,
        )
    except Exception as exc:
        _handle_fatal_error(store=store, guard_context=guard_context, exc=exc)
        raise ArchCompareLiveRunnerError(
            "preflight_provider_failed",
            str(exc),
            partial_result=store.build_run_result(
                mode="live_preflight_failed",
                head_sha=guard_context.head_sha,
                config_registry=build_config_registry_document(),
            ),
        ) from exc

    store.preflight = {
        "flash": flash_preflight.to_dict(),
        "plus": plus_preflight.to_dict() if plus_preflight else None,
        "state_machine": preflight_state.to_dict(),
    }
    if not preflight_state.can_start_measurement():
        partial = _persist_preflight_failure(
            store=store,
            attempt_id=attempt_id,
            guard_context=guard_context,
            flash_preflight=flash_preflight,
            plus_preflight=plus_preflight,
            preflight_state=preflight_state,
            matrix_digest_value=matrix_digest_value,
            config_digest_value=config_digest_value,
            budget_plan=budget_plan,
        )
        raise ArchCompareLiveRunnerError(
            "preflight_failed",
            "capability preflight failed",
            partial_result=partial,
        )

    store.set_status("MEASUREMENT_IN_PROGRESS")
    store.persist_core()
    scenario_ids = tuple(dict.fromkeys(row.scenario_id for row in schedule.scenario_config_jobs))
    store.blind_variant_mapping = build_blind_variant_mapping(attempt_id=attempt_id, scenario_ids=scenario_ids)

    from core.target_runtime_client_context import load_target_runtime_client_context
    from evals.v5.arch_compare.arch_compare_contract import CLIENT_ID

    runtime_ctx = load_target_runtime_client_context(CLIENT_ID)
    session_histories: dict[str, dict[str, str]] = {}
    executed_jobs: set[tuple[str, str, str]] = set()
    measurement_errors: list[dict[str, Any]] = []

    try:
        for job in schedule.turn_config_jobs:
            scenario = scenario_for_id(job.scenario_id)
            turn = turn_for_job(job)
            config = config_for_job(job)
            job_key = (job.scenario_id, job.turn_id, job.config_id)
            if job_key in executed_jobs:
                raise ArchCompareLiveRunnerError("duplicate_job", f"duplicate_job:{job_key}")
            executed_jobs.add(job_key)

            prior_answers = session_histories.setdefault(job.session_id, {})
            dialog_before = build_dialog_history_for_session(
                scenario=scenario,
                turn=turn,
                prior_answers=prior_answers,
            )
            prompt_capture = build_prompt_capture(
                config=config,
                scenario=scenario,
                turn=turn,
                dialog_history=dialog_before,
            )

            envelope_json = None
            patient_text = None
            provider_calls = 0
            outbound_payload = None
            token_metadata: dict[str, Any] = {}
            turn_error: dict[str, Any] | None = None

            if turn.provider_turn:
                preflight_state.reserve_measurement()
                provider_calls = 1
                ledger_entry = store.ledger.start_call(
                    phase="measurement",
                    scenario_id=scenario.scenario_id,
                    turn_id=turn.turn_id,
                    config_id=config.config_id,
                    model_id=config.provider_model_id,
                )
                store.persist_after_call_started(ledger_entry)
                try:
                    envelope_json, patient_text, outbound_payload, token_metadata = _execute_live_provider_turn(
                        transport=transport,
                        scenario_id=scenario.scenario_id,
                        turn=turn,
                        config=config,
                        prompt_capture=prompt_capture,
                        ctx=runtime_ctx,
                    )
                    record = transport.records[-1].to_dict() if transport.records else {}
                    store.ledger.complete_call(
                        ledger_entry,
                        latency_ms=record.get("latency_ms"),
                        usage={
                            "prompt_tokens": record.get("prompt_tokens"),
                            "completion_tokens": record.get("completion_tokens"),
                        },
                    )
                except Exception as exc:
                    error_type, error_code = classify_provider_error(exc)
                    record = transport.records[-1].to_dict() if transport.records else {}
                    store.ledger.fail_call(
                        ledger_entry,
                        error_type=error_type,
                        error_code=error_code,
                        latency_ms=record.get("latency_ms"),
                    )
                    turn_error = {
                        "scenario_id": scenario.scenario_id,
                        "turn_id": turn.turn_id,
                        "config_id": config.config_id,
                        "error_type": error_type,
                        "error_code": error_code,
                        "message": str(exc),
                    }
                    measurement_errors.append(turn_error)
                    store.record_measurement_error(turn_error)
                    token_metadata = {
                        "request_timeout_sec": config.inference_settings.timeout_sec,
                        "production_sla_sec": 20,
                        "production_sla_breached": None,
                        "provider_error": error_code,
                    }
                finally:
                    transport.reset_calls()
                    store.persist_core()

            dialog_after = dialog_before
            if turn.provider_turn and patient_text:
                prior_answers[turn.turn_id] = patient_text
                dialog_after = build_dialog_history_for_session(
                    scenario=scenario,
                    turn=turn,
                    prior_answers=prior_answers,
                )

            if turn_error is not None:
                capture = build_structured_capture_for_provider_error(
                    attempt_id=attempt_id,
                    scenario=scenario,
                    turn=turn,
                    config=config,
                    session_id=job.session_id,
                    dialog_history_before=dialog_before,
                    prompt_capture=prompt_capture,
                    provider_call_count=provider_calls,
                    error_code=str(turn_error["error_code"]),
                    error_type=str(turn_error["error_type"]),
                    token_metadata=token_metadata,
                )
            else:
                capture = build_structured_capture(
                    attempt_id=attempt_id,
                    scenario=scenario,
                    turn=turn,
                    config=config,
                    session_id=job.session_id,
                    dialog_history_before=dialog_before,
                    dialog_history_after=dialog_after,
                    envelope_json=envelope_json,
                    patient_text=patient_text,
                    prompt_capture=prompt_capture,
                    provider_call_count=provider_calls,
                    token_metadata=token_metadata,
                )

            raw_turn = {
                "attempt_id": attempt_id,
                "scenario_id": job.scenario_id,
                "turn_id": job.turn_id,
                "config_id": job.config_id,
                "session_id": job.session_id,
                "provider_turn": turn.provider_turn,
                "provider_model_id": config.provider_model_id if turn.provider_turn else None,
                "raw_model_envelope": envelope_json,
                "patient_text": patient_text,
                "outbound_payload": outbound_payload,
                "token_metadata": token_metadata,
                "schedule_order_index": job.order_index,
                "turn_error": turn_error,
            }
            store.append_turn(raw_turn=raw_turn, structured_turn=capture.to_dict())

        preflight_state.assert_total_budget()
        assert_provider_budget(
            consumed=store.ledger.consumed_calls,
            max_calls=budget_plan.total_authorized_budget,
        )
        if len(executed_jobs) != len(schedule.turn_config_jobs):
            raise ArchCompareLiveRunnerError("turn_job_execution_incomplete", "incomplete schedule execution")

        final_status = (
            "MEASUREMENT_COMPLETE_WITH_ERRORS" if measurement_errors else "MEASUREMENT_COMPLETE"
        )
        store.set_status(final_status)
        result = store.build_run_result(
            mode="live_full_path",
            head_sha=guard_context.head_sha,
            config_registry=build_config_registry_document(),
        )
        result.update(
            {
                "matrix_digest": matrix_digest_value,
                "config_digest": config_digest_value,
                "disclaimer": None,
                "measurement_errors": measurement_errors,
                "status": final_status,
                "blind_variant_mapping": store.blind_variant_mapping,
                "preflight": store.preflight,
            }
        )
        finalize_live_artifacts(
            store=store,
            run_result=result,
            stdout_log=f"mode=live_full_path status={final_status}\n",
        )
        result["artifacts_finalized"] = True
        return result
    except ArchCompareArtifactWriteError as exc:
        _handle_fatal_error(store=store, guard_context=guard_context, exc=exc)
        raise ArchCompareLiveRunnerError(
            "incomplete_fatal",
            str(exc),
            partial_result=store.build_run_result(
                mode="live_incomplete_fatal",
                head_sha=guard_context.head_sha,
                config_registry=build_config_registry_document(),
            ),
        ) from exc
    except ArchCompareLiveRunnerError as exc:
        _handle_fatal_error(store=store, guard_context=guard_context, exc=exc)
        raise
    except Exception as exc:
        _handle_fatal_error(store=store, guard_context=guard_context, exc=exc)
        raise ArchCompareLiveRunnerError(
            "incomplete_fatal",
            str(exc),
            partial_result=store.build_run_result(
                mode="live_incomplete_fatal",
                head_sha=guard_context.head_sha,
                config_registry=build_config_registry_document(),
            ),
        ) from exc
    finally:
        store.persist_core()
