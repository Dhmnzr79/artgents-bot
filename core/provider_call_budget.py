"""HTTP-scoped provider call budget (ONE_CALL Stage 1).

Request-scoped via contextvars — safe for parallel requests and SSE worker threads
that install their own Flask request context.
"""

from __future__ import annotations

import inspect
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from logging_setup import get_logger, log_json

logger = get_logger("bot")


class ProviderCallPolicy(str, Enum):
    """Legacy path: account only. One-call path: enforce Stage 1 wiring bans."""

    LEGACY_ACCOUNTING = "legacy_accounting"
    ONE_CALL_LOCKED = "one_call_locked"


class ProviderCallBudgetError(RuntimeError):
    """Base class for transport-level budget violations."""


class ProviderCallBudgetExceeded(ProviderCallBudgetError):
    """Second provider call blocked before transport."""


class ProviderCallLegacyBlocked(ProviderCallBudgetError):
    """Legacy LLM wiring blocked while ONE_CALL_LOCKED is active."""


@dataclass
class ProviderCallBudget:
    request_id: str
    policy: ProviderCallPolicy
    call_count: int = 0
    reservations: list[dict[str, object]] = field(default_factory=list)

    def reserve(self, *, source: str, model: str) -> int:
        if self.policy == ProviderCallPolicy.ONE_CALL_LOCKED:
            if _is_legacy_provider_source(source):
                raise ProviderCallLegacyBlocked(
                    f"legacy provider call blocked ({source}) under ONE_CALL_LOCKED"
                )
            if self.call_count >= 1:
                raise ProviderCallBudgetExceeded(
                    f"provider call budget exhausted (source={source})"
                )
        self.call_count += 1
        call_index = self.call_count
        record = {
            "call_index": call_index,
            "source": source,
            "model": str(model or "")[:128],
            "reserved_at_monotonic": time.monotonic(),
            "outcome": "reserved",
        }
        self.reservations.append(record)
        log_json(
            logger,
            "provider_call_reserved",
            request_id=self.request_id,
            call_index=call_index,
            call_source=source,
            model=record["model"],
            policy=self.policy.value,
            provider_calls=self.call_count,
        )
        return call_index

    def record_outcome(
        self,
        *,
        call_index: int,
        outcome: str,
        duration_ms: int | None = None,
    ) -> None:
        matched: dict[str, object] | None = None
        for record in self.reservations:
            if record.get("call_index") == call_index:
                matched = record
                record["outcome"] = outcome
                if duration_ms is not None:
                    record["duration_ms"] = duration_ms
                break
        payload: dict[str, object] = {
            "request_id": self.request_id,
            "call_index": call_index,
            "outcome": outcome,
            "provider_calls": self.call_count,
        }
        if matched is not None:
            payload["call_source"] = matched["source"]
            payload["model"] = matched["model"]
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        log_json(logger, "provider_call_finished", **payload)


_budget_var: ContextVar[ProviderCallBudget | None] = ContextVar(
    "http_provider_call_budget", default=None
)


def current_provider_call_budget() -> ProviderCallBudget | None:
    return _budget_var.get()


def bind_http_provider_budget(
    *,
    request_id: str,
    sales_one_plus_on: bool,
) -> Token:
    policy = (
        ProviderCallPolicy.ONE_CALL_LOCKED
        if sales_one_plus_on
        else ProviderCallPolicy.LEGACY_ACCOUNTING
    )
    budget = ProviderCallBudget(request_id=str(request_id), policy=policy)
    return _budget_var.set(budget)


def reset_http_provider_budget(token: Token) -> None:
    _budget_var.reset(token)


@contextmanager
def http_provider_budget_scope(
    *,
    request_id: str,
    sales_one_plus_on: bool,
) -> Iterator[ProviderCallBudget]:
    token = bind_http_provider_budget(
        request_id=request_id,
        sales_one_plus_on=sales_one_plus_on,
    )
    budget = _budget_var.get()
    assert budget is not None
    try:
        yield budget
    finally:
        reset_http_provider_budget(token)


def infer_provider_call_source() -> str:
    """Best-effort caller lane for observability and legacy blocking."""
    for frame_info in inspect.stack()[1:12]:
        filename = (frame_info.filename or "").replace("\\", "/")
        if filename.endswith("ingress_gate.py"):
            return "ingress"
        if filename.endswith("turn_planner_llm.py"):
            return "planner"
        if filename.endswith("target_runtime_llm_backends.py"):
            name = frame_info.function or ""
            if "boundary" in name:
                return "medical_boundary"
            if "verifier" in name or "semantic" in name:
                return "verifier"
            if "composer" in name:
                return "composer"
            return "target_runtime"
        if filename.endswith("sales_one_plus_live_backend.py"):
            return "sales_fast"
        if filename.endswith("medical_boundary_eval_live_backend.py"):
            return "medical_boundary_eval"
        if filename.endswith("sales_one_plus_ab_live_backend.py"):
            return "sales_fast_eval"
        if filename.endswith("llm.py"):
            continue
        if "/evals/" in filename:
            return "eval"
    return "unknown"


def _is_legacy_provider_source(source: str) -> bool:
    if source == "sales_fast":
        return False
    if source in {
        "ingress",
        "planner",
        "medical_boundary",
        "composer",
        "verifier",
        "target_runtime",
    }:
        return True
    if source in {"eval", "sales_fast_eval", "unknown"}:
        return source != "sales_fast"
    return True


def reserve_provider_call(*, model: str, source: str | None = None) -> int | None:
    """Reserve a provider call before transport. Returns call_index or None if unbound."""
    budget = current_provider_call_budget()
    if budget is None:
        return None
    resolved = (source or infer_provider_call_source()).strip() or "unknown"
    return budget.reserve(source=resolved, model=model)


def record_provider_call_outcome(
    *,
    call_index: int | None,
    outcome: str,
    duration_ms: int | None = None,
) -> None:
    if call_index is None:
        return
    budget = current_provider_call_budget()
    if budget is None:
        return
    budget.record_outcome(
        call_index=call_index,
        outcome=outcome,
        duration_ms=duration_ms,
    )
