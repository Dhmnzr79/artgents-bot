"""Monetary cap ledger for SPEAKER-LIVE-1 (offline-persisted, eval-only)."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any

USD = Decimal("0.000001")
TIER_256K_MAX_TOKENS = 256_000

# Offline reserve planning only. One billed input token per UTF-8 byte of message content.
# Not a vendor-proven tokenizer upper bound; do not treat as monetary guarantee.
TOKEN_ESTIMATE_METHOD = "utf8_bytes_per_message_content"
MONETARY_ESTIMATE_RELIABILITY = "heuristic_not_vendor_proven"


class SpeakerExperimentCostError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SpeakerExperimentMonetaryCapExceeded(SpeakerExperimentCostError):
    def __init__(self, *, cap_usd: Decimal, reserved_usd: Decimal, spent_usd: Decimal) -> None:
        self.cap_usd = cap_usd
        self.reserved_usd = reserved_usd
        self.spent_usd = spent_usd
        super().__init__(
            "monetary_cap_exceeded",
            f"speaker_experiment_monetary_cap_exceeded:cap={cap_usd} "
            f"spent={spent_usd} reserved={reserved_usd}",
        )


class SpeakerExperimentCostTierExceeded(SpeakerExperimentCostError):
    def __init__(self, estimated_tokens: int) -> None:
        super().__init__(
            "cost_tier_exceeds_offline_bound",
            f"speaker_cost_tier_exceeds_offline_bound:{estimated_tokens}",
        )


def _persist_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd: int | None = None
    try:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        fd = os.open(str(tmp_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        os.write(fd, encoded)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(tmp_path, path)
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        tmp_path.unlink(missing_ok=True)
        raise SpeakerExperimentCostError("cost_ledger_persist_failed", str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SpeakerPricingSnapshot:
    model_id: str
    currency: str
    deployment_scope: str
    input_per_million_usd: str
    output_per_million_usd: str
    cached_input_per_million_usd: str
    input_per_million_usd_high_tier: str
    output_per_million_usd_high_tier: str
    context_tier: str
    pricing_source_url: str
    pricing_checked_on: str
    token_estimate_method: str = TOKEN_ESTIMATE_METHOD

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


DEFAULT_SPEAKER_PRICING = SpeakerPricingSnapshot(
    model_id="qwen3.7-plus-2026-05-26",
    currency="USD",
    deployment_scope="International",
    input_per_million_usd="0.40",
    output_per_million_usd="1.60",
    cached_input_per_million_usd="0.08",
    input_per_million_usd_high_tier="1.20",
    output_per_million_usd_high_tier="4.80",
    context_tier="0<Token<=256K",
    pricing_source_url="https://www.alibabacloud.com/help/en/model-studio/model-pricing",
    pricing_checked_on="2026-09-04",
)


def _money(value: Decimal) -> str:
    return str(value.quantize(USD, rounding=ROUND_HALF_UP))


def _money_ceil(value: Decimal) -> str:
    return str(value.quantize(USD, rounding=ROUND_CEILING))


def _to_decimal(value: str | Decimal | float | int) -> Decimal:
    return Decimal(str(value))


@dataclass
class SpeakerCostAttemptRecord:
    attempt_index: int
    case_id: str
    request_sha256: str
    reserved_usd_upper: str
    status: str = "reserved"
    reserved_at: float = 0.0
    finalized_at: float | None = None
    actual_usd: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_input_tokens_upper: int | None = None
    max_output_tokens: int | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpeakerCostLedger:
    experiment_id: str
    monetary_cap_usd: str
    currency: str = "USD"
    spent_usd: str = "0.000000"
    reserved_usd: str = "0.000000"
    pricing: SpeakerPricingSnapshot = field(default_factory=lambda: DEFAULT_SPEAKER_PRICING)
    attempts: list[SpeakerCostAttemptRecord] = field(default_factory=list)
    ledger_path: Path | None = None

    @property
    def spent(self) -> Decimal:
        return _to_decimal(self.spent_usd)

    @property
    def reserved(self) -> Decimal:
        return _to_decimal(self.reserved_usd)

    @property
    def cap(self) -> Decimal:
        return _to_decimal(self.monetary_cap_usd)

    def load(self) -> None:
        if self.ledger_path is None or not self.ledger_path.exists():
            return
        payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.experiment_id = str(payload["experiment_id"])
        self.monetary_cap_usd = str(payload["monetary_cap_usd"])
        self.currency = str(payload.get("currency", "USD"))
        self.spent_usd = str(payload.get("spent_usd", "0"))
        self.reserved_usd = str(payload.get("reserved_usd", "0"))
        pricing_payload = payload.get("pricing", DEFAULT_SPEAKER_PRICING.to_dict())
        self.pricing = SpeakerPricingSnapshot(**pricing_payload)
        self.attempts = [
            SpeakerCostAttemptRecord(**row) for row in payload.get("attempts", [])
        ]

    def persist(self) -> None:
        if self.ledger_path is None:
            return
        payload = {
            "experiment_id": self.experiment_id,
            "currency": self.currency,
            "monetary_cap_usd": self.monetary_cap_usd,
            "spent_usd": self.spent_usd,
            "reserved_usd": self.reserved_usd,
            "pricing": self.pricing.to_dict(),
            "attempts": [row.to_dict() for row in self.attempts],
        }
        _persist_json(self.ledger_path, payload)

    def summary(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "monetary_cap_usd": self.monetary_cap_usd,
            "spent_usd": self.spent_usd,
            "reserved_usd": self.reserved_usd,
            "outstanding_reserved_usd": _money(self.reserved),
            "remaining_usd": _money(max(self.cap - self.spent - self.reserved, Decimal("0"))),
            "token_estimate_method": self.pricing.token_estimate_method,
        }


def estimate_prompt_tokens_upper_from_messages(messages: list[dict[str, str]]) -> int:
    """Conservative offline upper bound on prompt tokens for sent messages."""

    total = 0
    for message in messages:
        content = str(message["content"])
        total += len(content.encode("utf-8"))
    return total


def estimate_prompt_tokens_upper_from_request(request: dict[str, Any]) -> int:
    from evals.v5.speaker_experiment_backend import build_chat_messages_for_request

    return estimate_prompt_tokens_upper_from_messages(build_chat_messages_for_request(request))


def _pricing_rates_for_prompt_tokens(
    prompt_tokens_upper: int,
    pricing: SpeakerPricingSnapshot,
) -> tuple[Decimal, Decimal]:
    if prompt_tokens_upper <= TIER_256K_MAX_TOKENS:
        return _to_decimal(pricing.input_per_million_usd), _to_decimal(pricing.output_per_million_usd)
    return (
        _to_decimal(pricing.input_per_million_usd_high_tier),
        _to_decimal(pricing.output_per_million_usd_high_tier),
    )


def estimate_attempt_cost_upper_usd(
    *,
    request: dict[str, Any],
    max_output_tokens: int,
    pricing: SpeakerPricingSnapshot = DEFAULT_SPEAKER_PRICING,
) -> tuple[int, Decimal]:
    input_upper = estimate_prompt_tokens_upper_from_request(request)
    if input_upper > TIER_256K_MAX_TOKENS:
        raise SpeakerExperimentCostTierExceeded(input_upper)
    input_rate, output_rate = _pricing_rates_for_prompt_tokens(input_upper, pricing)
    cost = (
        Decimal(input_upper) * input_rate + Decimal(max_output_tokens) * output_rate
    ) / Decimal(1_000_000)
    return input_upper, _to_decimal(_money_ceil(cost))


def compute_actual_cost_usd(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    pricing: SpeakerPricingSnapshot = DEFAULT_SPEAKER_PRICING,
) -> Decimal:
    input_rate, output_rate = _pricing_rates_for_prompt_tokens(prompt_tokens, pricing)
    cached_rate = _to_decimal(pricing.cached_input_per_million_usd)
    billable_input = max(prompt_tokens - cached_tokens, 0)
    return (
        Decimal(billable_input) * input_rate
        + Decimal(cached_tokens) * cached_rate
        + Decimal(completion_tokens) * output_rate
    ) / Decimal(1_000_000)


def estimate_batch_cost_upper_usd(
    *,
    requests: list[dict[str, Any]],
    max_output_tokens: int,
    pricing: SpeakerPricingSnapshot = DEFAULT_SPEAKER_PRICING,
) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []
    total = Decimal("0")
    tier_blocked = False
    for request in requests:
        try:
            input_upper, cost_upper = estimate_attempt_cost_upper_usd(
                request=request,
                max_output_tokens=max_output_tokens,
                pricing=pricing,
            )
        except SpeakerExperimentCostTierExceeded as exc:
            tier_blocked = True
            input_upper = exc.args[0].split(":")[-1]
            cost_upper = Decimal("0")
        total += cost_upper
        per_case.append(
            {
                "case_id": request["case_id"],
                "estimated_input_tokens_upper": input_upper,
                "estimated_cost_upper_usd": _money(cost_upper),
            }
        )
    return {
        "attempt_count": len(requests),
        "max_output_tokens": max_output_tokens,
        "token_estimate_method": TOKEN_ESTIMATE_METHOD,
        "estimate_reliability": MONETARY_ESTIMATE_RELIABILITY,
        "total_estimated_cost_upper_usd": _money(total),
        "tier_blocked": tier_blocked,
        "per_case": per_case,
    }


def _recompute_totals(ledger: SpeakerCostLedger) -> None:
    spent = Decimal("0")
    reserved = Decimal("0")
    for row in ledger.attempts:
        if row.status in {"reserved", "uncertain"}:
            reserved += _to_decimal(row.reserved_usd_upper)
        if row.actual_usd is not None:
            spent += _to_decimal(row.actual_usd)
    ledger.spent_usd = _money(spent)
    ledger.reserved_usd = _money(reserved)


def find_cost_attempt(
    ledger: SpeakerCostLedger,
    *,
    attempt_index: int,
    case_id: str,
    request_sha256: str,
) -> SpeakerCostAttemptRecord | None:
    for row in ledger.attempts:
        if (
            row.attempt_index == attempt_index
            and row.case_id == case_id
            and row.request_sha256 == request_sha256
        ):
            return row
    return None


def assert_cost_budget_available(
    ledger: SpeakerCostLedger,
    *,
    request: dict[str, Any],
    max_output_tokens: int,
) -> tuple[int, Decimal]:
    input_upper, cost_upper = estimate_attempt_cost_upper_usd(
        request=request,
        max_output_tokens=max_output_tokens,
        pricing=ledger.pricing,
    )
    projected_reserved = ledger.reserved + cost_upper
    if ledger.spent + projected_reserved > ledger.cap:
        raise SpeakerExperimentMonetaryCapExceeded(
            cap_usd=ledger.cap,
            reserved_usd=projected_reserved,
            spent_usd=ledger.spent,
        )
    return input_upper, cost_upper


def reserve_cost_before_transport(
    ledger: SpeakerCostLedger,
    *,
    case_id: str,
    attempt_index: int,
    request_sha256: str,
    request: dict[str, Any],
    max_output_tokens: int,
) -> SpeakerCostAttemptRecord:
    existing = find_cost_attempt(
        ledger,
        attempt_index=attempt_index,
        case_id=case_id,
        request_sha256=request_sha256,
    )
    if existing is not None:
        if existing.status in {"finalized", "uncertain"}:
            return existing
        if existing.status == "reserved":
            return existing
    input_upper, cost_upper = assert_cost_budget_available(
        ledger,
        request=request,
        max_output_tokens=max_output_tokens,
    )
    record = SpeakerCostAttemptRecord(
        attempt_index=attempt_index,
        case_id=case_id,
        request_sha256=request_sha256,
        reserved_usd_upper=_money_ceil(cost_upper),
        status="reserved",
        reserved_at=time.time(),
        estimated_input_tokens_upper=input_upper,
        max_output_tokens=max_output_tokens,
    )
    ledger.attempts.append(record)
    _recompute_totals(ledger)
    ledger.persist()
    return record


def expected_pricing_snapshot_from_transport_settings(
    transport_settings: dict[str, Any],
) -> SpeakerPricingSnapshot:
    model_id = str(transport_settings.get("provider_model_id", DEFAULT_SPEAKER_PRICING.model_id))
    deployment_scope = str(
        transport_settings.get("deployment_scope", DEFAULT_SPEAKER_PRICING.deployment_scope)
    )
    base = DEFAULT_SPEAKER_PRICING
    return SpeakerPricingSnapshot(
        model_id=model_id,
        currency=base.currency,
        deployment_scope=deployment_scope,
        input_per_million_usd=base.input_per_million_usd,
        output_per_million_usd=base.output_per_million_usd,
        cached_input_per_million_usd=base.cached_input_per_million_usd,
        input_per_million_usd_high_tier=base.input_per_million_usd_high_tier,
        output_per_million_usd_high_tier=base.output_per_million_usd_high_tier,
        context_tier=base.context_tier,
        pricing_source_url=base.pricing_source_url,
        pricing_checked_on=base.pricing_checked_on,
        token_estimate_method=TOKEN_ESTIMATE_METHOD,
    )


def assert_pricing_snapshot_matches(
    actual: SpeakerPricingSnapshot,
    expected: SpeakerPricingSnapshot,
) -> None:
    if actual.to_dict() != expected.to_dict():
        raise SpeakerExperimentCostError(
            "pricing_snapshot_mismatch",
            f"{actual.model_id}!={expected.model_id}",
        )


def _usage_is_complete(provider_call: dict[str, Any]) -> bool:
    return (
        provider_call.get("prompt_tokens") is not None
        and provider_call.get("completion_tokens") is not None
    )


def validate_provider_usage(provider_call: dict[str, Any]) -> tuple[bool, str | None]:
    if not _usage_is_complete(provider_call):
        return False, "usage_missing"
    try:
        prompt_tokens = int(provider_call["prompt_tokens"])
        completion_tokens = int(provider_call["completion_tokens"])
        cached_tokens = int(provider_call.get("cached_tokens") or 0)
    except (TypeError, ValueError):
        return False, "usage_invalid"
    if prompt_tokens < 0 or completion_tokens < 0 or cached_tokens < 0:
        return False, "usage_invalid"
    if cached_tokens > prompt_tokens:
        return False, "usage_invalid"
    return True, None


def finalize_cost_after_transport(
    ledger: SpeakerCostLedger,
    record: SpeakerCostAttemptRecord,
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cached_tokens: int | None = None,
    outcome: str,
    error_code: str | None = None,
) -> None:
    if record.status == "finalized" and record.actual_usd is not None:
        return
    if prompt_tokens is not None and completion_tokens is not None:
        actual = compute_actual_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens or 0,
            pricing=ledger.pricing,
        )
        record.actual_usd = _money(actual)
        record.prompt_tokens = prompt_tokens
        record.completion_tokens = completion_tokens
        record.cached_tokens = cached_tokens or 0
    record.status = outcome
    record.error_code = error_code
    record.finalized_at = time.time()
    _recompute_totals(ledger)
    ledger.persist()


def finalize_cost_from_provider_call(
    ledger: SpeakerCostLedger,
    record: SpeakerCostAttemptRecord,
    provider_call: dict[str, Any],
) -> None:
    usage_ok, usage_error = validate_provider_usage(provider_call)
    if not usage_ok:
        mark_cost_uncertain(ledger, record, error_code=usage_error)
        return
    finalize_cost_after_transport(
        ledger,
        record,
        prompt_tokens=int(provider_call["prompt_tokens"]),
        completion_tokens=int(provider_call["completion_tokens"]),
        cached_tokens=int(provider_call.get("cached_tokens") or 0),
        outcome="finalized",
    )


def mark_cost_uncertain(
    ledger: SpeakerCostLedger,
    record: SpeakerCostAttemptRecord,
    *,
    error_code: str | None = None,
) -> None:
    if record.status == "uncertain":
        return
    finalize_cost_after_transport(
        ledger,
        record,
        prompt_tokens=None,
        completion_tokens=None,
        outcome="uncertain",
        error_code=error_code,
    )


def reconcile_cost_ledger(
    *,
    cost_ledger: SpeakerCostLedger,
    experiment_id: str,
    attempt_records: list[Any],
    raw_payloads_by_attempt: dict[tuple[str, int], dict[str, Any]],
    requests_by_case_id: dict[str, dict[str, Any]] | None = None,
    max_output_tokens: int = 1024,
    monetary_cap_usd: str | None = None,
) -> None:
    if cost_ledger.experiment_id != experiment_id:
        raise SpeakerExperimentCostError(
            "cost_experiment_mismatch",
            f"{cost_ledger.experiment_id}!={experiment_id}",
        )
    if monetary_cap_usd is not None and cost_ledger.monetary_cap_usd != monetary_cap_usd:
        raise SpeakerExperimentCostError(
            "cost_cap_mismatch",
            f"{cost_ledger.monetary_cap_usd}!={monetary_cap_usd}",
        )

    requests_by_case_id = requests_by_case_id or {}

    for attempt in attempt_records:
        key = (attempt.case_id, attempt.attempt_index)
        raw_payload = raw_payloads_by_attempt.get(key)
        cost_row = find_cost_attempt(
            cost_ledger,
            attempt_index=attempt.attempt_index,
            case_id=attempt.case_id,
            request_sha256=attempt.request_sha256,
        )
        if raw_payload is None:
            if cost_row is not None and cost_row.status == "reserved":
                mark_cost_uncertain(cost_ledger, cost_row, error_code="raw_missing")
            continue

        if str(raw_payload.get("experiment_id", "")) != experiment_id:
            raise SpeakerExperimentCostError(
                "raw_experiment_mismatch",
                f"{attempt.case_id}:{attempt.attempt_index}",
            )
        if str(raw_payload.get("request_sha256", "")) != attempt.request_sha256:
            raise SpeakerExperimentCostError(
                "raw_request_sha256_mismatch",
                f"{attempt.case_id}:{attempt.attempt_index}",
            )

        provider_call = raw_payload.get("provider_call")
        if cost_row is not None and cost_row.status == "finalized":
            continue

        if cost_row is None:
            request = requests_by_case_id.get(attempt.case_id)
            if request is None:
                raise SpeakerExperimentCostError(
                    "cost_recovery_request_missing",
                    f"{attempt.case_id}:{attempt.attempt_index}",
                )
            input_upper, cost_upper = estimate_attempt_cost_upper_usd(
                request=request,
                max_output_tokens=max_output_tokens,
                pricing=cost_ledger.pricing,
            )
            cost_row = SpeakerCostAttemptRecord(
                attempt_index=attempt.attempt_index,
                case_id=attempt.case_id,
                request_sha256=attempt.request_sha256,
                reserved_usd_upper=_money_ceil(cost_upper),
                status="reserved",
                reserved_at=time.time(),
                estimated_input_tokens_upper=input_upper,
                max_output_tokens=max_output_tokens,
            )
            cost_ledger.attempts.append(cost_row)

        if provider_call is None:
            if cost_row.status == "reserved":
                mark_cost_uncertain(cost_ledger, cost_row, error_code="provider_call_missing")
            continue

        finalize_cost_from_provider_call(cost_ledger, cost_row, provider_call)

    _recompute_totals(cost_ledger)
    cost_ledger.persist()
