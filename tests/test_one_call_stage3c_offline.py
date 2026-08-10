"""Stage 3C offline: Speed Gate contract, harness, patient TTFT, call plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as app_module
from evals.v5.one_call_stage3c_speed_gate_call_plan import (
    build_frozen_call_plan,
    prove_old_max_for_matrix_cases,
)
from evals.v5.one_call_stage3c_speed_gate_contract import (
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MODEL_SNAPSHOT,
    PROPOSED_LIVE_ATTEMPT_ID,
    SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS,
    SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT,
)
from evals.v5.one_call_stage3c_speed_gate_fake_transport import SpeedGateFakeTransport
from evals.v5.one_call_stage3c_speed_gate_harness import (
    assert_offline_gate_closed,
    run_offline_dry_run,
)
from evals.v5.one_call_stage3c_speed_gate_live_runner import (
    SpeedGateLiveGovernanceError,
    assert_live_governance,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import (
    FROZEN_SPEED_GATE_CASES,
    frozen_matrix_sha256,
    assert_frozen_matrix_unchanged,
)
from evals.v5.one_call_stage3c_speed_gate_patient_ttft import measure_patient_visible_timing
from evals.v5.one_call_stage3c_speed_gate_speed_gate import evaluate_speed_gate

_OLD_ARTIFACT = Path(__file__).resolve().parents[1] / "evals" / "v5" / "artifacts" / (
    "one_call_flash_capability_v1_2026-08-10-01"
)
_OLD_SHA = "143c66bd2370563c0f7f2c3593290ed70309b2e460485bd9cb56aa01430c95e8"


def test_live_gate_default_none() -> None:
    assert LIVE_AUTHORIZED_ATTEMPT_ID is None


def test_proposed_live_attempt_id_frozen() -> None:
    assert PROPOSED_LIVE_ATTEMPT_ID == "one_call_stage3c_speed_gate_v1_2026-08-10-01"


def test_frozen_matrix_sha_stable() -> None:
    assert_frozen_matrix_unchanged()
    sha = frozen_matrix_sha256()
    assert len(sha) == 64
    assert sha == frozen_matrix_sha256()


def test_matrix_has_nine_cases() -> None:
    assert len(FROZEN_SPEED_GATE_CASES) == 9


def test_call_plan_live_budget() -> None:
    plan = build_frozen_call_plan()
    assert plan.old_max_per_turn == 5
    assert plan.new_max_per_free_text == 1
    assert plan.new_max_admin == 0
    assert plan.max_provider_calls_live == 6 * 5 + 6 * 1 + 3 * 0


def test_patient_ttft_excludes_control_markers() -> None:
    stream = (
        "event: status\ndata: {\"message\":\"…\"}\n\n"
        "event: typing\ndata: {\"phase\":\"writing\"}\n\n"
        "event: text_delta\ndata: @ANSWER\n\n"
        "event: text_delta\ndata: Видимый текст\n\n"
        "event: ui\ndata: {\"answer\":\"Видимый текст\"}\n\n"
        "event: done\ndata: {}\n\n"
    )
    timing = measure_patient_visible_timing(
        stream_text=stream,
        request_started_monotonic=0.0,
        completed_monotonic=1.0,
    )
    assert timing.patient_text_kind == "text_delta"
    assert timing.first_visible_excerpt is not None
    assert timing.first_visible_excerpt.startswith("В")


def test_patient_ttft_ui_only_uses_total() -> None:
    stream = (
        "event: status\ndata: {\"message\":\"…\"}\n\n"
        "event: ui\ndata: {\"answer\":\"Ответ пациенту\"}\n\n"
        "event: done\ndata: {}\n\n"
    )
    timing = measure_patient_visible_timing(
        stream_text=stream,
        request_started_monotonic=0.0,
        completed_monotonic=0.5,
    )
    assert timing.patient_ttft_ms == 500


def test_speed_gate_threshold_boundary_pass() -> None:
    summary = evaluate_speed_gate(
        warm_new_ttft_ms=[1000, 1100],
        warm_old_ttft_ms=[2000, 2100],
        warm_new_total_ms=[1200, 1300],
        warm_old_total_ms=[2000, 2100],
        new_provider_calls_ok=True,
        quality_pass=True,
    )
    assert summary["checks"]["ttft_p50_pass"]
    assert summary["verdict"] == "pass"


def test_speed_gate_threshold_boundary_fail_p95() -> None:
    summary = evaluate_speed_gate(
        warm_new_ttft_ms=[1000, 3000],
        warm_old_ttft_ms=[2000, 2100],
        warm_new_total_ms=[1200, 1300],
        warm_old_total_ms=[2000, 2100],
        new_provider_calls_ok=True,
        quality_pass=True,
    )
    assert not summary["checks"]["ttft_p95_pass"]


def test_speed_gate_formula_constants() -> None:
    assert SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT == 0.30
    assert SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS == 2000


def test_fake_transport_records_provider_source() -> None:
    transport = SpeedGateFakeTransport(answer_text="ok")
    transport.chat_completions_create(
        model=MODEL_SNAPSHOT,
        messages=[],
        provider_call_source="sales_fast",
    )
    assert transport.calls[-1].source == "sales_fast"


def test_live_governance_closed() -> None:
    with pytest.raises(SpeedGateLiveGovernanceError):
        assert_live_governance(PROPOSED_LIVE_ATTEMPT_ID)


def test_offline_gate_closed() -> None:
    assert_offline_gate_closed()


def test_production_does_not_import_dry_run_runner() -> None:
    text = Path(app_module.__file__).read_text(encoding="utf-8")
    assert "run_one_call_stage3c_speed_gate_dry_run" not in text


def test_old_live_artifact_untouched() -> None:
    import hashlib

    assert _OLD_ARTIFACT.exists()
    sha = hashlib.sha256(_OLD_ARTIFACT.joinpath("result.json").read_bytes()).hexdigest()
    assert sha == _OLD_SHA


def test_offline_dry_run_proves_old_peak_and_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_offline_dry_run(
        monkeypatch,
        attempt_id="stage3c_pytest_dry_run",
        write_artifacts=False,
    )
    peak, proved = prove_old_max_for_matrix_cases(
        {
            row["case_id"]: row["provider_call_count"]
            for row in result["latency_runs"]
            if row["arm"] == "OLD"
        }
    )
    assert peak <= 5
    assert proved
    assert result["call_plan"]["old_max_proved_offline"]
    admin_calls = [row["provider_call_count"] for row in result["admin_runs"]]
    assert admin_calls == [0, 0, 0]
    new_calls = [
        row["provider_call_count"]
        for row in result["latency_runs"]
        if row["arm"] == "NEW" and row["case_id"] != "s01_microfact"
    ]
    assert all(count <= 1 for count in new_calls)


def test_offline_dry_run_writes_partial_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_dir = tmp_path / "stage3c_partial"
    monkeypatch.setattr(
        "evals.v5.one_call_stage3c_speed_gate_harness._ARTIFACTS_ROOT",
        tmp_path,
    )
    run_offline_dry_run(monkeypatch, attempt_id="stage3c_partial", write_artifacts=True)
    result_path = artifact_dir / "result.json"
    assert result_path.exists()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "offline_fake_transport"
    assert "speed_gate" in payload
