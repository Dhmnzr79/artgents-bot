"""Per-turn latency marks for orchestration / retrieval / chat (request.ctx)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator


def _bucket() -> dict[str, Any]:
    try:
        from flask import has_request_context, request

        if has_request_context():
            ctx = request.ctx
            return ctx.setdefault(
                "turn_timing",
                {"durations_ms": {}, "flags": {}, "marks": {}},
            )
    except Exception:
        pass
    return {"durations_ms": {}, "flags": {}, "marks": {}}


def mark(name: str) -> None:
    _bucket()["marks"][name] = time.monotonic()


def set_flag(name: str, value: Any) -> None:
    _bucket()["flags"][name] = value


def record_ms(name: str, ms: int, *, accumulate: bool = False) -> None:
    b = _bucket()
    v = max(0, int(ms))
    if accumulate and name in b["durations_ms"]:
        b["durations_ms"][name] = int(b["durations_ms"][name]) + v
    else:
        b["durations_ms"][name] = v


@contextmanager
def timed_stage(name: str, *, accumulate: bool = False) -> Iterator[None]:
    t0 = time.monotonic()
    try:
        yield
    finally:
        record_ms(name, int((time.monotonic() - t0) * 1000), accumulate=accumulate)


def cached_tokens_from_usage(resp: Any) -> int | None:
    u = getattr(resp, "usage", None)
    if u is None:
        return None
    details = getattr(u, "prompt_tokens_details", None)
    if details is None:
        return None
    ct = getattr(details, "cached_tokens", None)
    if ct is None and isinstance(details, dict):
        ct = details.get("cached_tokens")
    try:
        return int(ct) if ct is not None else None
    except (TypeError, ValueError):
        return None


def summary_for_turn_complete() -> dict[str, Any]:
    """Flat dict for turn_complete / bot_reply_completed details."""
    b = _bucket()
    durations = dict(b.get("durations_ms") or {})
    flags = dict(b.get("flags") or {})
    marks = dict(b.get("marks") or {})

    out: dict[str, Any] = {**durations, **{k: v for k, v in flags.items() if v is not None}}

    t0 = None
    try:
        from flask import has_request_context, request

        if has_request_context():
            raw = request.ctx.get("turn_t0_monotonic")
            if isinstance(raw, (int, float)):
                t0 = float(raw)
    except Exception:
        pass

    if t0 is not None:
        now = time.monotonic()
        out["total_ms"] = max(0, int((now - t0) * 1000))
        for key, ts in marks.items():
            if isinstance(ts, (int, float)):
                out[f"{key}_since_start_ms"] = max(0, int((float(ts) - t0) * 1000))

    if "orchestrate_ms" not in out and t0 is not None and "orchestrate_done" in marks:
        out["orchestrate_ms"] = max(
            0, int((float(marks["orchestrate_done"]) - t0) * 1000)
        )

    return {k: v for k, v in out.items() if v is not None and v != ""}
