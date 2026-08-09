"""Orchestration hook for the sales-fast one-call widget path (Stage 8)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config import SALES_ONE_PLUS_FLASH_MODEL
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.local_problem_gate import LocalProblemGateResult
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend
from core.target_sse_worker_context import current_text_sink


def _default_sales_fast_backend() -> SalesOnePlusLiveBackend:
    return SalesOnePlusLiveBackend(model=SALES_ONE_PLUS_FLASH_MODEL)


class _LazySalesFastBackend:
    """Defer provider construction until the one-call path actually needs it."""

    def __init__(self, factory: Callable[[], SalesOnePlusLiveBackend]) -> None:
        self._factory = factory
        self._backend: SalesOnePlusLiveBackend | None = None
        self.call_count = 0
        self.factory_invoked = False

    def _backend_or_create(self) -> SalesOnePlusLiveBackend:
        if self._backend is None:
            self.factory_invoked = True
            self._backend = self._factory()
        return self._backend

    def generate(self, invocation: object, /) -> object:
        backend = self._backend_or_create()
        result = backend.generate(invocation)
        self.call_count = int(getattr(backend, "call_count", 0) or 0)
        return result

    def generate_stream(
        self,
        invocation: object,
        on_raw_delta: Callable[[str], None],
        /,
    ) -> None:
        backend = self._backend_or_create()
        backend.generate_stream(invocation, on_raw_delta)
        self.call_count = int(getattr(backend, "call_count", 0) or 0)


def orchestrate_sales_fast_widget_turn(
    *,
    q: str,
    sid: str,
    client_id: str,
    data: dict[str, Any] | None = None,
    backend_factory: Callable[[], SalesOnePlusLiveBackend] | None = None,
    on_delta: Callable[[str], None] | None = None,
    local_gate_result: LocalProblemGateResult | None = None,
) -> AskOrchestrationResult:
    _ = data
    if backend_factory is None:
        backend_factory = _default_sales_fast_backend
    backend = _LazySalesFastBackend(backend_factory)
    text_sink = on_delta if on_delta is not None else current_text_sink()
    outcome = run_sales_fast_widget_turn(
        client_id=client_id,
        sid=sid,
        user_message=q,
        backend=backend,
        on_delta=text_sink,
        local_gate_result=local_gate_result,
    )
    payload = outcome.widget.payload
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    route = str(meta.get("service_route") or "sales_fast")
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route=route,
    )
