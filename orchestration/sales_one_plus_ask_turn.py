"""Sales-one-plus HTTP entry: gate-first candidate path without legacy ingress."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from config import (
    INPUT_MAX_CHARS,
)
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.ui_service_action import is_ui_service_ref
from core import turn_timing
from core.local_problem_gate import decide_local_problem_gate
from core.sales_fast_widget_runtime import (
    sales_fast_widget_outcome_from_local_gate,
)
from core.lead_context import take_lead_provider_question
from flow_handlers import handle_flows
from lead_interrupt import (
    LEAD_CANCEL_REF,
    LEAD_PENDING_ANSWER_REF,
    LEAD_PENDING_CONTINUE_NAME_REF,
    LEAD_PENDING_RETRY_PHONE_REF,
    LEAD_PAUSE_REF,
    LEAD_RESUME_REF,
)
from logging_setup import get_logger, log_json
from orchestration.lead_flow import lead_flow_orchestration_result
from orchestration.route_guards import (
    check_rate_limit,
    normalize_question_text,
    rate_limited_response_payload,
)
from orchestration.sales_fast_widget_turn import orchestrate_sales_fast_widget_turn
from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn
from policy import contacts_intent
from session import (
    get_topic_state,
    mark_nav_ref_used,
    mem_get,
    mem_reset,
    sid_from_body,
)
from ux_builder import empty_question_response

logger = get_logger("bot")

_LEAD_FLOW_GOVERNED_REFS = frozenset(
    {
        LEAD_PAUSE_REF,
        LEAD_RESUME_REF,
        LEAD_CANCEL_REF,
        LEAD_PENDING_ANSWER_REF,
        LEAD_PENDING_CONTINUE_NAME_REF,
        LEAD_PENDING_RETRY_PHONE_REF,
    }
)

GOVERNED_TYPED_UI_GATE = LocalProblemGateResult(
    decision="pass",
    reason_code="governed_typed_ui",
)


def _maybe_clear_unrelated_pending_price_clarify_for_turn(
    *,
    sid: str,
    client_id: str,
    user_message: str,
    ref: str | None,
) -> None:
    if ref and is_ui_service_ref(ref):
        return
    from core.pending_price_clarify import maybe_clear_unrelated_pending_price_clarify
    from core.target_runtime_client_context import load_target_runtime_client_context

    try:
        bundle = load_target_runtime_client_context(client_id).bundle
    except Exception:
        return
    maybe_clear_unrelated_pending_price_clarify(
        sid,
        user_message=user_message,
        bundle=bundle,
        is_governed_service_click=False,
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
        branch_hint_text=q,
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


def _session_bound_label_for_ref(*, ref: str, sid: str) -> str | None:
    from core.target_runtime_session import read_target_runtime_session

    ref_eff = str(ref or "").strip()
    if not ref_eff:
        return None
    session_state = read_target_runtime_session(sid)
    for item in session_state.followups:
        if str(item.ref or "").strip() == ref_eff:
            label = str(item.label or "").strip()
            return label or None
    return None


def _is_governed_ref_label_only_click(*, ref: str, q: str, sid: str) -> bool:
    """True for ref-only clicks or ref+q where q equals the session-bound label."""

    q_eff = str(q or "").strip()
    if not q_eff:
        return True
    label = _session_bound_label_for_ref(ref=ref, sid=sid)
    if not label:
        return False
    return q_eff.casefold() == label.casefold()


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

    governed_typed_ref = (
        is_ui_scope_ref(ref_eff)
        or is_ui_service_ref(ref_eff)
        or is_ui_stage_ref(ref_eff)
    )

    if q and not governed_typed_ref:
        from core.target_runtime_followup_nav import resolve_target_followup_navigation

        session_state = read_target_runtime_session(sid)
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
        return q

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
        label = str(ui_resolution.planner_message or "").strip()
        if not label:
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
        return (q or label).strip() or label
    if is_ui_service_ref(ref_eff):
        from core.pending_price_clarify import (
            is_pending_price_clarify_fresh,
            read_pending_price_clarify,
        )
        from core.target_runtime_client_context import load_target_runtime_client_context
        from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
        from session import mem_get

        try:
            runtime_context = load_target_runtime_client_context(client_id)
            active_ids = ServiceReferenceCatalogSnapshot.from_bundle(
                runtime_context.bundle
            ).active_service_ids
        except Exception:
            active_ids = frozenset()
        pending_allowed: frozenset[str] | None = None
        pending = read_pending_price_clarify(mem_get(sid))
        if pending is not None and is_pending_price_clarify_fresh(
            pending,
            session_turn_count=session_state.session_turn_count,
        ):
            pending_allowed = frozenset(pending.allowed_service_ids)
        ui_resolution = resolve_ui_service_ref_click(
            ref=ref_eff,
            followups=session_state.followups,
            active_service_ids=active_ids,
            expected_client_id=client_id,
            pending_allowed_service_ids=pending_allowed,
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
        label = str(ui_resolution.planner_message or "").strip()
        if not label:
            service = None
            try:
                runtime_context = load_target_runtime_client_context(client_id)
                service = runtime_context.bundle.services.get(ui_resolution.action.service_id)
            except Exception:
                service = None
            if service is not None:
                label = str(service.name or ui_resolution.action.service_id).strip()
        return (q or label or ui_resolution.action.service_id).strip()
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
        label = str(ui_resolution.planner_message or "").strip()
        if not label:
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
        return (q or label).strip() or label
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

    governed_ui_ref = bool(ref) and (
        is_ui_scope_ref(ref) or is_ui_stage_ref(ref) or is_ui_service_ref(ref)
    )
    governed_typed_ui = bool(
        ref
        and governed_ui_ref
        and _is_governed_ref_label_only_click(ref=ref, q=q, sid=sid)
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
        if not q:
            q = ref_outcome
        local_gate_result = GOVERNED_TYPED_UI_GATE
        try_run_typed_ui_planner_turn(
            sid=sid,
            client_id=client_id,
            enqueue_resolver_trace=enqueue_resolver_trace,
        )
    elif ref and ref not in _LEAD_FLOW_GOVERNED_REFS:
        ref_outcome = _resolve_governed_typed_ui_ref(
            ref=ref,
            q=q,
            sid=sid,
            client_id=client_id,
        )
        if isinstance(ref_outcome, AskOrchestrationResult):
            return ref_outcome
        q = ref_outcome

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

    provider_q = take_lead_provider_question()
    if provider_q:
        q = provider_q

    if q:
        _maybe_clear_unrelated_pending_price_clarify_for_turn(
            sid=sid,
            client_id=client_id,
            user_message=q,
            ref=ref,
        )

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
        if local_gate_result.decision == "spam":
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
