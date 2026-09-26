import os
import time
import json
from collections import deque

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)
from pg_sink import init_pg_sink

from config import DEBUG_TOKEN, PORT
from core.client_host import resolve_request_client_id
from core.d2_http_adapter import run_d2_ask_json
from core import d2_diagnostics as diagnostics
from core.d2_dialogue_store import D2RequestIdConflict, D2RequestInProgress
from core.client_config_loader import (
    WidgetPresentationLoadError,
    build_public_widget_config,
)
from core.origin_guard import validate_widget_origin
from core.widget_cors import (
    apply_widget_cors_headers,
    widget_cors_preflight_response,
)
from core.video_catalog_loader import catalog_for_widget, get_external_video_src
from lead_service import handle_lead
from logging_setup import LOG_FILE, get_logger, log_json, make_request_context
from session import (
    bind_client_id,
    clear_session_client_binding,
    sid_from_body,
)


app = Flask(__name__, static_folder="static")
logger = get_logger("bot")
APP_ENV = (os.getenv("APP_ENV") or "local").strip().lower()
init_pg_sink(logger)


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
diagnostics.startup()

_HEALTH_PROBE_PATHS = frozenset({"/health/live", "/health/ready"})


def _is_health_probe_path() -> bool:
    return (request.path or "") in _HEALTH_PROBE_PATHS


@app.get("/health/live")
def health_live():
    """Process liveness (no DB, no tenant routing, no secrets)."""
    return jsonify({"ok": True, "status": "live"}), 200


@app.get("/health/ready")
def health_ready():
    """Deployment readiness (prod fail-closed; local skips mandatory PG)."""
    from core.prod_readiness import evaluate_readiness

    ok, payload = evaluate_readiness()
    return jsonify(payload), (200 if ok else 503)


@app.before_request
def _before():
    request.ctx = make_request_context(cookie_sid=request.cookies.get("sid"))
    request.ctx["path"] = request.path
    request.ctx["method"] = request.method
    request.ctx["t0"] = time.time()


@app.before_request
def _widget_cors_preflight():
    if _is_health_probe_path():
        return None
    return widget_cors_preflight_response()


@app.teardown_request
def _clear_session_client_binding_teardown(exc):
    clear_session_client_binding()


@app.after_request
def _after(resp):
    if request.path.startswith("/dashboard") or _is_health_probe_path():
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


@app.post("/ask")
@diagnostics.http_attempt
def ask():
    """Return the durable D2 final result through the JSON transport."""
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return safe_jsonify({"error": "invalid_request"}), 400
        client_id = resolve_request_client_id(data.get("client_id"), host=request.host)
        if client_id is None:
            return safe_jsonify({"error": "unknown_client"}), 403
        blocked = _widget_origin_forbidden(client_id)
        if blocked:
            return blocked
        result = run_d2_ask_json(data, client_id=client_id)
        request.ctx["sid"] = result["sid"]
        request.ctx["session_id"] = result["sid"]
        request.ctx["client_id"] = client_id
        request.ctx["request_id"] = result["request_id"]
        diagnostics.stage("transport")
        return safe_jsonify(result)
    except D2RequestIdConflict as exc:
        diagnostics.failure(exc)
        return safe_jsonify({"error": "request_id_payload_conflict"}), 409
    except D2RequestInProgress as exc:
        diagnostics.failure(exc)
        return safe_jsonify({"error": "request_in_progress"}), 409
    except ValueError as exc:
        diagnostics.failure(exc)
        return safe_jsonify({"error": "d2_invalid_turn"}), 400
    except Exception as exc:
        diagnostics.failure(exc)
        logger.error("d2_ask_failed")
        return safe_jsonify({"error": "d2_turn_failed"}), 503

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # отключает буферизацию в nginx
}


def _sse_typing_line(phase: str) -> str:
    return f"event: typing\ndata: {json.dumps({'phase': phase}, ensure_ascii=False)}\n\n"


_SSE_INITIAL_STATUS_PHRASE = "Проверяю вопрос"


def _sse_status_line(message: str) -> str:
    return f"event: status\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"


@app.post("/ask/stream")
@diagnostics.http_attempt
def ask_stream():
    """SSE framing of the same durable D2 result returned by JSON /ask."""
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return safe_jsonify({"error": "invalid_request"}), 400
    client_id = resolve_request_client_id(data.get("client_id"), host=request.host)
    if client_id is None:
        return safe_jsonify({"error": "unknown_client"}), 403
    blocked = _widget_origin_forbidden(client_id)
    if blocked:
        return blocked

    # The generator holds only captured values, never Flask's request context.
    # Closing before the first status leaves the D2 store untouched; closing
    # during the synchronous turn allows its atomic completion to finish.
    def _gen():
        from session import clear_session_client_binding

        try:
            diagnostics.stage("transport")
            yield _sse_status_line(_SSE_INITIAL_STATUS_PHRASE)
            try:
                out = run_d2_ask_json(data, client_id=client_id)
            except D2RequestIdConflict as exc:
                diagnostics.failure(exc)
                error = "request_id_payload_conflict"
            except D2RequestInProgress as exc:
                diagnostics.failure(exc)
                error = "request_in_progress"
            except ValueError as exc:
                diagnostics.failure(exc)
                error = "d2_invalid_turn"
            except Exception as exc:
                diagnostics.failure(exc)
                logger.error("d2_ask_stream_failed")
                error = "d2_turn_failed"
            else:
                diagnostics.stage("transport")
                try:
                    typing_line = _sse_typing_line("writing")
                    ui_line = f"event: ui\ndata: {json.dumps(out, ensure_ascii=False)}\n\n"
                except Exception as exc:
                    diagnostics.failure(exc)
                    logger.error("d2_ask_stream_framing_failed")
                    yield 'event: error\ndata: {"error":"d2_stream_transport_failed"}\n\n'
                    return
                yield typing_line
                yield ui_line
                diagnostics.stage("stream_done")
                yield "event: done\ndata: {}\n\n"
                return
            yield f"event: error\ndata: {json.dumps({'error': error})}\n\n"
        finally:
            clear_session_client_binding()

    return app.response_class(diagnostics.stream(_gen()), mimetype="text/event-stream", headers=_SSE_HEADERS)


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
    try:
        cfg = build_public_widget_config(client_id)
    except WidgetPresentationLoadError as exc:
        if exc.code == "widget_config_not_found":
            return jsonify({"error": "widget_config_not_found"}), 404
        return jsonify({"error": "widget_config_invalid"}), 400
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
    payload, status = handle_lead(data, client_id=client_id)
    return jsonify(payload), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

