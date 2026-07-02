"""Orchestration: chunk → LLM answer → policy → session side-effects → HTTP payload."""

from __future__ import annotations

import inspect
import json as _json
import os
from typing import Any, Callable

from core.claim_gate import detect_forbidden_claims
from core.consult_nudge import (
    plan_consult_nudge,
    record_consult_nudge_after_answer,
    topic_exhausted_after_this_chunk,
)
from core.answer_plan_apply import (
    apply_answer_plan_append,
    clean_answer_for_applied_appends,
    payment_terms_suppress_refs,
)
from core.answer_packet import assemble_answer_packet
from core.answer_packet_materialize import materialize_cards
from core.answer_packet_snapshot import build_and_publish_answer_packet, publish_answer_packet
from core.answer_planner import _real_aspect_count, answer_plan_from_ctx
from core.answer_slots import assemble_answer_slots, doc_meta_has_consult_value, merge_deterministic_appends
from core.md_clean import strip_alias_comments
from core.numeric_fact_gate import apply_numeric_fact_gate
from core.stream_answer_text import AnswerFormatContext, StreamTextAccumulator, format_answer_for_display

import session as session_mod
from contracts.answer_slots import AnswerSlotsTelemetry
from config import COMPOSER_ON
from llm import (
    generate_answer_from_packet,
    generate_answer_stream,
    generate_answer_with_empathy,
)
from logging_setup import log_json
from verifier import build_turn_trace_prefix, schedule_verifier_shadow_if_needed
from meta_loader import get_doc_meta
from policy import apply_response_policy
from session import (
    defer_refs,
    get_topic_state,
    increment_doc_turn_if_contentful,
    is_lead_context,
    mark_h3_covered,
    mark_situation_offered,
    mark_video_pending,
    mark_video_shown,
    mem_add_bot,
    mem_add_user,
    mem_get,
    pop_deferred_ref,
    record_answer_slots_shown,
    set_cta_shown,
    set_current_doc,
    set_last_aspect,
)
from core.lead_context import lead_interrupt_no_topic
from retriever import get_chunk_by_ref
from ux_builder import build_ask_response, normalize_policy_payload

_APPLY_POLICY_PARAMS = inspect.signature(apply_response_policy).parameters


def _planned_consult_nudge_for_chunk(
    *,
    sid: str,
    route: str,
    meta: dict,
    chunk: dict,
    topic_state: dict,
    client_id: str | None = None,
) -> str | None:
    if is_lead_context(mem_get(sid)):
        return None
    if doc_meta_has_consult_value(meta, h3_id=chunk.get("h3_id")):
        return None
    exhausted = topic_exhausted_after_this_chunk(
        meta,
        topic_state,
        chunk_h3_id=chunk.get("h3_id"),
    )
    kind = plan_consult_nudge(
        sid, route, topic_exhausted=exhausted, client_id=client_id
    )
    if kind:
        meta["consult_nudge"] = kind
    return kind


def _mark_suggest_ref_used_compat(sid: str, doc_id: str, used: bool = True) -> None:
    fn = getattr(session_mod, "mark_suggest_ref_used", None)
    if callable(fn):
        fn(sid, doc_id, used)


def _nav_ref_suppress_list() -> list[str]:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return []
        ctx = getattr(request, "ctx", None)
        ref = str((ctx or {}).get("nav_ref") or "").strip()
        return [ref] if ref else []
    except Exception:
        return []


def _plan_append_suppress_refs(
    plan_meta: dict[str, Any] | None,
    *,
    doc_id: str | None = None,
    answer_body: str | None = None,
) -> list[str]:
    return payment_terms_suppress_refs(
        plan_meta=plan_meta,
        doc_id=doc_id,
        answer_body=answer_body,
    )


def _increment_doc_turn_with_pre(
    sid: str,
    doc_id: str | None,
    *,
    contentful: bool,
    is_low_score: bool,
    is_error: bool,
    lead_flow_active: bool,
) -> int | None:
    pre_turn = increment_doc_turn_if_contentful(
        sid,
        doc_id,
        contentful=contentful,
        is_low_score=is_low_score,
        is_error=is_error,
        lead_flow_active=lead_flow_active,
    )
    if pre_turn is not None or not doc_id:
        return pre_turn
    if contentful and not is_low_score and not is_error and not lead_flow_active:
        cur = int((get_topic_state(sid, doc_id) or {}).get("doc_turn_count") or 0)
        if cur > 0:
            return cur - 1
    return None


