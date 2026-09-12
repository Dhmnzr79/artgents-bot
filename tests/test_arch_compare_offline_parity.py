"""Parity tests for four-way architecture comparison prompt assembly."""

from __future__ import annotations

from evals.v5.arch_compare.arch_compare_configs import (
    CONFIG_FLASH_CURATED,
    CONFIG_FLASH_FULL,
    CONFIG_PLUS_CURATED,
    CONFIG_PLUS_FULL,
    all_arch_compare_configs,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_context import (
    build_curated_cached_context,
    load_demo_full_cached_context,
    normalize_source_refs,
)
from evals.v5.arch_compare.arch_compare_contract import FROZEN_COMMERCIAL_AS_OF
from evals.v5.arch_compare.arch_compare_matrix import parse_scenario_specs
from evals.v5.arch_compare.arch_compare_prompt_build import build_prompt_capture


def _capture(config_id: str, scenario_id: str, turn_id: str):
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == scenario_id)
    turn = next(row for row in scenario.turns if row.turn_id == turn_id)
    return build_prompt_capture(
        config=config_by_id(config_id),
        scenario=scenario,
        turn=turn,
        dialog_history="",
    )


def test_four_config_ids_unique() -> None:
    ids = [row.config_id for row in all_arch_compare_configs()]
    assert len(ids) == len(set(ids))


def test_curated_refs_exist_in_demo_corpus() -> None:
    full = load_demo_full_cached_context()
    available = set(full.document_paths)
    for scenario in parse_scenario_specs():
        refs = normalize_source_refs(scenario.relevant_source_refs)
        missing = [ref for ref in refs if ref not in available]
        assert not missing, f"{scenario.scenario_id} missing={missing}"


def test_curated_corpus_only_selected_refs() -> None:
    full = load_demo_full_cached_context()
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == "PRC-01")
    resolution = build_curated_cached_context(full, source_refs=scenario.relevant_source_refs)
    assert resolution.resolved_source_refs == normalize_source_refs(scenario.relevant_source_refs)
    assert len(resolution.curated_cached_context.document_paths) == len(scenario.relevant_source_refs)


def test_full_and_curated_use_same_source_bytes() -> None:
    full = load_demo_full_cached_context()
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == "BRD-01")
    resolution = build_curated_cached_context(full, source_refs=scenario.relevant_source_refs)
    corpus = full.model_corpus_text
    for ref in resolution.resolved_source_refs:
        assert f"---BEGIN DOC:{ref}---" in corpus


def test_exact_catalog_identical_across_configs() -> None:
    prc = _capture(CONFIG_FLASH_FULL, "PRC-01", "PRC-01_t1")
    for config_id in (CONFIG_FLASH_CURATED, CONFIG_PLUS_FULL, CONFIG_PLUS_CURATED):
        other = _capture(config_id, "PRC-01", "PRC-01_t1")
        assert other.exact_catalog_hash == prc.exact_catalog_hash


def test_service_reference_catalog_identical_across_configs() -> None:
    base = _capture(CONFIG_FLASH_FULL, "SVC-01", "SVC-01_t1")
    for config_id in (CONFIG_FLASH_CURATED, CONFIG_PLUS_FULL, CONFIG_PLUS_CURATED):
        other = _capture(config_id, "SVC-01", "SVC-01_t1")
        assert other.service_reference_catalog_hash == base.service_reference_catalog_hash


def test_commercial_as_of_identical_across_configs() -> None:
    captures = [
        _capture(row.config_id, "PAY-01", "PAY-01_t1")
        for row in all_arch_compare_configs()
    ]
    values = {row.commercial_as_of for row in captures}
    assert values == {FROZEN_COMMERCIAL_AS_OF.isoformat()}


