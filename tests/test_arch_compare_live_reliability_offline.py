"""Offline reliability tests for architecture comparison LIVE runner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.v5.arch_compare.arch_compare_configs import (
    ARCH_COMPARE_INFERENCE_SETTINGS,
    FLASH_PROVIDER_MODEL_ID,
    PLUS_PROVIDER_MODEL_ID,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_fake_transport import build_fake_envelope_json
from evals.v5.arch_compare.arch_compare_live_contract import (
    EVAL_REQUEST_TIMEOUT_SEC,
    LIVE_MEASUREMENT_ID,
    PRODUCTION_SLA_REFERENCE_SEC,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
    frozen_config_digest,
)
from evals.v5.arch_compare.arch_compare_live_guard import (
    ArchCompareLiveGuardError,
    assert_seventy_first_call_blocked,
    authorization_manifest_from_dict,
    build_guard_context,
    validate_run_mode,
)
from evals.v5.arch_compare.arch_compare_live_persistence import (
    ArchCompareCallLedger,
    ArchCompareLiveArtifactStore,
    atomic_write_json,
)
from evals.v5.arch_compare.arch_compare_live_report import (
    assert_blind_review_secrecy,
    build_blind_review_markdown,
)
from evals.v5.arch_compare.arch_compare_live_runner import (
    ArchCompareLiveRunnerError,
    build_call_budget_plan,
    run_arch_compare_live_full_path,
)
from evals.v5.arch_compare.arch_compare_live_schedule import build_execution_schedule
from evals.v5.arch_compare.arch_compare_live_transport import ArchCompareLiveTransport
from evals.v5.arch_compare.arch_compare_matrix import frozen_matrix_digest
from evals.v5.arch_compare.arch_compare_provider_payload import build_composer_provider_payload

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _valid_manifest(*, attempt_id: str) -> dict:
    return {
        "attempt_id": attempt_id,
        "expected_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True
        ).strip(),
        "matrix_digest": frozen_matrix_digest(),
        "config_digest": frozen_config_digest(),
        "allowed_model_ids": [FLASH_PROVIDER_MODEL_ID, PLUS_PROVIDER_MODEL_ID],
        "max_provider_calls": TOTAL_AUTHORIZED_PROVIDER_BUDGET,
        "client_id": "demo",
        "issued_for_measurement": LIVE_MEASUREMENT_ID,
        "explicit_live": True,
        "includes_capability_preflight": True,
    }


def _live_ctx(tmp_path: Path, attempt_id: str):
    return build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id=attempt_id,
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id=attempt_id)),
        artifact_dir=tmp_path / attempt_id,
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="sk-archcompare-live-mock-abcdef123456",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def _envelope(marker: str) -> str:
    return build_fake_envelope_json(
        scenario_id="PRC-01",
        turn_id="PRC-01_t1",
        route="ANSWER",
        patient_text=f"arch_compare_live_mock:{marker}",
    )


def _mock_provider(*, responses: list[str], fail_at: int | None = None, timeout_at: int | None = None):
    state = {"call": 0}

    def chat_completions_create(**kwargs):
        state["call"] += 1
        if fail_at is not None and state["call"] == fail_at:
            raise RuntimeError("Request timed out.")
        if timeout_at is not None and state["call"] == timeout_at:
            raise TimeoutError("request timed out")
        content = responses[min(state["call"] - 1, len(responses) - 1)]
        return SimpleNamespace(
            model=kwargs.get("model"),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=2, completion_tokens=4),
        )

    return chat_completions_create, state


def test_artifact_directory_created_before_first_provider_call(tmp_path: Path) -> None:
    mock_create, _ = _mock_provider(responses=['{"invalid": true}'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "preflight_first")
    with pytest.raises(ArchCompareLiveRunnerError):
        run_arch_compare_live_full_path(
            attempt_id="preflight_first",
            guard_context=ctx,
            transport=transport,
        )
    artifact_dir = tmp_path / "preflight_first"
    assert (artifact_dir / "manifest.json").exists()
    assert (artifact_dir / "schedule.json").exists()
    assert (artifact_dir / "call_ledger.json").exists()
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PREFLIGHT_FAILED"


def test_preflight_failure_persists_partial_artifacts(tmp_path: Path) -> None:
    mock_create, _ = _mock_provider(responses=['{"invalid": true}'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "preflight_partial")
    with pytest.raises(ArchCompareLiveRunnerError):
        run_arch_compare_live_full_path(
            attempt_id="preflight_partial",
            guard_context=ctx,
            transport=transport,
        )
    artifact_dir = tmp_path / "preflight_partial"
    assert (artifact_dir / "error_report.json").exists()
    assert (artifact_dir / "raw_turns.json").exists()
    assert json.loads((artifact_dir / "raw_turns.json").read_text(encoding="utf-8")) == []


def test_call_marked_started_before_provider_invocation() -> None:
    ledger = ArchCompareCallLedger(attempt_id="ledger")
    started = ledger.start_call(
        phase="preflight",
        scenario_id="PREFLIGHT",
        turn_id="PREFLIGHT_flash",
        config_id="flash_full",
        model_id=FLASH_PROVIDER_MODEL_ID,
    )
    assert started.status == "started"
    assert ledger.consumed_calls == 1


def test_started_call_counts_toward_budget() -> None:
    ledger = ArchCompareCallLedger(attempt_id="ledger")
    ledger.start_call(
        phase="measurement",
        scenario_id="S1",
        turn_id="S1_t1",
        config_id="flash_full",
        model_id=FLASH_PROVIDER_MODEL_ID,
    )
    with pytest.raises(RuntimeError):
        for _ in range(TOTAL_AUTHORIZED_PROVIDER_BUDGET):
            ledger.start_call(
                phase="measurement",
                scenario_id="S",
                turn_id="T",
                config_id="flash_full",
                model_id=FLASH_PROVIDER_MODEL_ID,
            )


def test_successful_call_becomes_completed() -> None:
    ledger = ArchCompareCallLedger(attempt_id="ledger")
    entry = ledger.start_call(
        phase="preflight",
        scenario_id="PREFLIGHT",
        turn_id="PREFLIGHT_flash",
        config_id="flash_full",
        model_id=FLASH_PROVIDER_MODEL_ID,
    )
    ledger.complete_call(entry, latency_ms=1500, usage={"prompt_tokens": 1, "completion_tokens": 2})
    assert entry.status == "completed"
    assert entry.latency_ms == 1500


def test_timeout_becomes_failed_without_retry(tmp_path: Path) -> None:
    responses = [_envelope("ok")] * 2 + [_envelope("x")] * 68
    mock_create, state = _mock_provider(responses=responses, fail_at=3)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "timeout_one")
    result = run_arch_compare_live_full_path(
        attempt_id="timeout_one",
        guard_context=ctx,
        transport=transport,
    )
    assert result["status"] == "MEASUREMENT_COMPLETE_WITH_ERRORS"
    assert state["call"] == 70
    ledger = json.loads((tmp_path / "timeout_one" / "call_ledger.json").read_text(encoding="utf-8"))
    failed = [row for row in ledger["calls"] if row["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["error_code"] == "request_timeout"


def test_measurement_continues_after_timeout(tmp_path: Path) -> None:
    responses = [_envelope("ok")] * 2 + [_envelope("x")] * 68
    mock_create, state = _mock_provider(responses=responses, fail_at=3)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "continue_after_timeout")
    result = run_arch_compare_live_full_path(
        attempt_id="continue_after_timeout",
        guard_context=ctx,
        transport=transport,
    )
    assert len(result["structured_turns"]) == 76
    assert state["call"] == 70


def test_complete_with_errors_builds_blind_review(tmp_path: Path) -> None:
    responses = [_envelope("ok")] * 2 + [_envelope("x")] * 68
    mock_create, _ = _mock_provider(responses=responses, fail_at=3)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "blind_with_errors")
    run_arch_compare_live_full_path(
        attempt_id="blind_with_errors",
        guard_context=ctx,
        transport=transport,
    )
    blind_md = (tmp_path / "blind_with_errors" / "blind_review.md").read_text(encoding="utf-8")
    assert "Ответ не получен: timeout/provider error" in blind_md
    assert_blind_review_secrecy(blind_md)
    assert "latency" not in blind_md.casefold()


def test_atomic_json_remains_valid_after_write_failure(tmp_path: Path) -> None:
    schedule = build_execution_schedule(attempt_id="atomic_fail")
    budget = build_call_budget_plan(schedule).to_dict()
    artifact_dir = tmp_path / "attempt"
    store = ArchCompareLiveArtifactStore.initialize(
        artifact_dir=artifact_dir,
        attempt_id="atomic_fail",
        schedule=schedule.to_dict(),
        budget_plan=budget,
        head_sha="0" * 40,
        matrix_digest=frozen_matrix_digest(),
        config_digest=frozen_config_digest(),
        measurement_id=LIVE_MEASUREMENT_ID,
    )
    manifest_path = artifact_dir / "manifest.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))

    import evals.v5.arch_compare.arch_compare_live_persistence as persistence

    real_atomic = persistence.atomic_write_json

    def boom(path: Path, payload):
        if path.name == "manifest.json":
            raise OSError("simulated write failure")
        real_atomic(path, payload)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(persistence, "atomic_write_json", boom)
    with pytest.raises(persistence.ArchCompareArtifactWriteError):
        store.persist_core()
    monkeypatch.undo()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == original


def test_exact_call_count_from_ledger(tmp_path: Path) -> None:
    responses = [_envelope(f"c{i}") for i in range(70)]
    mock_create, _ = _mock_provider(responses=responses)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "exact_count")
    run_arch_compare_live_full_path(
        attempt_id="exact_count",
        guard_context=ctx,
        transport=transport,
    )
    ledger = json.loads((tmp_path / "exact_count" / "call_ledger.json").read_text(encoding="utf-8"))
    assert ledger["consumed_calls"] == 70


def test_seventy_first_call_blocked() -> None:
    with pytest.raises(ArchCompareLiveGuardError):
        assert_seventy_first_call_blocked(call_index=71)


def test_eval_timeout_is_sixty_for_flash_and_plus() -> None:
    assert EVAL_REQUEST_TIMEOUT_SEC == 60
    flash_payload = build_composer_provider_payload(
        config=config_by_id("flash_full"),
        messages=({"role": "user", "content": "x"},),
        stream=False,
    )
    plus_payload = build_composer_provider_payload(
        config=config_by_id("plus_full"),
        messages=({"role": "user", "content": "x"},),
        stream=False,
    )
    assert flash_payload["timeout"] == 60
    assert plus_payload["timeout"] == 60
    assert ARCH_COMPARE_INFERENCE_SETTINGS.timeout_sec == 60.0


def test_sla_breach_marker_recorded_on_success() -> None:
    ledger = ArchCompareCallLedger(attempt_id="sla")
    entry = ledger.start_call(
        phase="measurement",
        scenario_id="S",
        turn_id="T",
        config_id="flash_full",
        model_id=FLASH_PROVIDER_MODEL_ID,
    )
    ledger.complete_call(entry, latency_ms=PRODUCTION_SLA_REFERENCE_SEC * 1000 + 1, usage={})
    assert entry.production_sla_breached is True


def test_chat_api_key_missing_blocks_live(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="missing_key",
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id="missing_key")),
        artifact_dir=tmp_path / "missing_key",
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        validate_run_mode(ctx)
    assert exc.value.code == "chat_api_key_missing"


def test_chat_base_url_placeholder_blocks_live(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="placeholder_url",
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id="placeholder_url")),
        artifact_dir=tmp_path / "placeholder_url",
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="sk-archcompare-live-mock-abcdef123456",
        chat_base_url="offline-test-placeholder",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        validate_run_mode(ctx)
    assert exc.value.code == "chat_base_url_placeholder"


def test_existing_attempt_directory_blocks_live(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "exists"
    attempt_dir.mkdir()
    (attempt_dir / "manifest.json").write_text("{}", encoding="utf-8")
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="exists",
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id="exists")),
        artifact_dir=attempt_dir,
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="sk-archcompare-live-mock-abcdef123456",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        validate_run_mode(ctx)
    assert exc.value.code == "artifact_dir_exists"


def test_preflight_failure_still_blocks_measurement(tmp_path: Path) -> None:
    mock_create, state = _mock_provider(responses=['{"invalid": true}'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "preflight_block")
    with pytest.raises(ArchCompareLiveRunnerError) as exc:
        run_arch_compare_live_full_path(
            attempt_id="preflight_block",
            guard_context=ctx,
            transport=transport,
        )
    assert exc.value.code == "preflight_failed"
    assert state["call"] == 1


def test_secrets_not_written_to_artifacts(tmp_path: Path) -> None:
    responses = [_envelope(f"s{i}") for i in range(70)]
    mock_create, _ = _mock_provider(responses=responses)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "secret_safe")
    run_arch_compare_live_full_path(
        attempt_id="secret_safe",
        guard_context=ctx,
        transport=transport,
    )
    for path in (tmp_path / "secret_safe").glob("*"):
        if path.suffix in {".json", ".md", ".log"}:
            text = path.read_text(encoding="utf-8")
            assert "CHAT_API_KEY" not in text
            assert "sk-archcompare" not in text


def test_fatal_exception_preserves_partial_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_envelope(f"fatal{i}") for i in range(70)]
    mock_create, state = _mock_provider(responses=responses)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_ctx(tmp_path, "fatal_partial")
    original_append = ArchCompareLiveArtifactStore.append_turn
    saved_turns = {"count": 0}

    def append_then_fatal(self, *, raw_turn, structured_turn):
        original_append(self, raw_turn=raw_turn, structured_turn=structured_turn)
        saved_turns["count"] += 1
        if saved_turns["count"] >= 3:
            raise RuntimeError("simulated runner fatal")

    monkeypatch.setattr(ArchCompareLiveArtifactStore, "append_turn", append_then_fatal)

    with pytest.raises(ArchCompareLiveRunnerError) as exc:
        run_arch_compare_live_full_path(
            attempt_id="fatal_partial",
            guard_context=ctx,
            transport=transport,
        )
    assert exc.value.code == "incomplete_fatal"

    artifact_dir = tmp_path / "fatal_partial"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    ledger = json.loads((artifact_dir / "call_ledger.json").read_text(encoding="utf-8"))
    raw_turns = json.loads((artifact_dir / "raw_turns.json").read_text(encoding="utf-8"))
    structured_turns = json.loads((artifact_dir / "structured_turns.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "INCOMPLETE_FATAL"
    assert len(raw_turns) == 3
    assert len(structured_turns) == 3
    assert all("arch_compare_live_mock:fatal" in row["patient_text"] for row in raw_turns)
    assert ledger["consumed_calls"] == 5
    assert state["call"] == 5
    assert (artifact_dir / "error_report.json").exists()
