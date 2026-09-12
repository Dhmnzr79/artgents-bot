"""Offline tests for architecture comparison LIVE preparation (CP-ARCH-COMPARE-LIVE-PREP-V1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from evals.v5.arch_compare.arch_compare_configs import (
    FLASH_PROVIDER_MODEL_ID,
    PLUS_PROVIDER_MODEL_ID,
    config_by_id,
)
from evals.v5.arch_compare.arch_compare_contract import (
    BLIND_VARIANTS,
    CONFIG_IDS,
    EXPECTED_SCENARIO_CONFIG_RESULTS,
    EXPECTED_TURN_CONFIG_RESULTS,
    FAKE_PATIENT_TEXT_PREFIX,
    matrix_digest_sha256,
)
from evals.v5.arch_compare.arch_compare_fake_transport import (
    ArchCompareFakeTransport,
    build_fake_envelope_json,
)
from evals.v5.arch_compare.arch_compare_harness import build_blind_variant_mapping
from evals.v5.arch_compare.arch_compare_live_boundary import (
    capture_code_only_boundary,
    capture_provider_turn_boundary,
    drain_fake_streaming_boundary,
)
from evals.v5.arch_compare.arch_compare_live_capture import fake_live_patient_text
from evals.v5.arch_compare.arch_compare_live_contract import (
    FAKE_LIVE_DISCLAIMER,
    TOTAL_AUTHORIZED_PROVIDER_BUDGET,
    build_config_registry_document,
    evaluate_live_readiness,
    frozen_config_digest,
)
from evals.v5.arch_compare.arch_compare_live_guard import (
    ArchCompareLiveGuardError,
    assert_fake_mode_allowed,
    assert_live_authorized,
    assert_provider_budget,
    assert_seventy_first_call_blocked,
    assert_single_provider_call_per_turn,
    authorization_manifest_from_dict,
    budget_plan_summary,
    build_guard_context,
)
from evals.v5.arch_compare.arch_compare_live_hooks import (
    active_eval_hook_names,
    eval_hook_scope,
    install_eval_hook,
    restore_eval_hooks,
)
from evals.v5.arch_compare.arch_compare_live_preflight import (
    ArchComparePreflightBudgetError,
    ArchComparePreflightStateMachine,
    assert_authorization_manifest_budget,
    assert_cache_probe_separate_budget,
    run_mock_capability_preflight,
)
from evals.v5.arch_compare.arch_compare_live_report import (
    assert_blind_review_secrecy,
    build_blind_review_markdown,
    persist_live_prep_artifacts,
)
from evals.v5.arch_compare.arch_compare_live_runner import (
    build_call_budget_plan,
    run_arch_compare_fake_full_path,
)
from evals.v5.arch_compare.arch_compare_live_schedule import (
    build_execution_schedule,
    config_position_balance,
    rotated_config_order,
    scenario_for_id,
    session_id_for,
    turn_for_job,
)
from evals.v5.arch_compare.arch_compare_matrix import parse_scenario_specs
from evals.v5.arch_compare.arch_compare_provider_payload import (
    assert_context_payload_parity,
    assert_flash_plus_payload_parity,
    build_composer_provider_payload,
)
from evals.v5.arch_compare.run_arch_compare_live import main as run_arch_compare_live_main

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _guard_context(tmp_path: Path, *, attempt_id: str = "prep_test_v1", live: bool = False):
    return build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id=attempt_id,
        live_requested=live,
        authorization=None,
        artifact_dir=tmp_path / attempt_id,
        transport_kind="fake",
        head_sha=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True
        ).strip(),
        working_tree_clean=False,
    )


def _authorized_manifest(*, attempt_id: str, max_calls: int, includes_preflight: bool = True) -> dict:
    from evals.v5.arch_compare.arch_compare_matrix import frozen_matrix_digest

    return {
        "attempt_id": attempt_id,
        "expected_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True
        ).strip(),
        "matrix_digest": frozen_matrix_digest(),
        "config_digest": frozen_config_digest(),
        "allowed_model_ids": [FLASH_PROVIDER_MODEL_ID, PLUS_PROVIDER_MODEL_ID],
        "max_provider_calls": max_calls,
        "client_id": "demo",
        "issued_for_measurement": "one_call_arch_compare_live_v1",
        "explicit_live": True,
        "includes_capability_preflight": includes_preflight,
    }


def test_schedule_contains_all_jobs() -> None:
    schedule = build_execution_schedule(attempt_id="sched_v1")
    assert len(schedule.scenario_config_jobs) == EXPECTED_SCENARIO_CONFIG_RESULTS
    assert len(schedule.turn_config_jobs) == EXPECTED_TURN_CONFIG_RESULTS


def test_config_order_balanced_and_reproducible() -> None:
    first = build_execution_schedule(attempt_id="seed_a")
    second = build_execution_schedule(attempt_id="seed_a")
    assert first.config_order_by_scenario == second.config_order_by_scenario
    assert rotated_config_order(scenario_index=0) == CONFIG_IDS
    assert rotated_config_order(scenario_index=1) == CONFIG_IDS[1:] + CONFIG_IDS[:1]
    balance = config_position_balance(first)
    for config_id in CONFIG_IDS:
        positions = balance[config_id]
        assert positions[0] == positions[1] == positions[2] == positions[3] == 4


def test_pinned_model_ids_in_config_registry() -> None:
    registry = build_config_registry_document()
    assert registry["flash_provider_model_id"] == "qwen3.7-flash-2026-07-15"
    assert registry["plus_provider_model_id"] == "qwen3.7-plus-2026-05-26"
    assert registry["enable_thinking"] is False
    for row in registry["configs"]:
        assert row["provider_model_id_status"] == "resolved"
        assert "2026-" in row["provider_model_id"]


def test_outbound_payload_parity_flash_plus() -> None:
    flash = config_by_id("flash_full")
    plus = config_by_id("plus_full")
    messages = ({"role": "user", "content": "test"},)
    assert_flash_plus_payload_parity(flash_config=flash, plus_config=plus, messages=messages)
    flash_payload = build_composer_provider_payload(config=flash, messages=messages, stream=False)
    plus_payload = build_composer_provider_payload(config=plus, messages=messages, stream=False)
    assert flash_payload["model"] == FLASH_PROVIDER_MODEL_ID
    assert plus_payload["model"] == PLUS_PROVIDER_MODEL_ID
    assert flash_payload["extra_body"]["enable_thinking"] is False
    assert plus_payload["extra_body"]["enable_thinking"] is False


def test_outbound_payload_parity_full_vs_curated() -> None:
    full = config_by_id("flash_full")
    curated = config_by_id("flash_curated")
    full_messages = ({"role": "user", "content": "full context"},)
    curated_messages = ({"role": "user", "content": "curated context"},)
    assert_context_payload_parity(
        full_config=full,
        curated_config=curated,
        full_messages=full_messages,
        curated_messages=curated_messages,
    )


def test_model_id_in_raw_artifacts_not_blind_review(tmp_path: Path) -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="model_id_v1",
        guard_context=_guard_context(tmp_path),
    )
    raw = result["raw_turns"][0]
    assert raw["provider_model_id"] in {FLASH_PROVIDER_MODEL_ID, PLUS_PROVIDER_MODEL_ID}
    markdown = build_blind_review_markdown(attempt_id="model_id_v1", run_result=result)
    assert_blind_review_secrecy(markdown)
    assert "qwen3.7" not in markdown


def test_multi_turn_session_isolation() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="session_iso_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    sw_rows = [
        row
        for row in result["structured_turns"]
        if row["scenario_id"] == "SW-01" and row["config_id"] == "flash_full"
    ]
    t2 = next(row for row in sw_rows if row["turn_id"] == "SW-01_t2")
    assert "SW-01_t1" in t2["dialog_history_before"]
    assert "flash_curated" not in t2["session_id"]


def test_config_isolation_markers() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="cfg_iso_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    markers = {
        (row["scenario_id"], row["turn_id"], row["config_id"]): row["patient_text"]
        for row in result["structured_turns"]
        if row["provider_turn"]
    }
    for key, text in markers.items():
        scenario_id, turn_id, config_id = key
        assert text == fake_live_patient_text(
            attempt_id="cfg_iso_v1",
            scenario_id=scenario_id,
            turn_id=turn_id,
            config_id=config_id,
        )
        assert config_id in text
        assert FAKE_PATIENT_TEXT_PREFIX in text


def test_no_retry_single_provider_call_per_turn_guard() -> None:
    with pytest.raises(ArchCompareLiveGuardError):
        assert_single_provider_call_per_turn(turn_calls=2)


def test_call_budget_calculation() -> None:
    schedule = build_execution_schedule(attempt_id="budget_v1")
    plan = build_call_budget_plan(schedule)
    assert plan.turn_config_jobs == EXPECTED_TURN_CONFIG_RESULTS
    assert plan.scenario_config_jobs == EXPECTED_SCENARIO_CONFIG_RESULTS
    assert plan.provider_turn_jobs == 17 * 4
    assert plan.code_only_turn_jobs == 2 * 4
    assert plan.capability_preflight_budget == 2
    assert plan.measurement_budget == 68
    assert plan.total_authorized_budget == 70
    assert plan.max_provider_calls == 70
    summary = budget_plan_summary()
    assert summary["total_authorized_budget"] == 70


def test_default_deny_live_guard() -> None:
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        assert_fake_mode_allowed(live_requested=True)
    assert exc.value.code == "live_requires_authorization"


def test_live_guard_failures(tmp_path: Path) -> None:
    manifest = {
        "attempt_id": "x",
        "expected_head": "0" * 40,
        "matrix_digest": "bad",
        "config_digest": "bad",
        "allowed_model_ids": ["m"],
        "max_provider_calls": 1,
        "client_id": "demo",
        "issued_for_measurement": "one_call_arch_compare_live_v1",
        "explicit_live": True,
    }
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="x",
        live_requested=True,
        authorization=authorization_manifest_from_dict(manifest),
        artifact_dir=tmp_path,
        transport_kind="fake",
        head_sha="1" * 40,
        working_tree_clean=False,
        chat_api_key="offline-test-placeholder",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError):
        assert_live_authorized(ctx)


def test_ready_for_authorized_preflight_status() -> None:
    readiness = evaluate_live_readiness(max_provider_calls=TOTAL_AUTHORIZED_PROVIDER_BUDGET)
    assert readiness.status == "READY_FOR_AUTHORIZED_PREFLIGHT"
    assert readiness.plus_provider_model_id_status == "resolved"
    assert readiness.enable_thinking is False


def test_manifest_budget_guards() -> None:
    with pytest.raises(RuntimeError):
        assert_authorization_manifest_budget(max_provider_calls=68, includes_preflight=True)
    assert_authorization_manifest_budget(max_provider_calls=70, includes_preflight=True)
    with pytest.raises(ArchCompareLiveGuardError):
        assert_seventy_first_call_blocked(call_index=71)
    with pytest.raises(RuntimeError):
        assert_cache_probe_separate_budget(cache_probe_calls=4, measurement_remaining=2)


def test_preflight_state_machine_blocks_measurement_on_failure() -> None:
    state = ArchComparePreflightStateMachine()
    state.flash_result = type("R", (), {"success": False})()
    with pytest.raises(ArchComparePreflightBudgetError):
        state.reserve_measurement()


def test_mock_preflight_two_calls() -> None:
    transport = ArchCompareFakeTransport()
    state = ArchComparePreflightStateMachine()
    flash, plus = run_mock_capability_preflight(
        attempt_id="preflight_v1",
        transport=transport,
        state=state,
    )
    assert flash.success
    assert plus is not None and plus.success
    assert state.preflight_consumed == 2
    assert state.can_start_measurement()


def test_fake_transport_cannot_be_canonical_live_artifact(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="fake_live",
        live_requested=True,
        authorization=authorization_manifest_from_dict(
            _authorized_manifest(attempt_id="fake_live", max_calls=70)
        ),
        artifact_dir=tmp_path / "fake_live",
        transport_kind="fake",
        working_tree_clean=True,
        chat_api_key="sk-real-looking-but-test",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        assert_live_authorized(ctx)
    assert exc.value.code == "fake_transport_in_live"


def test_manifest_68_rejected_for_preflight_plus_measurement(tmp_path: Path) -> None:
    ctx = build_guard_context(
        repo_root=_REPO_ROOT,
        attempt_id="budget68",
        live_requested=True,
        authorization=authorization_manifest_from_dict(
            _authorized_manifest(attempt_id="budget68", max_calls=68, includes_preflight=True)
        ),
        artifact_dir=tmp_path,
        transport_kind="live",
        working_tree_clean=True,
        chat_api_key="sk-real-looking-but-test",
        chat_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    with pytest.raises(ArchCompareLiveGuardError) as exc:
        assert_live_authorized(ctx)
    assert exc.value.code == "authorization_budget_invalid"


def test_full_structured_capture_without_regex() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="capture_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    prc = next(
        row
        for row in result["structured_turns"]
        if row["scenario_id"] == "PRC-01" and row["config_id"] == "flash_full"
    )
    assert prc["visible_answer"]
    assert prc["patient_text"]
    assert prc["stable_prefix_hash"]
    assert len(prc["selected_offer_ids"]) >= 1
    assert prc["presentation_capture_status"] == "full"


def test_terminal_boundary_capture_prc03() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="terminal_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    prc03 = next(
        row
        for row in result["structured_turns"]
        if row["scenario_id"] == "PRC-03" and row["config_id"] == "flash_full"
    )
    assert prc03["presentation_capture_status"] == "terminal_boundary_full"
    assert prc03["visible_answer"]
    assert prc03["degraded_flags"] == ()
    assert "terminal_bound_package" not in prc03["degraded_flags"]


def test_code_only_boundary_capture() -> None:
    schedule = build_execution_schedule(attempt_id="code_only_v1")
    for job in schedule.turn_config_jobs:
        if job.provider_turn:
            continue
        turn = turn_for_job(job)
        boundary = capture_code_only_boundary(turn=turn, session_id=job.session_id)
        assert boundary.presentation_capture_status == "code_only_boundary_full"
        assert boundary.visible_answer
        if turn.expected_route_class == "ADMIN":
            assert "администратор" in boundary.visible_answer.casefold()
        if turn.expected_route_class == "LOCAL":
            assert "+7" in boundary.visible_answer


def test_visible_answer_available_on_fake_path() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="visible_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    assert all(row["visible_answer"] for row in result["structured_turns"])
    assert all(row["presentation_capture_status"] for row in result["structured_turns"])


def test_blocking_streaming_boundary_parity() -> None:
    transport = ArchCompareFakeTransport()
    envelope = build_fake_envelope_json(scenario_id="PRC-01", turn_id="PRC-01_t1")
    transport.prepare_turn_envelopes((envelope,))
    blocking = transport.chat_completions_create(model=FLASH_PROVIDER_MODEL_ID, stream=False, messages=[])
    transport.prepare_turn_envelopes((envelope,))
    streaming = drain_fake_streaming_boundary(
        transport=transport,
        model=FLASH_PROVIDER_MODEL_ID,
        messages=[],
    )
    assert blocking.choices[0].message.content == streaming


def test_blind_mapping_hidden_and_reproducible() -> None:
    scenario_ids = tuple(row.scenario_id for row in parse_scenario_specs())
    first = build_blind_variant_mapping(attempt_id="blind_seed", scenario_ids=scenario_ids)
    second = build_blind_variant_mapping(attempt_id="blind_seed", scenario_ids=scenario_ids)
    assert first == second
    assert first != build_blind_variant_mapping(attempt_id="other_seed", scenario_ids=scenario_ids)


def test_blind_mapping_changes_between_scenarios() -> None:
    scenario_ids = tuple(row.scenario_id for row in parse_scenario_specs())
    mapping = build_blind_variant_mapping(attempt_id="vary_seed", scenario_ids=scenario_ids)
    first = mapping[scenario_ids[0]]["A"]
    different_found = any(mapping[sid]["A"] != first for sid in scenario_ids[1:])
    assert different_found or len(scenario_ids) == 1


def test_review_pack_hides_config_model_context() -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="review_v1",
        guard_context=_guard_context(Path("/unused")),
    )
    markdown = build_blind_review_markdown(attempt_id="review_v1", run_result=result)
    assert FAKE_LIVE_DISCLAIMER in markdown
    assert "НЕ ДЛЯ ОЦЕНКИ КАЧЕСТВА МОДЕЛИ" in markdown
    for token in ("flash_full", "plus_curated", "context_mode", "provider_model_id", "presentation_capture_status"):
        assert token not in markdown
    for variant in BLIND_VARIANTS:
        assert f"Вариант {variant}" in markdown


def test_technical_report_contains_configuration(tmp_path: Path) -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="tech_v1",
        guard_context=_guard_context(tmp_path),
    )
    paths = persist_live_prep_artifacts(
        artifacts_root=tmp_path,
        attempt_id="tech_v1",
        run_result=result,
    )
    technical = paths["technical_report_md"].read_text(encoding="utf-8")
    assert '"config_ids"' in technical
    assert build_config_registry_document()["config_ids"]
    assert "qwen3.7-plus-2026-05-26" in technical


def test_no_secrets_in_artifacts(tmp_path: Path) -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="secrets_v1",
        guard_context=_guard_context(tmp_path),
    )
    paths = persist_live_prep_artifacts(
        artifacts_root=tmp_path,
        attempt_id="secrets_v1",
        run_result=result,
        stdout_log="mode=fake\n",
    )
    for path in paths.values():
        if path.suffix in {".json", ".md", ".log"}:
            text = path.read_text(encoding="utf-8")
            assert "OPENAI_API_KEY=" not in text
            assert "Authorization: Bearer" not in text


def test_fake_full_run_zero_provider_calls(tmp_path: Path) -> None:
    result = run_arch_compare_fake_full_path(
        attempt_id="zero_calls_v1",
        guard_context=_guard_context(tmp_path),
    )
    assert result["provider_call_total"] == 0
    assert result["fake_transport_call_total"] == 70
    assert result["preflight"]["flash"]["success"] is True
    assert result["live_readiness"]["status"] == "READY_FOR_AUTHORIZED_PREFLIGHT"
    assert len(result["structured_turns"]) == EXPECTED_TURN_CONFIG_RESULTS


def test_hooks_restore_after_exception() -> None:
    restore_eval_hooks()

    def boom() -> None:
        raise RuntimeError("hook boom")

    with pytest.raises(RuntimeError):
        with eval_hook_scope({"boom_hook": boom}):
            assert "boom_hook" in active_eval_hook_names()
            boom()
    assert active_eval_hook_names() == ()

    install_eval_hook("temp", lambda: None)
    restore_eval_hooks()
    assert active_eval_hook_names() == ()


def test_stage53_not_imported_from_live_prep_modules() -> None:
    import evals.v5.arch_compare.arch_compare_live_runner as runner
    import evals.v5.arch_compare.arch_compare_live_schedule as schedule

    assert "stage53" not in runner.__file__
    assert "stage53" not in schedule.__file__
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "stage53" not in source


def test_product_runtime_diff_absent() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "core", "config.py", "contracts", "clients", "orchestration"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip() == ""


def test_cli_default_is_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(_REPO_ROOT))
    code = run_arch_compare_live_main(
        [
            "--attempt-id",
            "cli_fake_v1",
            "--artifacts-root",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert (tmp_path / "cli_fake_v1" / "manifest.json").is_file()


def test_cli_live_without_authorization_rejected() -> None:
    code = run_arch_compare_live_main(["--attempt-id", "cli_live_v1", "--live"])
    assert code == 2


def test_provider_budget_guard() -> None:
    with pytest.raises(ArchCompareLiveGuardError):
        assert_provider_budget(consumed=2, max_calls=1)


def test_session_id_unique_per_config() -> None:
    a = session_id_for(attempt_id="a1", scenario_id="PRC-01", config_id="flash_full")
    b = session_id_for(attempt_id="a1", scenario_id="PRC-01", config_id="flash_curated")
    assert a != b


def test_matrix_digest_helper_import_from_contract() -> None:
    from evals.v5.arch_compare.arch_compare_contract import matrix_digest_sha256 as contract_digest

    sample = b'{"a":1}\n'
    assert contract_digest(sample) == matrix_digest_sha256(sample)


def test_provider_boundary_not_equal_patient_text_for_materialized() -> None:
    schedule = build_execution_schedule(attempt_id="boundary_v1")
    job = next(
        row
        for row in schedule.turn_config_jobs
        if row.scenario_id == "PRC-01" and row.turn_id == "PRC-01_t1" and row.config_id == "flash_full"
    )
    scenario = scenario_for_id(job.scenario_id)
    turn = turn_for_job(job)
    patient_text = fake_live_patient_text(
        attempt_id="boundary_v1",
        scenario_id=job.scenario_id,
        turn_id=job.turn_id,
        config_id=job.config_id,
    )
    envelope = build_fake_envelope_json(
        scenario_id=job.scenario_id,
        turn_id=job.turn_id,
        patient_text=patient_text,
        service_id=turn.expected_service_id,
        commercial_intent=turn.commercial_intent,
        promotion_scope=turn.promotion_scope,
    )
    boundary = capture_provider_turn_boundary(
        envelope_json=envelope,
        scenario=scenario,
        turn=turn,
        patient_text=patient_text,
        session_id=job.session_id,
    )
    assert boundary.presentation_capture_status == "full"
    assert boundary.visible_answer != patient_text
