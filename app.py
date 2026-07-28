import os
import re
import sys
import time
import json
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from collections import deque

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
from core import turn_timing
from core.client_host import resolve_request_client_id
from contracts.ask_orchestration import AskOrchestrationResult
from core.client_config_loader import load_widget_config, tone_to_txt_dict
from core.origin_guard import validate_widget_origin
from core.target_sse_worker_context import worker_execution_context
from core.widget_cors import (
    apply_widget_cors_headers,
    widget_cors_preflight_response,
)
from core.routing_loader import THRESHOLDS
from core.video_catalog_loader import catalog_for_widget, get_external_video_src
from lead_service import handle_lead
from core.observability_pii import observability_turn_preview, observability_user_texts
from logging_setup import LOG_FILE, emit_bot_event, get_logger, make_request_context, log_json, redact_text
from session import (
    bind_client_id,
    get_topic_state,
    mem_add_bot,
    mem_add_user,
    mem_get,
    is_active_lead_flow,
    record_last_bot_payload,
    sid_from_body,
)
from orchestration.target_fullcontext_turn import orchestrate_target_fullcontext_turn
from orchestration.helpers import get_last_content_ui_payload_compat
from orchestration.lead_flow import build_service_payload
from orchestration.finalize_turn import finalize_ask
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from orchestration.planner_turn import run_planner_turn
from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn
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


