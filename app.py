import os
import re
import sys
import time
import json
import threading
from datetime import datetime, timezone
from typing import Any
from collections import deque
import numpy as np

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)
from pg_sink import enqueue_v5_turn_trace, init_pg_sink

from config import DEBUG_TOKEN, PORT
from core.client_host import resolve_request_client_id
from contracts.ask_orchestration import AskOrchestrationResult
from core.client_config_loader import load_widget_config, tone_to_txt_dict
from core.origin_guard import validate_widget_origin
from core.widget_cors import (
    apply_widget_cors_headers,
    widget_cors_preflight_response,
)
from core.routing_loader import THRESHOLDS
from core.video_catalog_loader import catalog_for_widget, get_external_video_src
from lead_service import handle_lead
from core.observability_pii import observability_turn_preview, observability_user_texts
from logging_setup import LOG_FILE, emit_bot_event, get_logger, make_request_context, log_json, redact_text
from chunk_responder import respond_from_chunk, respond_from_chunk_stream
from retriever import (
    alias_debug_score_for_chunk,
    best_alias_hit_in_corpus,
    normalize_retrieval_query,
    retrieve,
)
from session import (
    bind_client_id,
    get_topic_state,
    mem_add_bot,
    mem_add_user,
    mem_get,
    is_active_lead_flow,
    record_last_bot_payload,
)
from orchestration.ask_turn import orchestrate_routing_after_resolver
from orchestration.helpers import get_last_content_ui_payload_compat
from orchestration.lead_flow import build_service_payload, lead_flow_orchestration_result
from orchestration.policy_compat import apply_response_policy_compat
from orchestration.finalize_turn import finalize_ask
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from orchestration.resolver_turn import run_resolver_turn
from orchestration.route_guards import resolve_client_ip
from policy import apply_ui_source_policy
from ux_builder import internal_error_response, normalize_policy_payload, reset_session_response


def _enqueue_v5_resolver_trace(
    *,
    decision,
    safety_net_used: list[str],
    resolver_bypassed_env: bool,
) -> None:
    ctx = getattr(request, "ctx", None) or {}
    turn_id = ctx.get("request_id")
    if not turn_id:
        return
    try:
        enqueue_v5_turn_trace(
            {
                "turn_id": str(turn_id),
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "sid": ctx.get("sid"),
                "client_id": ctx.get("client_id"),
                "request_id": str(turn_id),
                "gate_traces": [],
                "decision_frame": decision.model_dump() if decision is not None else None,
                "retrieval_candidates": [],
                "errors": [],
                "safety_net_used": list(safety_net_used),
                "resolver_bypassed_env": bool(resolver_bypassed_env),
            }
        )
    except Exception:
        pass


app = Flask(__name__, static_folder="static")
logger = get_logger("bot")
APP_ENV = (os.getenv("APP_ENV") or "local").strip().lower()
init_pg_sink(logger)


def _client_txt(client_id: str | None) -> dict[str, str]:
    return tone_to_txt_dict(client_id)


def _skip_lead_pii_in_session_hist(payload: dict) -> bool:
    pmeta = payload.get("meta") or {}
    return bool(pmeta.get("lead_flow") or pmeta.get("situation_collect"))


def _suppress_plan_append_quick_replies(payload: dict, plan_apply_meta: dict[str, Any]) -> None:
    from core.answer_plan_apply import payment_terms_suppress_refs
    from core.price_answer_assembler import hide_navigated_quick_replies

    meta = payload.get("meta") or {}
    suppress_list = payment_terms_suppress_refs(
        plan_meta={
            "answer_plan": meta.get("answer_plan"),
            "answer_plan_apply": plan_apply_meta,
        },
        doc_id=meta.get("doc_id"),
        answer_body=str(payload.get("answer") or ""),
    )
    if not suppress_list:
        return
    suppress = {str(r).strip().lower() for r in suppress_list if str(r).strip()}
    payload["quick_replies"] = hide_navigated_quick_replies(
        list(payload.get("quick_replies") or []),
        exclude_refs=suppress,
    )
    meta = payload.setdefault("meta", {})
    if isinstance(meta.get("followups"), list):
        meta["followups"] = hide_navigated_quick_replies(
            list(meta.get("followups") or []),
            exclude_refs=suppress,
        )


