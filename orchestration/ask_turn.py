from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from contracts.ask_orchestration import AskOrchestrationResult
from logging_setup import emit_bot_event, get_logger
from orchestration.catalog_flow import (
    catalog_md_priority_from_a3,
    try_a3_catalog_facts,
    try_a3_doctor_route,
)
from orchestration.helpers import decision_dump
from core.patient_situation import record_patient_situation_ctx
from core.patient_situation_session import (
    persist_patient_situation_after_turn,
    resolve_patient_situation_for_turn,
)
from core.dialog_focus import record_dialog_focus_ctx
from core.price_offers import is_crown_inclusion_content_query
from orchestration.composer_flow import try_composer_overlay
from orchestration.patient_playbook_flow import try_patient_options_overview
from orchestration.price_flow import price_lookup_intent_fallback, try_a3_price_route
from orchestration.retrieval_flow import run_content_arbiter_path, run_selection_fallback
from policy import contacts_intent
from core.answer_planner import build_answer_plan, publish_answer_plan
from core.answer_packet_snapshot import build_and_publish_answer_packet
from core.md_chunks import CONTACTS_CHUNK_REF, get_chunk_by_ref
from query_selector import select_price_service_route
from retriever import normalize_retrieval_query
from source_routing import route_source, slim_source_route_payload

logger = get_logger("bot")


def orchestrate_routing_after_resolver(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    decision,
    scope_topic_candidate: str | None,
    resolver_bypassed_env: bool,
    data: dict,
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    lead_flow_from_result: Callable[..., AskOrchestrationResult],
    apply_response_policy: Callable[..., dict],
) -> AskOrchestrationResult:
    """
    Post-Resolver routing: contacts overlay → A3 source_routing → price fallback → content/retrieval.
    Extracted from app._orchestrate_ask_turn (Phase 3c).
    """
    decision_frame = decision_dump(decision)
    situation, carry_meta = resolve_patient_situation_for_turn(q, sid=sid, client_id=client_id)
    record_patient_situation_ctx(situation, carry_meta=carry_meta)
    persist_patient_situation_after_turn(
        sid,
        q,
        client_id=client_id,
        fresh_result=situation,
        carry_meta=carry_meta,
    )
    record_dialog_focus_ctx(q, sid=sid, client_id=client_id, decision=decision)

    qp_loc = normalize_retrieval_query(q) or (q or "")
    if contacts_intent(qp_loc.strip()) or contacts_intent((q or "").strip()):
        intent = "contacts"
        scope_topic_candidate = None
        request.ctx["retrieval_scope_topic"] = None
        request.ctx["retrieval_scope_guard_reason"] = "none"
        request.ctx["effective_intent"] = "contacts"

    if intent == "contacts":
        picked = get_chunk_by_ref(CONTACTS_CHUNK_REF, client_id=client_id)
        if picked:
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=picked,
                llm_question=q,
                log_event="Answer generated from contacts intent",
                chunk_route="contacts_chunk",
                decision_frame=decision_frame,
            )

    md_catalog_priority_ref = None
    md_catalog_priority_sid = None
    md_catalog_priority_score = None
    md_catalog_priority_match_method = None

    q_raw = (q or "").strip()
    if is_crown_inclusion_content_query(q_raw):
        intent = "content"
        request.ctx["effective_intent"] = "content"

    if intent != "contacts":
        sr = route_source(q, sid=sid, client_id=client_id, decision=decision, app_intent=intent)
        srd = slim_source_route_payload(sr)
        request.ctx["source_route_decision"] = srd
        emit_bot_event(logger, "source_route_decision", status="ok", details=srd)

        plan = build_answer_plan(
            q=q,
            sid=sid,
            client_id=client_id,
            intent=intent,
            decision=decision,
            source_route=sr,
        )
        publish_answer_plan(plan)
        route_hint = str(getattr(decision, "route_intent", None) or intent or "content")
        build_and_publish_answer_packet(
            plan,
            client_id=client_id,
            route=route_hint,
            service_id=plan.service_id,
            source_ref=str(getattr(sr, "ref", None) or "") or None,
        )

        md_prio = catalog_md_priority_from_a3(sr)
        if md_prio is not None:
            md_catalog_priority_ref = md_prio.ref
            md_catalog_priority_sid = md_prio.service_id
            md_catalog_priority_score = md_prio.match_score
            md_catalog_priority_match_method = md_prio.match_method

        if intent == "content" or md_catalog_priority_ref:
            playbook_result = try_patient_options_overview(
                q=q,
                sid=sid,
                client_id=client_id,
                intent=intent,
                decision=decision,
                situation=situation,
                md_catalog_priority_ref=md_catalog_priority_ref,
                decision_frame=decision_frame,
            )
            if playbook_result is not None:
                return playbook_result

        doc_result = try_a3_doctor_route(
            q=q,
            sid=sid,
            client_id=client_id,
            sr=sr,
            decision_frame=decision_frame,
        )
        if doc_result is not None:
            return doc_result

        composer_result = try_composer_overlay(
            q=q,
            sid=sid,
            client_id=client_id,
            intent=intent,
            plan=plan,
            sr=sr,
            decision=decision,
            decision_frame=decision_frame,
        )
        if composer_result is not None:
            return composer_result

        facts_result = try_a3_catalog_facts(
            q=q,
            sid=sid,
            client_id=client_id,
            sr=sr,
            decision_frame=decision_frame,
        )
        if facts_result is not None:
            return facts_result

        if not is_crown_inclusion_content_query(q_raw):
            price_result = try_a3_price_route(
                q=q,
                sid=sid,
                client_id=client_id,
                sr=sr,
                decision=decision,
                decision_frame=decision_frame,
            )
            if price_result is not None:
                return price_result
    else:
        request.ctx["source_route_decision"] = {
            "source": "contacts",
            "ref": None,
            "service_id": None,
            "concern_ref": None,
            "match_method": "none",
            "match_score": 0.0,
        }

    if intent == "price_lookup":
        price_fb = price_lookup_intent_fallback(
            q=q,
            sid=sid,
            client_id=client_id,
            decision=decision,
            decision_frame=decision_frame,
            select_price_service_route=select_price_service_route,
        )
        if price_fb is not None:
            return price_fb

    if intent == "content" or md_catalog_priority_ref:
        return run_content_arbiter_path(
            q=q,
            sid=sid,
            client_id=client_id,
            intent=intent,
            decision=decision,
            decision_frame=decision_frame,
            scope_topic_candidate=scope_topic_candidate,
            resolver_bypassed_env=resolver_bypassed_env,
            md_catalog_priority_ref=md_catalog_priority_ref,
            md_catalog_priority_sid=md_catalog_priority_sid,
            md_catalog_priority_score=md_catalog_priority_score,
            md_catalog_priority_match_method=md_catalog_priority_match_method,
            data=data,
            client_txt=client_txt,
            service_payload=service_payload,
            lead_flow_from_result=lead_flow_from_result,
            apply_response_policy=apply_response_policy,
        )

    return run_selection_fallback(
        q=q,
        sid=sid,
        client_id=client_id,
        decision_frame=decision_frame,
        scope_topic_candidate=scope_topic_candidate,
        apply_response_policy=apply_response_policy,
    )
