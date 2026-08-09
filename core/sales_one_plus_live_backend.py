"""Lazy one-shot provider adapter for the sales-fast ONE_CALL candidate."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from config import SALES_ONE_PLUS_FLASH_MODEL
from contracts.sales_one_plus import SalesOnePlusInvocation
from core.one_call_cache_observability import OneCallCacheObservability
from core.turn_timing import cached_tokens_from_usage
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create


class SalesOnePlusLiveBackendError(RuntimeError):
    """Typed one-shot adapter failure."""


def sales_one_plus_model() -> str:
    return SALES_ONE_PLUS_FLASH_MODEL


def _messages(invocation: SalesOnePlusInvocation) -> tuple[dict[str, str], ...]:
    return (
        {"role": "system", "content": invocation.system_prompt},
        {"role": "user", "content": invocation.user_prompt},
    )


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


def _build_observability(
    *,
    invocation: SalesOnePlusInvocation,
    response: Any,
    requested_model: str,
    provider_started: float,
    local_prefix_cache_hit: bool,
    prefix_build_ms: int | None,
) -> OneCallCacheObservability:
    observed = getattr(response, "model", None)
    observed_model = str(observed) if observed is not None else None
    usage = getattr(response, "usage", None)
    cached_tokens = cached_tokens_from_usage(response)
    provider_cache_hit = bool(cached_tokens is not None and cached_tokens > 0)
    provider_ms = max(0, int((time.monotonic() - provider_started) * 1000))
    identity = invocation.pack_identity
    return OneCallCacheObservability(
        local_prefix_cache_hit=local_prefix_cache_hit,
        provider_cache_hit=provider_cache_hit,
        cached_tokens=cached_tokens,
        prompt_tokens=_usage_int(usage, "prompt_tokens"),
        completion_tokens=_usage_int(usage, "completion_tokens"),
        client_pack_hash=identity.client_pack_hash,
        prompt_contract_version=identity.prompt_contract_version,
        requested_model=requested_model,
        observed_model=observed_model,
        provider_model_verified=observed_model == requested_model if observed_model else False,
        prefix_build_ms=prefix_build_ms,
        provider_ms=provider_ms,
        total_ms=(prefix_build_ms or 0) + provider_ms,
    )


class SalesOnePlusLiveBackend:
    """Allow one blocking or streaming provider call, collectively."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or sales_one_plus_model()
        self.call_count = 0
        self.last_observability: OneCallCacheObservability | None = None

    def _claim_call(self) -> None:
        self.call_count += 1
        if self.call_count > 1:
            raise SalesOnePlusLiveBackendError("sales_one_plus_retry_forbidden")

    def generate(self, invocation: SalesOnePlusInvocation, /) -> object:
        self._claim_call()
        provider_started = time.monotonic()
        response = chat_completions_create(
            model=self.model,
            temperature=0,
            max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=_messages(invocation),
            provider_call_source="sales_fast",
        )
        self.last_observability = _build_observability(
            invocation=invocation,
            response=response,
            requested_model=self.model,
            provider_started=provider_started,
            local_prefix_cache_hit=bool(invocation.local_prefix_cache_hit),
            prefix_build_ms=invocation.prefix_build_ms,
        )
        return (response.choices[0].message.content or "").strip()

    def generate_stream(
        self,
        invocation: SalesOnePlusInvocation,
        on_raw_delta: Callable[[str], None],
        /,
    ) -> None:
        self._claim_call()
        provider_started = time.monotonic()
        stream = chat_completions_create(
            model=self.model,
            temperature=0,
            max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=_messages(invocation),
            stream=True,
            stream_options={"include_usage": True},
            provider_call_source="sales_fast",
        )
        last_chunk: Any = None
        for chunk in stream:
            last_chunk = chunk
            choices = getattr(chunk, "choices", None) or ()
            if not choices:
                continue
            text = getattr(getattr(choices[0], "delta", None), "content", None)
            if text:
                on_raw_delta(str(text))
        if last_chunk is not None:
            self.last_observability = _build_observability(
                invocation=invocation,
                response=last_chunk,
                requested_model=self.model,
                provider_started=provider_started,
                local_prefix_cache_hit=bool(invocation.local_prefix_cache_hit),
                prefix_build_ms=invocation.prefix_build_ms,
            )