def _service_reply(
    payload: dict,
    sid: str,
    q: str,
    *,
    doc_id: str | None = None,
    track_user: bool = True,
    route: str | None = None,
):
    from core.answer_plan_apply import apply_answer_plan_append
    from core.answer_packet_snapshot import build_and_publish_answer_packet
    from core.answer_planner import answer_plan_from_ctx
    from core.consult_nudge import record_consult_nudge_after_answer, reset_consult_nudge_on_route
    from session import set_last_aspect

    reset_consult_nudge_on_route(route, sid)
    if track_user and q and not _skip_lead_pii_in_session_hist(payload):
        mem_add_user(sid, q)
    if route:
        payload.setdefault("meta", {})["service_route"] = str(route).strip()
    r = (route or "").strip().lower()
    plan = answer_plan_from_ctx()
    pmeta = payload.get("meta") or {}
    if plan is not None and r in {"price_lookup", "price_concern", "catalog_facts"}:
        svc_id = str(pmeta.get("matched_service_id") or plan.service_id or "").strip() or None
        plan_tail, plan_apply_meta = apply_answer_plan_append(
            plan,
            client_id=pmeta.get("client_id"),
            service_id=svc_id,
            q=q,
            existing_append=None,
            price_offer_meta=pmeta if isinstance(pmeta, dict) else None,
            answer_body=str(payload.get("answer") or ""),
        )
        if plan_tail:
            base = str(payload.get("answer") or "").strip()
            if plan_tail not in base:
                payload["answer"] = f"{base}\n\n{plan_tail}" if base else plan_tail
        if plan.primary_aspect:
            set_last_aspect(sid, plan.primary_aspect)
        payload.setdefault("meta", {})["answer_plan"] = plan.model_dump()
        packet = build_and_publish_answer_packet(
            plan,
            client_id=pmeta.get("client_id"),
            route=r,
            service_id=svc_id,
            apply_meta=plan_apply_meta,
        )
        payload.setdefault("meta", {})["answer_packet"] = packet.model_dump()
        if plan_apply_meta.get("applied") or plan_apply_meta.get("suppressed"):
            _suppress_plan_append_quick_replies(payload, plan_apply_meta)
            payload.setdefault("meta", {})["answer_plan_apply"] = plan_apply_meta
    if (
        r in {"price_lookup", "price_concern", "catalog_facts"}
        and not _skip_lead_pii_in_session_hist(payload)
    ):
        from core.follow_up_rewrite import persist_focus_from_service_turn

        pmeta = payload.get("meta") or {}
        svc_id = str(pmeta.get("matched_service_id") or "").strip() or None
        topic = (plan.topic if plan else None) or str(pmeta.get("service_topic") or "").strip() or None
        persist_focus_from_service_turn(
            sid,
            client_id=pmeta.get("client_id"),
            matched_service_id=svc_id,
            route=r,
            answer=str(payload.get("answer") or ""),
            topic=topic,
        )
    if r == "price_lookup" and not is_active_lead_flow(mem_get(sid)):
        pmeta = payload.get("meta") or {}
        record_consult_nudge_after_answer(
            sid,
            route,
            pmeta.get("consult_nudge"),
            str(payload.get("answer") or ""),
        )
    payload = apply_ui_source_policy(payload, route=route)
    payload = normalize_policy_payload(payload)
    answer = (payload.get("answer") or "").strip()
    turn_meta = None
    if track_user and (q or "").strip():
        qs = (q or "").strip()
        pmeta = payload.get("meta") or {}
        turn_meta = {
            "interaction": "user_message",
            "question_len": len(qs),
            "preview": observability_turn_preview(qs, route=route, meta=pmeta),
        }
    out = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    if answer:
        mem_add_bot(sid, answer)
    return safe_jsonify(out)


