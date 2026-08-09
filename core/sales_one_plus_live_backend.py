"""Lazy one-shot provider adapter for the dormant one-Plus candidate."""

from __future__ import annotations

import os
from collections.abc import Callable

from contracts.sales_one_plus import SalesOnePlusInvocation
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create


class SalesOnePlusLiveBackendError(RuntimeError):
    """Typed one-shot adapter failure."""


def sales_one_plus_model() -> str:
    return (os.getenv("SALES_ONE_PLUS_MODEL") or "").strip() or "qwen3.7-plus"


def _messages(invocation: SalesOnePlusInvocation) -> tuple[dict[str, str], ...]:
    return (
        {"role": "system", "content": invocation.system_prompt},
        {"role": "user", "content": invocation.user_prompt},
    )


class SalesOnePlusLiveBackend:
    """Allow one blocking or streaming provider call, collectively."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or sales_one_plus_model()
        self.call_count = 0

    def _claim_call(self) -> None:
        self.call_count += 1
        if self.call_count > 1:
            raise SalesOnePlusLiveBackendError("sales_one_plus_retry_forbidden")

    def generate(self, invocation: SalesOnePlusInvocation, /) -> object:
        self._claim_call()
        response = chat_completions_create(
            model=self.model,
            temperature=0,
            max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=_messages(invocation),
            provider_call_source="sales_fast",
        )
        return (response.choices[0].message.content or "").strip()

    def generate_stream(
        self,
        invocation: SalesOnePlusInvocation,
        on_raw_delta: Callable[[str], None],
        /,
    ) -> None:
        self._claim_call()
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
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or ()
            if not choices:
                continue
            text = getattr(getattr(choices[0], "delta", None), "content", None)
            if text:
                on_raw_delta(str(text))
