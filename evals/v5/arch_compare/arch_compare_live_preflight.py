"""Capability preflight state machine for architecture comparison LIVE prep (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from evals.v5.arch_compare.arch_compare_configs import (
    FLASH_PROVIDER_MODEL_ID,
    PLUS_PROVIDER_MODEL_ID,
    ArchCompareConfig,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_contract import CONFIG_FLASH_FULL, CONFIG_PLUS_FULL
from evals.v5.arch_compare.arch_compare_fake_transport import (
    ArchCompareFakeTransport,
    build_fake_envelope_json,
)
from evals.v5.arch_compare.arch_compare_live_contract import (
    CAPABILITY_PREFLIGHT_BUDGET,
    MEASUREMENT_PROVIDER_BUDGET,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
)
from evals.v5.arch_compare.arch_compare_provider_payload import build_composer_provider_payload

PreflightCheckStatus = Literal["pass", "fail"]


class ArchComparePreflightBudgetError(RuntimeError):
    code = "preflight_budget_error"




@dataclass(frozen=True, slots=True)
class ArchComparePreflightCheck:
    name: str
    status: PreflightCheckStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArchComparePreflightResult:
    model_role: str
    provider_model_id: str
    success: bool
    checks: tuple[ArchComparePreflightCheck, ...]
    provider_call_count: int
    error_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_role": self.model_role,
            "provider_model_id": self.provider_model_id,
            "success": self.success,
            "checks": [row.to_dict() for row in self.checks],
            "provider_call_count": self.provider_call_count,
            "error_code": self.error_code,
        }


@dataclass
class ArchComparePreflightStateMachine:
    """Budget-aware preflight gate before measurement (mock-only in prep checkpoint)."""

    preflight_budget: int = CAPABILITY_PREFLIGHT_BUDGET
    measurement_budget: int = MEASUREMENT_PROVIDER_BUDGET
    total_authorized: int = TOTAL_AUTHORIZED_PROVIDER_BUDGET
    preflight_consumed: int = 0
    measurement_consumed: int = 0
    flash_result: ArchComparePreflightResult | None = None
    plus_result: ArchComparePreflightResult | None = None
    readiness_state: str = "PREPARED_LIVE_DISABLED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_budget": self.preflight_budget,
            "measurement_budget": self.measurement_budget,
            "total_authorized": self.total_authorized,
            "preflight_consumed": self.preflight_consumed,
            "measurement_consumed": self.measurement_consumed,
            "flash_result": self.flash_result.to_dict() if self.flash_result else None,
            "plus_result": self.plus_result.to_dict() if self.plus_result else None,
            "readiness_state": self.readiness_state,
            "can_start_measurement": self.can_start_measurement(),
        }

    def can_start_measurement(self) -> bool:
        return bool(
            self.flash_result
            and self.plus_result
            and self.flash_result.success
            and self.plus_result.success
            and self.preflight_consumed == self.preflight_budget
        )

    def reserve_preflight(self) -> None:
        if self.preflight_consumed >= self.preflight_budget:
            raise ArchComparePreflightBudgetError(
                f"preflight_budget_exhausted:consumed={self.preflight_consumed} max={self.preflight_budget}"
            )
        self.preflight_consumed += 1

    def reserve_measurement(self) -> None:
        if not self.can_start_measurement():
            raise ArchComparePreflightBudgetError(
                "measurement_blocked_until_preflight:measurement requires two successful preflight calls"
            )
        if self.measurement_consumed >= self.measurement_budget:
            raise ArchComparePreflightBudgetError(
                f"measurement_budget_exhausted:consumed={self.measurement_consumed} max={self.measurement_budget}"
            )
        self.measurement_consumed += 1

    def assert_total_budget(self) -> None:
        total = self.preflight_consumed + self.measurement_consumed
        if total > self.total_authorized:
            raise ArchComparePreflightBudgetError(
                f"total_provider_budget_exceeded:total={total} max={self.total_authorized}"
            )


def _validate_preflight_envelope(*, content: str, provider_model_id: str) -> list[ArchComparePreflightCheck]:
    checks: list[ArchComparePreflightCheck] = []
    if not content.strip():
        checks.append(ArchComparePreflightCheck("envelope_non_empty", "fail", "empty content"))
    else:
        checks.append(ArchComparePreflightCheck("envelope_non_empty", "pass", "content present"))
    if '"route"' not in content:
        checks.append(ArchComparePreflightCheck("structured_output", "fail", "route missing"))
    else:
        checks.append(ArchComparePreflightCheck("structured_output", "pass", "route present"))
    if provider_model_id not in (FLASH_PROVIDER_MODEL_ID, PLUS_PROVIDER_MODEL_ID):
        checks.append(ArchComparePreflightCheck("model_id_allowed", "fail", provider_model_id))
    else:
        checks.append(ArchComparePreflightCheck("model_id_allowed", "pass", provider_model_id))
    checks.append(ArchComparePreflightCheck("tools_disabled", "pass", "mock transport has no tools"))
    checks.append(ArchComparePreflightCheck("web_search_disabled", "pass", "mock transport has no web search"))
    return checks


def _run_mock_preflight_for_config(
    *,
    transport: ArchCompareFakeTransport,
    config: ArchCompareConfig,
    attempt_id: str,
) -> ArchComparePreflightResult:
    envelope = build_fake_envelope_json(
        scenario_id="PREFLIGHT",
        turn_id=f"PREFLIGHT_{config.model_role}",
        route="ANSWER",
        patient_text=f"arch_compare_preflight:{attempt_id}:{config.model_role}",
    )
    transport.prepare_turn_envelopes((envelope,))
    payload = build_composer_provider_payload(
        config=config,
        messages=({"role": "user", "content": "preflight"},),
        stream=False,
    )
    response = transport.chat_completions_create(**payload)
    content = response.choices[0].message.content
    checks = _validate_preflight_envelope(content=content, provider_model_id=config.provider_model_id)
    success = all(row.status == "pass" for row in checks)
    return ArchComparePreflightResult(
        model_role=config.model_role,
        provider_model_id=config.provider_model_id,
        success=success,
        checks=tuple(checks),
        provider_call_count=1,
        error_code=None if success else "preflight_validation_failed",
    )


def run_mock_capability_preflight(
    *,
    attempt_id: str,
    transport: ArchCompareFakeTransport,
    state: ArchComparePreflightStateMachine,
) -> tuple[ArchComparePreflightResult, ArchComparePreflightResult | None]:
    flash_config = config_by_id(CONFIG_FLASH_FULL)
    state.reserve_preflight()
    flash_result = _run_mock_preflight_for_config(
        transport=transport,
        config=flash_config,
        attempt_id=attempt_id,
    )
    state.flash_result = flash_result
    transport.reset_calls()
    if not flash_result.success:
        state.readiness_state = "PREFLIGHT_FAILED"
        state.plus_result = None
        return flash_result, None

    state.reserve_preflight()
    plus_config = config_by_id(CONFIG_PLUS_FULL)
    plus_result = _run_mock_preflight_for_config(
        transport=transport,
        config=plus_config,
        attempt_id=attempt_id,
    )
    state.plus_result = plus_result
    transport.reset_calls()
    if not plus_result.success:
        state.readiness_state = "PREFLIGHT_FAILED"
        return flash_result, plus_result

    state.readiness_state = "READY_FOR_MEASUREMENT"
    return flash_result, plus_result


def assert_authorization_manifest_budget(*, max_provider_calls: int, includes_preflight: bool) -> None:
    from evals.v5.arch_compare.arch_compare_live_contract import (
        TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        assert_authorization_manifest_budget as _assert_budget,
    )

    _assert_budget(max_provider_calls=max_provider_calls, includes_preflight=includes_preflight)


def assert_cache_probe_separate_budget(*, cache_probe_calls: int, measurement_remaining: int) -> None:
    from evals.v5.arch_compare.arch_compare_live_contract import (
        assert_cache_probe_separate_budget as _assert_probe,
    )

    _assert_probe(cache_probe_calls=cache_probe_calls, measurement_remaining=measurement_remaining)