def _to_plain(o):
    import numpy as _np

    if isinstance(o, (_np.floating,)):
        return float(o)
    if isinstance(o, (_np.integer,)):
        return int(o)
    if isinstance(o, _np.ndarray):
        return o.tolist()
    if isinstance(o, set):
        return list(o)
    return o


def _sanitize(x):
    if isinstance(x, dict):
        return {k: _sanitize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sanitize(v) for v in x]
    return _to_plain(x)


def _resolve_request_ip() -> str:
    return resolve_client_ip(
        x_forwarded_for=request.headers.get("X-Forwarded-For"),
        remote_addr=request.remote_addr,
    )


def safe_jsonify(payload):
    return jsonify(_sanitize(payload))


def _bind_chat_ctx(sid: str, client_id: str) -> None:
    """sid/client_id для логов + SQLite (dashboard)."""
    request.ctx["sid"] = sid
    request.ctx["session_id"] = sid
    request.ctx["client_id"] = client_id
    bind_client_id(sid, client_id)


def _widget_origin_forbidden(client_id: str | None):
    err = validate_widget_origin(client_id)
    if not err:
        return None
    return safe_jsonify({"error": err, "client_id": client_id}), 403


def _startup_check() -> None:
    from core.startup_check import run_startup_check

    run_startup_check(logger)


_startup_check()


@app.before_request
def _before():
    request.ctx = make_request_context(cookie_sid=request.cookies.get("sid"))
    request.ctx["path"] = request.path
    request.ctx["method"] = request.method
    request.ctx["t0"] = time.time()


@app.before_request
def _widget_cors_preflight():
    return widget_cors_preflight_response()


@app.after_request
def _after(resp):
    if request.path.startswith("/dashboard"):
        return resp
    latency = int((time.time() - request.ctx["t0"]) * 1000)
    log_json(
        logger,
        "http_request",
        **{
            **request.ctx,
            "status": resp.status_code,
            "latency_ms": latency,
            "ip": request.remote_addr,
        },
    )
    return apply_widget_cors_headers(resp)


@app.get("/_debug/ping")
def debug_ping():
    if APP_ENV == "prod":
        return jsonify({"error": "not_found"}), 404
    if request.headers.get("X-Debug-Token") != DEBUG_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": True})


def _dashboard_guard():
    """Legacy JSONL dashboard — disabled in prod (use admin_dashboard/)."""
    if APP_ENV == "prod":
        return jsonify({"error": "not_found"}), 404
    return None


def _load_recent_bot_events(
    log_path: str,
    *,
    max_scan_lines: int,
    limit: int,
) -> list:
    rows: list = []
    if not os.path.isfile(log_path):
        return rows
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        tail = deque(f, maxlen=max_scan_lines)
    for raw in reversed(tail):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("kind") != "bot_event":
            continue
        rows.append(obj)
        if len(rows) >= limit:
            break
    return rows


@app.get("/dashboard")
def dashboard_page():
    denied = _dashboard_guard()
    if denied:
        return denied
    return send_from_directory("static", "dashboard.html")


@app.get("/dashboard/events")
def dashboard_events_api():
    denied = _dashboard_guard()
    if denied:
        return denied
    try:
        lim = min(max(int(request.args.get("limit", 200)), 1), 500)
    except ValueError:
        lim = 200
    try:
        scan = min(max(int(request.args.get("scan", 25000)), 100), 200000)
    except ValueError:
        scan = 25000
    events = _load_recent_bot_events(LOG_FILE, max_scan_lines=scan, limit=lim)
    payload = {
        "count": len(events),
        "events": events,
    }
    if APP_ENV != "prod":
        payload["log_file"] = LOG_FILE
    return jsonify(payload)