def _apply_response_policy_compat(
    payload: dict,
    session_state: dict,
    q: str,
    *,
    topic_state: dict,
    doc_meta: dict,
    pre_doc_turn_count: int | None,
    session_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    kw: dict = {
        "payload": payload,
        "session_state": session_state,
        "q": q,
        "topic_state": topic_state,
        "doc_meta": doc_meta,
    }
    if "pre_doc_turn_count" in _APPLY_POLICY_PARAMS:
        kw["pre_doc_turn_count"] = pre_doc_turn_count
    if "session_id" in _APPLY_POLICY_PARAMS:
        kw["session_id"] = session_id
    if "client_id" in _APPLY_POLICY_PARAMS:
        kw["client_id"] = client_id
    return apply_response_policy(**kw)


def chunk_context_md_for_llm(chunk: dict) -> str:
    """Контент для генерации: H2 + H3 + тело чанка (имя врача и т.п. часто только в h2)."""
    parts: list[str] = []
    h2 = (chunk.get("h2") or "").strip()
    h3 = (chunk.get("h3") or "").strip()
    body = strip_alias_comments((chunk.get("text") or "").strip())
    if h2:
        parts.append(h2)
    if h3:
        parts.append(h3)
    if body:
        parts.append(body)
    return "\n\n".join(parts) if parts else ""


def source_ref_from_chunk(chunk: dict) -> str:
    """Единственный ref источника для Generator (basename.md#anchor)."""
    meta = chunk.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    file = str(chunk.get("file") or "")
    base = os.path.basename(file)
    if not base:
        return ""
    if not base.lower().endswith(".md"):
        base = f"{base}.md"
    h3 = str(chunk.get("h3_id") or meta.get("h3_id") or "").strip()
    h2 = str(chunk.get("h2_id") or meta.get("h2_id") or "").strip()
    anchor = (h3 or h2 or "korotko").strip().lower() or "korotko"
    return f"{base}#{anchor}"


def build_generator_source_from_chunk(chunk: dict, meta: dict) -> dict:
    """Один элемент sources[] для LLM (длина 1)."""
    m = meta if isinstance(meta, dict) else {}
    doc_id = str(m.get("doc_id") or "").strip()
    if not doc_id:
        doc_id = os.path.splitext(os.path.basename(str(chunk.get("file") or "")))[0]
    return {
        "ref": source_ref_from_chunk(chunk),
        "content": chunk_context_md_for_llm(chunk),
        "doc_id": doc_id or None,
        "doc_type": str(m.get("doc_type") or chunk.get("doc_type") or "") or None,
        "subtype": str(m.get("subtype") or chunk.get("subtype") or "") or None,
    }


def _append_generator_append_text(answer: str, append_text: str | None) -> str:
    at = (append_text or "").strip()
    if not at:
        return answer
    base = (answer or "").strip()
    if at in base:
        return answer
    return f"{base}\n\n{at}" if base else at


def _merge_price_offer_meta_into_payload(
    payload: dict,
    *,
    price_offer_meta: dict | None = None,
) -> None:
    pom = price_offer_meta if isinstance(price_offer_meta, dict) and price_offer_meta else None
    if pom is None:
        try:
            from flask import has_request_context, request

            if has_request_context():
                ctx_pom = request.ctx.get("price_offer_meta")
                if isinstance(ctx_pom, dict) and ctx_pom:
                    pom = ctx_pom
        except Exception:
            pass
    if isinstance(pom, dict) and pom:
        payload.setdefault("meta", {}).update(pom)


def _apply_patient_playbook_ui(payload: dict, route: str) -> None:
    """Inject playbook quick replies + telemetry meta after chunk generation."""
    if route != "patient_options_overview":
        return
    try:
        from flask import has_request_context, request
    except ImportError:
        return
    if not has_request_context() or not hasattr(request, "ctx"):
        return
    ctx_qr = request.ctx.get("patient_options_quick_replies")
    if isinstance(ctx_qr, list) and ctx_qr:
        payload["quick_replies"] = ctx_qr
    payload.setdefault("meta", {})["ui_source_family"] = "patient_options"
    for key in (
        "patient_options_overview_used",
        "patient_options_situation_kind",
        "patient_options_service_ids",
        "patient_options_source",
        "patient_options_skipped",
        "patient_options_strategy",
    ):
        if key in request.ctx:
            payload.setdefault("meta", {})[key] = request.ctx[key]


def _is_doctor_meta(meta: dict, route: str) -> bool:
    doc_type = str(meta.get("doc_type") or "").strip().lower()
    doc_id = str(meta.get("doc_id") or "").strip().lower()
    return route == "doctors_list" or doc_type == "doctor" or doc_id.startswith("doctors__doctor")


def _append_doctor_consult_bridge(
    *,
    answer: str,
    meta: dict,
    route: str,
    client_id: str | None,
) -> tuple[str, dict | None]:
    if not _is_doctor_meta(meta, route):
        return answer, None
    from core.marketing_policy import select_doctor_consult_bridge

    meta["cta_action"] = "lead"
    meta["cta_key"] = "doctor"
    bridge = select_doctor_consult_bridge(client_id=client_id, meta=meta)
    text = bridge.text.strip()
    if not text or text in (answer or ""):
        return answer, None
    out = _append_generator_append_text(answer, text)
    return out, {
        "doctor_consult_bridge": {
            "reason": bridge.reason,
            "service_id": bridge.service_id,
        }
    }


def _apply_answer_slots_and_price_append(
    *,
    answer: str,
    meta: dict,
    chunk: dict,
    q: str,
    route: str,
    sid: str,
    doc_id: str | None,
    generator_append_text: str | None,
    lead_context: bool,
    price_offer_meta: dict | None = None,
    matched_service_id: str | None = None,
    skip_answer_slots_reason: str | None = None,
) -> tuple[str, dict | None, str, dict | None]:
    """Append clinic/consult/promo slots, planner append, then price tail."""
    tstate = get_topic_state(sid, doc_id) if doc_id else {}
    plan = answer_plan_from_ctx()
    svc_id = str(matched_service_id or meta.get("matched_service_id") or "").strip() or None
    plan_append, plan_apply_meta = apply_answer_plan_append(
        plan,
        client_id=meta.get("client_id"),
        service_id=svc_id,
        q=q,
        existing_append=generator_append_text,
        price_offer_meta=price_offer_meta,
        answer_body=answer,
    )
    answer = clean_answer_for_applied_appends(
        answer,
        plan_apply_meta.get("applied") or [],
    )
    if skip_answer_slots_reason:
        slots_text = ""
        telemetry = AnswerSlotsTelemetry()
        telemetry.suppressed["answer_slots"] = skip_answer_slots_reason
    else:
        slots_text, telemetry = assemble_answer_slots(
            meta=meta,
            h3_id=chunk.get("h3_id"),
            q=q,
            route=route,
            topic_state=tstate,
            lead_context=lead_context,
        )
    combined_append = merge_deterministic_appends(
        slots_text=slots_text,
        generator_append_text=plan_append,
    )
    answer = _append_generator_append_text(answer, combined_append or None)
    if doc_id and telemetry.appended:
        next_turn = int(tstate.get("doc_turn_count") or 0) + 1
        record_answer_slots_shown(
            sid,
            doc_id,
            slot_keys=list(telemetry.appended),
            turn=next_turn,
        )
    slot_meta = telemetry.model_dump() if telemetry.appended or telemetry.suppressed else None
    plan_meta: dict[str, Any] | None = None
    if plan is not None:
        if plan.primary_aspect:
            set_last_aspect(sid, plan.primary_aspect)
        chunk_ref = None
        if doc_id:
            h3 = str(chunk.get("h3_id") or "").strip()
            chunk_ref = f"{doc_id}.md#{h3}" if h3 else f"{doc_id}.md"
        packet = build_and_publish_answer_packet(
            plan,
            client_id=meta.get("client_id"),
            route=route,
            service_id=svc_id,
            primary_chunk_ref=chunk_ref,
            apply_meta=plan_apply_meta,
        )
        plan_meta = {
            "answer_plan": plan.model_dump(),
            "answer_packet": packet.model_dump(),
        }
        if plan_apply_meta.get("applied") or plan_apply_meta.get("suppressed"):
            plan_meta["answer_plan_apply"] = plan_apply_meta
    return answer, slot_meta, combined_append, plan_meta


def _apply_numeric_fact_gate(
    *,
    answer: str,
    route: str,
    meta: dict,
    client_id: str | None,
    deterministic_append: str,
    price_offer_meta: dict | None,
) -> tuple[str, dict | None]:
    gate_meta = dict(meta)
    if isinstance(price_offer_meta, dict):
        gate_meta.update(price_offer_meta)
    result = apply_numeric_fact_gate(
        answer=answer,
        route=route,
        meta=gate_meta,
        client_id=client_id,
        allowed_source_text=(deterministic_append or "").strip() or None,
    )
    gate_payload = result.meta_dict()
    if not gate_payload:
        return answer, None
    return result.answer, gate_payload


def verifier_effective_source_body(*, chunk_md_body: str, generator_append_text: str | None) -> str:
    """Текст «разрешённых фактов» для A7: чанк + детерминированный хвост (цены и т.д.), если был."""
    base = (chunk_md_body or "").strip()
    at = (generator_append_text or "").strip()
    if not at:
        return base
    return (
        f"{base}\n\n---\n"
        "Ниже — детерминированное дополнение к ответу пользователю (не из LLM-генератора по чанку). "
        "Для verifier это часть разрешённого контекста фактов наравне с основным источником:\n\n"
        f"{at}"
    )


def ensure_answer(answer: str, chunk: dict) -> str:
    if isinstance(answer, str) and answer.strip():
        return answer
    return (
        "Сейчас не получилось сформулировать ответ. "
        "Попробуйте переформулировать вопрос или выберите тему ниже."
    )


def _answer_format_context(
    *,
    user_question: str,
    chunk: dict,
    meta: dict | None = None,
) -> AnswerFormatContext:
    m = meta if isinstance(meta, dict) else {}
    doc_id = str(m.get("doc_id") or "").strip()
    if not doc_id:
        doc_id = os.path.splitext(os.path.basename(str(chunk.get("file") or "")))[0]
    return AnswerFormatContext(
        user_question=user_question,
        h2=str(chunk.get("h2") or "") or None,
        h3=str(chunk.get("h3") or "") or None,
        doc_id=doc_id or None,
    )


def format_generator_answer(
    answer: str,
    *,
    user_question: str,
    chunk: dict,
    meta: dict | None = None,
) -> str:
    """Пост-оформление ответа Generator (вводная перед списком в начале)."""
    ctx = _answer_format_context(user_question=user_question, chunk=chunk, meta=meta)
    return format_answer_for_display(answer, ctx)


def _persist_subject_focus(
    *,
    sid: str,
    client_id: str | None,
    doc_id: str | None,
    matched_service_id: str | None,
    route: str,
    meta: dict,
    skip_topic: bool,
    answer: str,
) -> None:
    if skip_topic or not (answer or "").strip():
        return
    if route in (
        "guided",
        "lead_cancelled",
        "retrieval_no_candidates",
        "low_score_fallback",
        "error",
    ):
        return
    from core.follow_up_rewrite import resolve_focus_from_turn
    from session import set_last_catalog_service, set_last_subject

    focus = resolve_focus_from_turn(
        client_id=client_id,
        doc_id=doc_id,
        matched_service_id=matched_service_id,
        route=route,
        meta=meta,
    )
    if not focus:
        return
    set_last_subject(
        sid,
        service_id=focus["service_id"],
        topic=focus["topic"],
        label=focus["label"],
        last_route=str(focus.get("last_route") or route),
    )
    set_last_catalog_service(sid, focus["service_id"])


def meta_for_chunk(chunk: dict, client_id: str | None = None) -> dict:
    meta = get_doc_meta(
        os.path.basename(chunk.get("file", "") or ""),
        client_id=client_id or chunk.get("client_id"),
    ) or {}
    meta = dict(meta)
    if not meta.get("doc_id"):
        meta["doc_id"] = os.path.splitext(os.path.basename(chunk.get("file", "") or ""))[0]
    return meta


def _packet_composer_generation(
    *,
    q: str,
    llm_question: str | None,
    meta: dict,
    chunk: dict,
    sid: str,
    client_id: str | None,
    route: str,
    matched_service_id: str | None,
    doc_id: str | None,
) -> dict[str, Any] | None:
    """Try packet composer path (multi-aspect plan + >=2 materialized cards). None → single-source."""
    if not COMPOSER_ON:
        return None
    plan = answer_plan_from_ctx()
    if plan is None:
        return None
    if _real_aspect_count(plan.aspects) < 2:
        meta["composer_skip_reason"] = "single_aspect"
        return None
    svc_id = (
        str(matched_service_id or meta.get("matched_service_id") or plan.service_id or "").strip()
        or None
    )
    chunk_ref = None
    if doc_id:
        h3 = str(chunk.get("h3_id") or "").strip()
        chunk_ref = f"{doc_id}.md#{h3}" if h3 else f"{doc_id}.md"
    packet = assemble_answer_packet(
        plan,
        client_id=client_id,
        route=route,
        service_id=svc_id,
        primary_chunk_ref=chunk_ref,
    )
    materialized = materialize_cards(packet, client_id=client_id)
    if len(materialized) < 2:
        return None
    answer, profile = generate_answer_from_packet(
        llm_question or q,
        materialized,
        meta,
        sid,
    )
    if not profile.get("composer_used"):
        return None
    hits = detect_forbidden_claims(answer)
    if hits:
        meta["composer_skip_reason"] = "forbidden_claim"
        meta["forbidden_claim_hits"] = hits
        return None
    publish_answer_packet(packet)
    if plan.primary_aspect:
        set_last_aspect(sid, plan.primary_aspect)
    allowed_source = "\n\n".join(
        c.text for c in materialized if (c.text or "").strip()
    )
    return {
        "answer": answer,
        "profile": profile,
        "deterministic_append": allowed_source,
        "plan_meta": {
            "answer_plan": plan.model_dump(),
            "answer_packet": packet.model_dump(),
        },
        "slot_meta": None,
    }


def _composer_display_chunk(
    *,
    client_id: str | None,
    matched_service_id: str | None,
    primary_chunk_ref: str | None,
) -> dict:
    ref = (primary_chunk_ref or "").strip()
    if ref:
        ch = get_chunk_by_ref(ref, client_id=client_id)
        if isinstance(ch, dict):
            out = dict(ch)
            out.setdefault("_score", 1.0)
            return out
    sid = (matched_service_id or "").strip()
    if sid:
        for guess in (
            f"implantation__service__{sid}.md#korotko",
            f"extraction__service__{sid}.md#korotko",
            f"treatment__service__{sid}.md#korotko",
        ):
            ch = get_chunk_by_ref(guess, client_id=client_id)
            if isinstance(ch, dict):
                out = dict(ch)
                out.setdefault("_score", 1.0)
                return out
    return {"file": "composer.md", "h3_id": None, "h2_id": None, "_score": 1.0}


def respond_from_composer(
    *,
    composed_answer: str,
    materialized_cards: list,
    q: str,
    sid: str,
    client_id: str | None,
    matched_service_id: str | None,
    route: str,
    primary_chunk_ref: str | None,
    finalize_ask: Callable[..., dict],
    logger,
    log_event: str = "Answer generated from composer",
) -> dict:
    """Build full /ask payload for composer overlay (no slots/price append)."""
    from core.consult_nudge import record_consult_nudge_after_answer
    from core.follow_up_rewrite import persist_focus_from_service_turn

    if (q or "").strip():
        mem_add_user(sid, q)
    skip_topic = lead_interrupt_no_topic()
    chunk = _composer_display_chunk(
        client_id=client_id,
        matched_service_id=matched_service_id,
        primary_chunk_ref=primary_chunk_ref,
    )
    meta = meta_for_chunk(chunk, client_id=client_id)
    if client_id is not None:
        meta["client_id"] = client_id
    sid_svc = str(matched_service_id or "").strip()
    if sid_svc:
        meta["matched_service_id"] = sid_svc
    doc_id = meta.get("doc_id")
    if doc_id and not skip_topic:
        set_current_doc(sid, doc_id)

    answer = ensure_answer(str(composed_answer or ""), chunk)
    answer = format_generator_answer(
        answer,
        user_question=q,
        chunk=chunk,
        meta=meta,
    )
    meta["answer_path"] = "composer"

    plan = answer_plan_from_ctx()
    if plan is not None and plan.primary_aspect:
        set_last_aspect(sid, plan.primary_aspect)

    allowed_source = "\n\n".join(
        str(getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else "") or "").strip()
        for c in (materialized_cards or [])
        if str(getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else "") or "").strip()
    )
    answer, numeric_gate_meta = _apply_numeric_fact_gate(
        answer=answer,
        route=route,
        meta=meta,
        client_id=client_id,
        deterministic_append=allowed_source,
        price_offer_meta=None,
    )

    _persist_subject_focus(
        sid=sid,
        client_id=client_id,
        doc_id=doc_id,
        matched_service_id=sid_svc or None,
        route=route,
        meta=meta,
        skip_topic=skip_topic,
        answer=answer,
    )
    if route in {"price_lookup", "price_concern"} and sid_svc:
        persist_focus_from_service_turn(
            sid,
            client_id=client_id,
            matched_service_id=sid_svc,
            route=route,
            answer=answer,
            topic=(plan.topic if plan else None),
        )

    st = mem_get(sid)
    lead_context = is_lead_context(st)
    pre_turn = _increment_doc_turn_with_pre(
        sid,
        doc_id,
        contentful=bool(answer.strip()),
        is_low_score=False,
        is_error=False,
        lead_flow_active=lead_context,
    )
    tstate = get_topic_state(sid, doc_id) if doc_id else {}

    plan_meta: dict[str, Any] | None = None
    if plan is not None:
        plan_meta = {"answer_plan": plan.model_dump()}
        try:
            from core.answer_packet_snapshot import answer_packet_from_ctx

            packet = answer_packet_from_ctx()
            if packet is not None:
                plan_meta["answer_packet"] = packet.model_dump()
        except Exception:
            pass

    s0_ref = source_ref_from_chunk(chunk)
    generator_input = {
        "source_ref": s0_ref,
        "source_count": len(materialized_cards or []),
        "route": route,
        "doc_id": meta.get("doc_id"),
        "doc_type": meta.get("doc_type"),
        "subtype": meta.get("subtype"),
        "h2_id": chunk.get("h2_id"),
        "h3_id": chunk.get("h3_id"),
        "composer": True,
    }

    payload = build_ask_response(
        answer=answer,
        top=chunk,
        meta=meta,
        sid=sid,
        profile={},
        client_id=client_id,
        topic_state=tstate,
        suppress_refs=_plan_append_suppress_refs(plan_meta, doc_id=doc_id, answer_body=answer),
    )
    if route:
        payload.setdefault("meta", {})["orch_route"] = route
    payload.setdefault("meta", {})["answer_path"] = "composer"
    if plan_meta:
        payload.setdefault("meta", {}).update(plan_meta)
    if numeric_gate_meta:
        payload.setdefault("meta", {}).update(numeric_gate_meta)
    _apply_patient_playbook_ui(payload, route)
    payload = _apply_response_policy_compat(
        payload,
        st,
        q,
        topic_state=tstate,
        doc_meta=meta,
        pre_doc_turn_count=pre_turn,
        session_id=sid,
        client_id=client_id,
    )
    payload = normalize_policy_payload(payload)
    payload.setdefault("meta", {})["generator_input"] = generator_input

    consult_meta = (
        {}
        if lead_context
        else record_consult_nudge_after_answer(sid, route, None, answer)
    )
    if consult_meta:
        payload.setdefault("meta", {}).update(consult_meta)

    log_json(
        logger,
        log_event,
        file=chunk.get("file"),
        score=round(float(chunk.get("_score", 0.0)), 3),
        answer_length=len(answer),
        generator_input=generator_input,
        answer_path="composer",
    )
    qs = (q or "").strip()
    turn_meta = (
        {"interaction": "user_message", "question_len": len(qs), "preview": qs[:120]}
        if qs
        else None
    )
    out = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    bot_text = str(out.get("answer") or answer).strip()
    if bot_text:
        mem_add_bot(sid, bot_text)
    return out


