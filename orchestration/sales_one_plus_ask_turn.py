"""Sales-one-plus HTTP entry: gate-first candidate path without legacy ingress."""

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
from contracts.local_problem_gate import LocalProblemGateResult
from core import turn_timing
from core.local_problem_gate import decide_local_problem_gate
from core.sales_fast_widget_runtime import (
    sales_fast_widget_outcome_from_local_gate,
)
from flow_handlers import handle_flows
from logging_setup import get_logger, log_json
from orchestration.lead_flow import lead_flow_orchestration_result
from orchestration.route_guards import (
    check_rate_limit,
    is_message_burst,
    normalize_question_text,
    rate_limited_response_payload,
    should_soft_redirect_no_intent,
    soft_redirect_payload,
)
from orchestration.sales_fast_widget_turn import orchestrate_sales_fast_widget_turn
from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn
from policy import contacts_intent
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

GOVERNED_TYPED_UI_GATE = LocalProblemGateResult(
    decision="pass",
    reason_code="governed_typed_ui",
)


def _service_reply_from_gate(
    gate: LocalProblemGateResult,
    *,
    q: str,
    sid: str,
    client_id: str,
) -> AskOrchestrationResult:
    outcome = sales_fast_widget_outcome_from_local_gate(
        gate,
        client_id=client_id,
        sid=sid,
    )
    if outcome is None:
        raise ValueError("sales_one_plus_gate_not_terminal")
    meta = outcome.widget.payload.get("meta") if isinstance(outcome.widget.payload.get("meta"), dict) else {}
    route = str(meta.get("service_route") or "sales_fast")
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=outcome.widget.payload,
        service_doc_id=None,
        service_track_user=True,
        service_route=route,
    )


def _contact_aspects_from_message(q: str) -> tuple[str, ...] | None:
    """Map existing CONTACTS_RE matches to planner contact aspects; None → pass to Flash."""

    from config import CONTACTS_RE

    if not q:
        return None
    aspects: list[str] = []
    seen: set[str] = set()
    for match in CONTACTS_RE.finditer(q):
        token = match.group(0).lower()
        aspect: str | None = None
        if "парков" in token:
            aspect = "contact_parking"
        elif "телефон" in token:
            aspect = "contact_phone"
        elif "whatsapp" in token:
            aspect = "contact_whatsapp"
        elif "график" in token or "время" in token or "суббот" in token or "воскресен" in token:
            aspect = "contact_hours"
        elif any(
            part in token
            for part in ("адрес", "наход", "доехать", "проехать", "клиник", "метро", "располож", "карт")
        ):
            aspect = "contact_address"
        if aspect is None:
            return None
        if aspect not in seen:
            seen.add(aspect)
            aspects.append(aspect)
    if aspects:
        return tuple(aspects)
    if "контакт" in q.lower():
        return ("contacts",)
    if contacts_intent(q):
        return None
    return None


def _try_deterministic_contacts_terminal(
    *,
    q: str,
    sid: str,
    client_id: str,
    service_payload: Callable[..., dict],
) -> AskOrchestrationResult | None:
    aspects = _contact_aspects_from_message(q)
    if aspects is None:
        return None
    from core.target_contact_authority import contact_fields_from_turn_aspects
    from core.target_structured_answer import materialize_structured_contact_answer_text

    contact_fields = contact_fields_from_turn_aspects(aspects, primary_aspect=aspects[0])
    if contact_fields is None:
        return None
    answer = materialize_structured_contact_answer_text(
        client_id,
        contact_fields=contact_fields,
    )
    if not answer.strip():
        return None
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=service_payload(answer, sid, client_id),
        service_doc_id=None,
        service_track_user=True,
        service_route="sales_fast_contacts",
    )