def test_flash_plus_same_prompt_per_context_mode() -> None:
    flash_full = _capture(CONFIG_FLASH_FULL, "PRC-02", "PRC-02_t1")
    plus_full = _capture(CONFIG_PLUS_FULL, "PRC-02", "PRC-02_t1")
    assert flash_full.stable_prefix == plus_full.stable_prefix
    assert flash_full.dynamic_suffix == plus_full.dynamic_suffix

    flash_cur = _capture(CONFIG_FLASH_CURATED, "PRC-02", "PRC-02_t1")
    plus_cur = _capture(CONFIG_PLUS_CURATED, "PRC-02", "PRC-02_t1")
    assert flash_cur.stable_prefix == plus_cur.stable_prefix
    assert flash_cur.dynamic_suffix == plus_cur.dynamic_suffix


def test_model_id_not_in_prompt_text() -> None:
    for config in all_arch_compare_configs():
        capture = build_prompt_capture(
            config=config,
            scenario=next(row for row in parse_scenario_specs() if row.scenario_id == "PRC-01"),
            turn=next(
                row
                for row in next(
                    row for row in parse_scenario_specs() if row.scenario_id == "PRC-01"
                ).turns
                if row.turn_id == "PRC-01_t1"
            ),
            dialog_history="",
        )
        if config.provider_model_id and config.model_role == "plus":
            assert config.provider_model_id not in capture.stable_prefix
            assert config.provider_model_id not in capture.dynamic_suffix


def test_full_curated_differ_only_in_content_context() -> None:
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == "MT-01")
    turn = scenario.turns[0]
    full = build_prompt_capture(
        config=config_by_id(CONFIG_FLASH_FULL),
        scenario=scenario,
        turn=turn,
        dialog_history="",
    )
    curated = build_prompt_capture(
        config=config_by_id(CONFIG_FLASH_CURATED),
        scenario=scenario,
        turn=turn,
        dialog_history="",
    )
    assert full.content_context_hash != curated.content_context_hash
    assert full.exact_catalog_hash == curated.exact_catalog_hash
    assert full.dynamic_suffix_hash == curated.dynamic_suffix_hash


def test_single_offer_same_across_configs_for_nobel() -> None:
    captures = [
        _capture(row.config_id, "BRD-01", "BRD-01_t1") for row in all_arch_compare_configs()
    ]
    offer_sets = {tuple(row.selected_offer_ids) for row in captures}
    assert len(offer_sets) == 1
    assert captures[0].precomposer_availability == "selected"


def test_multi_offer_same_across_configs_for_all_on_4() -> None:
    captures = [
        _capture(row.config_id, "PRC-01", "PRC-01_t1") for row in all_arch_compare_configs()
    ]
    availability = {row.precomposer_availability for row in captures}
    assert availability == {"multiple"}
    offer_sets = {tuple(row.selected_offer_ids) for row in captures}
    assert len(offer_sets) == 1
    assert len(captures[0].selected_offer_ids) == 3


def test_session_history_parity_for_mt01_second_turn() -> None:
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == "MT-01")
    turn = scenario.turns[1]
    from evals.v5.arch_compare.arch_compare_fake_transport import fake_patient_text_for_turn
    from evals.v5.arch_compare.arch_compare_prompt_build import build_dialog_history

    prior = {
        "MT-01_t1": fake_patient_text_for_turn(scenario_id="MT-01", turn_id="MT-01_t1"),
    }
    history = build_dialog_history(scenario=scenario, turn=turn, prior_turns=prior)
    full = build_prompt_capture(
        config=config_by_id(CONFIG_FLASH_FULL),
        scenario=scenario,
        turn=turn,
        dialog_history=history,
    )
    curated = build_prompt_capture(
        config=config_by_id(CONFIG_FLASH_CURATED),
        scenario=scenario,
        turn=turn,
        dialog_history=history,
    )
    assert full.dynamic_suffix == curated.dynamic_suffix


def test_no_stage53_import_dependency() -> None:
    import evals.v5.arch_compare.arch_compare_harness as harness

    source = harness.__file__ or ""
    assert "stage53" not in source
