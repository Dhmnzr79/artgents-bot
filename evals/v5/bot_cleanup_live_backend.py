"""Eval-only provider backend and call budget for bot_cleanup LIVE (sales-fast /ask path)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import config
from contracts.sales_one_plus import SalesOnePlusInvocation
from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError,
    build_openai_compatible_client_kwargs,
    observability_from_base_url,
    validate_alibaba_chat_transport_config,
)
from core.one_call_cache_observability import OneCallCacheObservability
from core.turn_timing import cached_tokens_from_usage
from evals.v5.bot_cleanup_scenarios_format import FUTURE_LIVE_MODEL
from evals.v5.speaker_experiment_cost import (
    SpeakerCostAttemptRecord,
    SpeakerCostLedger,
    SpeakerExperimentMonetaryCapExceeded,
    estimate_prompt_tokens_upper_from_messages,
    finalize_cost_from_provider_call,
    mark_cost_uncertain,
)
from llm import LLM_REQUEST_TIMEOUT_SEC
from decimal import Decimal, ROUND_CEILING

PLUS_MODEL_FAMILY = "qwen3.7-plus"
REQUESTED_PROVIDER_MODEL_ID = FUTURE_LIVE_MODEL

INFERENCE_SETTINGS: dict[str, Any] = {
    "temperature": 0,
    "max_completion_tokens": 1024,
    "timeout_sec": float(LLM_REQUEST_TIMEOUT_SEC),
    "response_format": {"type": "json_object"},
    "stream": False,
    "enable_thinking": False,
    "max_retries": 0,
    "provider_call_source": "bot_cleanup_live",
}


class BotCleanupBudgetExceeded(RuntimeError):
    """Provider attempt blocked before transport."""


class BotCleanupModelMismatch(RuntimeError):
    """Observed provider model is not an allowed resolution of the requested Plus ID."""


class BotCleanupBackendRetryForbidden(RuntimeError):
    """Second generate()/generate_stream() on the same backend instance."""


class BotCleanupTransportAlreadyCompleted(RuntimeError):
    """Provider transport for this turn/request was already finalized."""


class BotCleanupUncertainAttempt(RuntimeError):
    """Prior attempt outcome is reserved/uncertain; manual review required."""


class BotCleanupRequestHashConflict(RuntimeError):
    """Same turn_id was started with a different request hash."""


class BotCleanupRawPersistError(RuntimeError):
    """Provider response snapshot could not be persisted."""


@dataclass
class ProviderAttemptRecord:
    attempt_index: int
    turn_id: str | None
    requested_model: str
    request_sha256: str
    reserved_at: float
    outcome: str = "reserved"
    observed_model: str | None = None
    error_code: str | None = None
    duration_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_index": self.attempt_index,
            "turn_id": self.turn_id,
            "requested_model": self.requested_model,
            "request_sha256": self.request_sha256,
            "reserved_at": self.reserved_at,
            "outcome": self.outcome,
            "observed_model": self.observed_model,
            "error_code": self.error_code,
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
        }


@dataclass
class BotCleanupCallBudget:
    max_calls: int
    consumed: int = 0
    ledger: list[ProviderAttemptRecord] = None  # type: ignore[assignment]
    ledger_path: Any = None

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = []

    def load(self) -> None:
        if self.ledger_path is None or not self.ledger_path.exists():
            return
        payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.max_calls = int(payload.get("max_calls", self.max_calls))
        self.consumed = int(payload.get("consumed", 0))
        self.ledger = [
            ProviderAttemptRecord(**row) for row in payload.get("ledger", [])
        ]

    def persist(self) -> None:
        if self.ledger_path is None:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "max_calls": self.max_calls,
            "consumed": self.consumed,
            "ledger": [row.to_dict() for row in self.ledger],
        }
        self.ledger_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def find_turn_attempt(self, turn_id: str, request_sha256: str) -> ProviderAttemptRecord | None:
        for row in reversed(self.ledger):
            if row.turn_id == turn_id and row.request_sha256 == request_sha256:
                return row
        return None

    def find_turn_records(self, turn_id: str) -> list[ProviderAttemptRecord]:
        return [row for row in self.ledger if row.turn_id == turn_id]

    def assert_turn_transport_allowed(
        self,
        *,
        turn_id: str | None,
        request_sha256: str,
    ) -> ProviderAttemptRecord | None:
        tid = turn_id or ""
        records = self.find_turn_records(tid)
        if not records:
            return None
        hashes = {row.request_sha256 for row in records}
        if request_sha256 not in hashes:
            raise BotCleanupRequestHashConflict(
                f"bot_cleanup_request_hash_conflict:{tid}:{request_sha256}"
            )
        existing = self.find_turn_attempt(tid, request_sha256)
        if existing is None:
            return None
        if existing.outcome in _FINALIZED_BUDGET_OUTCOMES:
            raise BotCleanupTransportAlreadyCompleted(
                f"bot_cleanup_transport_already_completed:{tid}:{existing.outcome}"
            )
        if existing.outcome in _UNCERTAIN_BUDGET_OUTCOMES:
            raise BotCleanupUncertainAttempt(
                f"bot_cleanup_uncertain_attempt:{tid}:{existing.outcome}"
            )
        return existing

    def reserve_before_transport(
        self,
        *,
        turn_id: str | None,
        requested_model: str,
        request_sha256: str,
    ) -> ProviderAttemptRecord:
        existing = self.assert_turn_transport_allowed(
            turn_id=turn_id,
            request_sha256=request_sha256,
        )
        if existing is not None and existing.outcome in _UNCERTAIN_BUDGET_OUTCOMES:
            raise BotCleanupUncertainAttempt(
                f"bot_cleanup_uncertain_attempt:{turn_id}:{existing.outcome}"
            )
        if self.consumed >= self.max_calls:
            raise BotCleanupBudgetExceeded(
                f"bot_cleanup_budget_exhausted:{self.max_calls}"
            )
        self.consumed += 1
        record = ProviderAttemptRecord(
            attempt_index=self.consumed,
            turn_id=turn_id,
            requested_model=requested_model,
            request_sha256=request_sha256,
            reserved_at=time.monotonic(),
        )
        self.ledger.append(record)
        self.persist()
        return record

    def finalize(
        self,
        record: ProviderAttemptRecord,
        *,
        outcome: str,
        observed_model: str | None = None,
        error_code: str | None = None,
        duration_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cached_tokens: int | None = None,
    ) -> None:
        record.outcome = outcome
        record.observed_model = observed_model
        record.error_code = error_code
        record.duration_ms = duration_ms
        record.prompt_tokens = prompt_tokens
        record.completion_tokens = completion_tokens
        record.cached_tokens = cached_tokens
        self.persist()


@dataclass(frozen=True, slots=True)
class BotCleanupTransportObservability:
    provider_kind: str
    endpoint_host: str
    provider_region: str | None
    requested_model: str
    inference_settings: dict[str, Any]


def assert_not_flash_model(model: str) -> None:
    normalized = (model or "").strip().lower()
    if "flash" in normalized:
        raise AlibabaEndpointConfigurationError("bot_cleanup_flash_forbidden", model)
    if not normalized.startswith(PLUS_MODEL_FAMILY):
        raise AlibabaEndpointConfigurationError("bot_cleanup_model_family_invalid", model)


_FINALIZED_BUDGET_OUTCOMES = frozenset({"ok", "error", "model_mismatch"})
_UNCERTAIN_BUDGET_OUTCOMES = frozenset({"reserved", "uncertain"})


def assert_observed_model_exact(*, requested: str, observed: str | None) -> None:
    observed_model = str(observed or "").strip()
    if not observed_model:
        raise BotCleanupModelMismatch(f"model_missing:requested={requested}")
    if observed_model != requested:
        raise BotCleanupModelMismatch(
            f"model_mismatch:requested={requested} observed={observed_model}"
        )


def build_provider_messages(invocation: SalesOnePlusInvocation) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": invocation.system_prompt},
        {"role": "user", "content": invocation.user_prompt},
    ]


def build_provider_request_payload(
    invocation: SalesOnePlusInvocation,
    *,
    model: str = REQUESTED_PROVIDER_MODEL_ID,
    stream: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "temperature": INFERENCE_SETTINGS["temperature"],
        "max_completion_tokens": INFERENCE_SETTINGS["max_completion_tokens"],
        "timeout": INFERENCE_SETTINGS["timeout_sec"],
        "messages": build_provider_messages(invocation),
        "response_format": INFERENCE_SETTINGS["response_format"],
        "stream": stream,
        "provider_call_source": INFERENCE_SETTINGS["provider_call_source"],
        "extra_body": {"enable_thinking": INFERENCE_SETTINGS["enable_thinking"]},
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def hash_provider_request_dict(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def serialize_provider_response(response: Any) -> dict[str, Any]:
    choices: list[dict[str, Any]] = []
    for choice in getattr(response, "choices", None) or ():
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        choices.append({"message": {"content": content}})
    usage = getattr(response, "usage", None)
    usage_dict: dict[str, Any] | None = None
    if usage is not None:
        usage_dict = {
            "prompt_tokens": _usage_int(usage, "prompt_tokens"),
            "completion_tokens": _usage_int(usage, "completion_tokens"),
        }
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            usage_dict["prompt_tokens_details"] = {
                "cached_tokens": _usage_int(details, "cached_tokens"),
            }
    return {
        "model": getattr(response, "model", None),
        "choices": choices,
        "usage": usage_dict,
    }


def rebuild_provider_response(snapshot: dict[str, Any]) -> Any:
    provider_snapshot = snapshot.get("provider_snapshot") or {}
    choices = []
    for item in provider_snapshot.get("choices") or []:
        message = item.get("message") if isinstance(item, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        choices.append(SimpleNamespace(message=SimpleNamespace(content=content)))
    usage_raw = provider_snapshot.get("usage") or {}
    details_raw = usage_raw.get("prompt_tokens_details") or {}
    usage = SimpleNamespace(
        prompt_tokens=usage_raw.get("prompt_tokens"),
        completion_tokens=usage_raw.get("completion_tokens"),
        prompt_tokens_details=SimpleNamespace(
            cached_tokens=details_raw.get("cached_tokens") or 0,
        ),
    )
    return SimpleNamespace(
        model=provider_snapshot.get("model"),
        choices=choices,
        usage=usage,
    )


def provider_raw_content(snapshot: dict[str, Any]) -> str:
    provider_snapshot = snapshot.get("provider_snapshot") or {}
    choices = provider_snapshot.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    return str(content or "")


def resolve_transport_observability() -> BotCleanupTransportObservability:
    base_url, _ = validate_alibaba_chat_transport_config()
    host = (urlparse(base_url).hostname or "").strip().lower()
    obs = observability_from_base_url(base_url)
    return BotCleanupTransportObservability(
        provider_kind=obs.provider_kind,
        endpoint_host=host,
        provider_region=obs.provider_region,
        requested_model=REQUESTED_PROVIDER_MODEL_ID,
        inference_settings=dict(INFERENCE_SETTINGS),
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
) -> OneCallCacheObservability:
    observed = getattr(response, "model", None)
    observed_model = str(observed) if observed is not None else None
    usage = getattr(response, "usage", None)
    cached_tokens = cached_tokens_from_usage(response)
    provider_ms = max(0, int((time.monotonic() - provider_started) * 1000))
    identity = invocation.pack_identity
    return OneCallCacheObservability(
        local_prefix_cache_hit=bool(invocation.local_prefix_cache_hit),
        provider_cache_hit=bool(cached_tokens is not None and cached_tokens > 0),
        cached_tokens=cached_tokens,
        prompt_tokens=_usage_int(usage, "prompt_tokens"),
        completion_tokens=_usage_int(usage, "completion_tokens"),
        client_pack_hash=identity.client_pack_hash,
        prompt_contract_version=identity.prompt_contract_version,
        requested_model=requested_model,
        observed_model=observed_model,
        provider_model_verified=observed_model == requested_model if observed_model else False,
        prefix_build_ms=invocation.prefix_build_ms,
        provider_ms=provider_ms,
        total_ms=(invocation.prefix_build_ms or 0) + provider_ms,
    )


def build_openai_client_for_eval() -> Any:
    from openai import OpenAI

    kwargs = build_openai_compatible_client_kwargs(validate_endpoint=True)
    return OpenAI(**kwargs)


def eval_chat_completions_create(*, model: str, **kwargs: Any) -> Any:
    """Direct SDK call bypassing llm.py http budget (eval budget is authoritative)."""
    client = build_openai_client_for_eval()
    kwargs = dict(kwargs)
    kwargs.pop("provider_call_source", None)
    extra_body = dict(kwargs.pop("extra_body", None) or {})
    if not config.QWEN_ENABLE_THINKING:
        extra_body.setdefault("enable_thinking", False)
    if extra_body:
        kwargs["extra_body"] = extra_body
    return client.chat.completions.create(model=model, **kwargs)


def _money_ceil(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING))


def reserve_bot_cleanup_monetary_cost(
    ledger: SpeakerCostLedger,
    *,
    case_id: str,
    request_sha256: str,
    messages: list[dict[str, str]],
    max_output_tokens: int,
) -> SpeakerCostAttemptRecord:
    for row in ledger.attempts:
        if row.case_id == case_id and row.request_sha256 == request_sha256:
            if row.status in {"finalized", "uncertain"}:
                raise BotCleanupTransportAlreadyCompleted(
                    f"bot_cleanup_cost_already_finalized:{case_id}:{row.status}"
                )
            if row.status == "reserved":
                raise BotCleanupUncertainAttempt(
                    f"bot_cleanup_cost_reserved:{case_id}"
                )
    input_upper = estimate_prompt_tokens_upper_from_messages(messages)
    input_rate = Decimal(ledger.pricing.input_per_million_usd)
    output_rate = Decimal(ledger.pricing.output_per_million_usd)
    cost_upper = (
        Decimal(input_upper) * input_rate + Decimal(max_output_tokens) * output_rate
    ) / Decimal(1_000_000)
    reserved_upper = _money_ceil(cost_upper)
    projected = ledger.spent + ledger.reserved + Decimal(reserved_upper)
    if projected > ledger.cap:
        raise SpeakerExperimentMonetaryCapExceeded(
            cap_usd=ledger.cap,
            reserved_usd=projected,
            spent_usd=ledger.spent,
        )
    record = SpeakerCostAttemptRecord(
        attempt_index=len(ledger.attempts) + 1,
        case_id=case_id,
        request_sha256=request_sha256,
        reserved_usd_upper=reserved_upper,
        status="reserved",
        reserved_at=time.time(),
        estimated_input_tokens_upper=input_upper,
        max_output_tokens=max_output_tokens,
    )
    ledger.attempts.append(record)
    ledger.reserved_usd = _money_ceil(ledger.reserved + Decimal(reserved_upper))
    ledger.persist()
    return record


ProviderRawPersistHook = Callable[[dict[str, Any]], None]


class BotCleanupLiveBackend:
    """One provider call per instance; eval budget + Plus model pin."""

    def __init__(
        self,
        *,
        budget: BotCleanupCallBudget,
        turn_id: str | None = None,
        model: str = REQUESTED_PROVIDER_MODEL_ID,
        chat_completions_create: Callable[..., Any] | None = None,
        cost_ledger: Any | None = None,
        provider_raw_persist: ProviderRawPersistHook | None = None,
        replay_provider_raw: dict[str, Any] | None = None,
        replay_record: ProviderAttemptRecord | None = None,
    ) -> None:
        assert_not_flash_model(model)
        self.model = model
        self.budget = budget
        self.turn_id = turn_id
        self.call_count = 0
        self.last_record: ProviderAttemptRecord | None = None
        self.last_raw_output: str | None = None
        self.last_provider_raw_path: str | None = None
        self.last_observability: OneCallCacheObservability | None = None
        self.last_request_payload: dict[str, Any] | None = None
        self.last_request_sha256: str | None = None
        self.cost_ledger = cost_ledger
        self.last_cost_record: Any | None = None
        self._provider_raw_persist = provider_raw_persist
        self._replay_provider_raw = replay_provider_raw
        self._replay_record = replay_record
        if chat_completions_create is None:
            self._chat_completions_create = eval_chat_completions_create
        else:
            self._chat_completions_create = chat_completions_create

    def _claim_call(self) -> None:
        self.call_count += 1
        if self.call_count > 1:
            raise BotCleanupBackendRetryForbidden("bot_cleanup_retry_forbidden")

    def _persist_provider_snapshot(
        self,
        *,
        record: ProviderAttemptRecord,
        response: Any,
        request_sha256: str,
    ) -> str:
        if self._provider_raw_persist is None:
            raise BotCleanupRawPersistError("provider_raw_persist_hook_missing")
        content = provider_raw_content(
            {"provider_snapshot": serialize_provider_response(response)}
        )
        self.last_raw_output = content
        payload = {
            "turn_id": self.turn_id,
            "attempt_index": record.attempt_index,
            "request_sha256": request_sha256,
            "requested_model": self.model,
            "provider_snapshot": serialize_provider_response(response),
        }
        self._provider_raw_persist(payload)
        return content

    def _finalize_response(
        self,
        record: ProviderAttemptRecord,
        response: Any,
        *,
        started: float,
        content: str,
    ) -> str:
        observed = getattr(response, "model", None)
        observed_model = str(observed) if observed is not None else None
        assert_observed_model_exact(requested=self.model, observed=observed_model)
        usage = getattr(response, "usage", None)
        duration_ms = int((time.monotonic() - started) * 1000)
        cached = cached_tokens_from_usage(response)
        self.budget.finalize(
            record,
            outcome="ok",
            observed_model=observed_model,
            duration_ms=duration_ms,
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            cached_tokens=cached,
        )
        if self.cost_ledger is not None and self.last_cost_record is not None:
            provider_call = {
                "prompt_tokens": _usage_int(usage, "prompt_tokens"),
                "completion_tokens": _usage_int(usage, "completion_tokens"),
                "cached_tokens": cached or 0,
            }
            finalize_cost_from_provider_call(
                self.cost_ledger,
                self.last_cost_record,
                provider_call,
            )
        self.last_raw_output = content
        return content

    def _reserve(self, invocation: SalesOnePlusInvocation, *, stream: bool) -> ProviderAttemptRecord:
        payload = build_provider_request_payload(invocation, model=self.model, stream=stream)
        self.last_request_payload = payload
        self.last_request_sha256 = hash_provider_request_dict(payload)
        if self.cost_ledger is not None and self.turn_id:
            self.last_cost_record = reserve_bot_cleanup_monetary_cost(
                self.cost_ledger,
                case_id=self.turn_id,
                request_sha256=self.last_request_sha256,
                messages=list(payload.get("messages") or []),
                max_output_tokens=int(INFERENCE_SETTINGS["max_completion_tokens"]),
            )
        return self.budget.reserve_before_transport(
            turn_id=self.turn_id,
            requested_model=self.model,
            request_sha256=self.last_request_sha256,
        )

    def _generate_from_replay(
        self,
        invocation: SalesOnePlusInvocation,
        *,
        record: ProviderAttemptRecord,
    ) -> object:
        if self._replay_provider_raw is None:
            raise BotCleanupUncertainAttempt("bot_cleanup_replay_raw_missing")
        response = rebuild_provider_response(self._replay_provider_raw)
        started = time.monotonic()
        content = provider_raw_content(self._replay_provider_raw)
        self.last_raw_output = content
        self.last_observability = _build_observability(
            invocation=invocation,
            response=response,
            requested_model=self.model,
            provider_started=started,
        )
        return self._finalize_response(record, response, started=started, content=content)

    def generate(self, invocation: SalesOnePlusInvocation, /) -> object:
        self._claim_call()
        if self._replay_provider_raw is not None:
            record = self._replay_record
            if record is None:
                request_sha256 = str(self._replay_provider_raw.get("request_sha256") or "")
                record = self.budget.assert_turn_transport_allowed(
                    turn_id=self.turn_id,
                    request_sha256=request_sha256,
                )
            if record is None:
                raise BotCleanupUncertainAttempt("bot_cleanup_replay_record_missing")
            self.last_record = record
            self.last_request_sha256 = record.request_sha256
            return self._generate_from_replay(invocation, record=record)

        record = self._reserve(invocation, stream=False)
        self.last_record = record
        started = time.monotonic()
        payload = dict(self.last_request_payload or {})
        request_sha256 = str(self.last_request_sha256 or "")
        try:
            response = self._chat_completions_create(**payload)
            content = self._persist_provider_snapshot(
                record=record,
                response=response,
                request_sha256=request_sha256,
            )
            self.last_observability = _build_observability(
                invocation=invocation,
                response=response,
                requested_model=self.model,
                provider_started=started,
            )
            return self._finalize_response(record, response, started=started, content=content)
        except BotCleanupBudgetExceeded:
            raise
        except BotCleanupRawPersistError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self.budget.finalize(
                record,
                outcome="uncertain",
                error_code=type(exc).__name__,
                duration_ms=duration_ms,
            )
            if self.cost_ledger is not None and self.last_cost_record is not None:
                mark_cost_uncertain(
                    self.cost_ledger,
                    self.last_cost_record,
                    error_code=type(exc).__name__,
                )
            raise BotCleanupUncertainAttempt(str(exc)) from exc
        except BotCleanupModelMismatch as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self.budget.finalize(
                record,
                outcome="model_mismatch",
                error_code=type(exc).__name__,
                duration_ms=duration_ms,
            )
            if self.cost_ledger is not None and self.last_cost_record is not None:
                mark_cost_uncertain(
                    self.cost_ledger,
                    self.last_cost_record,
                    error_code=type(exc).__name__,
                )
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            outcome = "error" if not isinstance(exc, BotCleanupModelMismatch) else "model_mismatch"
            self.budget.finalize(
                record,
                outcome=outcome,
                error_code=type(exc).__name__,
                duration_ms=duration_ms,
            )
            if self.cost_ledger is not None and self.last_cost_record is not None:
                mark_cost_uncertain(
                    self.cost_ledger,
                    self.last_cost_record,
                    error_code=type(exc).__name__,
                )
            raise

    def generate_stream(
        self,
        invocation: SalesOnePlusInvocation,
        on_raw_delta: Callable[[str], None],
        /,
    ) -> None:
        self._claim_call()
        record = self._reserve(invocation, stream=True)
        self.last_record = record
        started = time.monotonic()
        payload = dict(self.last_request_payload or {})
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        try:
            stream = self._chat_completions_create(**payload)
            last_chunk: Any = None
            parts: list[str] = []
            for chunk in stream:
                last_chunk = chunk
                choices = getattr(chunk, "choices", None) or ()
                if not choices:
                    continue
                text = getattr(getattr(choices[0], "delta", None), "content", None)
                if text:
                    parts.append(str(text))
                    on_raw_delta(str(text))
            if last_chunk is None:
                raise RuntimeError("bot_cleanup_empty_stream")
            content = "".join(parts).strip()
            self.last_raw_output = content
            self.last_observability = _build_observability(
                invocation=invocation,
                response=last_chunk,
                requested_model=self.model,
                provider_started=started,
            )
            self._finalize_response(record, last_chunk, started=started, content=content)
        except BotCleanupBudgetExceeded:
            raise
        except BotCleanupModelMismatch as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self.budget.finalize(
                record,
                outcome="model_mismatch",
                error_code=type(exc).__name__,
                duration_ms=duration_ms,
            )
            if self.cost_ledger is not None and self.last_cost_record is not None:
                mark_cost_uncertain(
                    self.cost_ledger,
                    self.last_cost_record,
                    error_code=type(exc).__name__,
                )
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            outcome = "error" if not isinstance(exc, BotCleanupModelMismatch) else "model_mismatch"
            self.budget.finalize(
                record,
                outcome=outcome,
                error_code=type(exc).__name__,
                duration_ms=duration_ms,
            )
            if self.cost_ledger is not None and self.last_cost_record is not None:
                mark_cost_uncertain(
                    self.cost_ledger,
                    self.last_cost_record,
                    error_code=type(exc).__name__,
                )
            raise
