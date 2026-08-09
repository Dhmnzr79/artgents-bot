"""Offline ONE_CALL Flash capability harness — frozen plan, fake transport only (Stage 3A).

Stage 3B gap (not claimed LIVE-ready): wall-timeout enforcement and Windows process
isolation for real provider transport — see STAGE_3B_LIVE_GAPS in contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from core.one_call_closed_envelope_validation import (
    ClosedEnvelopeValidationError,
    parse_and_validate_closed_envelope_json,
    sample_valid_json_mode_envelope,
)
from core.sales_one_plus_protocol import SalesOnePlusProtocolError, parse_sales_one_plus_output
from evals.v5.one_call_flash_capability_contract import (
    CapabilityCaseSpec,
    CapabilityOutcome,
    FROZEN_CAPABILITY_CASES,
    JSON_MODE_PROBE_USER,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_CALLS,
    MODEL_SNAPSHOT,
    PROPOSED_LIVE_ATTEMPT_ID,
    STAGE_3B_LIVE_GAPS,
    build_attempt_marker_payload,
)


class CapabilityHarnessBlockedError(RuntimeError):
    """LIVE gate closed — no provider calls permitted."""


class CapabilityBudgetExceededError(RuntimeError):
    """Harness exceeded MAX_CALLS budget."""


class ResponseFormatUnsupportedError(RuntimeError):
    """Provider rejected response_format (typed transport error)."""


STABLE_PREFIX_BYTES = "STABLE_PREFIX_BYTE_IDENTICAL_FOR_CACHE_PROBES"
CACHE_COLD_DYNAMIC_SUFFIX = "DYNAMIC_SUFFIX_CACHE_COLD_ONLY"
CACHE_REPEAT_DYNAMIC_SUFFIX = "DYNAMIC_SUFFIX_CACHE_REPEAT_ONLY"


@dataclass(frozen=True, slots=True)
class FakeProviderResponse:
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    raise_error: Exception | None = None
    malformed: bool = False


@dataclass
class FakeProviderTransport:
    """Single-shot fake transport — one attempt per chat_completions_create call."""

    responses: list[FakeProviderResponse]
    calls: int = 0
    attempts_per_case: dict[str, int] = field(default_factory=dict)
    _current_case_id: str | None = None

    def set_case(self, case_id: str) -> None:
        self._current_case_id = case_id

    def chat_completions_create(self, **kwargs: Any) -> Any:
        self.calls += 1
        if self.calls > MAX_CALLS:
            raise CapabilityBudgetExceededError("capability_max_calls_exceeded")
        case_id = self._current_case_id or f"call_{self.calls}"
        attempt = self.attempts_per_case.get(case_id, 0) + 1
        self.attempts_per_case[case_id] = attempt
        if attempt > 1:
            raise RuntimeError("capability_case_retry_forbidden")

        index = min(self.calls - 1, len(self.responses) - 1)
        payload = self.responses[index]
        if payload.raise_error is not None:
            raise payload.raise_error

        if kwargs.get("stream"):
            return self._stream(payload)
        return self._blocking(payload)

    def _blocking(self, payload: FakeProviderResponse) -> Any:
        class _Message:
            content = payload.content if not payload.malformed else None

        class _Choice:
            message = _Message()

        class _Details:
            cached_tokens = payload.cached_tokens

        class _Usage:
            prompt_tokens = payload.prompt_tokens
            completion_tokens = payload.completion_tokens
            prompt_tokens_details = _Details()

        class _Response:
            model = payload.model
            choices = [_Choice()]
            usage = _Usage()

        return _Response()

    def _stream(self, payload: FakeProviderResponse) -> list[Any]:
        class _Delta:
            content = payload.content if not payload.malformed else None

        class _Choice:
            delta = _Delta()

        class _Details:
            cached_tokens = payload.cached_tokens

        class _Usage:
            prompt_tokens = payload.prompt_tokens
            completion_tokens = payload.completion_tokens
            prompt_tokens_details = _Details()

        class _Chunk:
            choices = [_Choice()]
            model = payload.model
            usage = _Usage()

        return [_Chunk()]


@dataclass(frozen=True, slots=True)
class CapabilityCaseResult:
    case_id: str
    outcome: CapabilityOutcome
    requested_model: str
    observed_model: str | None
    provider_model_verified: bool
    stream: bool
    response_format_strategy: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    transport_attempts: int
    error_code: str | None = None


def assert_live_gate_closed() -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is not None:
        raise CapabilityHarnessBlockedError("live_gate_must_remain_none_in_stage3a")


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


def _cache_probe_messages(dynamic_suffix: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": STABLE_PREFIX_BYTES},
        {"role": "user", "content": dynamic_suffix},
    ]


def _json_mode_messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": JSON_MODE_PROBE_USER}]


def _legacy_messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "Capability legacy line-protocol probe."}]


def _messages_for_case(case: CapabilityCaseSpec) -> list[dict[str, str]]:
    if case.case_id == "cache_cold":
        return _cache_probe_messages(CACHE_COLD_DYNAMIC_SUFFIX)
    if case.case_id == "cache_repeat":
        return _cache_probe_messages(CACHE_REPEAT_DYNAMIC_SUFFIX)
    if case.response_format_strategy == "json_mode":
        return _json_mode_messages()
    return _legacy_messages()


def _classify_transport_error(error: Exception) -> CapabilityOutcome:
    if isinstance(error, ResponseFormatUnsupportedError):
        return "unsupported"
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


def execute_capability_case(
    transport: FakeProviderTransport,
    case: CapabilityCaseSpec,
    *,
    messages: list[dict[str, str]] | None = None,
) -> CapabilityCaseResult:
    """Run one frozen case with at most one transport attempt."""

    assert_live_gate_closed()
    transport.set_case(case.case_id)
    case_messages = messages or _messages_for_case(case)
    kwargs: dict[str, Any] = {
        "model": case.requested_model,
        "messages": case_messages,
        "temperature": 0,
    }
    if case.response_format_strategy == "json_mode":
        kwargs["response_format"] = {"type": "json_object"}
    if case.stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

    error: Exception | None = None
    observed_model: str | None = None
    content: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    attempts_before = transport.attempts_per_case.get(case.case_id, 0)

    try:
        if case.stream:
            stream = transport.chat_completions_create(**kwargs)
            last = None
            for chunk in stream:
                last = chunk
                choices = getattr(chunk, "choices", None) or ()
                if choices:
                    text = getattr(getattr(choices[0], "delta", None), "content", None)
                    if text:
                        content = (content or "") + str(text)
            if last is not None:
                observed_model = getattr(last, "model", None)
                prompt_tokens, completion_tokens, cached_tokens = _usage_from_response(last)
        else:
            resp = transport.chat_completions_create(**kwargs)
            observed_model = getattr(resp, "model", None)
            choices = getattr(resp, "choices", None) or ()
            if choices:
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None)
            prompt_tokens, completion_tokens, cached_tokens = _usage_from_response(resp)
    except Exception as exc:  # noqa: BLE001
        error = exc

    attempts = transport.attempts_per_case.get(case.case_id, 0) - attempts_before
    outcome = _classify_outcome(
        case=case,
        observed_model=str(observed_model) if observed_model is not None else None,
        content=str(content) if content is not None else None,
        cached_tokens=cached_tokens,
        error=error,
        messages=case_messages,
    )
    verified = observed_model == case.requested_model if observed_model else False
    return CapabilityCaseResult(
        case_id=case.case_id,
        outcome=outcome,
        requested_model=case.requested_model,
        observed_model=str(observed_model) if observed_model is not None else None,
        provider_model_verified=verified,
        stream=case.stream,
        response_format_strategy=case.response_format_strategy,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        transport_attempts=max(1, attempts) if error is None or attempts > 0 else 1,
        error_code=type(error).__name__ if error is not None else None,
    )


def run_offline_capability_plan(
    transport: FakeProviderTransport,
    *,
    cases: tuple[CapabilityCaseSpec, ...] = FROZEN_CAPABILITY_CASES,
    messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute frozen offline capability plan — fake transport only."""

    assert_live_gate_closed()
    results: list[CapabilityCaseResult] = []
    for case in cases:
        if transport.calls >= MAX_CALLS:
            break
        result = execute_capability_case(
            transport,
            case,
            messages=messages if messages is not None else None,
        )
        results.append(result)

    json_mode_results = [
        result for result in results if result.response_format_strategy == "json_mode"
    ]
    offline_json_mode_validator_passed = bool(json_mode_results) and all(
        result.outcome == "supported" for result in json_mode_results
    )
    provider_json_mode_support_asserted = (
        LIVE_AUTHORIZED_ATTEMPT_ID is not None and offline_json_mode_validator_passed
    )
    return {
        "measurement_id": "one_call_flash_capability",
        "model_snapshot": MODEL_SNAPSHOT,
        "live_gate": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "max_calls": MAX_CALLS,
        "provider_calls": transport.calls,
        "provider_json_mode_support_asserted": provider_json_mode_support_asserted,
        "offline_json_mode_validator_passed": offline_json_mode_validator_passed,
        "stage_3b_live_gaps": list(STAGE_3B_LIVE_GAPS),
        "attempt_marker": build_attempt_marker_payload(),
        "case_results": [asdict(result) for result in results],
    }