def respond_from_chunk(
    *,
    chunk: dict,
    q: str,
    sid: str,
    client_id: str | None,
    finalize_ask: Callable[..., dict],
    safe_jsonify: Callable[[dict], Any],
    logger,
    llm_question: str | None = None,
    log_event: str = "Answer generated",
    route: str = "retrieval_chunk",
    generator_append_text: str | None = None,
    price_offer_meta: dict | None = None,
    matched_service_id: str | None = None,
):
    if (q or "").strip():
        mem_add_user(sid, q)
    skip_topic = lead_interrupt_no_topic()
    meta = meta_for_chunk(chunk, client_id=client_id)
    if client_id is not None:
        meta["client_id"] = client_id
    sid_svc = str(matched_service_id or "").strip()
    if sid_svc:
        meta["matched_service_id"] = sid_svc
    doc_id = meta.get("doc_id")
    if doc_id and not skip_topic:
        set_current_doc(sid, doc_id)

    sources = [build_generator_source_from_chunk(chunk, meta)]
    s0 = sources[0]
    generator_input = {
        "source_ref": s0.get("ref"),
        "source_count": 1,
        "route": route,
        "doc_id": s0.get("doc_id"),
        "doc_type": s0.get("doc_type"),
        "subtype": s0.get("subtype"),
        "h2_id": chunk.get("h2_id"),
        "h3_id": chunk.get("h3_id"),
    }

    tstate_pre = get_topic_state(sid, doc_id) if doc_id else {}
    planned_nudge = _planned_consult_nudge_for_chunk(
        sid=sid,
        route=route,
        meta=meta,
        chunk=chunk,
        topic_state=tstate_pre,
        client_id=client_id,
    )

    composer_hit: dict[str, Any] | None = None
    try:
        composer_hit = _packet_composer_generation(
            q=q,
            llm_question=llm_question,
            meta=meta,
            chunk=chunk,
            sid=sid,
            client_id=client_id,
            route=route,
            matched_service_id=sid_svc or None,
            doc_id=doc_id,
        )
    except Exception:
        composer_hit = None

    if composer_hit is not None:
        answer = str(composer_hit.get("answer") or "")
        profile = composer_hit.get("profile") or {}
        meta["answer_path"] = "composer"
    else:
        answer, profile = generate_answer_with_empathy(
            llm_question or q, sources, meta, sid
        )
        meta["answer_path"] = "single_source"

    answer = ensure_answer(answer, chunk)
    answer = format_generator_answer(
        answer, user_question=llm_question or q, chunk=chunk, meta=meta
    )
    _persist_subject_focus(
        sid=sid,
        client_id=client_id,
        doc_id=doc_id,
        matched_service_id=sid_svc or None,
        route=route,
        meta=meta,
        skip_topic=skip_topic,
        answer=answer,
    )
    st_pre = mem_get(sid)
    lead_context = is_lead_context(st_pre)
    answer, doctor_bridge_meta = _append_doctor_consult_bridge(
        answer=answer,
        meta=meta,
        route=route,
        client_id=client_id,
    )
    if composer_hit is not None:
        slot_meta = composer_hit.get("slot_meta")
        deterministic_append = str(composer_hit.get("deterministic_append") or "")
        plan_meta = composer_hit.get("plan_meta")
    else:
        answer, slot_meta, deterministic_append, plan_meta = _apply_answer_slots_and_price_append(
            answer=answer,
            meta=meta,
            chunk=chunk,
            q=q,
            route=route,
            sid=sid,
            doc_id=doc_id,
            generator_append_text=generator_append_text,
            lead_context=lead_context,
            price_offer_meta=price_offer_meta,
            matched_service_id=sid_svc or None,
            skip_answer_slots_reason="doctor_consult_bridge" if doctor_bridge_meta else None,
        )
    answer, numeric_gate_meta = _apply_numeric_fact_gate(
        answer=answer,
        route=route,
        meta=meta,
        client_id=client_id,
        deterministic_append=deterministic_append,
        price_offer_meta=price_offer_meta,
    )

    st = mem_get(sid)
    pre_turn = _increment_doc_turn_with_pre(
        sid,
        doc_id,
        contentful=bool(answer.strip()),
        is_low_score=False,
        is_error=False,
        lead_flow_active=lead_context,
    )
    tstate = get_topic_state(sid, doc_id) if doc_id else {}
    suggest_h3 = set(meta.get("suggest_h3") or [])
    h3_id = chunk.get("h3_id")
    if h3_id and h3_id in suggest_h3 and not skip_topic:
        mark_h3_covered(sid, doc_id, h3_id)
        tstate = get_topic_state(sid, doc_id)

    consult_meta = (
        {}
        if lead_context
        else record_consult_nudge_after_answer(sid, route, planned_nudge, answer)
    )

    suppress_refs = _nav_ref_suppress_list() + _plan_append_suppress_refs(
        plan_meta,
        doc_id=doc_id,
        answer_body=answer,
    )
    payload = build_ask_response(
        answer=answer,
        top=chunk,
        meta=meta,
        sid=sid,
        profile=profile,
        client_id=client_id,
        topic_state=tstate,
        suppress_refs=suppress_refs,
    )
    if route:
        payload.setdefault("meta", {})["orch_route"] = route
    if meta.get("answer_path"):
        payload.setdefault("meta", {})["answer_path"] = meta["answer_path"]
    if meta.get("composer_skip_reason"):
        payload.setdefault("meta", {})["composer_skip_reason"] = meta["composer_skip_reason"]
    if meta.get("forbidden_claim_hits"):
        payload.setdefault("meta", {})["forbidden_claim_hits"] = meta["forbidden_claim_hits"]
    if route == "price_concern":
        payload.setdefault("meta", {})["intent"] = "price_concern"
    _apply_patient_playbook_ui(payload, route)
    if slot_meta:
        payload.setdefault("meta", {})["answer_slots"] = slot_meta
    if plan_meta:
        payload.setdefault("meta", {}).update(plan_meta)
    if numeric_gate_meta:
        payload.setdefault("meta", {}).update(numeric_gate_meta)
    _merge_price_offer_meta_into_payload(payload, price_offer_meta=price_offer_meta)
    if doctor_bridge_meta:
        payload.setdefault("meta", {}).update(doctor_bridge_meta)
    if consult_meta:
        payload.setdefault("meta", {}).update(consult_meta)
    payload = _apply_response_policy_compat(
        payload,
        st,
        q,
        topic_state=tstate,
        doc_meta=meta,
        pre_doc_turn_count=pre_turn,
        session_id=sid,
        client_id=client_id,
    )
    refs_before_ui = list(payload.get("quick_replies") or [])
    payload = normalize_policy_payload(payload)
    payload.setdefault("meta", {})["generator_input"] = generator_input
    pdec = (payload.get("meta") or {}).get("policy_decision") or {}
    ui_dropped = set((payload.get("meta") or {}).get("ui_dropped") or [])
    if doc_id and not skip_topic:
        if bool(pdec.get("show_video")):
            mark_video_shown(sid, doc_id)
        elif meta.get("video_key") and not bool(get_topic_state(sid, doc_id).get("video_shown")):
            mark_video_pending(sid, doc_id, pending=True)

        sit = payload.get("situation") or {}
        if sit.get("show") and sit.get("mode") == "normal":
            mark_situation_offered(sid, doc_id)

        if bool(pdec.get("defer_refs")):
            defer_refs(sid, doc_id, pdec.get("refs_to_defer") or [])
        elif "refs_with_two_followups_conflict" in ui_dropped and refs_before_ui:
            defer_refs(sid, doc_id, refs_before_ui[:1])
        elif payload.get("quick_replies"):
            _mark_suggest_ref_used_compat(sid, doc_id, True)
            tstate_after = get_topic_state(sid, doc_id)
            if tstate_after.get("refs_deferred"):
                pop_deferred_ref(sid, doc_id)

    if payload.get("cta") and doc_id and not skip_topic:
        set_cta_shown(sid, doc_id, shown=True)

    verifier_src = verifier_effective_source_body(
        chunk_md_body=str(s0.get("content") or ""),
        generator_append_text=deterministic_append or None,
    )
    v_trace = build_turn_trace_prefix(
        answer=str(payload.get("answer") or answer),
        source_ref=str(generator_input.get("source_ref") or ""),
        source_text=verifier_src,
    )
    v_trace["verifier_source_has_deterministic_append"] = bool((deterministic_append or "").strip())
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["verifier_turn"] = v_trace
    except Exception:
        pass
    final_answer = str(payload.get("answer") or answer)
    schedule_verifier_shadow_if_needed(
        answer=final_answer,
        source_text=verifier_src,
        source_ref=str(generator_input.get("source_ref") or ""),
        sid=sid,
        client_id=client_id,
        route=route,
        logger_=logger,
        trace_prefix=v_trace,
    )

    log_json(
        logger,
        log_event,
        file=chunk.get("file"),
        score=round(float(chunk.get("_score", 0.0)), 3),
        answer_length=len(final_answer),
        generator_input=generator_input,
        verifier_triggered=v_trace.get("verifier_triggered"),
        verifier_trigger_reason=v_trace.get("verifier_trigger_reason"),
    )
    qs = (q or "").strip()
    turn_meta = (
        {"interaction": "user_message", "question_len": len(qs), "preview": qs[:120]}
        if qs
        else None
    )
    out = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    bot_text = str(out.get("answer") or answer).strip()
    if bot_text:
        mem_add_bot(sid, bot_text)
    return safe_jsonify(out)


