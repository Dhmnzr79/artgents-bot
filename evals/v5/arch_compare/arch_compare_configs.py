"""Four frozen architecture comparison configurations (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import config

from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from evals.v5.arch_compare.arch_compare_contract import (
    CONFIG_FLASH_CURATED,
    CONFIG_FLASH_FULL,
    CONFIG_PLUS_CURATED,
    CONFIG_PLUS_FULL,
    CONFIG_IDS,
    CONTEXT_MODE_CURATED,
    CONTEXT_MODE_FULL,
    MEASUREMENT_ID,
    MODEL_ROLE_FLASH,
    MODEL_ROLE_PLUS,
)

ModelRole = Literal["flash", "plus"]
ContextMode = Literal["full", "curated"]

# Canonical Plus provider slug is not pinned in config.py (QWEN_PLUS_MODEL aliases flash).
# .env.example comments suggest qwen3.7-plus — unresolved until owner LIVE gate.
PLUS_PROVIDER_MODEL_ID: str | None = None
PLUS_PROVIDER_MODEL_ID_HINT = "qwen3.7-plus (.env.example comment; not config-canonical)"


@dataclass(frozen=True, slots=True)
class ArchCompareConfig:
    config_id: str
    model_role: ModelRole
    context_mode: ContextMode
    provider_model_id: str | None
    provider_model_id_status: Literal["resolved", "unresolved"]
    temperature: float | None
    reasoning_effort: str | None
    prompt_contract_version: int
    measurement_id: str

    @property
    def is_plus(self) -> bool:
        return self.model_role == MODEL_ROLE_PLUS


def _flash_config(*, config_id: str, context_mode: ContextMode) -> ArchCompareConfig:
    return ArchCompareConfig(
        config_id=config_id,
        model_role=MODEL_ROLE_FLASH,
        context_mode=context_mode,
        provider_model_id=config.SALES_ONE_PLUS_FLASH_MODEL,
        provider_model_id_status="resolved",
        temperature=None,
        reasoning_effort=None,
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        measurement_id=MEASUREMENT_ID,
    )


def _plus_config(*, config_id: str, context_mode: ContextMode) -> ArchCompareConfig:
    return ArchCompareConfig(
        config_id=config_id,
        model_role=MODEL_ROLE_PLUS,
        context_mode=context_mode,
        provider_model_id=PLUS_PROVIDER_MODEL_ID,
        provider_model_id_status="unresolved",
        temperature=None,
        reasoning_effort=None,
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        measurement_id=MEASUREMENT_ID,
    )


def all_arch_compare_configs() -> tuple[ArchCompareConfig, ...]:
    return (
        _flash_config(config_id=CONFIG_FLASH_FULL, context_mode=CONTEXT_MODE_FULL),
        _flash_config(config_id=CONFIG_FLASH_CURATED, context_mode=CONTEXT_MODE_CURATED),
        _plus_config(config_id=CONFIG_PLUS_FULL, context_mode=CONTEXT_MODE_FULL),
        _plus_config(config_id=CONFIG_PLUS_CURATED, context_mode=CONTEXT_MODE_CURATED),
    )


def config_by_id(config_id: str) -> ArchCompareConfig:
    for row in all_arch_compare_configs():
        if row.config_id == config_id:
            return row
    raise KeyError(config_id)


def assert_config_registry() -> None:
    configs = all_arch_compare_configs()
    ids = [row.config_id for row in configs]
    if len(ids) != len(set(ids)):
        raise RuntimeError("arch_compare_config_ids_not_unique")
    if tuple(ids) != CONFIG_IDS:
        raise RuntimeError(f"arch_compare_config_order_mismatch expected={CONFIG_IDS} actual={tuple(ids)}")
