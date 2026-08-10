"""Stage 3C quality guard v2 contract tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from evals.v5.one_call_stage3c_speed_gate_contract import PROPOSED_LIVE_ATTEMPT_ID_V2
from evals.v5.one_call_stage3c_speed_gate_harness import _evaluate_quality
from evals.v5.one_call_stage3c_speed_gate_speed_gate import (
    compute_speed_gate_quality_pass,
    evaluate_speed_gate,
)


def test_proposed_v2_attempt_id_prepared() -> None:
    assert PROPOSED_LIVE_ATTEMPT_ID_V2 == "one_call_stage3c_speed_gate_v2_2026-08-11-01"


def test_s02_implant_answer_passes_without_lechenie_word() -> None:
    quality = _evaluate_quality(
        "s02_service",
        arm="NEW",
        http_result={
            "answer_text": "Имплантация восстанавливает зуб с коронкой на импланте.",
            "meta": {"service_route": "sales_fast_materialized"},
            "widget_payload_ready": True,
        },
        provider_call_count=1,
    )
    assert quality["pass"]
    assert not quality["critical_failures"]


def test_s02_missing_implant_is_critical() -> None:
    quality = _evaluate_quality(
        "s02_service",
        arm="NEW",
        http_result={
            "answer_text": "Общий ответ без ключевой темы.",
            "meta": {"service_route": "sales_fast_materialized"},
            "widget_payload_ready": True,
        },
        provider_call_count=1,
    )
    assert not quality["pass"]
    assert any("missing_critical:имплант" in item for item in quality["critical_failures"])


def test_s03_rassrochka_noncritical_only() -> None:
    quality = _evaluate_quality(
        "s03_exact_price",
        arm="NEW",
        http_result={
            "answer_text": "Классическая имплантация — 76 200 ₽ за один зуб.",
            "meta": {"service_route": "sales_fast_materialized"},
            "widget_payload_ready": True,
        },
        provider_call_count=1,
    )
    assert quality["pass"]
    assert any(flag.startswith("missing_noncritical:") for flag in quality["noncritical_review_flags"])


def test_old_quality_failure_does_not_block_new_speed_gate() -> None:
    latency_runs = [
        {
            "arm": "OLD",
            "quality": {
                "pass": False,
                "critical_failures": ["missing_critical:76"],
            },
        },
        {
            "arm": "NEW",
            "quality": {"pass": True, "critical_failures": []},
        },
    ]
    admin_runs = [{"quality": {"pass": True}}]
    assert compute_speed_gate_quality_pass(latency_runs, admin_runs)


def test_new_critical_failure_blocks_speed_gate() -> None:
    latency_runs = [
        {
            "arm": "NEW",
            "quality": {
                "pass": False,
                "critical_failures": ["forbidden_price:636000"],
            },
        }
    ]
    assert not compute_speed_gate_quality_pass(latency_runs, [])


def test_invalid_ttft_yields_inconclusive_speed_gate() -> None:
    latency_runs = [
        {
            "arm": "NEW",
            "kind": "latency",
            "latency_category": "warm",
            "ttft_measurement_valid": False,
            "patient_ttft_ms": None,
            "total_ms": 1000,
        },
        {
            "arm": "OLD",
            "kind": "latency",
            "latency_category": "warm",
            "ttft_measurement_valid": True,
            "patient_ttft_ms": 2000,
            "total_ms": 2000,
        },
    ]
    summary = evaluate_speed_gate(
        warm_new_ttft_ms=[],
        warm_old_ttft_ms=[2000],
        warm_new_total_ms=[1000],
        warm_old_total_ms=[2000],
        new_provider_calls_ok=True,
        quality_pass=True,
        ttft_measurement_ready=False,
    )
    assert summary["verdict"] == "inconclusive"
    assert not summary["checks"]["ttft_measurement_pass"]


def test_v1_live_artifact_unmodified() -> None:
    repo = Path(__file__).resolve().parents[1]
    result_path = repo / "evals/v5/artifacts/one_call_stage3c_speed_gate_v1_2026-08-10-01/result.json"
    assert result_path.exists()
    expected_sha = "e9704a8f4068f6dde4b494403cbfdeedf972eb953856773ba075144ee25c6459"
    actual_sha = hashlib.sha256(result_path.read_bytes()).hexdigest()
    assert actual_sha == expected_sha


def test_v1_forensic_report_exists() -> None:
    repo = Path(__file__).resolve().parents[1]
    report = repo / "evals/v5/reports/one_call_stage3c_speed_gate_v1_forensic_report.json"
    assert report.exists()
    payload = __import__("json").loads(report.read_text(encoding="utf-8"))
    assert payload["ttft_measurement_valid"] is False
    assert payload["artifact_modified"] is False
