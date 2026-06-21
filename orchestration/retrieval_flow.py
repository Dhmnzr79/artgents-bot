from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from flask import request

from arbiter import decide_content_route
from content_arbiter import collect_content_candidates
from contracts.ask_orchestration import AskOrchestrationResult
from flow_handlers import resume_active_lead_flow
from logging_setup import emit_bot_event, get_logger, log_json
from core.metadata_first_observability import metadata_first_turn_details
from orchestration.helpers import (
    apply_content_retrieval_scope_ctx,
    apply_metadata_first_after_content_route,
    guided_menu_payload,
    log_selection,
    service_price_line_for_content,
    slim_content_arbiter_details,
    with_default_anchor,
)
from query_selector import select_chunk_for_question
from core.follow_up_rewrite import get_follow_up_turn_ctx
from session import is_active_lead_flow, is_lead_context, mem_get, set_last_catalog_service
from ux_builder import (
    build_service_facts_card_payload,
    low_score_response,
    no_candidates_response,
)

logger = get_logger("bot")


def run_content_arbiter_path(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    decision,
    decision_frame: dict[str, Any] | None,
    scope_topic_candidate: str | None,
    resolver_bypassed_env: bool,
    md_catalog_priority_ref: str | None,
    md_catalog_priority_sid: str | None,
    md_catalog_priority_score: float | None,
    md_catalog_priority_match_method: str | None,
    data: dict,
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    lead_flow_from_result: Callable[..., AskOrchestrationResult],
    apply_response_policy: Callable[..., dict],
) -> AskOrchestrationResult:
    if (
        decision is not None
        and not resolver_bypassed_env
        and str(decision.route_intent or "").strip().lower() == "unknown"
        and bool(decision.needs_clarification)
        and intent == "content"
        and not md_catalog_priority_ref
        and not is_lead_context(mem_get(sid))
    ):
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=guided_menu_payload(sid, client_id),
            service_doc_id=None,
            service_track_user=True,
            service_route="guided",
            decision_frame=decision_frame,
        )
    get_follow_up_turn_ctx(q, sid=sid, client_id=client_id)
    effective_scope_topic = apply_content_retrieval_scope_ctx(
        scope_topic_candidate,
        q,
        client_id,
        decision=decision,
    )
    fu = request.ctx.get("follow_up") if isinstance(getattr(request, "ctx", None), dict) else None
    if isinstance(fu, dict) and fu.get("follow_up_mode"):
        effective_scope_topic = None
        request.ctx["retrieval_scope_topic"] = None
        request.ctx["retrieval_scope_guard_reason"] = "follow_up_mode"
    cands = collect_content_candidates(
        q=q,
        sid=sid,
        client_id=client_id,
        scope_topic=effective_scope_topic,
        decision=decision,
        catalog_md_priority_ref=md_catalog_priority_ref,
        catalog_md_priority_service_id=md_catalog_priority_sid,
        catalog_md_priority_match_score=md_catalog_priority_score,
        catalog_md_priority_match_method=md_catalog_priority_match_method,
    )
    rdbg_turn = (cands.retrieval or {}).get("debug_meta") or {}
    if rdbg_turn.get("scope_widen_fallback"):
        request.ctx["retrieval_scope_widen_fallback"] = True
    sel = decide_content_route(
        q=q,
        sid=sid,
        client_id=client_id,
        candidates=cands,
        decision_frame=decision,
    )
    dm_sel = sel.debug_meta if isinstance(sel.debug_meta, dict) else {}
    apply_metadata_first_after_content_route(
        decision=decision,
        retrieval_debug_meta=rdbg_turn,
        selected_doc_id=sel.selected_doc_id,
        selected_chunk=sel.selected_chunk,
        selected_route=sel.selected_route,
        alias_candidate=cands.alias,
    )
    emit_bot_event(
        logger,
        "retrieval_metadata",
        status="ok",
        details=metadata_first_turn_details(),
    )
    request.ctx["arbiter_status"] = dm_sel.get("arbiter_status")
    request.ctx["arbiter_selected_ref"] = dm_sel.get("arbiter_selected_ref")
    request.ctx["arbiter_confidence"] = dm_sel.get("arbiter_confidence")
    request.ctx["arbiter_reason"] = dm_sel.get("arbiter_reason")
    request.ctx["arbiter_candidate_count"] = dm_sel.get("candidate_count")
    emit_bot_event(
        logger,
        "content_arbiter_selected",
        status="ok",
        details=slim_content_arbiter_details(
            {
                "selected_kind": sel.kind,
                "selected_route": sel.selected_route,
                "selected_doc_id": sel.selected_doc_id,
                "reason": sel.reason,
                "selected_by": dm_sel.get("selected_by"),
                "arbiter_status": dm_sel.get("arbiter_status"),
                "arbiter_selected_ref": dm_sel.get("arbiter_selected_ref"),
                "arbiter_confidence": dm_sel.get("arbiter_confidence"),
                "arbiter_reason": dm_sel.get("arbiter_reason"),
                "arbiter_alternative": dm_sel.get("arbiter_alternative"),
                "candidate_count": dm_sel.get("candidate_count"),
                "candidate_refs": dm_sel.get("candidate_refs"),
                "min_confidence": dm_sel.get("min_confidence"),
                "debug_meta": sel.debug_meta,
                "candidates": sel.candidates,
                "rejected_candidates": sel.rejected_candidates,
            }
        ),
    )
    if sel.selected_route == "catalog_md_first":
        cat = cands.catalog
        sid_svc = str(cat.get("matched_service_id") or "")
        md_ref = with_default_anchor(str(cat.get("md_entry_ref") or ""))
        service = cat.get("service") or {}
        price_line = service_price_line_for_content(service, client_id)
        gen_append = (price_line or "").strip() or None
        if md_ref:
            from retriever import get_chunk_by_ref

            ch = get_chunk_by_ref(md_ref, client_id=client_id)
            if ch:
                log_json(
                    logger,
                    "catalog_route",
                    route="md_first",
                    matched_service_id=sid_svc,
                    match_score=cat.get("match_score"),
                    md_entry_ref=md_ref,
                )
                if sid_svc:
                    set_last_catalog_service(sid, sid_svc)
                llm_q = q or f"Информация из {md_ref}"
                if request.ctx.get("a3_catalog_md_session_hint"):
                    low = (q or "").lower()
                    if "врем" in low or "срок" in low or "сколько" in low:
                        llm_q = (
                            f"{llm_q}\n\n"
                            "Пациент спрашивает про длительность или сроки по этой услуге. Ответь кратко и "
                            "обязательно включи в ответ слово «срок» или «сроки» (типичный ориентир по этапам)."
                        )
                emit_bot_event(
                    logger,
                    "content_arbiter_price_injection",
                    status="ok",
                    details={
                        "selected_route": "catalog_md_first",
                        "price_line_applied": bool(gen_append),
                        "md_entry_ref": md_ref,
                        "matched_service_id": sid_svc,
                    },
                )
                return AskOrchestrationResult(
                    kind="chunk",
                    q=q,
                    sid=sid,
                    client_id=client_id,
                    chosen_chunk=ch,
                    llm_question=llm_q,
                    log_event="Answer generated from md_entry_ref",
                    chunk_route="catalog_md_first",
                    decision_frame=decision_frame,
                    generator_append_text=gen_append,
                )
    if sel.selected_route == "catalog_facts":
        cat = cands.catalog
        svc = cat.get("service") or {}
        sid_svc = str(cat.get("matched_service_id") or "")
        payload = build_service_facts_card_payload(
            sid=sid,
            client_id=client_id,
            service_id=sid_svc,
            service=svc,
            match_score=float(cat.get("match_score") or 0.0),
            user_question=q,
        )
        price_line = service_price_line_for_content(svc, client_id)
        price_applied = False
        if price_line:
            base = (payload.get("answer") or "").strip()
            payload["answer"] = f"{base}\n\n{price_line}" if base else price_line
            payload.setdefault("meta", {})["price_display_applied"] = "always"
            price_applied = True
        log_json(
            logger,
            "catalog_route",
            route="facts",
            matched_service_id=sid_svc,
            match_score=cat.get("match_score"),
        )
        if sid_svc:
            set_last_catalog_service(sid, sid_svc)
        emit_bot_event(
            logger,
            "content_arbiter_price_injection",
            status="ok",
            details={
                "selected_route": "catalog_facts",
                "price_line_applied": bool(price_applied),
                "matched_service_id": sid_svc,
            },
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="catalog_facts",
            decision_frame=decision_frame,
        )
    if sel.selected_route == "guided":
        if is_active_lead_flow(mem_get(sid)) and (q or "").strip():
            flow_result = resume_active_lead_flow(
                data=data,
                sid=sid,
                q=q,
                client_id=client_id,
                txt=client_txt(client_id),
                service_payload=service_payload,
            )
            if flow_result is not None:
                log_json(logger, "lead_flow_resume", sid=sid, client_id=client_id, stage="arbiter_guided")
                return lead_flow_from_result(
                    q=q,
                    sid=sid,
                    client_id=client_id,
                    flow_result=flow_result,
                    decision=decision,
                )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=guided_menu_payload(sid, client_id),
            service_doc_id=None,
            service_track_user=True,
            service_route="guided",
            decision_frame=decision_frame,
        )
    if sel.selected_route == "retrieval_chunk" and isinstance(sel.selected_chunk, dict):
        dmeta = cands.retrieval.get("debug_meta") or {} if isinstance(cands.retrieval, dict) else {}
        log_selection(
            q=q,
            chosen_chunk=sel.selected_chunk,
            chosen_score=sel.selected_chunk.get("_score"),
            original_top_score=dmeta.get("top_score"),
            rerank_applied=bool((cands.retrieval or {}).get("rerank_applied")),
        )
        return AskOrchestrationResult(
            kind="chunk",
            q=q,
            sid=sid,
            client_id=client_id,
            chosen_chunk=sel.selected_chunk,
            llm_question=None,
            log_event="Answer generated",
            chunk_route="retrieval_chunk",
            decision_frame=decision_frame,
        )
    rmode = str((cands.retrieval or {}).get("mode") or "")
    if rmode == "no_candidates":
        emit_bot_event(
            logger,
            "retrieval_fallback",
            status="no_candidates",
            details={
                "reason": "no_candidates",
                "question_preview": (q or "")[:200],
                "top_score": ((cands.retrieval or {}).get("debug_meta") or {}).get("top_score"),
            },
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=no_candidates_response(client_id),
            service_doc_id=None,
            service_track_user=True,
            service_route="retrieval_no_candidates",
            decision_frame=decision_frame,
        )
    if rmode == "low_score":
        dmeta = cands.retrieval.get("debug_meta") or {} if isinstance(cands.retrieval, dict) else {}
        emit_bot_event(
            logger,
            "retrieval_fallback",
            status="low_score",
            details={
                "reason": "low_score",
                "question_preview": (q or "")[:200],
                "top_score": dmeta.get("top_score"),
                "threshold": dmeta.get("threshold"),
                "alias_score": dmeta.get("alias_score"),
                "top_candidate": dmeta.get("top_candidate"),
                "query_user_raw": (dmeta.get("query_user_raw") or "")[:200],
            },
        )
        st_ls = mem_get(sid)
        pls = low_score_response(sid, client_id)
        pls = apply_response_policy(
            pls,
            st_ls,
            q,
            topic_state={},
            doc_meta={},
            pre_doc_turn_count=None,
            session_id=sid,
            client_id=client_id,
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=pls,
            service_doc_id=None,
            service_track_user=True,
            service_route="low_score_fallback",
            decision_frame=decision_frame,
        )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=no_candidates_response(client_id),
        service_doc_id=None,
        service_track_user=True,
        service_route="error",
        decision_frame=decision_frame,
    )