def _resolve_governed_typed_ui_ref(
    *,
    ref: str,
    q: str,
    sid: str,
    client_id: str,
) -> AskOrchestrationResult | str:
    """Validate governed UI ref; return terminal clarify or synthetic continue text."""

    ref_eff = str(ref).strip()
    try:
        request.ctx["nav_ref"] = ref_eff
    except Exception:
        pass
    mark_nav_ref_used(sid, ref_eff)

    if q:
        from core.target_runtime_followup_nav import resolve_target_followup_navigation
        from core.target_runtime_session import read_target_runtime_session

        session_state = read_target_runtime_session(sid)
        nav = resolve_target_followup_navigation(
            ref=ref_eff,
            q=q,
            followups=session_state.followups,
        )
        if nav is not None and nav.matched_ref is None:
            from core.target_runtime_followup_nav import build_target_unknown_ref_clarify_payload

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
                service_route="sales_fast_followup_unknown",
            )
        if nav is not None and nav.user_message:
            return nav.user_message
        return q

    from contracts.ui_scope_action import is_ui_scope_ref
    from contracts.ui_service_action import is_ui_service_ref
    from contracts.ui_stage_action import is_ui_stage_ref
    from core.target_runtime_followup_nav import build_target_unknown_ref_clarify_payload
    from core.target_runtime_session import (
        read_target_runtime_session,
        write_session_patient_facts_from_ui_action,
        write_session_patient_facts_from_ui_stage_action,
    )
    from core.target_ui_scope_action import resolve_ui_scope_ref_click
    from core.target_ui_service_action import resolve_ui_service_ref_click
    from core.target_ui_stage_action import resolve_ui_stage_ref_click

    session_state = read_target_runtime_session(sid)
    if is_ui_scope_ref(ref_eff):
        ui_resolution = resolve_ui_scope_ref_click(
            ref=ref_eff,
            followups=session_state.followups,
        )
        if ui_resolution.kind != "ok" or ui_resolution.action is None:
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
                service_route="sales_fast_followup_unknown",
            )
        write_session_patient_facts_from_ui_action(sid, ui_resolution.action)
        try:
            request.ctx["current_ui_scope_action"] = ui_resolution.action.model_dump()
        except Exception:
            pass
        return "продолжить"
    if is_ui_service_ref(ref_eff):
        from core.target_runtime_client_context import load_target_runtime_client_context
        from core.service_reference_catalog import ServiceReferenceCatalogSnapshot

        try:
            runtime_context = load_target_runtime_client_context(client_id)
            active_ids = ServiceReferenceCatalogSnapshot.from_bundle(
                runtime_context.bundle
            ).active_service_ids
        except Exception:
            active_ids = frozenset()
        ui_resolution = resolve_ui_service_ref_click(
            ref=ref_eff,
            followups=session_state.followups,
            active_service_ids=active_ids,
            expected_client_id=client_id,
        )
        if ui_resolution.kind != "ok" or ui_resolution.action is None:
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
                service_route="sales_fast_followup_unknown",
            )
        try:
            request.ctx["current_ui_service_action"] = ui_resolution.action.model_dump()
        except Exception:
            pass
        try:
            request.ctx["current_ui_scope_action"] = {
                "service_id": ui_resolution.action.service_id,
                "extent": None,
                "jaw": None,
                "provenance": ui_resolution.action.ref,
            }
        except Exception:
            pass
        return "продолжить"
    if is_ui_stage_ref(ref_eff):
        ui_resolution = resolve_ui_stage_ref_click(
            ref=ref_eff,
            followups=session_state.followups,
        )
        if ui_resolution.kind != "ok" or ui_resolution.action is None:
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
                service_route="sales_fast_followup_unknown",
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
        return "продолжить"

    from core.target_runtime_followup_nav import resolve_target_followup_navigation

    nav = resolve_target_followup_navigation(
        ref=ref_eff,
        q=q,
        followups=session_state.followups,
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
            service_route="sales_fast_followup_unknown",
        )
    if nav is not None and nav.user_message:
        return nav.user_message
    return "продолжить"


