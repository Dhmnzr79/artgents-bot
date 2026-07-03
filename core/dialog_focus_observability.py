"""Safe dialog focus telemetry helpers."""

from __future__ import annotations

from typing import Any


def slim_dialog_focus_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in (
        "focus_service_id",
        "focus_topic",
        "attribute",
        "explicit_topic_change",
        "resolved_service_id",
        "source",
        "used_llm",
        "confidence",
        "reason",
    ):
        if key in raw:
            out[key] = raw[key]
    rewrite = str(raw.get("query_rewrite") or "").strip()
    if rewrite:
        out["query_rewrite"] = rewrite[:200]
    return out


def dialog_focus_response_meta() -> dict[str, Any]:
    try:
        from flask import has_request_context, request

        if has_request_context() and isinstance(getattr(request, "ctx", None), dict):
            return slim_dialog_focus_payload(request.ctx.get("dialog_focus_decision"))
    except Exception:
        return {}
    return {}
