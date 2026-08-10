"""Provider transport instrumentation for Stage 3C Speed Gate LIVE runner."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from evals.v5.one_call_stage3c_speed_gate_contract import (
    MAX_PROVIDER_CALLS_LIVE,
    MODEL_SNAPSHOT,
)
from evals.v5.one_call_stage3c_speed_gate_fake_transport import (
    ProviderCallRecord,
    SpeedGateFakeTransport,
)


class MeasurementProviderBudgetExceeded(RuntimeError):
    """Global LIVE measurement budget exhausted before transport."""


@dataclass
class MeasurementProviderBudget:
    max_calls: int = MAX_PROVIDER_CALLS_LIVE
    consumed: int = 0
    completed: int = 0

    def remaining(self) -> int:
        return max(0, self.max_calls - self.consumed)

    def reserve_before_transport(self) -> int:
        if self.consumed >= self.max_calls:
            raise MeasurementProviderBudgetExceeded(
                f"measurement provider budget exhausted ({self.max_calls})"
            )
        self.consumed += 1
        return self.consumed


@dataclass
class InstrumentedProviderCall:
    call_index: int
    call_source: str
    requested_model: str
    observed_model: str | None = None
    stream: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    provider_ttft_ms: int | None = None
    duration_ms: int | None = None
    outcome: str = "reserved"
    verified: bool = False
    error_code: str | None = None


@dataclass
class SpeedGateLiveTransport:
    """Wraps real or fake provider create with global measurement budget."""

    budget: MeasurementProviderBudget
    use_fake_transport: bool
    fake_transport: SpeedGateFakeTransport | None = None
    real_create: Callable[..., Any] | None = None
    on_provider_start: Callable[[InstrumentedProviderCall], None] | None = None
    on_provider_finish: Callable[[InstrumentedProviderCall], None] | None = None
    on_provider_error: Callable[[InstrumentedProviderCall], None] | None = None
    calls: list[InstrumentedProviderCall] = field(default_factory=list)

    def chat_completions_create(self, **kwargs: Any) -> Any:
        model = str(kwargs.get("model") or MODEL_SNAPSHOT)
        source = str(kwargs.get("provider_call_source") or "unknown")
        stream = bool(kwargs.get("stream"))
        call_index = self.budget.reserve_before_transport()
        call = InstrumentedProviderCall(
            call_index=call_index,
            call_source=source,
            requested_model=model,
            stream=stream,
        )
        self.calls.append(call)
        if self.on_provider_start is not None:
            self.on_provider_start(call)

        started = time.monotonic()
        first_delta_at: float | None = None
        try:
            if self.use_fake_transport:
                assert self.fake_transport is not None
                fake_kwargs = dict(kwargs)
                fake_kwargs["model"] = model
                response = self.fake_transport.chat_completions_create(**fake_kwargs)
            else:
                assert self.real_create is not None
                response = self.real_create(**kwargs)

            if stream and isinstance(response, list):
                for chunk in response:
                    delta = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
                    if delta and first_delta_at is None:
                        first_delta_at = time.monotonic()
            observed = getattr(response, "model", None) if not isinstance(response, list) else None
            if isinstance(response, list) and response:
                observed = getattr(response[-1], "model", observed)
            call.observed_model = str(observed or model)
            call.verified = call.observed_model == model
            usage = _extract_usage(response)
            call.prompt_tokens = usage[0]
            call.completion_tokens = usage[1]
            call.cached_tokens = usage[2]
            duration_ms = int((time.monotonic() - started) * 1000)
            call.duration_ms = duration_ms
            if first_delta_at is not None:
                call.provider_ttft_ms = max(0, int((first_delta_at - started) * 1000))
            else:
                call.provider_ttft_ms = duration_ms
            call.outcome = "ok"
            self.budget.completed += 1
            if self.on_provider_finish is not None:
                self.on_provider_finish(call)
            return response
        except Exception as exc:
            call.duration_ms = int((time.monotonic() - started) * 1000)
            call.outcome = "error"
            call.error_code = type(exc).__name__
            if self.on_provider_error is not None:
                self.on_provider_error(call)
            raise

    def reset_turn_calls(self) -> None:
        self.calls.clear()

    def turn_call_count(self) -> int:
        return len(self.calls)


def _extract_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    if isinstance(response, list):
        for chunk in reversed(response):
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                return _usage_triplet(usage)
        return None, None, None
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None, None
    return _usage_triplet(usage)


def _usage_triplet(usage: Any) -> tuple[int | None, int | None, int | None]:
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    return (
        int(prompt) if prompt is not None else None,
        int(completion) if completion is not None else None,
        int(cached) if cached is not None else None,
    )


def instrumented_call_to_record(call: InstrumentedProviderCall) -> dict[str, Any]:
    return asdict(call)


def fake_record_to_dict(record: ProviderCallRecord) -> dict[str, Any]:
    return asdict(record)
