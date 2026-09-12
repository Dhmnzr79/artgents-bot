"""Eval-only LIVE provider transport for architecture comparison (reuses llm.chat_completions_create)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any

from evals.v5.arch_compare.arch_compare_configs import ArchCompareConfig
from evals.v5.arch_compare.arch_compare_live_guard import ArchCompareLiveGuardContext, ArchCompareLiveGuardError
from evals.v5.arch_compare.arch_compare_provider_payload import build_composer_provider_payload

PROVIDER_CALL_SOURCE = "arch_compare_live"


@dataclass(frozen=True, slots=True)
class ArchCompareProviderCallRecord:
    model: str
    stream: bool
    latency_ms: int
    ttft_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    observed_model: str | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _usage_int(usage: Any, key: str) -> int | None:
    if usage is None:
        return None
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _blocking_response(*, content: str, model: str, usage: Any) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
    )


class ArchCompareLiveTransport:
    """Thin adapter over production chat_completions_create with call accounting."""

    def __init__(
        self,
        *,
        chat_completions_create: Callable[..., Any] | None = None,
    ) -> None:
        if chat_completions_create is None:
            from llm import chat_completions_create as default_create

            self._chat_completions_create = default_create
        else:
            self._chat_completions_create = chat_completions_create
        self.calls: list[dict[str, Any]] = []
        self.records: list[ArchCompareProviderCallRecord] = []

    def reset_calls(self) -> None:
        self.calls.clear()
        self.records.clear()

    def chat_completions_create(self, **kwargs: Any) -> Any:
        payload = dict(kwargs)
        payload.setdefault("provider_call_source", PROVIDER_CALL_SOURCE)
        stream = bool(payload.get("stream"))
        model = str(payload.get("model") or "")
        started = time.monotonic()
        ttft_ms: int | None = None
        error: str | None = None
        try:
            if stream:
                content, usage, observed_model, ttft_ms = self._complete_stream(payload, started)
                response = _blocking_response(content=content, model=observed_model or model, usage=usage)
            else:
                response = self._chat_completions_create(**payload)
                content = (response.choices[0].message.content or "").strip()
                usage = getattr(response, "usage", None)
                observed_model = getattr(response, "model", None)
                response = _blocking_response(
                    content=content,
                    model=str(observed_model or model),
                    usage=usage,
                )
        except Exception as exc:
            error = str(exc)
            latency_ms = int((time.monotonic() - started) * 1000)
            self.calls.append({"model": model, "stream": stream, "error": error})
            self.records.append(
                ArchCompareProviderCallRecord(
                    model=model,
                    stream=stream,
                    latency_ms=latency_ms,
                    ttft_ms=ttft_ms,
                    prompt_tokens=None,
                    completion_tokens=None,
                    observed_model=None,
                    error=error,
                )
            )
            raise

        latency_ms = int((time.monotonic() - started) * 1000)
        usage = getattr(response, "usage", None)
        observed_model = getattr(response, "model", None)
        self.calls.append({"model": model, "stream": stream})
        self.records.append(
            ArchCompareProviderCallRecord(
                model=model,
                stream=stream,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                prompt_tokens=_usage_int(usage, "prompt_tokens"),
                completion_tokens=_usage_int(usage, "completion_tokens"),
                observed_model=str(observed_model) if observed_model is not None else None,
                error=None,
            )
        )
        return response

    def _complete_stream(self, payload: dict[str, Any], started: float) -> tuple[str, Any, str | None, int | None]:
        stream = self._chat_completions_create(**payload)
        parts: list[str] = []
        last_chunk: Any = None
        ttft_ms: int | None = None
        for chunk in stream:
            last_chunk = chunk
            choices = getattr(chunk, "choices", None) or ()
            if not choices:
                continue
            text = getattr(getattr(choices[0], "delta", None), "content", None)
            if text:
                if ttft_ms is None:
                    ttft_ms = int((time.monotonic() - started) * 1000)
                parts.append(str(text))
        usage = getattr(last_chunk, "usage", None) if last_chunk is not None else None
        observed_model = getattr(last_chunk, "model", None) if last_chunk is not None else None
        return "".join(parts), usage, (str(observed_model) if observed_model else None), ttft_ms

    def complete_for_config(
        self,
        *,
        config: ArchCompareConfig,
        messages: tuple[dict[str, str], ...],
        stream: bool = False,
    ) -> tuple[str, ArchCompareProviderCallRecord]:
        payload = build_composer_provider_payload(
            config=config,
            messages=messages,
            stream=stream,
        )
        response = self.chat_completions_create(**payload)
        content = (response.choices[0].message.content or "").strip()
        record = self.records[-1]
        return content, record


def create_guarded_live_transport(ctx: ArchCompareLiveGuardContext) -> ArchCompareLiveTransport:
    """Create production transport only after LIVE guard has passed."""
    if not ctx.live_requested:
        raise ArchCompareLiveGuardError("live_not_requested", "live transport requires --live")
    if ctx.transport_kind != "live":
        raise ArchCompareLiveGuardError("transport_kind_invalid", ctx.transport_kind)
    return ArchCompareLiveTransport()
