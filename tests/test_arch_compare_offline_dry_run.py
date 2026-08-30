"""Dry-run and blind-review tests for architecture comparison offline harness."""

from __future__ import annotations

from evals.v5.arch_compare.arch_compare_contract import (
    BLIND_VARIANTS,
    DRY_RUN_DISCLAIMER,
    EXPECTED_TURN_CONFIG_RESULTS,
)
from evals.v5.arch_compare.arch_compare_fake_transport import ArchCompareFakeTransport
from evals.v5.arch_compare.arch_compare_harness import (
    build_blind_variant_mapping,
    run_arch_compare_dry_run,
    verify_fake_transport_wiring,
)
from evals.v5.arch_compare.arch_compare_matrix import parse_scenario_specs
from evals.v5.arch_compare.arch_compare_report import (
    build_blind_review_markdown,
    persist_dry_run_artifacts,
)
from evals.v5.arch_compare.arch_compare_configs import config_by_id


def test_dry_run_zero_provider_calls() -> None:
    result = run_arch_compare_dry_run(attempt_id="test_offline_v1")
    assert result["provider_call_total"] == 0
    assert len(result["turns"]) == EXPECTED_TURN_CONFIG_RESULTS
    assert DRY_RUN_DISCLAIMER in result["disclaimer"]


def test_blind_mapping_deterministic_and_shuffled() -> None:
    scenario_ids = tuple(row.scenario_id for row in parse_scenario_specs())
    first = build_blind_variant_mapping(attempt_id="seed_a", scenario_ids=scenario_ids)
    second = build_blind_variant_mapping(attempt_id="seed_a", scenario_ids=scenario_ids)
    assert first == second
    # Not every scenario should map A -> flash_full (identity mapping).
    identity_hits = sum(
        1
        for scenario_id, mapping in first.items()
        if mapping["A"] == "flash_full"
    )
    assert identity_hits < len(scenario_ids)


def test_blind_review_hides_config_metadata() -> None:
    dry_run = run_arch_compare_dry_run(attempt_id="review_test_v1")
    markdown = build_blind_review_markdown(attempt_id="review_test_v1", dry_run=dry_run)
    assert DRY_RUN_DISCLAIMER in markdown
    assert "flash_full" not in markdown
    assert "plus_curated" not in markdown
    assert "context_mode" not in markdown
    for variant in BLIND_VARIANTS:
        assert f"**Вариант {variant}**" in markdown


def test_persist_artifacts_writes_mapping_separately(tmp_path, monkeypatch) -> None:
    import evals.v5.arch_compare.arch_compare_report as report

    monkeypatch.setattr(report, "_ARTIFACTS_ROOT", tmp_path)
    dry_run = run_arch_compare_dry_run(attempt_id="artifact_test")
    paths = persist_dry_run_artifacts(attempt_id="artifact_test", dry_run=dry_run)
    assert paths["blind_variant_mapping_json"].is_file()
    assert paths["blind_review_md"].is_file()
    mapping_text = paths["blind_variant_mapping_json"].read_text(encoding="utf-8")
    review_text = paths["blind_review_md"].read_text(encoding="utf-8")
    assert "flash_full" in mapping_text
    assert "flash_full" not in review_text


def test_fake_transport_wiring_single_call_budget() -> None:
    scenario = next(row for row in parse_scenario_specs() if row.scenario_id == "PRC-01")
    turn = scenario.turns[0]
    calls = verify_fake_transport_wiring(
        scenario=scenario,
        turn=turn,
        config=config_by_id("flash_full"),
    )
    assert calls == 0


def test_fake_transport_blocks_second_call() -> None:
    transport = ArchCompareFakeTransport()
    transport.prepare_turn_envelopes(('{"route":"ANSWER","patient_text":"x"}',))
    transport.chat_completions_create(model="m", messages=[])
    try:
        transport.chat_completions_create(model="m", messages=[])
        raised = False
    except RuntimeError:
        raised = True
    assert raised


def test_fake_transport_stream_and_blocking_same_visible_text() -> None:
    payload = '{"route":"ANSWER","patient_text":"same_text"}'
    blocking = ArchCompareFakeTransport()
    blocking.prepare_turn_envelopes((payload,))
    block_resp = blocking.chat_completions_create(model="m", stream=False, messages=[])
    stream_transport = ArchCompareFakeTransport()
    stream_transport.prepare_turn_envelopes((payload,))
    stream = stream_transport.chat_completions_create(model="m", stream=True, messages=[])
    chunks = list(stream)
    assert block_resp.choices[0].message.content == payload
    assert chunks[0].choices[0].delta.content == payload