def sample_offline_fake_responses() -> list[FakeProviderResponse]:
    """Default fake transport payloads aligned with frozen six-case plan."""

    envelope = sample_valid_json_mode_envelope()
    return [
        FakeProviderResponse(model=MODEL_SNAPSHOT, content=envelope),
        FakeProviderResponse(model=MODEL_SNAPSHOT, content=envelope),
        FakeProviderResponse(model=MODEL_SNAPSHOT, content="@ANSWER\nlegacy ok"),
        FakeProviderResponse(model=MODEL_SNAPSHOT, content="@ANSWER\nlegacy stream ok"),
        FakeProviderResponse(model=MODEL_SNAPSHOT, content="@ANSWER\ncold", cached_tokens=0),
        FakeProviderResponse(
            model=MODEL_SNAPSHOT,
            content="@ANSWER\nwarm",
            cached_tokens=128,
        ),
    ]


def run_offline_capability_matrix(
    transport: FakeProviderTransport,
    *,
    blocking_fn: Callable[[FakeProviderTransport], Any] | None = None,
    streaming_fn: Callable[[FakeProviderTransport], Any] | None = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper — prefer run_offline_capability_plan."""

    if blocking_fn is None and streaming_fn is None:
        return run_offline_capability_plan(transport)
    assert_live_gate_closed()
    if blocking_fn is not None:
        blocking_fn(transport)
    if streaming_fn is not None:
        streaming_fn(transport)
    return run_offline_capability_plan(transport)
