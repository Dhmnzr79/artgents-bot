"""SSE widget answer delivery mode inference (Phase 2A — buffered reveal)."""

from __future__ import annotations

from typing import Any, Literal, Mapping

WidgetAnswerDeliveryMode = Literal["real_model", "buffered_model", "code_owned"]

_CODE_OWNED_ROUTE_MARKERS = (
    "contacts",
    "terminal",
    "spam",
    "guided",
    "lead_",
    "booking",
    "situation",
    "duplicate_short",
    "rate_limited",
    "offtopic",
    "retrieval_no",
    "low_score",
)


def infer_widget_sse_delivery_mode(
    *,
    text_delta_count: int,
    ui_payload: Mapping[str, Any] | None,
) -> WidgetAnswerDeliveryMode:
    """Infer delivery from emitted SSE facts. Production Phase 2A uses buffered/code_owned only."""

    if text_delta_count > 0:
        return "real_model"
    meta = ui_payload.get("meta") if isinstance(ui_payload, Mapping) else None
    if not isinstance(meta, Mapping):
        return "buffered_model"
    route = str(meta.get("service_route") or "").lower()
    provider_calls = meta.get("provider_calls")
    if isinstance(provider_calls, int) and provider_calls <= 0:
        if any(marker in route for marker in _CODE_OWNED_ROUTE_MARKERS):
            return "code_owned"
        if route.endswith("_local") or route in {"local", "sales_fast_contacts"}:
            return "code_owned"
    return "buffered_model"