def _orchestrate_ask_turn(data: dict):
    pre = run_pre_resolver_turn(
        data,
        resolve_client_id=resolve_request_client_id,
        bind_chat_ctx=_bind_chat_ctx,
        resolve_ip=_resolve_request_ip,
        client_txt=_client_txt,
        service_payload=build_service_payload,
        get_last_content_ui_payload=get_last_content_ui_payload_compat,
    )
    if isinstance(pre, AskOrchestrationResult):
        return pre

    resolver = run_resolver_turn(
        q=pre.q,
        sid=pre.sid,
        client_id=pre.client_id,
        st=pre.st,
        enqueue_resolver_trace=_enqueue_v5_resolver_trace,
    )

    return orchestrate_routing_after_resolver(
        q=pre.q,
        sid=pre.sid,
        client_id=pre.client_id,
        intent=resolver.intent,
        decision=resolver.decision,
        scope_topic_candidate=resolver.scope_topic_candidate,
        resolver_bypassed_env=resolver.resolver_bypassed_env,
        data=pre.data,
        client_txt=_client_txt,
        service_payload=build_service_payload,
        lead_flow_from_result=lead_flow_orchestration_result,
        apply_response_policy=apply_response_policy_compat,
    )


def _dispatch_orchestration_json(orch_r: AskOrchestrationResult):
    """JSON-ответ для /ask (как до рефакторинга)."""
    if orch_r.kind == "unknown_client":
        return jsonify(orch_r.client_error or {"error": "unknown_client"}), orch_r.http_status
    if orch_r.kind == "reset_session":
        return safe_jsonify(reset_session_response(orch_r.sid))
    if orch_r.kind == "service_reply":
        resp = _service_reply(
            orch_r.service_payload,
            orch_r.sid,
            orch_r.q,
            doc_id=orch_r.service_doc_id,
            track_user=orch_r.service_track_user,
            route=orch_r.service_route,
        )
        if orch_r.http_status != 200:
            return resp, orch_r.http_status
        return resp
    if orch_r.kind == "chunk":
        return respond_from_chunk(
            chunk=orch_r.chosen_chunk,
            q=orch_r.q,
            sid=orch_r.sid,
            client_id=orch_r.client_id,
            finalize_ask=finalize_ask,
            safe_jsonify=safe_jsonify,
            logger=logger,
            llm_question=orch_r.llm_question,
            log_event=orch_r.log_event,
            route=orch_r.chunk_route,
            generator_append_text=orch_r.generator_append_text,
            price_offer_meta=orch_r.price_offer_meta,
            matched_service_id=orch_r.matched_service_id,
        )
    raise RuntimeError(f"bad orchestration kind: {orch_r.kind}")

@app.post("/ask")
def ask():
    q = ""
    request.ctx["turn_t0_monotonic"] = time.monotonic()
    try:
        data = request.get_json(force=True) or {}
        client_id = resolve_request_client_id(data.get("client_id"), host=request.host)
        if client_id is None:
            return safe_jsonify({"error": "unknown_client"}), 403
        blocked = _widget_origin_forbidden(client_id)
        if blocked:
            return blocked
        orch_r = _orchestrate_ask_turn(data)
        from core.turn_timing import mark

        mark("orchestrate_done")
        q = orch_r.q or ""
        return _dispatch_orchestration_json(orch_r)
    except Exception as e:
        logger.exception("ask_failed", extra={"q": q, "err": str(e)})
        if request.ctx.get("sid") and (q or "").strip():
            emit_bot_event(
                logger,
                "turn_complete",
                status="error",
                details={
                    "turn_number": None,
                    "user_text_redacted": redact_text((q or ""), max_len=8000),
                    "user_preview_redacted": redact_text((q or ""), max_len=200),
                    "bot_text_redacted": "",
                    "intent": None,
                    "doc_id": None,
                    "route": "error",
                    "low_score": False,
                    "lead_flow": False,
                    "handoff_filter": False,
                    "answer_chars": 0,
                    "latency_ms": None,
                    "fallback_reason": "ask_failed",
                    "retrieval_scope_topic": None,
                    "retrieval_scope_guard_reason": "none",
                    "retrieval_scope_widen_fallback": False,
                    "legacy_intent": None,
                    "effective_intent": "",
                },
            )
        emit_bot_event(
            logger,
            "ask_failed",
            status="error",
            details={"error": str(e)[:500], "question_preview": (q or "")[:200]},
        )
        return safe_jsonify(internal_error_response()), 200

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # отключает буферизацию в nginx
}


