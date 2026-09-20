"""Bounded live provider for the isolated D2 CP3 A08 harness."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from config import DEFAULT_LLM_MODEL
from contracts.d2_dialogue import D2ProviderInput
from core.one_call_prompt_contract import (
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
    one_call_contract_header,
)
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create


CP3_MAX_PROVIDER_CALLS = 2

D2_DIALOGUE_FOLLOW_UP_INSTRUCTIONS = """=== D2_DIALOGUE_FOLLOW_UP ===
D2_SESSION_CONTEXT is authoritative typed context, not prose to repeat. When its freshness is fresh, ordinary.situation_state is non-null, and the user explicitly names a different D2 direction, emit one price request for that direction: set topic_id to that direction id and service_id=null. Declare a subject with relation=self and age_group=unknown. Set that request's situation to {scope_commitment:"unknown",extent:"unknown",tooth_count:null,jaw:"unknown",continuity:"same"}. The application, not the model, carries the stored situation. Do not select a concrete service merely because the user named a direction.
"""


class D2LiveProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class D2LiveCallObservation:
    call_index: int
    requested_model: str
    observed_model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int


def _usage_int(usage: object, key: str) -> int | None:
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_d2_d1r_messages(request: D2ProviderInput) -> tuple[dict[str, str], dict[str, str]]:
    """Reuse the sole production D1R contract with the captured D2 input."""
    directions = [item.model_dump(mode="json") for item in request.model_view.direction_prices]
    system = "\n\n".join((
        one_call_contract_header(),
        "=== TYPED_ENVELOPE_INSTRUCTIONS ===\n" + ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
        request.model_view.service_reference_catalog.block_text(),
        request.model_view.active_service_catalog.block_text(),
        "=== D2_DIRECTION_PRICES ===\n" + json.dumps(
            directions, ensure_ascii=False, separators=(",", ":"),
        ),
        D2_DIALOGUE_FOLLOW_UP_INSTRUCTIONS,
    ))
    user = "\n\n".join((
        "=== D2_SESSION_CONTEXT ===\n" + request.context.model_dump_json(),
        "=== USER_MESSAGE ===\n" + request.user_message,
    ))
    return {"role": "system", "content": system}, {"role": "user", "content": user}


class D2Cp3LiveProvider:
    """One shared two-call allowance for the two sequential CP3 A08 turns."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_LLM_MODEL,
        transport: Callable[..., object] = chat_completions_create,
        max_calls: int = CP3_MAX_PROVIDER_CALLS,
    ) -> None:
        if max_calls != CP3_MAX_PROVIDER_CALLS:
            raise ValueError("d2_cp3_exactly_two_calls_required")
        self.model = model
        self._transport = transport
        self._max_calls = max_calls
        self.observations: list[D2LiveCallObservation] = []

    @property
    def call_count(self) -> int:
        return len(self.observations)

    def generate(self, request: D2ProviderInput) -> str:
        if self.call_count >= self._max_calls:
            raise D2LiveProviderError("d2_cp3_provider_budget_exhausted")
        call_index = self.call_count + 1
        system, user = build_d2_d1r_messages(request)
        started = time.monotonic()
        response = self._transport(
            model=self.model,
            temperature=0,
            max_completion_tokens=1024,
            timeout=LLM_REQUEST_TIMEOUT_SEC,
            messages=(system, user),
            response_format={"type": "json_object"},
            provider_call_source="d2_cp3_live",
        )
        choices = getattr(response, "choices", None) or ()
        if not choices:
            raise D2LiveProviderError("d2_cp3_response_choices_missing")
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if not isinstance(content, str) or not content.strip():
            raise D2LiveProviderError("d2_cp3_response_content_missing")
        usage = getattr(response, "usage", None)
        observed = getattr(response, "model", None)
        self.observations.append(D2LiveCallObservation(
            call_index=call_index,
            requested_model=self.model,
            observed_model=str(observed) if observed is not None else None,
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        ))
        return content.strip()
