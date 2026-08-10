"""Stage 3B offline preflight: honest probes, IPC, ledger, artifacts."""

from __future__ import annotations

import json
import multiprocessing
from dataclasses import asdict
from pathlib import Path

import pytest

import config
import llm as llm_module
from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError,
    build_openai_compatible_client_kwargs,
    validate_alibaba_chat_base_url,
    validate_capability_live_model,
)
from core.one_call_closed_envelope_validation import sample_valid_json_mode_envelope
from evals.v5.one_call_flash_capability_contract import (
    FROZEN_CAPABILITY_CASES,
    LIVE_AUTHORIZED_ATTEMPT_ID,
    MAX_CALLS,
    MODEL_SNAPSHOT,
    PROPOSED_LIVE_ATTEMPT_ID,
    case_by_id,
    frozen_case_ids,
)
from evals.v5.one_call_flash_capability_harness import (
    FakeProviderResponse,
    FakeProviderTransport,
    ResponseFormatUnsupportedError,
    sample_offline_fake_responses,
)
from evals.v5.one_call_flash_capability_live_artifacts import (
    artifact_paths_for_attempt,
)
from evals.v5.one_call_flash_capability_live_runner import (
    CapabilityLiveGovernanceError,
    assert_live_governance,
    build_capability_conclusions,
    run_live_attempt,
    run_preflight_blocked,
    spawn_isolated_case,
)
from evals.v5.one_call_flash_capability_live_transport import (
    execute_live_capability_transport,
)
from evals.v5.one_call_flash_capability_plan import (
    cache_stable_prefix_sha256,
    frozen_capability_plan_document,
    frozen_capability_plan_sha256,
    messages_for_live_case,
)
from evals.v5.one_call_flash_capability_probes import (
    JSON_MODE_CAPABILITY_PROBE_USER,
    LEGACY_CAPABILITY_PROBE_USER,
    build_cache_cold_dynamic_suffix,
    build_cache_repeat_dynamic_suffix,
    probe_template_for_case_id,
)
from evals.v5.run_one_call_flash_capability_live import main as live_cli_main


SINGAPORE_ENDPOINT = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_CN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MAAS_ENDPOINT = "https://ws-123.ap-southeast-1.maas.aliyuncs.com/v1"
MAAS_HYPHEN_WORKSPACE_ENDPOINT = "https://my-workspace.ap-southeast-1.maas.aliyuncs.com/v1"


def _patch_live_gate(
    monkeypatch: pytest.MonkeyPatch,
    attempt_id: str = PROPOSED_LIVE_ATTEMPT_ID,
) -> None:
    monkeypatch.setattr(
        "evals.v5.one_call_flash_capability_contract.LIVE_AUTHORIZED_ATTEMPT_ID",
        attempt_id,
    )
    monkeypatch.setattr(
        "evals.v5.one_call_flash_capability_live_runner.LIVE_AUTHORIZED_ATTEMPT_ID",
        attempt_id,
    )


def _patch_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CHAT_BASE_URL", SINGAPORE_ENDPOINT)
    monkeypatch.setattr(config, "CHAT_API_KEY", "sk-test-key")


def _ledger_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]


@pytest.mark.parametrize(
    "base_url",
    [
        SINGAPORE_ENDPOINT,
        DASHSCOPE_CN_ENDPOINT,
        MAAS_ENDPOINT,
        MAAS_HYPHEN_WORKSPACE_ENDPOINT,
    ],
)
def test_alibaba_endpoint_allowed(base_url: str) -> None:
    assert validate_alibaba_chat_base_url(base_url).startswith("https://")


