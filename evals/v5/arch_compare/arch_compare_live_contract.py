"""Frozen contract for architecture comparison LIVE preparation (CP-ARCH-COMPARE-LIVE-PREP-V1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

from evals.v5.arch_compare.arch_compare_configs import (
    ARCH_COMPARE_INFERENCE_SETTINGS,
    FLASH_PROVIDER_MODEL_ID,
    PLUS_MODEL_FAMILY,
    PLUS_MODEL_SNAPSHOT,
    PLUS_OFFICIAL_SOURCES,
    PLUS_PROVIDER_MODEL_ID,
    all_arch_compare_configs,
)
from evals.v5.arch_compare.arch_compare_contract import (
    CLIENT_ID,
    CONFIG_IDS,
    EXPECTED_SCENARIO_CONFIG_RESULTS,
    EXPECTED_TURN_CONFIG_RESULTS,
    FROZEN_MATRIX_DIGEST,
    MEASUREMENT_ID,
)

LIVE_PREP_MEASUREMENT_ID = "one_call_arch_compare_live_prep_v1"
LIVE_MEASUREMENT_ID = "one_call_arch_compare_live_v1"

MAX_RETRIES = 0
DEFAULT_CLIENT_ID = CLIENT_ID

EVAL_REQUEST_TIMEOUT_SEC = 60
PRODUCTION_SLA_REFERENCE_SEC = 20

CAPABILITY_PREFLIGHT_BUDGET = 2
MEASUREMENT_PROVIDER_BUDGET = 68
TOTAL_AUTHORIZED_PROVIDER_BUDGET = CAPABILITY_PREFLIGHT_BUDGET + MEASUREMENT_PROVIDER_BUDGET
OPTIONAL_CACHE_PROBE_BUDGET = 4

FAKE_LIVE_DISCLAIMER = (
    "FAKE — НЕ ДЛЯ ОЦЕНКИ КАЧЕСТВА МОДЕЛИ. "
    "Offline/fake wiring only; 0 provider/network calls."
)

LiveReadinessState = Literal[
    "PREPARED_LIVE_DISABLED",
    "READY_FOR_AUTHORIZED_PREFLIGHT",
    "PREFLIGHT_PENDING",
    "PREFLIGHT_FAILED",
    "READY_FOR_MEASUREMENT",
    "MEASUREMENT_IN_PROGRESS",
    "MEASUREMENT_COMPLETE",
    "MEASUREMENT_COMPLETE_WITH_ERRORS",
    "MEASUREMENT_FAILED",
    "INCOMPLETE_FATAL",
]

OWNER_REVIEW_SCALE_FIELDS: tuple[str, ...] = (
    "answers_question_1_5",
    "clear_1_5",
    "helps_decision_1_5",
    "not_overloaded_1_5",
    "natural_convincing_1_5",
    "comment",
    "best_variant",
)


def _digest_json(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_config_registry_document() -> dict[str, Any]:
    from evals.v5.arch_compare.arch_compare_provider_payload import inference_settings_document

    rows = []
    for config in all_arch_compare_configs():
        rows.append(
            {
                "config_id": config.config_id,
                "model_role": config.model_role,
                "context_mode": config.context_mode,
                "provider_model_id": config.provider_model_id,
                "provider_model_id_status": config.provider_model_id_status,
                "prompt_contract_version": config.prompt_contract_version,
                "inference_settings": config.inference_settings.to_dict(),
            }
        )
    return {
        "measurement_id": MEASUREMENT_ID,
        "config_ids": list(CONFIG_IDS),
        "configs": rows,
        "flash_provider_model_id": FLASH_PROVIDER_MODEL_ID,
        "plus_provider_model_id": PLUS_PROVIDER_MODEL_ID,
        "plus_model_family": PLUS_MODEL_FAMILY,
        "plus_model_snapshot": PLUS_MODEL_SNAPSHOT,
        "plus_official_sources": list(PLUS_OFFICIAL_SOURCES),
        "shared_inference_settings": inference_settings_document(),
        "enable_thinking": ARCH_COMPARE_INFERENCE_SETTINGS.enable_thinking,
    }


def frozen_config_digest() -> str:
    return _digest_json(build_config_registry_document())


@dataclass(frozen=True, slots=True)
class ArchCompareLiveAuthorizationManifest:
    """External one-shot authorization for a future LIVE attempt (not created in prep)."""

    attempt_id: str
    expected_head: str
    matrix_digest: str
    config_digest: str
    allowed_model_ids: tuple[str, ...]
    max_provider_calls: int
    client_id: str
    issued_for_measurement: str
    explicit_live: bool
    includes_capability_preflight: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ArchCompareLiveAuthorizationManifest:
        return cls(
            attempt_id=str(payload["attempt_id"]),
            expected_head=str(payload["expected_head"]),
            matrix_digest=str(payload["matrix_digest"]),
            config_digest=str(payload["config_digest"]),
            allowed_model_ids=tuple(str(x) for x in payload["allowed_model_ids"]),
            max_provider_calls=int(payload["max_provider_calls"]),
            client_id=str(payload["client_id"]),
            issued_for_measurement=str(payload["issued_for_measurement"]),
            explicit_live=bool(payload["explicit_live"]),
            includes_capability_preflight=bool(payload.get("includes_capability_preflight", True)),
        )


@dataclass(frozen=True, slots=True)
class ArchCompareCallBudgetPlan:
    scenario_count: int
    turn_count: int
    config_count: int
    scenario_config_jobs: int
    turn_config_jobs: int
    provider_turn_jobs: int
    code_only_turn_jobs: int
    capability_preflight_budget: int
    measurement_budget: int
    total_authorized_budget: int
    max_provider_calls: int
    fake_provider_calls: int
    optional_cache_probe_budget: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArchCompareLiveReadiness:
    status: LiveReadinessState
    reasons: tuple[str, ...]
    capability_preflight_budget: int
    measurement_budget: int
    total_authorized_budget: int
    optional_cache_probe_budget: int
    flash_provider_model_id: str
    plus_provider_model_id: str
    plus_provider_model_id_status: Literal["resolved"]
    enable_thinking: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_live_readiness(*, max_provider_calls: int | None = None) -> ArchCompareLiveReadiness:
    reasons: list[str] = []
    if not PLUS_PROVIDER_MODEL_ID:
        reasons.append("plus_provider_model_id_unresolved")
    if not FLASH_PROVIDER_MODEL_ID:
        reasons.append("flash_provider_model_id_unresolved")
    authorized = max_provider_calls if max_provider_calls is not None else TOTAL_AUTHORIZED_PROVIDER_BUDGET
    if authorized != TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        reasons.append("authorized_budget_not_70")
    status: LiveReadinessState = (
        "READY_FOR_AUTHORIZED_PREFLIGHT" if not reasons else "PREPARED_LIVE_DISABLED"
    )
    return ArchCompareLiveReadiness(
        status=status,
        reasons=tuple(reasons),
        capability_preflight_budget=CAPABILITY_PREFLIGHT_BUDGET,
        measurement_budget=MEASUREMENT_PROVIDER_BUDGET,
        total_authorized_budget=TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        optional_cache_probe_budget=OPTIONAL_CACHE_PROBE_BUDGET,
        flash_provider_model_id=FLASH_PROVIDER_MODEL_ID,
        plus_provider_model_id=PLUS_PROVIDER_MODEL_ID,
        plus_provider_model_id_status="resolved",
        enable_thinking=ARCH_COMPARE_INFERENCE_SETTINGS.enable_thinking,
    )


def default_authorization_manifest_template(*, max_provider_calls: int) -> dict[str, Any]:
    """Schema example only — not a real authorization for this checkpoint."""

    return ArchCompareLiveAuthorizationManifest(
        attempt_id="<owner_issued_attempt_id>",
        expected_head="<published_full_sha>",
        matrix_digest=FROZEN_MATRIX_DIGEST,
        config_digest=frozen_config_digest(),
        allowed_model_ids=(FLASH_PROVIDER_MODEL_ID, PLUS_PROVIDER_MODEL_ID),
        max_provider_calls=max_provider_calls,
        client_id=CLIENT_ID,
        issued_for_measurement=LIVE_MEASUREMENT_ID,
        explicit_live=True,
        includes_capability_preflight=True,
    ).to_dict()


def assert_authorization_manifest_budget(*, max_provider_calls: int, includes_preflight: bool) -> None:
    if includes_preflight and max_provider_calls != TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        raise RuntimeError(
            f"authorization_budget_invalid:preflight+measurement requires max={TOTAL_AUTHORIZED_PROVIDER_BUDGET}"
        )
    if max_provider_calls > TOTAL_AUTHORIZED_PROVIDER_BUDGET:
        raise RuntimeError(
            f"authorization_budget_exceeded:max={max_provider_calls} authorized={TOTAL_AUTHORIZED_PROVIDER_BUDGET}"
        )


def assert_cache_probe_separate_budget(*, cache_probe_calls: int, measurement_remaining: int) -> None:
    if cache_probe_calls > 0 and measurement_remaining < cache_probe_calls:
        raise RuntimeError(
            f"cache_probe_cannot_use_measurement_budget:remaining={measurement_remaining}"
        )


def assert_expected_job_counts(*, scenario_config_jobs: int, turn_config_jobs: int) -> None:
    if scenario_config_jobs != EXPECTED_SCENARIO_CONFIG_RESULTS:
        raise RuntimeError(
            f"scenario_config_jobs_mismatch expected={EXPECTED_SCENARIO_CONFIG_RESULTS} "
            f"actual={scenario_config_jobs}"
        )
    if turn_config_jobs != EXPECTED_TURN_CONFIG_RESULTS:
        raise RuntimeError(
            f"turn_config_jobs_mismatch expected={EXPECTED_TURN_CONFIG_RESULTS} "
            f"actual={turn_config_jobs}"
        )
