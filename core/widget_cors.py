"""CORS for cross-origin widget embed (pairs with core/origin_guard.py)."""
from __future__ import annotations

from flask import Response, request

from config import resolve_client_id
from core.client_host import resolve_request_client_id
from core.origin_guard import matching_widget_origin

_WIDGET_CORS_PREFIXES = (
    "/api/widget-config",
    "/api/video-catalog",
    "/api/media/",
    "/ask",
    "/lead",
    "/static/widget/",
)

_CORS_ALLOW_METHODS = "GET, POST, OPTIONS"
_CORS_ALLOW_HEADERS = "Content-Type, Range"
_CORS_MAX_AGE = "86400"


def is_widget_embed_cors_path(path: str) -> bool:
    p = (path or "").strip()
    if not p:
        return False
    return any(p == prefix or p.startswith(prefix) for prefix in _WIDGET_CORS_PREFIXES)


def resolve_widget_cors_client_id() -> str | None:
    """Resolve client_id for CORS / preflight (query, JSON body, or Host in prod)."""
    raw = (request.args.get("client_id") or "").strip()
    if not raw and request.method in {"POST", "PUT", "PATCH"}:
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            raw = str(data.get("client_id") or "").strip()
    if raw:
        return resolve_request_client_id(raw, host=request.host)
    host_cid = resolve_request_client_id(None, host=request.host)
    if host_cid:
        return host_cid
    return resolve_client_id(raw or None)


def _cors_headers(allow_origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": _CORS_ALLOW_METHODS,
        "Access-Control-Allow-Headers": _CORS_ALLOW_HEADERS,
        "Access-Control-Max-Age": _CORS_MAX_AGE,
        "Vary": "Origin",
    }


def widget_cors_preflight_response() -> Response | None:
    """Handle OPTIONS preflight for widget embed paths."""
    if request.method != "OPTIONS":
        return None
    if not is_widget_embed_cors_path(request.path):
        return None
    client_id = resolve_widget_cors_client_id()
    allow_origin = matching_widget_origin(client_id)
    if not allow_origin:
        return Response("", status=403)
    return Response("", status=204, headers=_cors_headers(allow_origin))


def apply_widget_cors_headers(response: Response) -> Response:
    """Attach CORS headers to widget embed API/static responses when Origin is allowed."""
    if not is_widget_embed_cors_path(request.path):
        return response
    if request.method == "OPTIONS":
        return response
    client_id = resolve_widget_cors_client_id()
    allow_origin = matching_widget_origin(client_id)
    if not allow_origin:
        return response
    for key, value in _cors_headers(allow_origin).items():
        response.headers[key] = value
    return response
