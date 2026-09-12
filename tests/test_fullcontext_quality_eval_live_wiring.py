from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.fullcontext_quality_eval_contract import (
    EXPECTED_LLM_CALLS,
    HarnessConfigError,
    MAX_COMPOSER_CALLS,
    MAX_VERIFIER_CALLS,
    OWNER_APPROVED_COMPOSER_MODEL,
    OWNER_APPROVED_VERIFIER_MODEL,
    append_call_ledger_entry,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    load_attempt_marker,
    record_provider_call_started,
)
from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
)
from evals.v5.run_fullcontext_quality_eval import prepare_live_run, run_live_harness


def test_attempt_marker_payload_records_owner_budget() -> None:
    payload = build_attempt_marker_payload(
        baseline_commit="abc123",
    )
    assert payload["status"] == "attempt_started"
    assert payload["baseline_commit"] == "abc123"
    assert payload["composer_model"] == OWNER_APPROVED_COMPOSER_MODEL
    assert payload["verifier_model"] == OWNER_APPROVED_VERIFIER_MODEL
    assert payload["max_llm_calls"] == EXPECTED_LLM_CALLS
    assert payload["max_composer_calls"] == MAX_COMPOSER_CALLS
    assert payload["max_verifier_calls"] == MAX_VERIFIER_CALLS
    assert payload["retry_count_max"] == 0


def test_record_provider_call_started_enforces_total_budget(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    for index in range(EXPECTED_LLM_CALLS):
        record_provider_call_started(
            marker,
            provider="composer" if index % 2 == 0 else "semantic_verifier",
        )
    with pytest.raises(HarnessConfigError, match="live LLM call budget exceeded"):
        record_provider_call_started(marker, provider="composer")


def test_record_provider_call_started_enforces_role_budgets(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    create_attempt_marker_exclusive(marker, build_attempt_marker_payload(baseline_commit="x"))
    for _ in range(MAX_COMPOSER_CALLS):
        record_provider_call_started(marker, provider="composer")
    with pytest.raises(HarnessConfigError, match="composer call budget exceeded"):
        record_provider_call_started(marker, provider="composer")


def test_call_ledger_append_start_and_complete(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    append_call_ledger_entry(
        ledger,
        {
            "case_id": "s57_pain_01",
            "provider": "composer",
            "phase": "call_start",
            "call_index": 1,
        },
    )
    append_call_ledger_entry(
        ledger,
        {
            "case_id": "s57_pain_01",
            "provider": "composer",
            "phase": "call_complete",
            "call_index": 1,
        },
    )
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "call_start"
    assert json.loads(lines[1])["phase"] == "call_complete"


def test_prepare_live_run_creates_marker_before_backend(tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    prepare_live_run(
        attempt_marker_path=marker,
        artifact_paths=(),
        baseline_commit="deadbeef",
    )
    payload = load_attempt_marker(marker)
    assert payload["status"] == "attempt_started"
    assert payload["baseline_commit"] == "deadbeef"


def test_run_live_harness_mocked_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = tmp_path / "raw.json"
    result = tmp_path / "result.json"
    manifest = tmp_path / "manifest.json"
    marker = tmp_path / "attempt.json"
    ledger = tmp_path / "ledger.jsonl"
    manual = tmp_path / "manual.json"
    artifact_paths = (raw, result, manifest, marker, ledger, manual)

    monkeypatch.setattr(
        "evals.v5.run_fullcontext_quality_eval._git_head_commit",
        lambda: "livebaseline",
    )

    def _mock_factory(*, call_ledger_path: Path, attempt_marker_path: Path):
        def factory(case: dict[str, object]) -> tuple[object, object]:
            return (
                FullContextResponseEvalRecordingComposerBackend(
                    str(case["offline_composer_stub"])
                ),
                FullContextResponseEvalRecordingSemanticBackend(),
            )

        return factory

    monkeypatch.setattr(
        "evals.v5.run_fullcontext_quality_eval._live_backend_factory",
        _mock_factory,
    )

    payload = run_live_harness(
        attempt_marker_path=marker,
        call_ledger_path=ledger,
        raw_path=raw,
        result_path=result,
        manifest_path=manifest,
        manual_review_path=manual,
        artifact_paths=artifact_paths,
    )

    assert raw.exists()
    assert result.exists()
    assert manifest.exists()
    assert manual.exists()
    assert payload["summary"]["total_llm_calls"] == 18
    assert payload["summary"]["composer_calls"] == 9
    assert payload["summary"]["verifier_calls"] == 9
    assert payload["summary"]["final_verdict"] == "PENDING_MANUAL_REVIEW"
    marker_payload = load_attempt_marker(marker)
    assert marker_payload["status"] == "attempt_completed"
    assert marker_payload["completed_provider_calls"] == 18
