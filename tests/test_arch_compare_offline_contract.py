"""Contract tests for architecture comparison offline harness."""

from __future__ import annotations

from evals.v5.arch_compare.arch_compare_configs import (
    FLASH_PROVIDER_MODEL_ID,
    PLUS_PROVIDER_MODEL_ID,
    PLUS_OFFICIAL_SOURCES,
    all_arch_compare_configs,
    assert_config_registry,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_contract import (
    CONFIG_IDS,
    DRY_RUN_DISCLAIMER,
    EXPECTED_CONFIG_COUNT,
    EXPECTED_SCENARIO_CONFIG_RESULTS,
    EXPECTED_TURN_CONFIG_RESULTS,
    MEASUREMENT_ID,
)
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION


def test_measurement_and_config_registry() -> None:
    assert MEASUREMENT_ID == "one_call_arch_compare_offline_v1"
    assert_config_registry()
    assert len(CONFIG_IDS) == EXPECTED_CONFIG_COUNT
    assert len(all_arch_compare_configs()) == EXPECTED_CONFIG_COUNT


def test_plus_provider_model_pinned() -> None:
    plus_full = config_by_id("plus_full")
    assert plus_full.model_role == "plus"
    assert plus_full.provider_model_id_status == "resolved"
    assert PLUS_PROVIDER_MODEL_ID == "qwen3.7-plus-2026-05-26"
    flash_full = config_by_id("flash_full")
    assert flash_full.provider_model_id == FLASH_PROVIDER_MODEL_ID
    assert len(PLUS_OFFICIAL_SOURCES) == 3


def test_prompt_contract_version_pinned() -> None:
    for row in all_arch_compare_configs():
        assert row.prompt_contract_version == ONE_CALL_PROMPT_CONTRACT_VERSION


def test_expected_result_cardinality() -> None:
    assert EXPECTED_SCENARIO_CONFIG_RESULTS == 16 * 4
    assert EXPECTED_TURN_CONFIG_RESULTS == 19 * 4


def test_dry_run_disclaimer_present() -> None:
    assert "Не предназначен для оценки качества модели" in DRY_RUN_DISCLAIMER