@pytest.mark.parametrize(
    ("base_url", "code"),
    [
        ("", "chat_base_url_missing"),
        ("https://api.openai.com/v1", "chat_base_url_host_blocked"),
        ("https://chat.openai.com/v1", "chat_base_url_host_blocked"),
        ("https://evil-dashscope-intl.aliyuncs.com.attacker.com/v1", "chat_base_url_host_blocked"),
        ("http://dashscope-intl.aliyuncs.com/v1", "chat_base_url_scheme_invalid"),
        ("https://unknown.example.com/v1", "chat_base_url_host_blocked"),
        ("https://dashscope-intl.aliyuncs.com/v1?key=secret", "chat_base_url_query_forbidden"),
        ("https://user:pass@dashscope-intl.aliyuncs.com/v1", "chat_base_url_credentials_forbidden"),
        ("https://not-maas.evil.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://evil.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://fake.ap-southeast-1.evil.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://a.b.ap-southeast-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://ws-123.eu-central-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://ap-southeast-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://-bad.ap-southeast-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://bad-.ap-southeast-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        ("https://bad_label.ap-southeast-1.maas.aliyuncs.com/v1", "chat_base_url_host_blocked"),
        (
            "https://ws-123.ap-southeast-1.maas.aliyuncs.com.evil.com/v1",
            "chat_base_url_host_blocked",
        ),
    ],
)
def test_alibaba_endpoint_blocked(base_url: str, code: str) -> None:
    with pytest.raises(AlibabaEndpointConfigurationError, match=code):
        validate_alibaba_chat_base_url(base_url)


def test_capability_model_pin() -> None:
    assert validate_capability_live_model(MODEL_SNAPSHOT) == MODEL_SNAPSHOT
    with pytest.raises(AlibabaEndpointConfigurationError, match="capability_model_invalid"):
        validate_capability_live_model("qwen3.7-plus")


def test_endpoint_block_zero_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def _counting_create(**_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _counting_create)
    monkeypatch.setattr(config, "CHAT_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(config, "CHAT_API_KEY", "sk-test")
    case = case_by_id("legacy_blocking")
    transport = FakeProviderTransport(responses=sample_offline_fake_responses())
    transport.set_case(case.case_id)
    with pytest.raises(AlibabaEndpointConfigurationError):
        execute_live_capability_transport(
            case,
            attempt_id="offline",
            transport=transport.chat_completions_create,
        )
    assert attempts == 0


def test_chat_client_max_retries_zero() -> None:
    assert llm_module.chat_client.max_retries == 0


def test_sdk_error_single_create_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def _fail_once(**_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transport_fail")

    _patch_endpoint(monkeypatch)
    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _fail_once)
    with pytest.raises(RuntimeError, match="transport_fail"):
        llm_module.chat_completions_create(
            model=MODEL_SNAPSHOT,
            messages=[{"role": "user", "content": "probe"}],
        )
    assert attempts == 1


def test_chat_completions_create_blocks_missing_endpoint_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def _never_called(**_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1

    monkeypatch.setattr(config, "CHAT_BASE_URL", "")
    monkeypatch.setattr(config, "CHAT_API_KEY", "sk-test")
    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _never_called)
    with pytest.raises(AlibabaEndpointConfigurationError, match="chat_base_url_missing"):
        llm_module.chat_completions_create(
            model=MODEL_SNAPSHOT,
            messages=[{"role": "user", "content": "probe"}],
        )
    assert attempts == 0


def test_gate_none_zero_children_zero_calls() -> None:
    assert LIVE_AUTHORIZED_ATTEMPT_ID is None
    summary = run_preflight_blocked(PROPOSED_LIVE_ATTEMPT_ID)
    assert summary["consumed_call_count"] == 0
    assert summary["spawned_child_count"] == 0
    assert summary["status"] == "live_blocked"


def test_wrong_attempt_id_zero_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gate(monkeypatch, PROPOSED_LIVE_ATTEMPT_ID)
    with pytest.raises(CapabilityLiveGovernanceError, match="attempt_id_mismatch"):
        assert_live_governance("wrong_attempt_id")


def test_json_probe_contains_all_nine_fields_and_example() -> None:
    probe = JSON_MODE_CAPABILITY_PROBE_USER.lower()
    for key in (
        "route",
        "service_id",
        "extent",
        "jaw",
        "stage",
        "scenario",
        "clarify_axis",
        "clarify_service_options",
        "patient_text",
    ):
        assert key in probe
    assert "json" in probe
    assert sample_valid_json_mode_envelope() in JSON_MODE_CAPABILITY_PROBE_USER


def test_legacy_probe_requires_answer_admin_markers() -> None:
    probe = LEGACY_CAPABILITY_PROBE_USER
    assert "@ANSWER" in probe
    assert "@ADMIN" in probe


def test_json_and_legacy_blocking_streaming_share_probe_contract() -> None:
    json_blocking = messages_for_live_case(case_by_id("json_mode_blocking"), attempt_id="x")
    json_streaming = messages_for_live_case(case_by_id("json_mode_streaming"), attempt_id="x")
    legacy_blocking = messages_for_live_case(case_by_id("legacy_blocking"), attempt_id="x")
    legacy_streaming = messages_for_live_case(case_by_id("legacy_streaming"), attempt_id="x")
    assert json_blocking == json_streaming
    assert legacy_blocking == legacy_streaming


def test_cache_suffixes_are_production_shaped_and_distinct() -> None:
    cold = build_cache_cold_dynamic_suffix()
    repeat = build_cache_repeat_dynamic_suffix()
    assert "<USER_MESSAGE_DATA>" in cold
    assert "<EXACT_SALES_RESOLUTION>" in cold
    assert cold != repeat


def test_frozen_plan_sha_includes_probe_templates() -> None:
    doc = frozen_capability_plan_document()
    for case in FROZEN_CAPABILITY_CASES:
        row = next(row for row in doc["cases"] if row["case_id"] == case.case_id)
        assert row["probe_template"] == probe_template_for_case_id(case.case_id)


def test_probe_template_change_changes_frozen_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    before = frozen_capability_plan_sha256()
    monkeypatch.setattr(
        "evals.v5.one_call_flash_capability_probes.LEGACY_CAPABILITY_PROBE_USER",
        LEGACY_CAPABILITY_PROBE_USER + " amended",
    )
    after = frozen_capability_plan_sha256()
    assert before != after


def test_cold_repeat_stable_prefix_sha_equal() -> None:
    sha = cache_stable_prefix_sha256(PROPOSED_LIVE_ATTEMPT_ID)
    cold = messages_for_live_case(case_by_id("cache_cold"), attempt_id=PROPOSED_LIVE_ATTEMPT_ID)
    repeat = messages_for_live_case(case_by_id("cache_repeat"), attempt_id=PROPOSED_LIVE_ATTEMPT_ID)
    assert cold[0]["content"] == repeat[0]["content"]
    assert cold[1]["content"] != repeat[1]["content"]
    assert sha == cache_stable_prefix_sha256(PROPOSED_LIVE_ATTEMPT_ID)


def test_one_child_one_transport_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    case = case_by_id("legacy_blocking")
    job = {
        "case_id": case.case_id,
        "attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "use_fake_transport": True,
        "fake_responses": [asdict(sample_offline_fake_responses()[2])],
    }
    ipc, cleanup = spawn_isolated_case(job, wall_timeout_seconds=30)
    assert cleanup
    assert ipc["status"] == "ok"
    assert ipc["result"]["transport_attempts"] == 1


def test_blocking_success_fake_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
        wall_timeout_seconds=30,
    )
    assert result["status"] == "completed"
    assert result["legacy_blocking_supported"]
    assert result["consumed_call_count"] == MAX_CALLS
    assert result["completed_call_count"] == MAX_CALLS
    assert result["status"] == "completed"


def test_streaming_first_delta_and_final(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    streaming = next(
        row for row in result["case_results"] if row["case_id"] == "json_mode_streaming"
    )
    assert streaming["first_delta_excerpt"] is not None
    assert streaming["response_excerpt"] is not None


def test_streaming_model_from_first_chunk_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_endpoint(monkeypatch)
    case = case_by_id("json_mode_streaming")

    def _stream_transport(**_kwargs: object) -> list[object]:
        class _Delta:
            content = "stream chunk"

        class _Choice:
            delta = _Delta()

        class _Details:
            cached_tokens = 0

        class _Usage:
            prompt_tokens = 3
            completion_tokens = 2
            prompt_tokens_details = _Details()

        class _ChunkFirst:
            model = MODEL_SNAPSHOT
            choices = [_Choice()]
            usage = None

        class _ChunkFinal:
            model = None
            choices = []
            usage = _Usage()

        return [_ChunkFirst(), _ChunkFinal()]

    result = execute_live_capability_transport(
        case,
        attempt_id="offline",
        transport=_stream_transport,
        validate_endpoint=False,
    )
    assert result.observed_model == MODEL_SNAPSHOT
    assert result.prompt_tokens == 3


def test_malformed_outcome_finish_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[0] = FakeProviderResponse(model=MODEL_SNAPSHOT, content="{not-json", malformed=True)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        fake_responses=fake,
    )
    json_blocking = next(
        row for row in result["case_results"] if row["case_id"] == "json_mode_blocking"
    )
    assert json_blocking["outcome"] == "malformed"
    assert json_blocking["ledger_event"] == "FINISH"
    events = _ledger_events(paths.calls_jsonl)
    assert events[0]["event"] == "START"
    assert events[1]["event"] == "FINISH"


def test_response_format_unsupported_error_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[0] = FakeProviderResponse(
        model=MODEL_SNAPSHOT,
        content="",
        raise_error=ResponseFormatUnsupportedError("unsupported"),
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        fake_responses=fake,
    )
    events = _ledger_events(paths.calls_jsonl)
    assert events[1]["event"] == "ERROR"
    assert result["status"] == "completed"
    assert result["consumed_call_count"] == MAX_CALLS


def test_provider_exception_error_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[0] = FakeProviderResponse(
        model=MODEL_SNAPSHOT,
        content="",
        raise_error=RuntimeError("boom"),
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        fake_responses=fake,
    )
    first = result["case_results"][0]
    assert first["ledger_event"] == "ERROR"
    events = _ledger_events(paths.calls_jsonl)
    assert events[1]["event"] == "ERROR"
    assert result["status"] == "completed"
    assert result["completed_call_count"] == MAX_CALLS - 1


class AuthenticationError(Exception):
    """Test double for OpenAI SDK authentication failure."""


def test_authentication_error_aborts_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt_id = "auth_abort_test_attempt"
    _patch_live_gate(monkeypatch, attempt_id)
    _patch_endpoint(monkeypatch)
    active_before = len(multiprocessing.active_children())
    fake = list(sample_offline_fake_responses())
    fake[0] = FakeProviderResponse(
        model=MODEL_SNAPSHOT,
        content="",
        raise_error=AuthenticationError("auth failed"),
    )
    paths = artifact_paths_for_attempt(attempt_id, artifacts_root=tmp_path)
    result = run_live_attempt(
        attempt_id,
        artifact_root=paths,
        use_fake_transport=True,
        fake_responses=fake,
    )
    assert result["status"] == "error"
    assert result["failure_kind"] == "provider_authentication_failed"
    assert result["consumed_call_count"] == 1
    assert result["completed_call_count"] == 0
    assert len(result["case_results"]) == 1
    events = _ledger_events(paths.calls_jsonl)
    assert len(events) == 2
    assert events[0]["event"] == "START"
    assert events[1]["event"] == "ERROR"
    assert events[1]["error_code"] == "AuthenticationError"
    assert paths.raw_json.exists()
    assert paths.result_json.exists()
    blob = paths.raw_json.read_text(encoding="utf-8") + paths.result_json.read_text(encoding="utf-8")
    assert "sk-" not in blob.lower()
    contract_text = (
        Path(__file__).resolve().parents[1]
        / "evals/v5/one_call_flash_capability_contract.py"
    ).read_text(encoding="utf-8")
    assert "LIVE_AUTHORIZED_ATTEMPT_ID: str | None = None" in contract_text
    assert len(multiprocessing.active_children()) == active_before


def test_model_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[2] = FakeProviderResponse(model="wrong-model", content="@ANSWER\nlegacy ok")
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
        fake_responses=fake,
    )
    legacy = next(row for row in result["case_results"] if row["case_id"] == "legacy_blocking")
    assert legacy["outcome"] == "model_mismatch"
    assert legacy["ledger_event"] == "FINISH"


