"""Per-turn latency marks for orchestration / retrieval / chat (request.ctx)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator


# PERF-0: stage status vocabulary. "completed" = ran to a normal outcome;
# "skipped" = never entered (deterministic bypass, use stage_skipped());
# "blocked" = entered but a deterministic/semantic check rejected the turn;
# "exception" = entered but the backend/transport raised.
_STAGE_STATUSES = frozenset({"completed", "skipped", "blocked", "exception"})


def _empty_bucket() -> dict[str, Any]:
    return {"durations_ms": {}, "flags": {}, "marks": {}, "stages": {}}


def _bucket() -> dict[str, Any]:
    try:
        from flask import has_request_context, request

        if has_request_context():
            ctx = request.ctx
            return ctx.setdefault("turn_timing", _empty_bucket())
    except Exception:
        pass
    return _empty_bucket()


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


def stage_start(name: str) -> None:
    """Open a named pipeline-stage span (Ingress/Planner/Boundary/Composer/Verifier/...)."""
    _bucket()["marks"][f"{name}_start"] = time.monotonic()


def stage_end(
    name: str,
    *,
    status: str,
    llm_used: bool | None = None,
    reason: str | None = None,
) -> None:
    """Close a span opened with stage_start(); records duration + outcome status."""
    resolved_status = status if status in _STAGE_STATUSES else "completed"
    b = _bucket()
    now = time.monotonic()
    t_start = b["marks"].get(f"{name}_start")
    duration_ms: int | None = None
    if isinstance(t_start, (int, float)):
        duration_ms = max(0, int((now - float(t_start)) * 1000))
        b["durations_ms"][f"{name}_ms"] = duration_ms
    b["marks"][f"{name}_end"] = now
    entry: dict[str, Any] = {"status": resolved_status, "duration_ms": duration_ms}
    if llm_used is not None:
        entry["llm_used"] = bool(llm_used)
    if reason:
        entry["reason"] = str(reason)
    b.setdefault("stages", {})[name] = entry


def stage_skipped(name: str, *, reason: str) -> None:
    """Record a stage that was never entered — explicit label, not absence/0ms (PERF-0 Rule 5)."""
    b = _bucket()
    b.setdefault("stages", {})[name] = {
        "status": "skipped",
        "duration_ms": None,
        "reason": str(reason),
    }


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
    stages = dict(b.get("stages") or {})

    out: dict[str, Any] = {**durations, **{k: v for k, v in flags.items() if v is not None}}
    if stages:
        out["stages"] = stages

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