def _service_reply(
    payload: dict,
    sid: str,
    q: str,
    *,
    doc_id: str | None = None,
    track_user: bool = True,
    route: str | None = None,
):
    if track_user and q and not _skip_lead_pii_in_session_hist(payload):
        mem_add_user(sid, q)
    if route:
        payload.setdefault("meta", {})["service_route"] = str(route).strip()
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
    # PERF-0: /ask returns one JSON body — "first server event" and "request
    # complete" are the same instant today (no progressive delivery yet).
    turn_timing.mark("first_server_event")
    turn_timing.mark("request_complete")
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

    typed_outcome = try_run_typed_ui_planner_turn(
        sid=pre.sid,
        client_id=pre.client_id,
        enqueue_resolver_trace=_enqueue_v5_resolver_trace,
    )
    if typed_outcome is None:
        run_planner_turn(
            q=pre.q,
            sid=pre.sid,
            client_id=pre.client_id,
            st=pre.st,
            enqueue_resolver_trace=_enqueue_v5_resolver_trace,
        )

    return orchestrate_target_fullcontext_turn(
        q=pre.q,
        sid=pre.sid,
        client_id=pre.client_id,
        data=pre.data,
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


# --- PERF-1: early SSE status events (docs/evidence/performance/
# FINAL_EARLY_SSE_STATUS_STREAMING_SEAM_AUDIT.md) ---------------------------
#
# Bounded worker capacity: an explicit admission Semaphore gates whether a turn
# runs on a background worker at all — NOT relying on ThreadPoolExecutor's own
# (effectively unbounded) internal work queue as the admission control. When
# capacity is exhausted, the SSE generator falls back to computing the turn
# synchronously, on the request thread, after already having emitted the first
# status event — /ask/stream never behaves worse than before this milestone.
_SSE_WORKER_CAPACITY = max(1, int(os.getenv("SSE_WORKER_CAPACITY", "8")))
_sse_worker_executor = ThreadPoolExecutor(
    max_workers=_SSE_WORKER_CAPACITY, thread_name_prefix="ask-stream-worker"
)
_sse_worker_admission = threading.Semaphore(_SSE_WORKER_CAPACITY)
_SSE_STATUS_QUEUE_MAXSIZE = 8
_SSE_STATUS_POLL_INTERVAL_SEC = 0.05

# Status text is derived only from PERF-0's real stage_start call sites (via the
# notification hook in core/turn_timing.py) — never from reason/q/free text, and
# skipped stages never enqueue (stage_skipped does not call the hook). No
# internal LLM/Boundary/Verifier names are exposed to the user.
_SSE_STAGE_STATUS_PHRASES = {
    "ingress": "Проверяю вопрос",
    "planner": "Проверяю вопрос",
    "boundary": "Ищу информацию в материалах клиники",
    "composer": "Ищу информацию в материалах клиники",
    "verifier_deterministic": "Готовлю ответ",
    "verifier_semantic": "Готовлю ответ",
}
_SSE_INITIAL_STATUS_PHRASE = _SSE_STAGE_STATUS_PHRASES["ingress"]


def _sse_status_line(message: str) -> str:
    return f"event: status\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"


def _make_status_emitter(status_queue: "queue.Queue[str]", *, already_sent: str | None):
    """Non-blocking, deduping, bounded-lossy status emitter for one turn.

    Called from core.turn_timing's stage_start hook (via the ContextVar sink),
    i.e. from the worker thread. Never blocks the pipeline: a full queue just
    drops the update (status is informational and coalescable, never the final
    result — see _run_sse_worker_turn / the guaranteed result channel below).
    """
    last = {"phrase": already_sent}

    def _emit(stage_name: str, _event: str) -> None:
        phrase = _SSE_STAGE_STATUS_PHRASES.get(stage_name)
        if not phrase or phrase == last["phrase"]:
            return
        last["phrase"] = phrase
        try:
            status_queue.put_nowait(phrase)
        except queue.Full:
            pass

    return _emit


def _build_sse_payload(orch_r: AskOrchestrationResult) -> tuple[dict, int]:
    """Build the final SSE `ui` payload dict (session writes + finalize_ask) for
    an orchestration result, without any turn_timing marks — the caller (the SSE
    generator, on its own kept-alive request context) marks first_server_event /
    request_complete at the actual yield points, not at payload-build time."""
    if orch_r.kind == "service_reply":
        payload = orch_r.service_payload
        sid = orch_r.sid
        q = orch_r.q
        doc_id = orch_r.service_doc_id
        track_user = orch_r.service_track_user
        route = orch_r.service_route
        if track_user and q and not _skip_lead_pii_in_session_hist(payload):
            mem_add_user(sid, q)
        if route:
            payload.setdefault("meta", {})["service_route"] = str(route).strip()
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
        http_status = orch_r.http_status if orch_r.http_status != 200 else 200
        return out, http_status
    if orch_r.kind == "reset_session":
        return reset_session_response(orch_r.sid), 200
    if orch_r.kind == "unknown_client":
        return (orch_r.client_error or {"error": "unknown_client"}), orch_r.http_status
    raise RuntimeError(f"bad orchestration kind: {orch_r.kind}")


def _run_sse_worker_turn(
    *,
    data: dict,
    client_id: str,
    request_id: str,
    sid: str,
    turn_t0_monotonic: float,
    status_emit,
) -> tuple[dict, int]:
    """Run the unmodified orchestration + payload build inside an independent,
    per-turn worker request context (core.target_sse_worker_context) — never
    shares request.ctx with the request-handling/generator thread. Never raises:
    mirrors ask_stream()'s own top-level error handling so the caller's
    Future.result() is always safe to read."""
    try:
        with worker_execution_context(
            app,
            request_id=request_id,
            sid=sid,
            client_id=client_id,
            turn_t0_monotonic=turn_t0_monotonic,
            status_emit=status_emit,
        ):
            orch_r = _orchestrate_ask_turn(data)
            turn_timing.mark("orchestrate_done")
            return _build_sse_payload(orch_r)
    except Exception as e:
        logger.exception("ask_stream_worker_failed", extra={"sid": sid, "err": str(e)})
        emit_bot_event(
            logger,
            "ask_stream_failed",
            status="error",
            details={"error": str(e)[:500]},
            request_id=request_id,
            sid=sid,
            client_id=client_id,
        )
        return internal_error_response(), 200


def _stream_ask_turn_response(data: dict, client_id: str):
    """PERF-1: /ask/stream's early-status path — first SSE event before
    orchestration starts/finishes; bounded background worker with a safe
    synchronous fallback under admission overload; exactly one orchestration
    call either way.

    Deliberately does NOT use flask.stream_with_context: that helper keeps the
    *original* request context alive across generator iteration by re-pushing
    it, which — observed directly — can leave a stale, unpopped RequestContext
    behind when a generator is torn down other than by being fully iterated
    in the exact same call frame that started it (Flask/Werkzeug's own
    `ctx.pop()` then raises "Popped wrong request context" against a
    *different* request's context, corrupting Flask's contextvar state for
    later requests on the same thread). To avoid that failure mode entirely,
    the generator body below never touches `flask.request` at all: the two
    SSE-transport marks (`first_server_event`, `request_complete`) are written
    directly into a bucket dict captured *before* the generator is returned,
    and both the worker-available and admission-overload paths run through
    the exact same `_run_sse_worker_turn` — which always pushes its own
    short-lived, independent request context and pops it in `finally` — the
    only difference being whether that call happens on a background thread
    (worker available) or inline on this thread (overload fallback).
    """
    request_id = str(request.ctx.get("request_id") or uuid.uuid4())
    sid = sid_from_body(data)
    turn_t0 = request.ctx.get("turn_t0_monotonic")
    if not isinstance(turn_t0, (int, float)):
        turn_t0 = time.monotonic()
    bucket = request.ctx.setdefault(
        "turn_timing", {"durations_ms": {}, "flags": {}, "marks": {}, "stages": {}}
    )
    status_queue: "queue.Queue[str]" = queue.Queue(maxsize=_SSE_STATUS_QUEUE_MAXSIZE)

    def _gen():
        # Requirement: first SSE event before orchestration starts or waits on
        # anything — this yield happens before any pipeline call whatsoever.
        yield _sse_status_line(_SSE_INITIAL_STATUS_PHRASE)
        bucket["marks"]["first_server_event"] = time.monotonic()

        acquired = _sse_worker_admission.acquire(blocking=False)
        if not acquired:
            # Safe synchronous fallback, inside the generator, after the first
            # status — runs the same _run_sse_worker_turn inline (own
            # independent context, not the live one), on this thread. Never
            # worse than pre-PERF-1 behavior.
            out, _http_status = _run_sse_worker_turn(
                data=data,
                client_id=client_id,
                request_id=request_id,
                sid=sid,
                turn_t0_monotonic=turn_t0,
                status_emit=None,
            )
            route = str((out.get("meta") or {}).get("service_route") or "")
            yield _sse_typing_line(_sse_typing_phase(kind="service_reply", route=route))
            yield f"event: ui\ndata: {json.dumps(_sanitize(out), ensure_ascii=False)}\n\n"
            bucket["marks"]["request_complete"] = time.monotonic()
            yield "event: done\ndata: {}\n\n"
            return

        emitter = _make_status_emitter(status_queue, already_sent=_SSE_INITIAL_STATUS_PHRASE)

        def _worker_entry():
            try:
                return _run_sse_worker_turn(
                    data=data,
                    client_id=client_id,
                    request_id=request_id,
                    sid=sid,
                    turn_t0_monotonic=turn_t0,
                    status_emit=emitter,
                )
            finally:
                _sse_worker_admission.release()

        try:
            future = _sse_worker_executor.submit(_worker_entry)
        except Exception:
            _sse_worker_admission.release()
            raise

        while not future.done():
            try:
                phrase = status_queue.get(timeout=_SSE_STATUS_POLL_INTERVAL_SEC)
            except queue.Empty:
                continue
            yield _sse_status_line(phrase)
        while True:
            try:
                phrase = status_queue.get_nowait()
            except queue.Empty:
                break
            yield _sse_status_line(phrase)

        out, _http_status = future.result()
        route = str((out.get("meta") or {}).get("service_route") or "")
        yield _sse_typing_line(_sse_typing_phase(kind="service_reply", route=route))
        yield f"event: ui\ndata: {json.dumps(_sanitize(out), ensure_ascii=False)}\n\n"
        bucket["marks"]["request_complete"] = time.monotonic()
        yield "event: done\ndata: {}\n\n"

    return app.response_class(_gen(), mimetype="text/event-stream", headers=_SSE_HEADERS)


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
    if track_user and q and not _skip_lead_pii_in_session_hist(payload):
        mem_add_user(sid, q)
    if route:
        payload.setdefault("meta", {})["service_route"] = str(route).strip()
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

    # PERF-0: the full turn (incl. Composer/Verifier) is already computed by
    # this point — the SSE generator below yields typing/ui/done back-to-back
    # with no real gap (seam audit Finding 2). These marks honestly reflect
    # that: they will only diverge once a future milestone streams Composer
    # tokens progressively instead of one blocking backend.generate() call.
    turn_timing.mark("first_server_event")
    turn_timing.mark("request_complete")

    phase = _sse_typing_phase(kind="service_reply", route=route)

    def _gen():
        yield _sse_typing_line(phase)
        yield f"event: ui\ndata: {json.dumps(_sanitize(out), ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return app.response_class(_gen(), mimetype="text/event-stream", headers=_SSE_HEADERS)


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
    raise RuntimeError(f"bad orchestration kind: {orch_r.kind}")


@app.post("/ask/stream")
def ask_stream():
    """Стриминговый вариант /ask. Протокол SSE:
      event: status      data: {"message": "..."}   — PERF-1 честный ранний статус (опционален для клиента)
      event: typing      data: {"phase":"searching"|"writing"} — фаза индикатора (перед ui, как раньше)
      event: text_delta  data: {"delta": "..."}   — токены ответа (пока не используется)
      event: ui          data: {полный payload}    — UI элементы после генерации
      event: done        data: {}                  — конец стрима
    Direct-ответы (цены, контакты, flow) отдают typing + ui + done без text_delta.
    /reset и /новая — тот же быстрый детерминированный путь, что и раньше, без early-status
    (PERF-1 не относится к административным командам).
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

        q_raw = str(data.get("q") or "").strip()
        if q_raw.lower() in ("/reset", "/новая"):
            orch_r = _orchestrate_ask_turn(data)
            turn_timing.mark("orchestrate_done")
            q = orch_r.q or ""
            return _dispatch_orchestration_sse(orch_r)

        return _stream_ask_turn_response(data, client_id)
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

