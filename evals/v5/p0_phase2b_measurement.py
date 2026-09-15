"""P0 Phase 2B live measurement — one provider stream call per row, eval-only."""

from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any

import config

from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import (
    OneCallEnvelopeProtocolError,
    parse_production_envelope_json,
)
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.provider_call_budget import http_provider_budget_scope
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_runtime_client_context import load_target_runtime_client_context
from core.turn_timing import cached_tokens_from_usage
from evals.v5.one_call_stage3c_speed_gate_quality_rules import (
    matches_forbidden_computed_total,
    matches_forbidden_term,
)
from evals.v5.p0_phase2b_contract import (
    CANDIDATE_MODEL_ID,
    CONTROL_MODEL_ID,
    FROZEN_PHASE2B_CASES,
    MEASUREMENT_ID,
    Phase2BCase,
    assert_call_plan_within_budget,
    build_call_plan,
)
from evals.v5.p0_phase2b_stream_probe import PatientTextStreamProbe
from session import bind_session_client, mem_add_bot, mem_add_user, mem_reset


class InstrumentedLiveBackend(SalesOnePlusLiveBackend):
    def __init__(self, *, model: str) -> None:
        super().__init__(model=model)
        self.probe = PatientTextStreamProbe()
        self.request_started_at = 0.0
        self.stream_completed_at: float | None = None
        self.first_raw_chunk_at: float | None = None
        self.envelope_validated_at: float | None = None

    def generate_stream(self, invocation, on_raw_delta, /) -> None:
        self.probe = PatientTextStreamProbe()
        self.request_started_at = time.monotonic()
        self.first_raw_chunk_at = None
        self.stream_completed_at = None
        self.envelope_validated_at = None

        def _wrapped(delta: str) -> None:
            now = time.monotonic()
            if self.first_raw_chunk_at is None and delta:
                self.first_raw_chunk_at = now
            self.probe.feed(delta, now)
            on_raw_delta(delta)

        super().generate_stream(invocation, _wrapped)
        self.stream_completed_at = time.monotonic()
        self.probe.finalize_timing(self.stream_completed_at)


@dataclass(frozen=True, slots=True)
class Phase2BRowResult:
    model_id: str
    case_id: str
    client_id: str
    attempt_index: int
    observed_model: str | None
    timings_ms: dict[str, int | None]
    patient_text_chunk_count: int
    two_plus_patient_text_chunks: bool
    early_patient_text_matches_final_answer: bool | None
    presentation_changed_text: bool | None
    envelope_route: str | None
    commercial_intent: str | None
    schema_ok: bool
    quality_issues: tuple[str, ...]
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    final_answer_excerpt: str | None
    failure_kind: str | None


from evals.v5.p0_phase2b_artifacts import baseline_report, persist_artifact

def _case_by_id(case_id: str) -> Phase2BCase | None:
    if case_id.startswith("canary_"):
        return Phase2BCase(
            case_id=case_id,
            client_id="demo",
            user_message="Есть ли у клиники парковка для пациентов?",
            category="faq_safe",
            repeat_eligible=False,
            critical_terms=("парков",),
            expected_route="ANSWER",
        )
    for row in FROZEN_PHASE2B_CASES:
        if row.case_id == case_id:
            return row
    return None


def _ms(start: float | None, end: float | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start) * 1000))


def _parse_envelope_for_client(client_id: str, raw_json: str):
    context = load_target_runtime_client_context(client_id)
    active = ActiveServiceCatalogSnapshot.from_bundle(context.bundle)
    refs = ServiceReferenceCatalogSnapshot.from_bundle(context.bundle)
    commercial = CommercialFactCatalogSnapshot.from_exact_catalog(
        ExactCommercialCatalogSnapshot.from_bundle(context.bundle)
    )
    return parse_production_envelope_json(
        raw_json,
        active_service_catalog=active,
        service_reference_catalog=refs,
        commercial_fact_catalog=commercial,
    )


def _quality_check(case: Phase2BCase, *, route: str | None, answer: str) -> tuple[str, ...]:
    issues: list[str] = []
    lowered = answer.lower()
    if case.expected_route and route and route.upper() != case.expected_route:
        issues.append(f"route_mismatch:{route}!={case.expected_route}")
    for term in case.critical_terms:
        if term.lower() not in lowered:
            issues.append(f"missing_critical:{term}")
    for term in case.forbidden_terms:
        if matches_forbidden_term(term, answer):
            issues.append(f"forbidden:{term}")
    if matches_forbidden_computed_total(answer):
        issues.append("forbidden_computed_total")
    return tuple(issues)


