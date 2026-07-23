from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from config import (
    ANTI_SPAM_BURST_MESSAGES,
    ANTI_SPAM_BURST_WINDOW_SEC,
    INPUT_MAX_CHARS,
)
from contracts.ask_orchestration import AskOrchestrationResult
from flow_handlers import handle_flows
from ingress_gate import build_ingress_payload, classify_ingress, ingress_service_route
from logging_setup import get_logger, log_json
from orchestration.context import AskTurnContext
from orchestration.helpers import decision_dump
from orchestration.lead_flow import lead_flow_orchestration_result
from orchestration.route_guards import (
    check_rate_limit,
    is_message_burst,
    is_obvious_noise,
    normalize_question_text,
    obvious_noise_ingress_result,
    rate_limited_response_payload,
    should_soft_redirect_no_intent,
    soft_redirect_payload,
)
from session import (
    get_topic_state,
    is_active_lead_flow,
    is_lead_context,
    mark_nav_ref_used,
    mem_get,
    mem_reset,
    set_anti_spam_redirect_shown,
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
    request.ctx["retrieval_scope_topic"] = None
    request.ctx["retrieval_scope_guard_reason"] = "none"
    request.ctx["retrieval_scope_widen_fallback"] = False
    request.ctx["legacy_intent"] = None
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
    if q and not ingress_skip:
        ingress_res = classify_ingress(q, client_id=client_id, sid=sid, skip=False)
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
        return lead_flow_orchestration_result(
            q=q, sid=sid, client_id=client_id, flow_result=flow_result, decision=decision
        )

    st = mem_get(sid)

    if not is_lead_context(st):
        if is_message_burst(st):
            set_anti_spam_redirect_shown(sid, True)
            log_json(
                logger,
                "anti_spam_burst_redirect",
                sid=sid,
                client_id=client_id,
                burst_window_sec=ANTI_SPAM_BURST_WINDOW_SEC,
                burst_messages=ANTI_SPAM_BURST_MESSAGES,
            )
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=soft_redirect_payload(sid, client_id),
                service_doc_id=None,
                service_track_user=True,
                service_route="booking_flow",
                decision_frame=decision_frame,
            )
        if should_soft_redirect_no_intent(st):
            set_anti_spam_redirect_shown(sid, True)
            log_json(
                logger,
                "anti_spam_soft_redirect",
                sid=sid,
                client_id=client_id,
                session_turn_count=int(st.get("session_turn_count") or 0),
            )
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=soft_redirect_payload(sid, client_id),
                service_doc_id=None,
                service_track_user=True,
                service_route="booking_flow",
                decision_frame=decision_frame,
            )

    if ref:
        ref_eff = str(ref).strip()
        if ref_eff:
            try:
                request.ctx["nav_ref"] = ref_eff
            except Exception:
                pass
            mark_nav_ref_used(sid, ref_eff)
        if not q:
            from core.target_runtime_followup_nav import (
                build_target_unknown_ref_clarify_payload,
                resolve_target_followup_navigation,
            )
            from core.target_runtime_session import read_target_runtime_session

            nav = resolve_target_followup_navigation(
                ref=ref_eff,
                q=q,
                followups=read_target_runtime_session(sid).followups,
            )
            if nav is not None and nav.matched_ref is None:
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

    return AskTurnContext(q=q, sid=sid, client_id=client_id, ref=ref, data=data, st=st)
