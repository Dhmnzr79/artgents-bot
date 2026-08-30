"""Four frozen architecture comparison configurations (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from llm import LLM_REQUEST_TIMEOUT_SEC

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

# Frozen provider snapshots for architecture comparison (eval-only).
FLASH_PROVIDER_MODEL_ID = "qwen3.7-flash-2026-07-15"
PLUS_PROVIDER_MODEL_ID = "qwen3.7-plus-2026-05-26"

PLUS_OFFICIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "title": "Alibaba Cloud Model Studio — Text generation models",
        "url": "https://www.alibabacloud.com/help/en/model-studio/text-generation-model",
        "checked_on": "2026-08-30",
    },
    {
        "title": "Alibaba Cloud Model Studio — Model pricing",
        "url": "https://www.alibabacloud.com/help/en/model-studio/model-pricing",
        "checked_on": "2026-08-30",
    },
    {
        "title": "Alibaba Cloud Model Studio — Context Cache",
        "url": "https://www.alibabacloud.com/help/en/model-studio/context-cache",
        "checked_on": "2026-08-30",
    },
)

PLUS_MODEL_FAMILY = "qwen3.7-plus"
PLUS_MODEL_SNAPSHOT = PLUS_PROVIDER_MODEL_ID


@dataclass(frozen=True, slots=True)
class ArchCompareInferenceSettings:
    """Mirrors production Composer sales-fast provider payload (sales_one_plus_live_backend)."""

    temperature: float
    max_completion_tokens: int
    timeout_sec: float
    response_format_type: str
    stream: bool
    stream_include_usage: bool
    enable_thinking: bool
    top_p: Literal["provider_default"]
    seed: Literal["provider_default"]
    tools_enabled: bool
    web_search_enabled: bool
    provider_call_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "timeout_sec": self.timeout_sec,
            "response_format": {"type": self.response_format_type},
            "stream": self.stream,
            "stream_options": {"include_usage": True} if self.stream else None,
            "extra_body": {"enable_thinking": self.enable_thinking},
            "top_p": self.top_p,
            "seed": self.seed,
            "tools_enabled": self.tools_enabled,
            "web_search_enabled": self.web_search_enabled,
            "provider_call_source": self.provider_call_source,
        }


ARCH_COMPARE_INFERENCE_SETTINGS = ArchCompareInferenceSettings(
    temperature=0,
    max_completion_tokens=1024,
    timeout_sec=LLM_REQUEST_TIMEOUT_SEC,
    response_format_type="json_object",
    stream=False,
    stream_include_usage=True,
    enable_thinking=False,
    top_p="provider_default",
    seed="provider_default",
    tools_enabled=False,
    web_search_enabled=False,
    provider_call_source="sales_fast",
)


@dataclass(frozen=True, slots=True)
class ArchCompareConfig:
    config_id: str
    model_role: ModelRole
    context_mode: ContextMode
    provider_model_id: str
    provider_model_id_status: Literal["resolved"]
    inference_settings: ArchCompareInferenceSettings
    prompt_contract_version: int
    measurement_id: str

    @property
    def is_plus(self) -> bool:
        return self.model_role == MODEL_ROLE_PLUS


def _config(
    *,
    config_id: str,
    model_role: ModelRole,
    context_mode: ContextMode,
    provider_model_id: str,
) -> ArchCompareConfig:
    return ArchCompareConfig(
        config_id=config_id,
        model_role=model_role,
        context_mode=context_mode,
        provider_model_id=provider_model_id,
        provider_model_id_status="resolved",
        inference_settings=ARCH_COMPARE_INFERENCE_SETTINGS,
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        measurement_id=MEASUREMENT_ID,
    )


def all_arch_compare_configs() -> tuple[ArchCompareConfig, ...]:
    return (
        _config(
            config_id=CONFIG_FLASH_FULL,
            model_role=MODEL_ROLE_FLASH,
            context_mode=CONTEXT_MODE_FULL,
            provider_model_id=FLASH_PROVIDER_MODEL_ID,
        ),
        _config(
            config_id=CONFIG_FLASH_CURATED,
            model_role=MODEL_ROLE_FLASH,
            context_mode=CONTEXT_MODE_CURATED,
            provider_model_id=FLASH_PROVIDER_MODEL_ID,
        ),
        _config(
            config_id=CONFIG_PLUS_FULL,
            model_role=MODEL_ROLE_PLUS,
            context_mode=CONTEXT_MODE_FULL,
            provider_model_id=PLUS_PROVIDER_MODEL_ID,
        ),
        _config(
            config_id=CONFIG_PLUS_CURATED,
            model_role=MODEL_ROLE_PLUS,
            context_mode=CONTEXT_MODE_CURATED,
            provider_model_id=PLUS_PROVIDER_MODEL_ID,
        ),
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