def _sse_typing_phase(*, kind: str, route: str | None) -> str:
    """Фаза индикатора в виджете: searching = «база знаний», writing = только «печатает»."""
    if kind == "chunk":
        return "searching"
    r = (route or "").strip().lower()
    if r.startswith("ingress_"):
        return "writing"
    if r in {
        "lead_flow",
        "booking_flow",
        "duplicate_short_circuit",
        "rate_limited",
        "guided",
        "error",
    }:
        return "writing"
    if r in {"price_lookup", "price_concern", "catalog_facts", "retrieval_no_candidates", "low_score_fallback"}:
        return "searching"
    return "writing"


def _sse_typing_line(phase: str) -> str:
    return f"event: typing\ndata: {json.dumps({'phase': phase}, ensure_ascii=False)}\n\n"


def _sse_service_reply(
    payload: dict,
    sid: str,
    q: str,
    *,
    doc_id: str | None = None,
    track_user: bool = True,
    route: str | None = None,
):
    """Обёртка _service_reply для SSE: один event ui + done."""
    from core.consult_nudge import record_consult_nudge_after_answer, reset_consult_nudge_on_route

    reset_consult_nudge_on_route(route, sid)
    if track_user and q and not _skip_lead_pii_in_session_hist(payload):
        mem_add_user(sid, q)
    if route:
        payload.setdefault("meta", {})["service_route"] = str(route).strip()
    r = (route or "").strip().lower()
    if r == "price_lookup" and not is_active_lead_flow(mem_get(sid)):
        pmeta = payload.get("meta") or {}
        record_consult_nudge_after_answer(
            sid,
            route,
            pmeta.get("consult_nudge"),
            str(payload.get("answer") or ""),
        )
    answer = (payload.get("answer") or "").strip()
    turn_meta = None
    if track_user and (q or "").strip():
        qs = (q or "").strip()
        pmeta = payload.get("meta") or {}
        turn_meta = {
            "interaction": "user_message",
            "question_len": len(qs),
            "preview": observability_turn_preview(qs, route=route, meta=pmeta),
        }
    out = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    if answer:
        mem_add_bot(sid, answer)

    phase = _sse_typing_phase(kind="service_reply", route=route)

    def _gen():
        yield _sse_typing_line(phase)
        yield f"event: ui\ndata: {json.dumps(_sanitize(out), ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return app.response_class(_gen(), mimetype="text/event-stream", headers=_SSE_HEADERS)


def _sse_chunk_response(
    chunk: dict,
    q: str,
    sid: str,
    client_id: str | None,
    *,
    llm_question: str | None = None,
    log_event: str = "Answer generated",
    route: str = "retrieval_chunk",
    generator_append_text: str | None = None,
    price_offer_meta: dict | None = None,
    matched_service_id: str | None = None,
):
    """Стриминговый ответ из чанка через SSE."""
    return app.response_class(
        stream_with_context(
            respond_from_chunk_stream(
                chunk=chunk,
                q=q,
                sid=sid,
                client_id=client_id,
                finalize_ask=finalize_ask,
                logger=logger,
                llm_question=llm_question,
                log_event=log_event,
                route=route,
                generator_append_text=generator_append_text,
                price_offer_meta=price_offer_meta,
                matched_service_id=matched_service_id,
            ),
        ),
        mimetype="text/event-stream",
        headers=_SSE_HEADERS,
    )


