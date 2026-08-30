"""Offline tests for arch-compare report v2 and attempt 02 rebuild."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.arch_compare.arch_compare_attempt_rebuild import (
    READONLY_SOURCE_FILES,
    default_attempt02_paths,
    load_readonly_attempt_artifacts,
    rebuild_attempt_reports,
)
from evals.v5.arch_compare.arch_compare_live_report import assert_blind_review_secrecy
from evals.v5.arch_compare.arch_compare_live_report_v2 import (
    NOT_CAPTURED,
    ORIGIN_NOT_PROVABLE,
    PREVIOUS_ANSWER_NOT_CAPTURED,
    build_blind_review_markdown_v2,
    build_technical_report_markdown_v2,
    compute_persistence_counters,
)
from evals.v5.arch_compare.arch_compare_live_schedule import scenario_for_id
from evals.v5.arch_compare.arch_compare_production_parity import capture_arch_compare_price_turn
from tests.test_sales_one_plus_turn import answer_envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ATTEMPT02_SOURCE, _ATTEMPT02_REBUILT = default_attempt02_paths(_REPO_ROOT)
_SOURCE_SHA = "905524776f58cebc2d4003c9d01c6856ff620cc0"
_REBUILD_SHA = "2364bc4afc2f23539d467a43ffd7e428981b9047"


@pytest.fixture(scope="module")
def attempt02_source() -> Path:
    if not _ATTEMPT02_SOURCE.is_dir():
        pytest.skip("attempt 02 source artifacts missing")
    return _ATTEMPT02_SOURCE


@pytest.fixture(scope="module")
def attempt02_run_result(attempt02_source: Path) -> dict:
    return load_readonly_attempt_artifacts(attempt02_source)


def test_source_and_rebuild_sha_are_distinct(attempt02_run_result: dict) -> None:
    assert attempt02_run_result["source_attempt_sha"] == _SOURCE_SHA
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert f"source_attempt_sha: `{_SOURCE_SHA}`" in md
    assert f"rebuilt_with_sha: `{_REBUILD_SHA}`" in md
    assert _REBUILD_SHA not in attempt02_run_result["source_attempt_sha"]
    assert "published_sha" not in md


def test_old_attempt_not_signed_with_current_head(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert f"source_attempt_sha: `{_REBUILD_SHA}`" not in md
    assert attempt02_run_result["source_attempt_sha"] != _REBUILD_SHA


def test_real_question_in_blind_report(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    scenario = scenario_for_id("PRC-01")
    assert scenario.turns[0].user_message in md


def test_dialog_history_in_blind_report(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "Предыдущая история диалога" in md


def test_missing_previous_answer_marked_not_invented(tmp_path: Path) -> None:
    run_result = {
        "status": "INCOMPLETE_FATAL",
        "source_attempt_sha": _SOURCE_SHA,
        "structured_turns": [
            {
                "scenario_id": "MT-01",
                "turn_id": "MT-01_t2",
                "config_id": "flash_full",
                "session_id": "s1",
                "provider_turn": True,
                "patient_text": "ответ",
                "visible_answer": "ответ",
                "raw_model_envelope": '{"price_text": null}',
                "selected_offer_ids": [],
                "dialog_history_before": "",
            }
        ],
        "blind_variant_mapping": {
            "MT-01": {"A": "flash_full", "B": "flash_curated", "C": "plus_full", "D": "plus_curated"}
        },
        "call_ledger": {"calls": []},
    }
    md = build_blind_review_markdown_v2(
        attempt_id="x",
        run_result=run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert PREVIOUS_ANSWER_NOT_CAPTURED in md


def test_blind_report_has_variants_without_mapping(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "#### Вариант A" in md
    assert "flash_full" not in md
    assert "blind_variant_mapping" not in md


def test_blind_report_excludes_technical_fields(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert_blind_review_secrecy(md)
    assert "prompt_tokens" not in md.casefold()
    assert "latency_ms" not in md.casefold()


def test_technical_report_keeps_model_config_latency(attempt02_run_result: dict) -> None:
    md = build_technical_report_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "provider_model_id" in md
    assert "config_id" in md
    assert "latency_ms" in md
    assert "prompt_tokens" in md
    assert f"source_attempt_sha: `{_SOURCE_SHA}`" in md
    assert f"rebuilt_with_sha: `{_REBUILD_SHA}`" in md


def test_sections_separate_model_code_and_visible(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "Сырой patient_text модели" in md
    assert "Сырой model price_text" in md
    assert "Matrix expectation (not captured selection)" in md
    assert "Captured precomposer selection" in md
    assert "Блоки, добавленные кодом" in md
    assert "Commercial provenance (structured only)" in md
    assert "Полный итоговый видимый ответ" in md


def test_missing_telemetry_marked_not_captured(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert NOT_CAPTURED in md
    assert "owner: none" not in md


def test_missing_registry_not_empty_object(attempt02_run_result: dict) -> None:
    md = build_technical_report_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert NOT_CAPTURED in md
    assert '"config_ids": []' not in md


def test_matrix_expectation_separate_from_captured_selection(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "expected_service_id: all_on_4" in md
    assert "expected_brand: Nobel Biocare" in md
    assert "Captured precomposer selection" in md
    assert "brand_id: not_captured_in_attempt_02" in md


def test_capture_preserves_resolved_price_owner() -> None:
    from evals.v5.arch_compare.arch_compare_production_parity import scenario_turn_or_raise

    scenario, turn = scenario_turn_or_raise(scenario_id="BRD-01", turn_id="BRD-01_t1")
    patient = "Nobel Biocare — премиальный вариант All-on-4."
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=answer_envelope(
            patient,
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
        patient_text=patient,
    )
    assert capture.resolved_price_owner == "canonical_fallback"
    assert capture.resolved_price_diagnostic == "missing"
    assert capture.resolved_selected_offer_id == "all_on_4.jaw.nobel"
    assert capture.resolved_price_owner != "model_price_text"


def test_model_price_not_marked_canonical_fallback() -> None:
    from evals.v5.arch_compare.arch_compare_production_parity import scenario_turn_or_raise

    scenario, turn = scenario_turn_or_raise(scenario_id="BRD-01", turn_id="BRD-01_t1")
    patient = "Nobel Biocare — премиальный вариант All-on-4."
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=answer_envelope(
            patient,
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=(
                "Стоимость All-on-4 на Nobel Biocare — 428 000 ₽ за одну челюсть; "
                "КТ и костная пластика по показаниям — отдельно."
            ),
        ),
        patient_text=patient,
    )
    assert capture.resolved_price_owner == "model_price_text"
    assert capture.resolved_price_owner != "canonical_fallback"


def test_multi_block_owner_is_canonical_multi() -> None:
    from evals.v5.arch_compare.arch_compare_production_parity import scenario_turn_or_raise

    scenario, turn = scenario_turn_or_raise(scenario_id="PRC-01", turn_id="PRC-01_t1")
    capture = capture_arch_compare_price_turn(
        scenario=scenario,
        turn=turn,
        envelope_json=answer_envelope(
            "All-on-4 — полное восстановление челюсти на 4 имплантах.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
        patient_text="All-on-4 — полное восстановление челюсти на 4 имплантах.",
    )
    assert capture.resolved_price_owner == "canonical_multi"
    assert len(capture.resolved_multi_offer_ids) == 3


def test_commercial_provenance_uses_structured_origin_not_word_match(attempt02_run_result: dict) -> None:
    md = build_blind_review_markdown_v2(
        attempt_id="arch_compare_live_v1_2026-08-30-02",
        run_result=attempt02_run_result,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert "Commercial provenance (structured only)" in md
    assert ORIGIN_NOT_PROVABLE in md
    assert "гарантия: patient_text=" in md


def test_rebuild_is_idempotent(attempt02_source: Path, tmp_path: Path) -> None:
    out_a = tmp_path / "rebuild_a"
    out_b = tmp_path / "rebuild_b"
    rebuild_attempt_reports(
        source_dir=attempt02_source,
        output_dir=out_a,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    rebuild_attempt_reports(
        source_dir=attempt02_source,
        output_dir=out_b,
        rebuilt_with_sha=_REBUILD_SHA,
    )
    assert (out_a / "blind_review_v2.md").read_text(encoding="utf-8") == (
        out_b / "blind_review_v2.md"
    ).read_text(encoding="utf-8")


def test_source_artifacts_unchanged_after_rebuild(attempt02_source: Path, tmp_path: Path) -> None:
    mtimes_before = {
        name: (attempt02_source / name).stat().st_mtime_ns
        for name in READONLY_SOURCE_FILES
        if (attempt02_source / name).exists()
    }
    rebuild_attempt_reports(
        source_dir=attempt02_source,
        output_dir=tmp_path / "rebuilt",
        rebuilt_with_sha=_REBUILD_SHA,
    )
    mtimes_after = {
        name: (attempt02_source / name).stat().st_mtime_ns
        for name in mtimes_before
    }
    assert mtimes_before == mtimes_after


def test_attempt02_counters_46_of_47(attempt02_run_result: dict) -> None:
    counters = attempt02_run_result["persistence_counters"]
    assert counters.preflight_provider_calls_completed == 2
    assert counters.measurement_provider_calls_completed == 47
    assert counters.persisted_measurement_results == 46
    assert counters.missing_persisted_results == 1
    assert counters.total_provider_call_ordinal == 49


def test_persistence_summary_written(attempt02_source: Path, tmp_path: Path) -> None:
    paths = rebuild_attempt_reports(
        source_dir=attempt02_source,
        output_dir=tmp_path / "rebuilt_counters",
        rebuilt_with_sha=_REBUILD_SHA,
    )
    summary = json.loads(paths["persistence_summary_json"].read_text(encoding="utf-8"))
    assert summary["persisted_measurement_results"] == 46
    assert summary["missing_persisted_results"] == 1
