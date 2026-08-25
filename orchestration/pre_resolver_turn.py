from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from config import (
    INPUT_MAX_CHARS,
    SALES_ONE_PLUS_ON,
)
from contracts.ask_orchestration import AskOrchestrationResult
from core import turn_timing
from core.planner_compute_executor import (
    PlannerSpeculationHandle,
    discard_planner_speculation,
    try_submit_planner_speculation,
)
from flow_handlers import handle_flows
from ingress_gate import build_ingress_payload, classify_ingress, ingress_service_route
from logging_setup import get_logger, log_json
from orchestration.context import AskTurnContext
from orchestration.helpers import decision_dump
from orchestration.lead_flow import lead_flow_orchestration_result
from orchestration.route_guards import (
    check_rate_limit,
    is_obvious_noise,
    normalize_question_text,
    obvious_noise_ingress_result,
    rate_limited_response_payload,
)
from session import (
    get_topic_state,
    is_active_lead_flow,
    is_lead_context,
    mark_nav_ref_used,
    mem_get,
    mem_reset,
    recent_dialog_history,
    sid_from_body,
)
from ux_builder import empty_question_response

logger = get_logger("bot")


def run_pre_resolver_turn(
    data: dict,
    *,
    resolve_client_id: Callable[..., str | None],
    bind_chat_ctx: Callable[[str, str], None],
    resolve_ip: Callable[[], str],
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    get_last_content_ui_payload: Callable[[str], dict | None],
) -> AskOrchestrationResult | AskTurnContext:
    """
    Pre-Resolver pipeline: client/reset/rate/noise/ingress/flows/guards/target ref nav.
    """
    decision = None
    client_id = resolve_client_id(data.get("client_id"), host=request.host)
    if client_id is None:
        return AskOrchestrationResult(
            kind="unknown_client",
            client_error={"error": "unknown_client"},
            http_status=403,
        )

    q_raw = data.get("q") or ""
    q = (q_raw or "").strip()
    ref = (data.get("ref") or "").strip()
    sid = sid_from_body(data)

    if q and q.lower() in ("/reset", "/новая"):
        bind_chat_ctx(sid, client_id)
        mem_reset(sid)
        return AskOrchestrationResult(kind="reset_session", q=q, sid=sid, client_id=client_id)

    q, truncated = normalize_question_text(q_raw)
    bind_chat_ctx(sid, client_id)
    request.ctx["effective_intent"] = None

    if truncated:
        log_json(
            logger,
            "input_truncated",
            sid=sid,
            client_id=client_id,
            original_len=len((q_raw or "").strip()),
            max_len=INPUT_MAX_CHARS,
        )

    ip = resolve_ip()
    if not check_rate_limit(ip):
        log_json(logger, "rate_limited", sid=sid, client_id=client_id, ip=ip)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=rate_limited_response_payload(),
            service_route="rate_limited",
            http_status=429,
        )

    st = mem_get(sid)
    decision_frame = decision_dump(decision)

    if is_obvious_noise(q) and not is_lead_context(st):
        noise_res = obvious_noise_ingress_result()
        log_json(logger, "obvious_noise_short_circuit", sid=sid, client_id=client_id)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=build_ingress_payload(
                noise_res, sid=sid, client_id=client_id, question=q
            ),
            service_doc_id=None,
            service_track_user=True,
            service_route=ingress_service_route(noise_res),
            decision_frame=decision_frame,
        )

    ingress_skip = (
        bool(ref)
        or is_lead_context(st)
        or bool(st.get("situation_pending"))
        or bool(st.get("pending_lead_offer"))
    )
    speculative_handle: PlannerSpeculationHandle | None = None
    if q and not ingress_skip:

        def _fork_planner_speculation() -> None:
            if SALES_ONE_PLUS_ON:
                return
            # PERF-4 (Variant C): classify_ingress calls this exactly once,
            # immediately before its own real LLM call -- i.e. only after its own
            # deterministic checks (policy match, deterministic-normal, length) have
            # already found nothing (seam audit S6, Rule 4). This deliberately never
            # duplicates those checks out here: a test (or future code) that replaces
            # classify_ingress wholesale simply never calls this hook either, so
            # there is no way for this fork to fire out of step with what Ingress is
            # actually about to do. Session history is read here, in the main
            # thread (session.py's thread-local client-pack binding is correctly
            # bound for this thread), and handed over as part of an immutable
            # snapshot -- the worker thread itself never touches session.py, Flask
            # `request`, or `request.ctx`.
            nonlocal speculative_handle
            speculative_handle = try_submit_planner_speculation(
                client_id=client_id,
                sid=sid,
                q=q,
                history=recent_dialog_history(sid) if sid else "",
                request_id=request.ctx.get("request_id"),
            )
            if speculative_handle is not None:
                # Mark the real start of Planner's work now, in this thread, so the
                # PERF-0 stage duration and PERF-1 status-sink notification reflect
                # when the compute actually began -- honestly overlapping Ingress's
                # own span below, not artificially delayed until join time.
                turn_timing.stage_start("planner")

        turn_timing.stage_start("ingress")
        ingress_res = classify_ingress(
            q,
            client_id=client_id,
            sid=sid,
            skip=False,
            on_llm_path=_fork_planner_speculation,
        )
        turn_timing.stage_end(
            "ingress",
            status="completed",
            llm_used=ingress_res.source in ("llm", "fallback"),
            reason=ingress_res.source,
        )
        log_json(
            logger,
            "ingress_gate",
            sid=sid,
            client_id=client_id,
            route=ingress_res.route,
            reason=ingress_res.reason[:64],
            confidence=round(float(ingress_res.confidence), 4),
            source=ingress_res.source,
        )
        if ingress_res.route != "normal":
            discard_planner_speculation(speculative_handle)
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=build_ingress_payload(
                    ingress_res, sid=sid, client_id=client_id, question=q
                ),
                service_doc_id=None,
                service_track_user=True,
                service_route=ingress_service_route(ingress_res),
                decision_frame=decision_frame,
            )
    else:
        if not q:
            ingress_skip_reason = "empty_q"
        elif ref:
            ingress_skip_reason = "ref_click"
        elif is_lead_context(st):
            ingress_skip_reason = "lead_context"
        elif st.get("situation_pending"):
            ingress_skip_reason = "situation_pending"
        elif st.get("pending_lead_offer"):
            ingress_skip_reason = "pending_lead_offer"
        else:
            ingress_skip_reason = "ingress_skip"
        turn_timing.stage_skipped("ingress", reason=ingress_skip_reason)

    flow_result = handle_flows(
        data=data,
        st=st,
        sid=sid,
        q=q,
        client_id=client_id,
        txt=client_txt(client_id),
        service_payload=service_payload,
        get_last_content_ui_payload=get_last_content_ui_payload,
        get_topic_state=get_topic_state,
    )
    if flow_result is not None:
        discard_planner_speculation(speculative_handle)
        return lead_flow_orchestration_result(
            q=q, sid=sid, client_id=client_id, flow_result=flow_result, decision=decision
        )

    st = mem_get(sid)

    if ref:
        ref_eff = str(ref).strip()
        if ref_eff:
            try:
                request.ctx["nav_ref"] = ref_eff
            except Exception:
                pass
            mark_nav_ref_used(sid, ref_eff)
        if not q:
            from contracts.ui_scope_action import is_ui_scope_ref
            from contracts.ui_stage_action import is_ui_stage_ref
            from core.target_runtime_followup_nav import (
                build_target_unknown_ref_clarify_payload,
                resolve_target_followup_navigation,
            )
            from core.target_runtime_session import (
                read_target_runtime_session,
                write_session_patient_facts_from_ui_action,
                write_session_patient_facts_from_ui_stage_action,
            )
            from core.target_ui_scope_action import resolve_ui_scope_ref_click
            from core.target_ui_stage_action import resolve_ui_stage_ref_click

            session_state = read_target_runtime_session(sid)
            if is_ui_scope_ref(ref_eff):
                ui_resolution = resolve_ui_scope_ref_click(
                    ref=ref_eff,
                    followups=session_state.followups,
                )
                if ui_resolution.kind != "ok" or ui_resolution.action is None:
                    discard_planner_speculation(speculative_handle)
                    payload = build_target_unknown_ref_clarify_payload(
                        client_id=client_id,
                        sid=sid,
                    )
                    return AskOrchestrationResult(
                        kind="service_reply",
                        q=q,
                        sid=sid,
                        client_id=client_id,
                        service_payload=payload,
                        service_route="target_fullcontext_followup_unknown",
                        decision_frame=decision_frame,
                    )
                write_session_patient_facts_from_ui_action(sid, ui_resolution.action)
                try:
                    request.ctx["current_ui_scope_action"] = ui_resolution.action.model_dump()
                except Exception:
                    pass
                if not q:
                    q = "продолжить"
            elif is_ui_stage_ref(ref_eff):
                ui_resolution = resolve_ui_stage_ref_click(
                    ref=ref_eff,
                    followups=session_state.followups,
                )
                if ui_resolution.kind != "ok" or ui_resolution.action is None:
                    discard_planner_speculation(speculative_handle)
                    payload = build_target_unknown_ref_clarify_payload(
                        client_id=client_id,
                        sid=sid,
                    )
                    return AskOrchestrationResult(
                        kind="service_reply",
                        q=q,
                        sid=sid,
                        client_id=client_id,
                        service_payload=payload,
                        service_route="target_fullcontext_followup_unknown",
                        decision_frame=decision_frame,
                    )
                write_session_patient_facts_from_ui_stage_action(
                    sid,
                    ui_resolution.action,
                    prior=session_state.patient_facts,
                )
                try:
                    request.ctx["current_ui_stage_action"] = ui_resolution.action.model_dump()
                except Exception:
                    pass
                if not q:
                    q = "продолжить"
            else:
                nav = resolve_target_followup_navigation(
                    ref=ref_eff,
                    q=q,
                    followups=session_state.followups,
                )
                if nav is not None and nav.matched_ref is None:
                    discard_planner_speculation(speculative_handle)
                    payload = build_target_unknown_ref_clarify_payload(
                        client_id=client_id,
                        sid=sid,
                    )
                    return AskOrchestrationResult(
                        kind="service_reply",
                        q=q,
                        sid=sid,
                        client_id=client_id,
                        service_payload=payload,
                        service_route="target_fullcontext_followup_unknown",
                        decision_frame=decision_frame,
                    )
                if nav is not None and nav.user_message:
                    q = nav.user_message

    if not q:
        discard_planner_speculation(speculative_handle)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=empty_question_response(client_id),
            service_doc_id=None,
            service_track_user=False,
            service_route="error",
            decision_frame=decision_frame,
        )

    return AskTurnContext(
        q=q,
        sid=sid,
        client_id=client_id,
        ref=ref,
        data=data,
        st=st,
        planner_speculation=speculative_handle,
    )