def _dispatch_orchestration_sse(orch_r: AskOrchestrationResult):
    """SSE-упаковка результата оркестратора (как исторический /ask/stream)."""
    if orch_r.kind == "unknown_client":
        return jsonify(orch_r.client_error or {"error": "unknown_client"}), orch_r.http_status
    if orch_r.kind == "reset_session":
        return safe_jsonify(reset_session_response(orch_r.sid))
    if orch_r.kind == "service_reply":
        resp = _sse_service_reply(
            orch_r.service_payload,
            orch_r.sid,
            orch_r.q,
            doc_id=orch_r.service_doc_id,
            track_user=orch_r.service_track_user,
            route=orch_r.service_route,
        )
        if orch_r.http_status != 200:
            return resp, orch_r.http_status
        return resp
    if orch_r.kind == "chunk":
        return _sse_chunk_response(
            orch_r.chosen_chunk,
            orch_r.q,
            orch_r.sid,
            orch_r.client_id,
            llm_question=orch_r.llm_question,
            log_event=orch_r.log_event,
            route=orch_r.chunk_route,
            generator_append_text=orch_r.generator_append_text,
            price_offer_meta=orch_r.price_offer_meta,
            matched_service_id=orch_r.matched_service_id,
        )
    raise RuntimeError(f"bad orchestration kind: {orch_r.kind}")


@app.post("/ask/stream")
def ask_stream():
    """Стриминговый вариант /ask. Протокол SSE:
      event: typing      data: {"phase":"searching"|"writing"} — фаза индикатора (первым)
      event: text_delta  data: {"delta": "..."}   — токены ответа
      event: ui          data: {полный payload}    — UI элементы после генерации
      event: done        data: {}                  — конец стрима
    Direct-ответы (цены, контакты, flow) отдают typing + ui + done без text_delta.
    """
    q = ""
    request.ctx["turn_t0_monotonic"] = time.monotonic()
    try:
        data = request.get_json(force=True) or {}
        client_id = resolve_request_client_id(data.get("client_id"), host=request.host)
        if client_id is None:
            return safe_jsonify({"error": "unknown_client"}), 403
        blocked = _widget_origin_forbidden(client_id)
        if blocked:
            return blocked
        orch_r = _orchestrate_ask_turn(data)
        from core.turn_timing import mark

        mark("orchestrate_done")
        q = orch_r.q or ""
        return _dispatch_orchestration_sse(orch_r)
    except Exception as e:
        logger.exception("ask_stream_failed", extra={"q": q, "err": str(e)})
        if request.ctx.get("sid") and (q or "").strip():
            emit_bot_event(
                logger,
                "turn_complete",
                status="error",
                details={
                    "turn_number": None,
                    "user_text_redacted": redact_text((q or ""), max_len=8000),
                    "user_preview_redacted": redact_text((q or ""), max_len=200),
                    "bot_text_redacted": "",
                    "intent": None,
                    "doc_id": None,
                    "route": "error",
                    "low_score": False,
                    "lead_flow": False,
                    "handoff_filter": False,
                    "answer_chars": 0,
                    "latency_ms": None,
                    "fallback_reason": "ask_stream_failed",
                    "retrieval_scope_topic": None,
                    "retrieval_scope_guard_reason": "none",
                    "retrieval_scope_widen_fallback": False,
                    "legacy_intent": None,
                    "effective_intent": "",
                },
            )
        emit_bot_event(
            logger,
            "ask_stream_failed",
            status="error",
            details={"error": str(e)[:500], "question_preview": (q or "")[:200]},
        )
        return safe_jsonify(internal_error_response()), 200

