"""Scoped fake provider transport for Stage 5.3 offline harness."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from config import SALES_ONE_PLUS_FLASH_MODEL

_STAGE53_FAKE_QUEUE: ContextVar[tuple[str, ...] | None] = ContextVar(
    "stage53_fake_queue",
    default=None,
)


@dataclass
class Stage53FakeTransport:
    """Returns scripted production envelopes from an internal per-turn queue."""

    calls: list[dict[str, object]] = field(default_factory=list)

    def chat_completions_create(self, **kwargs: Any) -> Any:
        source = str(kwargs.get("provider_call_source") or "unknown")
        model = str(kwargs.get("model") or SALES_ONE_PLUS_FLASH_MODEL)
        stream = bool(kwargs.get("stream"))
        queue = _STAGE53_FAKE_QUEUE.get()
        if queue is None or not queue:
            raise RuntimeError(
                f"stage53_fake_queue_empty for provider_call_source={source!r}"
            )
        content = queue[0]
        remaining = queue[1:]
        _STAGE53_FAKE_QUEUE.set(remaining if remaining else None)
        self.calls.append(
            {
                "source": source,
                "model": model,
                "stream": stream,
            }
        )
        if stream:
            return self._stream(content, model=model)
        return self._blocking(content, model=model)

    def reset_calls(self) -> None:
        self.calls.clear()

    @staticmethod
    def _blocking(content: str, *, model: str) -> SimpleNamespace:
        return SimpleNamespace(
            model=model,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=128,
                completion_tokens=64,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )

    @staticmethod
    def _stream(content: str, *, model: str):
        payload = json.dumps({"delta": content}, ensure_ascii=False)
        yield SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=payload))],
        )
        yield SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=""))],
            usage=SimpleNamespace(
                prompt_tokens=128,
                completion_tokens=64,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


def push_fake_envelope_queue(envelopes: tuple[str, ...]) -> Token:
    """Install the next envelope(s) for the current harness turn."""

    return _STAGE53_FAKE_QUEUE.set(envelopes if envelopes else None)


def reset_fake_envelope_queue(token: Token | None = None) -> None:
    if token is None:
        _STAGE53_FAKE_QUEUE.set(None)
        return
    _STAGE53_FAKE_QUEUE.reset(token)


def current_fake_envelope_queue() -> tuple[str, ...] | None:
    value = _STAGE53_FAKE_QUEUE.get()
    if value is None:
        return None
    return tuple(value)