def test_cache_cold_repeat_prefix_and_cached_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    cold_row = next(row for row in result["case_results"] if row["case_id"] == "cache_cold")
    repeat_row = next(row for row in result["case_results"] if row["case_id"] == "cache_repeat")
    assert cold_row["stable_prefix_sha256"] == repeat_row["stable_prefix_sha256"]
    assert cold_row["cached_tokens"] == 0
    assert repeat_row["cached_tokens"] > 0
    assert result["provider_cache_hit_observed"]


def test_cache_hit_wrong_model_not_observed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[5] = FakeProviderResponse(
        model="wrong-model",
        content="@ANSWER\nwarm",
        cached_tokens=128,
    )
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
        fake_responses=fake,
    )
    assert result["provider_cache_hit_observed"] is False


def test_full_runner_timeout_aborts_remaining_cases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    active_before = len(multiprocessing.active_children())
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        wall_timeout_seconds=0.5,
        hang_on_case_id="json_mode_blocking",
    )
    assert result["status"] == "aborted"
    assert result["consumed_call_count"] == 1
    assert result["completed_call_count"] == 0
    assert result["wall_timeout_occurred"]
    assert len(result["case_results"]) == 1
    events = _ledger_events(paths.calls_jsonl)
    assert events[0]["event"] == "START"
    assert events[1]["event"] == "ERROR"
    assert paths.raw_json.exists()
    assert paths.result_json.exists()
    assert len(multiprocessing.active_children()) == active_before