def run_single_measurement(
    *,
    model_id: str,
    case_id: str,
    client_id: str,
    attempt_index: int,
    flask_app: Any,
) -> Phase2BRowResult:
    case = _case_by_id(case_id)
    if case is None:
        raise ValueError(f"unknown_case:{case_id}")

    allowed = set(config.ALLOWED_CLIENTS)
    if client_id not in allowed:
        config.ALLOWED_CLIENTS = frozenset(set(allowed) | {client_id})

    sid = f"p0-2b-{case_id}-{model_id.replace('.', '_')}-a{attempt_index}"
    bind_session_client(client_id)
    mem_reset(sid)
    for prior_user, prior_client in case.session_prefix:
        bind_session_client(prior_client)
        mem_add_user(sid, prior_user)
        mem_add_bot(sid, "[synthetic prior assistant turn for follow-up eval]")
    bind_session_client(client_id)

    backend = InstrumentedLiveBackend(model=model_id)
    started = time.monotonic()

    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": case.user_message, "sid": sid, "client_id": client_id},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": started}
        with http_provider_budget_scope(request_id=f"p0-2b-{sid}", sales_one_plus_on=True):
            outcome = run_sales_fast_widget_turn(
                client_id=client_id,
                sid=sid,
                user_message=case.user_message,
                backend=backend,
                on_delta=lambda _: None,
            )

    ui_ready_at = time.monotonic()
    widget = outcome.widget.payload or {}
    final_answer = str(widget.get("answer") or "")

    envelope_route: str | None = None
    commercial_intent: str | None = None
    schema_ok = True
    envelope_patient: str | None = None
    try:
        envelope = _parse_envelope_for_client(client_id, backend.probe.raw_json)
        envelope_route = envelope.route
        commercial_intent = envelope.commercial_intent
        envelope_patient = envelope.patient_text
        backend.envelope_validated_at = time.monotonic()
    except OneCallEnvelopeProtocolError as exc:
        schema_ok = False
        envelope_route = f"protocol_error:{exc.code}"

    streamed = backend.probe.streamed_patient_text
    early_match: bool | None = None
    presentation_changed: bool | None = None
    if envelope_patient and streamed:
        early_match = streamed == envelope_patient
    if envelope_patient and final_answer:
        presentation_changed = envelope_patient.strip() != final_answer.strip()

    quality_issues = _quality_check(case, route=envelope_route, answer=final_answer)
    if outcome.failure_kind:
        schema_ok = False
        quality_issues = (*quality_issues, f"failure:{outcome.failure_kind}")

    obs = backend.last_observability
    observed_model = obs.observed_model if obs is not None else None

    t0 = backend.request_started_at or started
    t_first_raw = backend.first_raw_chunk_at or backend.probe.first_raw_chunk_at
    t_pt_start = backend.probe.patient_text_value_start_at
    t_pt_end = backend.probe.patient_text_value_end_at
    t_stream_done = backend.stream_completed_at
    t_env = backend.envelope_validated_at or t_stream_done
    t_ui = ui_ready_at

    current_visible = _ms(t0, t_ui)
    hypo_ttft = _ms(t0, t_pt_start)
    gain = (current_visible - hypo_ttft) if current_visible is not None and hypo_ttft is not None else None

    timings = {
        "request_started": 0,
        "first_raw_chunk": _ms(t0, t_first_raw),
        "patient_text_value_start": hypo_ttft,
        "patient_text_value_end": _ms(t0, t_pt_end),
        "provider_stream_completed": _ms(t0, t_stream_done),
        "envelope_validated": _ms(t0, t_env),
        "presentation_completed": current_visible,
        "ui_answer_ready": current_visible,
        "provider_ttft": _ms(t0, t_first_raw),
        "current_time_to_visible_answer": current_visible,
        "hypothetical_safe_patient_ttft": hypo_ttft,
        "potential_streaming_gain_ms": gain,
        "total_latency": current_visible,
    }
    return Phase2BRowResult(
        model_id=model_id,
        case_id=case_id,
        client_id=client_id,
        attempt_index=attempt_index,
        observed_model=observed_model,
        timings_ms=timings,
        patient_text_chunk_count=backend.probe.patient_text_chunk_count,
        two_plus_patient_text_chunks=backend.probe.two_plus_value_chunks,
        early_patient_text_matches_final_answer=early_match,
        presentation_changed_text=presentation_changed,
        envelope_route=envelope_route,
        commercial_intent=commercial_intent,
        schema_ok=schema_ok,
        quality_issues=quality_issues,
        prompt_tokens=obs.prompt_tokens if obs else None,
        completion_tokens=obs.completion_tokens if obs else None,
        cached_tokens=cached_tokens_from_usage(obs) if obs else None,
        final_answer_excerpt=final_answer[:240] if final_answer else None,
        failure_kind=outcome.failure_kind,
    )


