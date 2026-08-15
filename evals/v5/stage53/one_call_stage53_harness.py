"""Offline Stage 5.3 multiclient matrix harness via production POST /ask."""

from __future__ import annotations

import time
from typing import Any

import config

from core.one_call_envelope_protocol import dumps_production_envelope
from core.target_runtime_client_context import clear_target_runtime_client_context_cache
from evals.v5.stage53.one_call_stage53_contract import LIVE_AUTHORIZED_ATTEMPT_ID, MEASUREMENT_ID
from evals.v5.stage53.one_call_stage53_fake_transport import (
    Stage53FakeTransport,
    push_fake_envelope_queue,
    reset_fake_envelope_queue,
)
from evals.v5.stage53.one_call_stage53_matrix import (
    Stage53CaseSpec,
    Stage53TurnSpec,
    assert_frozen_matrix_unchanged,
    parse_case_specs,
)
from evals.v5.stage53.one_call_stage53_quality_gates import evaluate_turn_gates
from session import bind_session_client, mem_reset


class Stage53HarnessBlockedError(RuntimeError):
    """LIVE gate open while offline harness requested."""


def assert_offline_gate_closed() -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        raise Stage53HarnessBlockedError("stage53_offline_live_gate_open")


def _configure_clients(monkeypatch: Any) -> None:
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))


def _configure_sales_one_plus(monkeypatch: Any, enabled: bool = True) -> None:
    import app as app_module

    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", enabled)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", enabled)


def _install_fake_transport(monkeypatch: Any, transport: Stage53FakeTransport) -> None:
    import ingress_gate
    import llm as llm_module
    from core import sales_one_plus_live_backend, target_runtime_llm_backends, turn_planner_llm

    def _budget_aware_fake_create(*, model: str, **kwargs: Any) -> Any:
        from core.provider_call_budget import record_provider_call_outcome, reserve_provider_call

        started = time.monotonic()
        call_index = reserve_provider_call(
            model=model,
            source=kwargs.get("provider_call_source"),
        )
        try:
            response = transport.chat_completions_create(model=model, **kwargs)
        except Exception:
            record_provider_call_outcome(
                call_index=call_index,
                outcome="error",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        record_provider_call_outcome(
            call_index=call_index,
            outcome="ok",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return response

    for module in (
        llm_module,
        ingress_gate,
        turn_planner_llm,
        target_runtime_llm_backends,
        sales_one_plus_live_backend,
    ):
        monkeypatch.setattr(module, "chat_completions_create", _budget_aware_fake_create)


def _envelope_json_from_spec(fake_envelope: dict[str, object] | None) -> str | None:
    if fake_envelope is None:
        return None
    overrides = dict(fake_envelope)
    patient_text = overrides.pop("patient_text", "Тестовый ответ Stage 5.3.")
    return dumps_production_envelope(patient_text=str(patient_text), **overrides)


def _post_ask(
    client: Any,
    *,
    q: str,
    sid: str,
    client_id: str,
) -> dict[str, Any]:
    response = client.post(
        "/ask",
        json={"q": q, "sid": sid, "client_id": client_id},
    )
    payload = response.get_json()
    if not isinstance(payload, dict):
        raise RuntimeError("stage53_ask_response_not_object")
    answer = str(payload.get("answer") or "")
    meta = payload.get("meta") or {}
    service_route = str(meta.get("service_route") or "")
    return {
        "status_code": int(response.status_code),
        "answer": answer,
        "meta": meta,
        "service_route": service_route,
        "payload": payload,
    }


def _run_turn(
    client: Any,
    transport: Stage53FakeTransport,
    case: Stage53CaseSpec,
    turn: Stage53TurnSpec,
    *,
    sid: str,
    client_id: str,
) -> dict[str, Any]:
    turn_client = turn.client_id or case.client_id
    bind_session_client(turn_client)
    transport.reset_calls()
    reset_fake_envelope_queue()
    envelope_json = _envelope_json_from_spec(turn.fake_envelope)
    token = None
    if envelope_json is not None:
        token = push_fake_envelope_queue((envelope_json,))
    try:
        http_result = _post_ask(
            client,
            q=turn.user_message,
            sid=sid,
            client_id=client_id,
        )
    finally:
        reset_fake_envelope_queue(token)

    provider_calls = len(transport.calls)
    gates = evaluate_turn_gates(
        http_result["answer"],
        http_result["service_route"],
        provider_calls,
        turn,
    )
    return {
        "user_message": turn.user_message,
        "sid": sid,
        "client_id": client_id,
        "provider_calls": provider_calls,
        "answer": http_result["answer"],
        "service_route": http_result["service_route"],
        "gates": gates,
        "meta": http_result["meta"],
    }


def _sid_for_case(case: Stage53CaseSpec, turn: Stage53TurnSpec, turn_index: int) -> str:
    if turn.sid:
        return turn.sid
    if case.session_sid:
        return case.session_sid
    return f"stage53-{case.case_id}-{turn_index}"


def run_offline_matrix(monkeypatch: Any) -> dict[str, Any]:
    """Execute the frozen matrix through production /ask with fake provider transport."""

    assert_offline_gate_closed()
    assert_frozen_matrix_unchanged()

    _configure_clients(monkeypatch)
    _configure_sales_one_plus(monkeypatch, True)
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")

    import app as app_module

    transport = Stage53FakeTransport()
    _install_fake_transport(monkeypatch, transport)
    client = app_module.app.test_client()

    for case in parse_case_specs():
        if case.session_sid:
            bind_session_client(case.client_id)
            mem_reset(case.session_sid)

    case_results: list[dict[str, Any]] = []
    total_provider_calls = 0

    for case in parse_case_specs():
        if case.case_id == "s53_j01_mt_cache_isolation":
            clear_target_runtime_client_context_cache()

        turn_results: list[dict[str, Any]] = []
        session_sid = case.session_sid
        is_multi_turn = len(case.turns) > 1
        for turn_index, turn in enumerate(case.turns):
            sid = _sid_for_case(case, turn, turn_index)
            if session_sid and not turn.sid:
                sid = session_sid
            turn_client = turn.client_id or case.client_id
            if case.case_id == "s53_j01_mt_cache_isolation":
                if turn_index == 0:
                    bind_session_client(turn_client)
                    mem_reset(sid)
            elif not is_multi_turn or turn_index == 0:
                bind_session_client(turn_client)
                mem_reset(sid)
            turn_result = _run_turn(
                client,
                transport,
                case,
                turn,
                sid=sid,
                client_id=turn_client,
            )
            total_provider_calls += int(turn_result["provider_calls"])
            turn_results.append(turn_result)

        if case.case_id == "s53_j01_mt_cache_isolation":
            clear_target_runtime_client_context_cache()

        case_pass = all(row["gates"]["pass"] for row in turn_results)
        case_results.append(
            {
                "case_id": case.case_id,
                "client_id": case.client_id,
                "pass": case_pass,
                "turns": turn_results,
            }
        )

    all_pass = all(row["pass"] for row in case_results)
    return {
        "measurement_id": MEASUREMENT_ID,
        "mode": "offline_fake_transport",
        "pass": all_pass,
        "case_count": len(case_results),
        "provider_call_total": total_provider_calls,
        "cases": case_results,
    }
