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
    fake_live_patient_text,
)
from evals.v5.arch_compare.arch_compare_live_contract import (
    CAPABILITY_PREFLIGHT_BUDGET,
    FAKE_LIVE_DISCLAIMER,
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
    run_mock_capability_preflight,
)
from evals.v5.arch_compare.arch_compare_live_schedule import (
    build_execution_schedule,
    config_for_job,
    scenario_for_id,
    turn_for_job,
)
from evals.v5.arch_compare.arch_compare_matrix import assert_frozen_matrix_unchanged, frozen_matrix_digest
from evals.v5.arch_compare.arch_compare_prompt_build import build_prompt_capture
from evals.v5.arch_compare.arch_compare_provider_payload import build_composer_provider_payload


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