def run_canary(model_id: str, *, flask_app: Any) -> dict[str, Any]:
    row = run_single_measurement(
        model_id=model_id,
        case_id="canary_control" if model_id == CONTROL_MODEL_ID else "canary_candidate",
        client_id="demo",
        attempt_index=0,
        flask_app=flask_app,
    )
    if not row.observed_model:
        raise RuntimeError(f"canary_no_observed_model:{model_id}")
    if row.observed_model != model_id:
        raise RuntimeError(
            f"model_mismatch requested={model_id} observed={row.observed_model}"
        )
    if row.failure_kind or not row.schema_ok:
        raise RuntimeError(f"canary_failed:{model_id}:{row.failure_kind}:{row.quality_issues}")
    return {
        "model_id": model_id,
        "observed_model": row.observed_model,
        "timings_ms": row.timings_ms,
    }


def run_full_matrix(flask_app: Any, *, include_canary: bool = False) -> dict[str, Any]:
    plan = build_call_plan(include_canary=include_canary, repeat_pass=True)
    assert_call_plan_within_budget(plan)
    rows: list[Phase2BRowResult] = []
    for model_id, case_id, client_id, attempt_index in plan:
        rows.append(
            run_single_measurement(
                model_id=model_id,
                case_id=case_id,
                client_id=client_id,
                attempt_index=attempt_index,
                flask_app=flask_app,
            )
        )
    return summarize_rows(rows, call_plan=plan)


def summarize_rows(
    rows: list[Phase2BRowResult],
    *,
    call_plan: list[tuple[str, str, str, int]],
) -> dict[str, Any]:
    by_model: dict[str, list[Phase2BRowResult]] = {CONTROL_MODEL_ID: [], CANDIDATE_MODEL_ID: []}
    for row in rows:
        by_model.setdefault(row.model_id, []).append(row)

    def _latency_stats(model_id: str, key: str) -> dict[str, int | None]:
        values = [
            int(row.timings_ms[key])
            for row in by_model.get(model_id, [])
            if row.timings_ms.get(key) is not None
        ]
        if not values:
            return {"median": None, "min": None, "max": None}
        return {
            "median": int(statistics.median(values)),
            "min": min(values),
            "max": max(values),
        }

    safe_gains = [
        int(row.timings_ms["potential_streaming_gain_ms"])
        for row in rows
        if row.timings_ms.get("potential_streaming_gain_ms") is not None
        and (spec := _case_by_id(row.case_id)) is not None
        and spec.category == "faq_safe"
        and row.envelope_route == "ANSWER"
        and row.early_patient_text_matches_final_answer is True
    ]

    gate_median_gain = int(statistics.median(safe_gains)) if safe_gains else None

    return {
        "measurement_id": MEASUREMENT_ID,
        "live_call_count": len(rows),
        "call_plan_size": len(call_plan),
        "latency_by_model": {
            model: {
                "provider_ttft": _latency_stats(model, "provider_ttft"),
                "current_time_to_visible_answer": _latency_stats(
                    model, "current_time_to_visible_answer"
                ),
                "hypothetical_safe_patient_ttft": _latency_stats(
                    model, "hypothetical_safe_patient_ttft"
                ),
                "potential_streaming_gain_ms": _latency_stats(
                    model, "potential_streaming_gain_ms"
                ),
                "total_latency": _latency_stats(model, "total_latency"),
            }
            for model in (CONTROL_MODEL_ID, CANDIDATE_MODEL_ID)
        },
        "safe_faq_gain_median_ms": gate_median_gain,
        "rows": [asdict(row) for row in rows],
    }
