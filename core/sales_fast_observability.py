"""Non-PII observability for the sales-fast widget path."""

from __future__ import annotations

from typing import Any

from core.provider_call_budget import current_provider_call_budget
from core import turn_timing


def collect_sales_fast_timings_ms() -> dict[str, int]:
    bucket = turn_timing.summary_for_turn_complete()
    key_map = {
        "sales_fast_local_gate_ms": "local_gate",
        "sales_fast_resolver_ms": "resolver",
        "sales_fast_model_ms": "provider",
        "sales_fast_presentation_ms": "presentation",
        "sales_fast_ms": "sales_fast",
    }
    timings: dict[str, int] = {}
    for raw_key, label in key_map.items():
        value = bucket.get(raw_key)
        if isinstance(value, int):
            timings[label] = value
    total = bucket.get("total_ms")
    if isinstance(total, int):
        timings["total"] = total
    elif isinstance(timings.get("sales_fast"), int):
        timings["total"] = timings["sales_fast"]
    return timings


def record_sales_fast_observability(
    *,
    architecture: str,
    route: str,
    provider_calls: int,
    model: str | None,
    failure_kind: str | None = None,
    timings: dict[str, int] | None = None,
    backend_invocations: int | None = None,
) -> None:
    budget = current_provider_call_budget()
    if budget is not None:
        provider_calls = int(budget.call_count)
    else:
        provider_calls = 0
    payload: dict[str, Any] = {
        "architecture": architecture,
        "route": route,
        "provider_calls": int(provider_calls),
        "model": model,
        "failure_kind": failure_kind,
    }
    if backend_invocations is not None:
        payload["backend_invocations"] = int(backend_invocations)
    if timings:
        payload["timings_ms"] = dict(timings)
    turn_timing.set_flag("sales_fast_observability", payload)
