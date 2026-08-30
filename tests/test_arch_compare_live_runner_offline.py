"""Offline tests for architecture comparison LIVE runner (mock provider only)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.v5.arch_compare.arch_compare_configs import (
    FLASH_PROVIDER_MODEL_ID,
    PLUS_PROVIDER_MODEL_ID,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_fake_transport import build_fake_envelope_json
from evals.v5.arch_compare.arch_compare_live_contract import (
    LIVE_MEASUREMENT_ID,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
    frozen_config_digest,
)
from evals.v5.arch_compare.arch_compare_live_guard import (
    ArchCompareLiveGuardError,
    authorization_manifest_from_dict,
    build_guard_context,
    validate_run_mode,
)
from evals.v5.arch_compare.arch_compare_live_hooks import (
    active_eval_hook_names,
    eval_hook_scope,
    restore_eval_hooks,
)
from evals.v5.arch_compare.arch_compare_live_preflight import (
    ArchComparePreflightStateMachine,
    run_capability_preflight,
)
from evals.v5.arch_compare.arch_compare_live_report import persist_live_prep_artifacts
from evals.v5.arch_compare.arch_compare_live_runner import (
    ArchCompareLiveRunnerError,
    run_arch_compare_fake_full_path,
    run_arch_compare_live_full_path,
)
from evals.v5.arch_compare.arch_compare_live_transport import (
    ArchCompareLiveTransport,
    create_guarded_live_transport,
)
from evals.v5.arch_compare.arch_compare_matrix import frozen_matrix_digest
from evals.v5.arch_compare.arch_compare_provider_payload import (
    assert_flash_plus_payload_parity,
    build_composer_provider_payload,
)
from evals.v5.arch_compare.run_arch_compare_live import main as run_arch_compare_live_main

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


def _live_credentials() -> dict[str, str]:
    return {
        "chat_api_key": "sk-archcompare-live-mock-abcdef123456",
        "chat_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }


def _live_guard_context(tmp_path: Path, *, attempt_id: str = "live_runner_test"):
    return build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id=attempt_id,
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id=attempt_id)),
        artifact_dir=tmp_path / attempt_id,
        transport_kind="live",
        working_tree_clean=True,
        **_live_credentials(),
    )


def _fake_guard_context(tmp_path: Path, *, attempt_id: str = "fake_runner_test"):
    return build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id=attempt_id,
        live_requested=False,
        authorization=None,
        artifact_dir=tmp_path / attempt_id,
        transport_kind="fake",
        working_tree_clean=False,
    )


def _valid_envelope(*, marker: str = "probe") -> str:
    return build_fake_envelope_json(
        scenario_id="PRC-01",
        turn_id="PRC-01_t1",
        route="ANSWER",
        patient_text=f"arch_compare_live_mock:{marker}",
    )


def _mock_provider(*, responses: list[str], fail_at: int | None = None):
    state = {"call": 0}

    def chat_completions_create(**kwargs):
        state["call"] += 1
        if fail_at is not None and state["call"] == fail_at:
            raise RuntimeError("mock_provider_error")
        stream = bool(kwargs.get("stream"))
        model = str(kwargs.get("model") or "")
        content = responses[min(state["call"] - 1, len(responses) - 1)]
        usage = SimpleNamespace(prompt_tokens=3, completion_tokens=5)
        if stream:
            def generator():
                yield SimpleNamespace(
                    model=model,
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
                )
                yield SimpleNamespace(model=model, choices=[], usage=usage)

            return generator()
        return SimpleNamespace(
            model=model,
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=usage,
        )

    return chat_completions_create, state


def test_live_without_manifest_rejects_before_transport(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="no_manifest",
        live_requested=True,
        authorization=None,
        artifact_dir=tmp_path,
        transport_kind="live",
        **_live_credentials(),
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        validate_run_mode(ctx)
    assert exc.value.code == "authorization_missing"


def test_placeholder_credentials_reject_before_transport(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="placeholder",
        live_requested=True,
        authorization=authorization_manifest_from_dict(_valid_manifest(attempt_id="placeholder")),
        artifact_dir=tmp_path / "placeholder",
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="offline-test-placeholder",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        validate_run_mode(ctx)
    assert exc.value.code == "chat_api_key_placeholder"


def test_guarded_live_branch_uses_real_runner(tmp_path: Path) -> None:
    responses = [_valid_envelope(marker=f"call_{i}") for i in range(70)]
    mock_create, state = _mock_provider(responses=responses)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_guard_context(tmp_path, attempt_id="live_branch")
    validate_run_mode(ctx)
    result = run_arch_compare_live_full_path(
        attempt_id="live_branch",
        guard_context=ctx,
        transport=transport,
    )
    assert result["mode"] == "live_full_path"
    assert result["status"] == "MEASUREMENT_COMPLETE"
    assert result["provider_call_total"] == 70
    assert result["fake_transport_call_total"] == 0
    assert state["call"] == 70


def test_flash_preflight_fail_stops_at_one_call(tmp_path: Path) -> None:
    mock_create, state = _mock_provider(responses=['{"invalid": true}'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    state_machine = ArchComparePreflightStateMachine()
    flash, plus = run_capability_preflight(
        attempt_id="flash_fail",
        transport=transport,
        state=state_machine,
        use_fake_queue=False,
    )
    assert flash.success is False
    assert plus is None
    assert state["call"] == 1


def test_plus_preflight_fail_stops_at_two_calls(tmp_path: Path) -> None:
    mock_create, state = _mock_provider(
        responses=[_valid_envelope(marker="flash_ok"), '{"invalid": true}']
    )
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    state_machine = ArchComparePreflightStateMachine()
    flash, plus = run_capability_preflight(
        attempt_id="plus_fail",
        transport=transport,
        state=state_machine,
        use_fake_queue=False,
    )
    assert flash.success is True
    assert plus is not None and plus.success is False
    assert state["call"] == 2


def test_preflight_failure_blocks_measurement(tmp_path: Path) -> None:
    mock_create, _ = _mock_provider(responses=['{"invalid": true}'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_guard_context(tmp_path, attempt_id="blocked_measurement")
    with pytest.raises(ArchCompareLiveRunnerError) as exc:
        run_arch_compare_live_full_path(
            attempt_id="blocked_measurement",
            guard_context=ctx,
            transport=transport,
        )
    assert exc.value.code == "preflight_failed"
    assert exc.value.partial_result["provider_call_total"] == 1


def test_model_ids_passed_to_mock_client(tmp_path: Path) -> None:
    seen_models: list[str] = []

    def chat_completions_create(**kwargs):
        seen_models.append(str(kwargs.get("model")))
        content = _valid_envelope(marker=seen_models[-1])
        return SimpleNamespace(
            model=kwargs.get("model"),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )

    transport = ArchCompareLiveTransport(chat_completions_create=chat_completions_create)
    state_machine = ArchComparePreflightStateMachine()
    run_capability_preflight(
        attempt_id="model_ids",
        transport=transport,
        state=state_machine,
        use_fake_queue=False,
    )
    assert seen_models[0] == FLASH_PROVIDER_MODEL_ID
    assert seen_models[1] == PLUS_PROVIDER_MODEL_ID


def test_flash_plus_payload_parity_in_live_transport() -> None:
    messages = ({"role": "user", "content": "parity"},)
    assert_flash_plus_payload_parity(
        flash_config=config_by_id("flash_full"),
        plus_config=config_by_id("plus_full"),
        messages=messages,
    )


def test_streaming_response_fully_drained() -> None:
    content = _valid_envelope(marker="stream")
    mock_create, _ = _mock_provider(responses=[content])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    payload = build_composer_provider_payload(
        config=config_by_id("flash_full"),
        messages=({"role": "user", "content": "stream"},),
        stream=True,
    )
    response = transport.chat_completions_create(**payload)
    drained = (response.choices[0].message.content or "").strip()
    assert drained == content
    assert transport.records[-1].ttft_ms is not None
    assert transport.records[-1].latency_ms >= 0


def test_invalid_envelope_does_not_retry_on_preflight() -> None:
    mock_create, state = _mock_provider(responses=['not-json'])
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    state_machine = ArchComparePreflightStateMachine()
    flash, _ = run_capability_preflight(
        attempt_id="no_retry",
        transport=transport,
        state=state_machine,
        use_fake_queue=False,
    )
    assert flash.success is False
    assert state["call"] == 1


def test_secrets_not_in_live_mock_artifacts(tmp_path: Path) -> None:
    responses = [_valid_envelope(marker=f"sec_{i}") for i in range(70)]
    mock_create, _ = _mock_provider(responses=responses)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_guard_context(tmp_path, attempt_id="secrets_live")
    result = run_arch_compare_live_full_path(
        attempt_id="secrets_live",
        guard_context=ctx,
        transport=transport,
    )
    artifact_dir = tmp_path / "secrets_live"
    for path in artifact_dir.glob("*"):
        if path.suffix in {".json", ".md", ".log"}:
            text = path.read_text(encoding="utf-8")
            assert "OPENAI_API_KEY" not in text
            assert "Authorization: Bearer" not in text
            assert "sk-archcompare" not in text


def test_hooks_restore_after_live_mock_success() -> None:
    restore_eval_hooks()
    responses = [_valid_envelope(marker=f"hook_{i}") for i in range(70)]
    mock_create, _ = _mock_provider(responses=responses)

    def hook() -> None:
        return None

    with eval_hook_scope({"live_hook": hook}):
        assert "live_hook" in active_eval_hook_names()
    assert active_eval_hook_names() == ()


def test_hooks_restore_after_live_mock_exception() -> None:
    restore_eval_hooks()

    def boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        with eval_hook_scope({"boom_hook": boom}):
            boom()
    assert active_eval_hook_names() == ()


def test_default_fake_path_zero_provider_calls(tmp_path: Path) -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="fake_zero",
        guard_context=_fake_guard_context(tmp_path),
    )
    assert result["provider_call_total"] == 0
    assert result["fake_transport_call_total"] == 70


def test_cli_live_without_authorization_still_rejected() -> None:
    code = run_arch_compare_live_main(["--attempt-id", "cli_live_reject", "--live"])
    assert code == 2


def test_provider_error_surfaces_without_retry(tmp_path: Path) -> None:
    responses = [_valid_envelope(marker="ok")] * 2 + [_valid_envelope(marker="x")] * 68
    mock_create, state = _mock_provider(responses=responses, fail_at=3)
    transport = ArchCompareLiveTransport(chat_completions_create=mock_create)
    ctx = _live_guard_context(tmp_path, attempt_id="provider_error")
    result = run_arch_compare_live_full_path(
        attempt_id="provider_error",
        guard_context=ctx,
        transport=transport,
    )
    assert result["status"] == "MEASUREMENT_COMPLETE_WITH_ERRORS"
    assert state["call"] == 70
    assert len(result["measurement_errors"]) == 1
