"""Single-case LIVE transport execution for ONE_CALL Flash capability (Stage 3B)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError,
    AlibabaTransportObservability,
    observability_from_base_url,
    validate_alibaba_chat_transport_config,
    validate_capability_live_model,
)
from core.one_call_closed_envelope_validation import (
    ClosedEnvelopeValidationError,
    parse_and_validate_closed_envelope_json,
)
from core.sales_one_plus_protocol import SalesOnePlusProtocolError, parse_sales_one_plus_output
from evals.v5.one_call_flash_capability_contract import CapabilityCaseSpec, CapabilityOutcome
from evals.v5.one_call_flash_capability_harness import ResponseFormatUnsupportedError
from evals.v5.one_call_flash_capability_plan import excerpt_text, messages_for_live_case


@dataclass(frozen=True, slots=True)
class CapabilityLiveTransportResult:
    outcome: CapabilityOutcome
    observed_model: str | None
    content: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    transport_attempts: int
    ttft_ms: int | None
    total_ms: int
    first_delta_excerpt: str | None
    error_code: str | None
    provider_kind: str | None
    provider_region: str | None


def _usage_from_response(resp: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None, None, None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    return (
        int(prompt) if prompt is not None else None,
        int(completion) if completion is not None else None,
        int(cached) if cached is not None else None,
    )


def _messages_contain_json_word(messages: list[dict[str, str]]) -> bool:
    for message in messages:
        content = str(message.get("content") or "")
        if "json" in content.lower():
            return True
    return False


def _classify_transport_error(error: Exception) -> CapabilityOutcome:
    if isinstance(error, ResponseFormatUnsupportedError):
        return "unsupported"
    if isinstance(error, AlibabaEndpointConfigurationError):
        return "transport_error"
    message = str(error).lower()
    if "response_format" in message and "unsupported" in message:
        return "unsupported"
    return "transport_error"


def _validate_legacy_content(
    *,
    observed_model: str | None,
    requested_model: str,
    content: str | None,
) -> CapabilityOutcome:
    if observed_model is None:
        return "malformed"
    if observed_model != requested_model:
        return "model_mismatch"
    if content is None or not str(content).strip():
        return "malformed"
    try:
        parse_sales_one_plus_output(content)
    except SalesOnePlusProtocolError:
        return "malformed"
    return "supported"


def _validate_json_mode_content(
    *,
    observed_model: str | None,
    requested_model: str,
    content: str | None,
) -> CapabilityOutcome:
    if observed_model is None:
        return "malformed"
    if observed_model != requested_model:
        return "model_mismatch"
    if content is None or not str(content).strip():
        return "malformed"
    try:
        parse_and_validate_closed_envelope_json(str(content))
    except ClosedEnvelopeValidationError:
        return "malformed"
    return "supported"


def _classify_outcome(
    *,
    case: CapabilityCaseSpec,
    observed_model: str | None,
    content: str | None,
    cached_tokens: int | None,
    error: Exception | None,
    messages: list[dict[str, str]],
) -> CapabilityOutcome:
    if error is not None:
        return _classify_transport_error(error)
    if case.response_format_strategy == "json_mode":
        if not _messages_contain_json_word(messages):
            return "malformed"
        return _validate_json_mode_content(
            observed_model=observed_model,
            requested_model=case.requested_model,
            content=content,
        )
    if case.case_id == "cache_repeat":
        if cached_tokens is None or cached_tokens <= 0:
            return "cache_miss"
        return _validate_legacy_content(
            observed_model=observed_model,
            requested_model=case.requested_model,
            content=content,
        )
    if case.case_id == "cache_cold":
        return _validate_legacy_content(
            observed_model=observed_model,
            requested_model=case.requested_model,
            content=content,
        )
    return _validate_legacy_content(
        observed_model=observed_model,
        requested_model=case.requested_model,
        content=content,
    )


def execute_live_capability_transport(
    case: CapabilityCaseSpec,
    *,
    attempt_id: str,
    transport: Callable[..., Any],
    eval_stable_prefix: str | None = None,
    transport_attempt_counter: dict[str, int] | None = None,
    validate_endpoint: bool = True,
) -> CapabilityLiveTransportResult:
    """Run one frozen case with at most one transport attempt."""

    if validate_endpoint:
        validate_capability_live_model(case.requested_model)
        base_url, _ = validate_alibaba_chat_transport_config()
        observability = observability_from_base_url(base_url)
    else:
        observability = AlibabaTransportObservability(provider_region="offline_fake")

    case_messages = messages_for_live_case(
        case,
        attempt_id=attempt_id,
        eval_stable_prefix=eval_stable_prefix,
    )
    kwargs: dict[str, Any] = {
        "model": case.requested_model,
        "messages": case_messages,
        "temperature": 0,
        "provider_call_source": f"one_call_flash_capability:{case.case_id}",
    }
    if case.response_format_strategy == "json_mode":
        kwargs["response_format"] = {"type": "json_object"}
    if case.stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

    attempts_before = 0
    if transport_attempt_counter is not None:
        attempts_before = transport_attempt_counter.get(case.case_id, 0)

    started = time.monotonic()
    error: Exception | None = None
    observed_model: str | None = None
    content: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    ttft_ms: int | None = None
    first_delta_excerpt: str | None = None

    try:
        if case.stream:
            stream = transport(**kwargs)
            last_usage_chunk = None
            for chunk in stream:
                if ttft_ms is None:
                    ttft_ms = int((time.monotonic() - started) * 1000)
                chunk_model = getattr(chunk, "model", None)
                if observed_model is None and chunk_model:
                    observed_model = chunk_model
                if getattr(chunk, "usage", None) is not None:
                    last_usage_chunk = chunk
                choices = getattr(chunk, "choices", None) or ()
                if choices:
                    text = getattr(getattr(choices[0], "delta", None), "content", None)
                    if text:
                        if first_delta_excerpt is None:
                            first_delta_excerpt = excerpt_text(str(text), max_chars=64)
                        content = (content or "") + str(text)
            if last_usage_chunk is not None:
                prompt_tokens, completion_tokens, cached_tokens = _usage_from_response(
                    last_usage_chunk
                )
        else:
            resp = transport(**kwargs)
            observed_model = getattr(resp, "model", None)
            choices = getattr(resp, "choices", None) or ()
            if choices:
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None)
            prompt_tokens, completion_tokens, cached_tokens = _usage_from_response(resp)
    except Exception as exc:  # noqa: BLE001
        error = exc

    total_ms = int((time.monotonic() - started) * 1000)
    attempts = 1
    if transport_attempt_counter is not None:
        transport_attempt_counter[case.case_id] = attempts_before + 1
        attempts = transport_attempt_counter[case.case_id] - attempts_before

    outcome = _classify_outcome(
        case=case,
        observed_model=str(observed_model) if observed_model is not None else None,
        content=str(content) if content is not None else None,
        cached_tokens=cached_tokens,
        error=error,
        messages=case_messages,
    )
    return CapabilityLiveTransportResult(
        outcome=outcome,
        observed_model=str(observed_model) if observed_model is not None else None,
        content=str(content) if content is not None else None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        transport_attempts=max(1, attempts) if error is None or attempts > 0 else 1,
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        first_delta_excerpt=first_delta_excerpt,
        error_code=type(error).__name__ if error is not None else None,
        provider_kind=observability.provider_kind,
        provider_region=observability.provider_region,
    )


def default_live_transport() -> Callable[..., Any]:
    from llm import chat_completions_create

    return chat_completions_create