@app.get("/__debug/retrieval")
def dbg():
    if APP_ENV == "prod":
        return jsonify({"error": "not_found"}), 404
    if request.headers.get("X-Debug-Token") != DEBUG_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    q = request.args.get("q", "")
    client_id = resolve_request_client_id(request.args.get("client_id"), host=request.host)
    if client_id is None:
        return jsonify({"error": "unknown_client"}), 403
    q_raw = (q or "").strip()
    q_use = normalize_retrieval_query(q_raw) or q_raw
    c = retrieve(q_raw, topk=5, client_id=client_id)
    alias_selected, alias_score = best_alias_hit_in_corpus(
        q_use,
        client_id=client_id,
        strong_threshold=float(THRESHOLDS.alias.strong_effective_min),
    )
    for x in c:
        dbg = alias_debug_score_for_chunk(q_use, x, client_id=client_id)
        x["alias_score"] = dbg.get("alias_effective")
        x["alias_debug"] = dbg
        x.pop("text", None)
    alias_summary = None
    if isinstance(alias_selected, dict):
        alias_summary = {
            "file": alias_selected.get("file"),
            "h2_id": alias_selected.get("h2_id"),
            "h3_id": alias_selected.get("h3_id"),
            "score": alias_selected.get("_score"),
        }
    return jsonify(
        {
            "q": q,
            "client_id": client_id,
            "alias_score": round(float(alias_score or 0.0), 4),
            "alias_selected": alias_summary,
            "candidates": c,
        }
    )


@app.get("/api/video-catalog")
def api_video_catalog():
    """Публичный каталог медиа по client_id для виджета (play-URL через прокси)."""
    client_id = resolve_request_client_id(request.args.get("client_id"), host=request.host)
    if client_id is None:
        return jsonify({"error": "unknown_client"}), 403
    blocked = _widget_origin_forbidden(client_id)
    if blocked:
        return blocked
    return jsonify({"client_id": client_id, "videos": catalog_for_widget(client_id)}), 200


@app.get("/api/media/<video_key>")
def api_media_proxy(video_key: str):
    """Прокси MP4 с S3 — same-origin для виджета (Range, без CORS)."""
    import urllib.error
    import urllib.request

    client_id = resolve_request_client_id(request.args.get("client_id"), host=request.host)
    if client_id is None:
        return jsonify({"error": "unknown_client"}), 403
    blocked = _widget_origin_forbidden(client_id)
    if blocked:
        body, status = blocked
        return body, status
    external = get_external_video_src(client_id=client_id, video_key=video_key)
    if not external:
        return jsonify({"error": "not_found"}), 404

    upstream_headers = {"User-Agent": "demo-bot-media-proxy/1"}
    range_header = request.headers.get("Range")
    if range_header:
        upstream_headers["Range"] = range_header

    req = urllib.request.Request(external, headers=upstream_headers, method="GET")
    try:
        upstream = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return Response(body, status=exc.code)

    resp_headers = {
        "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
    }
    for h in ("Content-Length", "Content-Range"):
        if upstream.headers.get(h):
            resp_headers[h] = upstream.headers[h]

    def generate():
        try:
            while True:
                chunk = upstream.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    return Response(
        stream_with_context(generate()),
        status=getattr(upstream, "status", 200) or 200,
        headers=resp_headers,
    )


@app.get("/api/widget-config")
def api_widget_config():
    client_id = resolve_request_client_id(request.args.get("client_id"), host=request.host)
    if client_id is None:
        return jsonify({"error": "unknown_client"}), 403
    blocked = _widget_origin_forbidden(client_id)
    if blocked:
        return blocked
    cfg = load_widget_config(client_id)
    if not cfg:
        return jsonify({"error": "widget_config_not_found"}), 404
    return jsonify(cfg)


@app.get("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


@app.post("/lead")
def create_lead():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error_code": "bad_json", "delivery": None}), 400
    client_id = resolve_request_client_id(data.get("client_id"), host=request.host)
    if client_id is None:
        return jsonify({"ok": False, "error_code": "unknown_client", "delivery": None}), 403
    blocked = _widget_origin_forbidden(client_id)
    if blocked:
        body, status = blocked
        return body, status
    data["client_id"] = client_id
    sid = sid_from_body(data)
    data["sid"] = sid
    data["request_id"] = request.ctx.get("request_id")
    _bind_chat_ctx(sid, client_id)
    payload, status = handle_lead(data)
    return jsonify(payload), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