def test_no_live_child_after_spawn_return(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    active_before = len(multiprocessing.active_children())
    job = {
        "case_id": "legacy_blocking",
        "attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "use_fake_transport": True,
        "fake_responses": [asdict(sample_offline_fake_responses()[2])],
    }
    _, cleanup = spawn_isolated_case(job, wall_timeout_seconds=10)
    assert cleanup
    assert len(multiprocessing.active_children()) == active_before


def test_partial_artifacts_durable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    fake = list(sample_offline_fake_responses())
    fake[0] = FakeProviderResponse(
        model=MODEL_SNAPSHOT,
        content="",
        raise_error=RuntimeError("boom"),
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifact_root=paths,
        use_fake_transport=True,
        fake_responses=fake,
    )
    raw = json.loads(paths.raw_json.read_text(encoding="utf-8"))
    assert raw["consumed_call_count"] >= 1
    assert paths.result_json.exists()


def test_artifacts_no_prompt_corpus_api_key_pii(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    for path in (paths.raw_json, paths.result_json, paths.calls_jsonl, paths.attempt_json):
        blob = path.read_text(encoding="utf-8")
        assert "APPROVED_MD_CORPUS" not in blob
        assert "=== SYSTEM_POLICY ===" not in blob
        assert "clients/demo/md/" not in blob
        assert "sk-test" not in blob
        assert SINGAPORE_ENDPOINT not in blob


def test_max_calls_six(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    result = run_live_attempt(
        PROPOSED_LIVE_ATTEMPT_ID,
        artifacts_root=tmp_path,
        use_fake_transport=True,
    )
    assert result["consumed_call_count"] == 6
    assert len(result["case_results"]) == 6
    assert tuple(row["case_id"] for row in result["case_results"]) == frozen_case_ids()


def test_existing_marker_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_live_gate(monkeypatch)
    _patch_endpoint(monkeypatch)
    paths = artifact_paths_for_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifacts_root=tmp_path)
    paths.attempt_json.parent.mkdir(parents=True, exist_ok=True)
    paths.attempt_json.write_text("{}", encoding="utf-8")
    with pytest.raises(Exception, match="ATTEMPT_MARKER_EXISTS"):
        run_live_attempt(PROPOSED_LIVE_ATTEMPT_ID, artifact_root=paths, use_fake_transport=True)


def test_cli_gate_none_exit() -> None:
    assert live_cli_main(["--attempt-id", PROPOSED_LIVE_ATTEMPT_ID]) == 3


def test_production_does_not_import_eval_runner() -> None:
    repo = Path(__file__).resolve().parents[1]
    production_paths = [
        repo / "llm.py",
        repo / "app.py",
        repo / "core" / "sales_fast_widget_runtime.py",
    ]
    forbidden = (
        "one_call_flash_capability_live_runner",
        "run_one_call_flash_capability_live",
    )
    for path in production_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text


def test_frozen_plan_sha256_stable() -> None:
    first = frozen_capability_plan_sha256()
    second = frozen_capability_plan_sha256()
    assert first == second
    assert len(first) == 64


def test_capability_conclusions_flags() -> None:
    from evals.v5.one_call_flash_capability_live_artifacts import CapabilityLiveCaseRecord

    records = [
        CapabilityLiveCaseRecord(
            case_id=case.case_id,
            outcome="supported",
            requested_model=MODEL_SNAPSHOT,
            observed_model=MODEL_SNAPSHOT,
            provider_model_verified=True,
            stream=case.stream,
            response_format_strategy=case.response_format_strategy,
            prompt_tokens=1,
            completion_tokens=1,
            cached_tokens=128 if case.case_id == "cache_repeat" else 0,
            transport_attempts=1,
            ttft_ms=1,
            total_ms=1,
            first_delta_excerpt="x",
            response_excerpt="y",
            error_code=None,
            ledger_event="FINISH",
        )
        for case in FROZEN_CAPABILITY_CASES
    ]
    conclusions = build_capability_conclusions(
        records,
        child_cleanup_verified_all_executed_cases=True,
        wall_timeout_occurred=False,
        max_retries_zero_configured=True,
    )
    assert conclusions["json_mode_blocking_supported"]
    assert conclusions["provider_cache_hit_observed"]
    assert conclusions["no_retry_verified"]
    assert conclusions["child_cleanup_verified_all_executed_cases"]
    assert conclusions["wall_timeout_occurred"] is False
    assert "wall_timeout_cleanup_verified" not in conclusions


def test_stage3a_offline_capability_plan_still_passes() -> None:
    transport = FakeProviderTransport(responses=sample_offline_fake_responses())
    from evals.v5.one_call_flash_capability_harness import run_offline_capability_plan

    summary = run_offline_capability_plan(transport)
    assert summary["provider_calls"] == MAX_CALLS
    assert summary["offline_json_mode_validator_passed"]