def run_selection_fallback(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None,
    scope_topic_candidate: str | None,
    apply_response_policy: Callable[..., dict],
) -> AskOrchestrationResult:
    log_json(logger, "Processing question", question=q[:100], question_length=len(q))
    effective_scope_topic = apply_content_retrieval_scope_ctx(
        scope_topic_candidate,
        q,
        client_id,
        decision=decision_frame,
    )
    selection = select_chunk_for_question(
        q,
        client_id=client_id,
        sid=sid,
        scope_topic=effective_scope_topic,
        decision=decision_frame,
    )
    mode = selection.get("mode")
    dmeta = selection.get("debug_meta") or {}
    if dmeta.get("scope_widen_fallback"):
        request.ctx["retrieval_scope_widen_fallback"] = True
    _fb_chunk = selection.get("chunk") if mode == "chunk" else None
    _fb_doc_id = None
    if isinstance(_fb_chunk, dict):
        _fb_file = os.path.basename(str(_fb_chunk.get("file") or ""))
        _fb_doc_id = os.path.splitext(_fb_file)[0] if _fb_file else None
    apply_metadata_first_after_content_route(
        decision=decision_frame,
        retrieval_debug_meta=dmeta,
        selected_doc_id=_fb_doc_id,
        selected_chunk=_fb_chunk if isinstance(_fb_chunk, dict) else None,
        selected_route="retrieval_chunk" if mode == "chunk" else None,
        alias_candidate=None,
    )
    emit_bot_event(
        logger,
        "retrieval_metadata",
        status="ok",
        details=metadata_first_turn_details(),
    )
    if mode == "no_candidates":
        log_json(logger, "No candidates found", question=q[:50])
        emit_bot_event(
            logger,
            "retrieval_fallback",
            status="no_candidates",
            details={
                "reason": "no_candidates",
                "question_preview": (q or "")[:200],
                "top_score": dmeta.get("top_score"),
            },
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=no_candidates_response(client_id),
            service_doc_id=None,
            service_track_user=True,
            service_route="retrieval_no_candidates",
            decision_frame=decision_frame,
        )
    if mode == "low_score":
        log_json(logger, "low_score_fallback", **dmeta)
        emit_bot_event(
            logger,
            "retrieval_fallback",
            status="low_score",
            details={
                "reason": "low_score",
                "question_preview": (q or "")[:200],
                "top_score": dmeta.get("top_score"),
                "threshold": dmeta.get("threshold"),
                "alias_score": dmeta.get("alias_score"),
                "top_candidate": dmeta.get("top_candidate"),
                "query_user_raw": (dmeta.get("query_user_raw") or "")[:200],
            },
        )
        st_ls = mem_get(sid)
        pls = low_score_response(sid, client_id)
        pls = apply_response_policy(
            pls,
            st_ls,
            q,
            topic_state={},
            doc_meta={},
            pre_doc_turn_count=None,
            session_id=sid,
            client_id=client_id,
        )
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=pls,
            service_doc_id=None,
            service_track_user=True,
            service_route="low_score_fallback",
            decision_frame=decision_frame,
        )
    if mode == "chunk":
        final_chunk = selection.get("chunk")
        if not isinstance(final_chunk, dict):
            log_json(logger, "selection_invalid_chunk", debug_meta=dmeta)
            emit_bot_event(
                logger,
                "retrieval_fallback",
                status="invalid_chunk",
                details={
                    "reason": "selection_invalid_chunk",
                    "question_preview": (q or "")[:200],
                    "debug_meta": dmeta,
                },
            )
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=no_candidates_response(client_id),
                service_doc_id=None,
                service_track_user=True,
                service_route="error",
                decision_frame=decision_frame,
            )
        if dmeta.get("selected_by") == "alias":
            log_json(
                logger,
                "alias_hit_selected",
                alias_score=dmeta.get("alias_score"),
                file=final_chunk.get("file"),
                h2_id=final_chunk.get("h2_id"),
                h3_id=final_chunk.get("h3_id"),
            )
        log_selection(
            q=q,
            chosen_chunk=final_chunk,
            chosen_score=final_chunk.get("_score"),
            original_top_score=dmeta.get("top_score"),
            rerank_applied=bool(selection.get("rerank_applied")),
        )
        return AskOrchestrationResult(
            kind="chunk",
            q=q,
            sid=sid,
            client_id=client_id,
            chosen_chunk=final_chunk,
            llm_question=None,
            log_event="Answer generated",
            chunk_route="retrieval_chunk",
            decision_frame=decision_frame,
        )
    log_json(logger, "selection_unknown_mode", mode=mode, debug_meta=dmeta)
    emit_bot_event(
        logger,
        "retrieval_fallback",
        status="unknown_mode",
        details={
            "reason": "selection_unknown_mode",
            "mode": mode,
            "question_preview": (q or "")[:200],
            "debug_meta": dmeta,
        },
    )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=no_candidates_response(client_id),
        service_doc_id=None,
        service_track_user=True,
        service_route="error",
        decision_frame=decision_frame,
    )