def respond_from_chunk_stream(
    *,
    chunk: dict,
    q: str,
    sid: str,
    client_id: str | None,
    finalize_ask: Callable[..., dict],
    logger,
    llm_question: str | None = None,
    log_event: str = "Answer generated",
    route: str = "retrieval_chunk",
    generator_append_text: str | None = None,
    price_offer_meta: dict | None = None,
    matched_service_id: str | None = None,
):
    """Generator yielding SSE strings: typing → text_delta → ui → done.

    Используй с Flask: Response(respond_from_chunk_stream(...), mimetype='text/event-stream')
    Полностью зеркалит respond_from_chunk, но стримит токены ответа.
    """
    yield 'event: typing\ndata: {"phase": "searching"}\n\n'
    if (q or "").strip():
        mem_add_user(sid, q)
    skip_topic = lead_interrupt_no_topic()
    meta = meta_for_chunk(chunk, client_id=client_id)
    if client_id is not None:
        meta["client_id"] = client_id
    sid_svc = str(matched_service_id or "").strip()
    if sid_svc:
        meta["matched_service_id"] = sid_svc
    doc_id = meta.get("doc_id")
    if doc_id and not skip_topic:
        set_current_doc(sid, doc_id)

    sources = [build_generator_source_from_chunk(chunk, meta)]
    s0 = sources[0]
    generator_input = {
        "source_ref": s0.get("ref"),
        "source_count": 1,
        "route": route,
        "doc_id": s0.get("doc_id"),
        "doc_type": s0.get("doc_type"),
        "subtype": s0.get("subtype"),
        "h2_id": chunk.get("h2_id"),
        "h3_id": chunk.get("h3_id"),
    }

    tstate_pre = get_topic_state(sid, doc_id) if doc_id else {}
    planned_nudge = _planned_consult_nudge_for_chunk(
        sid=sid,
        route=route,
        meta=meta,
        chunk=chunk,
        topic_state=tstate_pre,
        client_id=client_id,
    )

    fmt_ctx = _answer_format_context(
        user_question=llm_question or q, chunk=chunk, meta=meta
    )
    stream_acc = StreamTextAccumulator(ctx=fmt_ctx)
    full_text = ""
    profile: dict = {}
    writing_phase_sent = False

    def _yield_delta(display_delta: str) -> str:
        return (
            f"event: text_delta\ndata: "
            f"{_json.dumps({'delta': display_delta}, ensure_ascii=False)}\n\n"
        )

    try:
        for event_type, value in generate_answer_stream(
            llm_question or q, sources, meta, sid
        ):
            if event_type == "delta":
                full_text += value
                if not writing_phase_sent:
                    writing_phase_sent = True
                    yield 'event: typing\ndata: {"phase": "writing"}\n\n'
                out = stream_acc.ingest_llm_delta(value)
                if out:
                    yield _yield_delta(out)
            elif event_type == "done":
                full_text, profile = value
    except Exception as e:
        log_json(logger, "stream_chunk_failed", sid=sid, err=str(e)[:300])
        if not full_text.strip():
            full_text = LLM_FALLBACK_ANSWER

    raw_final = ensure_answer(full_text, chunk)
    if not writing_phase_sent and (raw_final or "").strip():
        writing_phase_sent = True
        yield 'event: typing\ndata: {"phase": "writing"}\n\n'

    tail = stream_acc.finalize(raw_final)
    if tail:
        yield _yield_delta(tail)

    answer_base = format_answer_for_display(raw_final, fmt_ctx)
    _persist_subject_focus(
        sid=sid,
        client_id=client_id,
        doc_id=doc_id,
        matched_service_id=sid_svc or None,
        route=route,
        meta=meta,
        skip_topic=skip_topic,
        answer=answer_base,
    )
    st_pre = mem_get(sid)
    lead_context = is_lead_context(st_pre)
    answer_base, doctor_bridge_meta = _append_doctor_consult_bridge(
        answer=answer_base,
        meta=meta,
        route=route,
        client_id=client_id,
    )
    answer, slot_meta, deterministic_append, plan_meta = _apply_answer_slots_and_price_append(
        answer=answer_base,
        meta=meta,
        chunk=chunk,
        q=q,
        route=route,
        sid=sid,
        doc_id=doc_id,
        generator_append_text=generator_append_text,
        lead_context=lead_context,
        price_offer_meta=price_offer_meta,
        matched_service_id=sid_svc or None,
        skip_answer_slots_reason="doctor_consult_bridge" if doctor_bridge_meta else None,
    )
    answer, numeric_gate_meta = _apply_numeric_fact_gate(
        answer=answer,
        route=route,
        meta=meta,
        client_id=client_id,
        deterministic_append=deterministic_append,
        price_offer_meta=price_offer_meta,
    )
    append_delta = answer[stream_acc.display_sent_len :]
    if append_delta:
        yield _yield_delta(append_delta)
        stream_acc.display_sent_len = len(answer)

    # Все session side-effects — идентично respond_from_chunk
    st = mem_get(sid)
    pre_turn = _increment_doc_turn_with_pre(
        sid,
        doc_id,
        contentful=bool(answer.strip()),
        is_low_score=False,
        is_error=False,
        lead_flow_active=lead_context,
    )
    tstate = get_topic_state(sid, doc_id) if doc_id else {}
    suggest_h3 = set(meta.get("suggest_h3") or [])
    h3_id = chunk.get("h3_id")
    if h3_id and h3_id in suggest_h3 and not skip_topic:
        mark_h3_covered(sid, doc_id, h3_id)
        tstate = get_topic_state(sid, doc_id)

    consult_meta = (
        {}
        if lead_context
        else record_consult_nudge_after_answer(sid, route, planned_nudge, answer)
    )

    suppress_refs = _nav_ref_suppress_list() + _plan_append_suppress_refs(
        plan_meta,
        doc_id=doc_id,
        answer_body=answer,
    )
    payload = build_ask_response(
        answer=answer,
        top=chunk,
        meta=meta,
        sid=sid,
        profile=profile,
        client_id=client_id,
        topic_state=tstate,
        suppress_refs=suppress_refs,
    )
    if route:
        payload.setdefault("meta", {})["orch_route"] = route
    if route == "price_concern":
        payload.setdefault("meta", {})["intent"] = "price_concern"
    _apply_patient_playbook_ui(payload, route)
    if slot_meta:
        payload.setdefault("meta", {})["answer_slots"] = slot_meta
    if plan_meta:
        payload.setdefault("meta", {}).update(plan_meta)
    if numeric_gate_meta:
        payload.setdefault("meta", {}).update(numeric_gate_meta)
    _merge_price_offer_meta_into_payload(payload, price_offer_meta=price_offer_meta)
    if doctor_bridge_meta:
        payload.setdefault("meta", {}).update(doctor_bridge_meta)
    if consult_meta:
        payload.setdefault("meta", {}).update(consult_meta)
    payload = _apply_response_policy_compat(
        payload,
        st,
        q,
        topic_state=tstate,
        doc_meta=meta,
        pre_doc_turn_count=pre_turn,
        session_id=sid,
        client_id=client_id,
    )
    refs_before_ui = list(payload.get("quick_replies") or [])
    payload = normalize_policy_payload(payload)
    payload.setdefault("meta", {})["generator_input"] = generator_input
    pdec = (payload.get("meta") or {}).get("policy_decision") or {}
    ui_dropped = set((payload.get("meta") or {}).get("ui_dropped") or [])

    if doc_id and not skip_topic:
        if bool(pdec.get("show_video")):
            mark_video_shown(sid, doc_id)
        elif meta.get("video_key") and not bool(get_topic_state(sid, doc_id).get("video_shown")):
            mark_video_pending(sid, doc_id, pending=True)
        sit = payload.get("situation") or {}
        if sit.get("show") and sit.get("mode") == "normal":
            mark_situation_offered(sid, doc_id)
        if bool(pdec.get("defer_refs")):
            defer_refs(sid, doc_id, pdec.get("refs_to_defer") or [])
        elif "refs_with_two_followups_conflict" in ui_dropped and refs_before_ui:
            defer_refs(sid, doc_id, refs_before_ui[:1])
        elif payload.get("quick_replies"):
            _mark_suggest_ref_used_compat(sid, doc_id, True)
            tstate_after = get_topic_state(sid, doc_id)
            if tstate_after.get("refs_deferred"):
                pop_deferred_ref(sid, doc_id)

    if payload.get("cta") and doc_id and not skip_topic:
        set_cta_shown(sid, doc_id, shown=True)

    verifier_src = verifier_effective_source_body(
        chunk_md_body=str(s0.get("content") or ""),
        generator_append_text=deterministic_append or None,
    )
    v_trace = build_turn_trace_prefix(
        answer=str(payload.get("answer") or answer),
        source_ref=str(generator_input.get("source_ref") or ""),
        source_text=verifier_src,
    )
    v_trace["verifier_source_has_deterministic_append"] = bool((deterministic_append or "").strip())
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["verifier_turn"] = v_trace
    except Exception:
        pass
    final_answer = str(payload.get("answer") or answer)
    schedule_verifier_shadow_if_needed(
        answer=final_answer,
        source_text=verifier_src,
        source_ref=str(generator_input.get("source_ref") or ""),
        sid=sid,
        client_id=client_id,
        route=route,
        logger_=logger,
        trace_prefix=v_trace,
    )

    log_json(
        logger,
        log_event,
        file=chunk.get("file"),
        score=round(float(chunk.get("_score", 0.0)), 3),
        answer_length=len(final_answer),
        generator_input=generator_input,
        verifier_triggered=v_trace.get("verifier_triggered"),
        verifier_trigger_reason=v_trace.get("verifier_trigger_reason"),
    )
    qs = (q or "").strip()
    turn_meta = (
        {"interaction": "user_message", "question_len": len(qs), "preview": qs[:120]}
        if qs
        else None
    )
    final = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    bot_text = str(final.get("answer") or final_answer).strip()
    if bot_text:
        mem_add_bot(sid, bot_text)
    yield f"event: ui\ndata: {_json.dumps(final, ensure_ascii=False, default=_sse_default)}\n\n"
    yield "event: done\ndata: {}\n\n"


def _sse_default(obj):
    """JSON default для SSE — обрабатывает numpy типы из retrieval."""
    try:
        import numpy as np
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