def _run_local_problem_gate(q: str) -> LocalProblemGateResult:
    turn_timing.stage_start("sales_fast_local_gate")
    gate = decide_local_problem_gate(q)
    turn_timing.stage_end(
        "sales_fast_local_gate",
        status="completed",
        reason=gate.reason_code,
    )
    return gate


def _post_gate_flows(
    *,
    data: dict,
    q: str,
    sid: str,
    client_id: str,
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    get_last_content_ui_payload: Callable[[str], dict | None],
) -> AskOrchestrationResult | None:
    st = mem_get(sid)
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
            q=q,
            sid=sid,
            client_id=client_id,
            flow_result=flow_result,
            decision=None,
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
            )
    return None


def orchestrate_sales_one_plus_ask_turn(
    data: dict,
    *,
    resolve_client_id: Callable[..., str | None],
    bind_chat_ctx: Callable[[str, str], None],
    resolve_ip: Callable[[], str],
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    get_last_content_ui_payload: Callable[[str], dict | None],
    enqueue_resolver_trace: Callable[..., None],
    on_delta: Callable[[str], None] | None = None,
) -> AskOrchestrationResult:
    """Candidate-only orchestration: no pre_resolver, ingress LLM, or legacy runtime."""

    client_id = resolve_client_id(data.get("client_id"), host=request.host)
    if client_id is None:
        return AskOrchestrationResult(
            kind="unknown_client",
            client_error={"error": "unknown_client"},
            http_status=403,
        )

    q_raw = data.get("q") or ""
    ref = (data.get("ref") or "").strip()
    sid = sid_from_body(data)

    if q_raw and str(q_raw).strip().lower() in ("/reset", "/новая"):
        bind_chat_ctx(sid, client_id)
        mem_reset(sid)
        return AskOrchestrationResult(kind="reset_session", q=str(q_raw).strip(), sid=sid, client_id=client_id)

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

    local_gate_result: LocalProblemGateResult | None = None
    from contracts.ui_scope_action import is_ui_scope_ref
    from contracts.ui_service_action import is_ui_service_ref
    from contracts.ui_stage_action import is_ui_stage_ref

    governed_typed_ui = bool(ref) and not q and (
        is_ui_scope_ref(ref) or is_ui_stage_ref(ref) or is_ui_service_ref(ref)
    )

    if governed_typed_ui:
        ref_outcome = _resolve_governed_typed_ui_ref(
            ref=ref,
            q=q,
            sid=sid,
            client_id=client_id,
        )
        if isinstance(ref_outcome, AskOrchestrationResult):
            return ref_outcome
        q = ref_outcome
        local_gate_result = GOVERNED_TYPED_UI_GATE
        try_run_typed_ui_planner_turn(
            sid=sid,
            client_id=client_id,
            enqueue_resolver_trace=enqueue_resolver_trace,
        )
    elif ref:
        ref_outcome = _resolve_governed_typed_ui_ref(
            ref=ref,
            q=q,
            sid=sid,
            client_id=client_id,
        )
        if isinstance(ref_outcome, AskOrchestrationResult):
            return ref_outcome
        q = ref_outcome

    if not governed_typed_ui:
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
            )

        local_gate_result = _run_local_problem_gate(q)
        if local_gate_result.decision != "pass":
            return _service_reply_from_gate(
                local_gate_result,
                q=q,
                sid=sid,
                client_id=client_id,
            )

        contacts = _try_deterministic_contacts_terminal(
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=service_payload,
        )
        if contacts is not None:
            return contacts

        flow_reply = _post_gate_flows(
            data=data,
            q=q,
            sid=sid,
            client_id=client_id,
            client_txt=client_txt,
            service_payload=service_payload,
            get_last_content_ui_payload=get_last_content_ui_payload,
        )
        if flow_reply is not None:
            return flow_reply

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
        )

    return orchestrate_sales_fast_widget_turn(
        q=q,
        sid=sid,
        client_id=client_id,
        data=data,
        local_gate_result=local_gate_result,
        on_delta=on_delta,
    )
