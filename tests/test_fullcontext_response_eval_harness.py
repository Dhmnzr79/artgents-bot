from __future__ import annotations

from pathlib import Path

import pytest

from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalLiveNotConfiguredError,
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
    FullContextResponseEvalTransportError,
)
from evals.v5.fullcontext_response_eval_contract import (
    ACCEPTANCE_THRESHOLDS,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LiveArtifactExistsError,
    assert_live_artifacts_absent,
    evaluate_threshold_verdict,
)
from evals.v5.run_fullcontext_response_eval import (
    forbidden_claim_violations,
    provider_call_violation,
    run_case,
    run_harness_with_backend_factory,
    summarize_results,
)
from evals.v5.fullcontext_response_eval_contract import load_frozen_matrix


def _case(case_id: str) -> dict[str, object]:
    spec = load_frozen_matrix()
    return next(item for item in spec["cases"] if item["case_id"] == case_id)


def test_provider_call_violation_rules() -> None:
    assert provider_call_violation(
        expected_outcome="terminal_boundary_uncertain",
        composer_calls=0,
        semantic_calls=0,
    ) is False
    assert provider_call_violation(
        expected_outcome="terminal_boundary_uncertain",
        composer_calls=1,
        semantic_calls=0,
    ) is True
    assert provider_call_violation(
        expected_outcome="materialize_verified",
        composer_calls=1,
        semantic_calls=1,
    ) is False


def test_forbidden_claim_violations_are_case_insensitive() -> None:
    assert forbidden_claim_violations("Вам можно имплант", ["вам можно"]) == ["вам можно"]


def test_terminal_case_has_zero_provider_calls() -> None:
    spec = load_frozen_matrix()
    from evals.v5.run_fullcontext_response_eval import _load_pipeline_context

    context = _load_pipeline_context(spec)
    case = _case("fc_terminal_01")
    composer = FullContextResponseEvalRecordingComposerBackend("unused")
    semantic = FullContextResponseEvalRecordingSemanticBackend()
    row = run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert row["observed_outcome"] == "terminal_boundary_uncertain"
    assert row["composer_call_count"] == 0
    assert row["semantic_call_count"] == 0
    assert row["provider_call_violation"] is False


def test_pain_case_materializes_with_one_composer_and_verifier() -> None:
    spec = load_frozen_matrix()
    from evals.v5.run_fullcontext_response_eval import _load_pipeline_context

    context = _load_pipeline_context(spec)
    case = _case("fc_pain_01")
    composer = FullContextResponseEvalRecordingComposerBackend(str(case["offline_composer_stub"]))
    semantic = FullContextResponseEvalRecordingSemanticBackend()
    row = run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert row["observed_outcome"] == "materialize_verified"
    assert row["observed_response_mode"] == "medical_handoff"
    assert row["composer_call_count"] == 1
    assert row["semantic_call_count"] == 1
    assert row["verification_status"] == "verified"


def test_price_case_verifies_structured_amount() -> None:
    spec = load_frozen_matrix()
    from evals.v5.run_fullcontext_response_eval import _load_pipeline_context

    context = _load_pipeline_context(spec)
    case = _case("fc_price_01")
    composer = FullContextResponseEvalRecordingComposerBackend(str(case["offline_composer_stub"]))
    semantic = FullContextResponseEvalRecordingSemanticBackend()
    row = run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert row["status"] == "OK"
    assert "318" in (row["response_text"] or "")


def test_offline_harness_runs_all_cases_without_live() -> None:
    def factory(case: dict[str, object]) -> tuple[
        FullContextResponseEvalRecordingComposerBackend,
        FullContextResponseEvalRecordingSemanticBackend,
    ]:
        return (
            FullContextResponseEvalRecordingComposerBackend(str(case["offline_composer_stub"])),
            FullContextResponseEvalRecordingSemanticBackend(),
        )

    payload = run_harness_with_backend_factory(backend_factory=factory)
    assert payload["summary"]["total_cases"] == 20
    assert payload["summary"]["pipeline_error_count"] == 0
    assert payload["summary"]["provider_call_violation_count"] == 0


def test_composer_recording_backend_forbids_retry() -> None:
    backend = FullContextResponseEvalRecordingComposerBackend("text")
    from core.target_composer_executor import TargetComposerInvocation

    invocation = TargetComposerInvocation(
        system_policy="p",
        cached_full_context="c",
        response_directives_json="{}",
        primary_evidence_json="[]",
        user_message="m",
    )
    backend.generate(invocation)
    with pytest.raises(FullContextResponseEvalTransportError):
        backend.generate(invocation)


def test_live_not_configured_adapter_raises() -> None:
    from evals.v5.fullcontext_response_eval_backend import FullContextResponseEvalComposerAdapter
    from core.target_composer_executor import TargetComposerInvocation

    adapter = FullContextResponseEvalComposerAdapter(delegate=None)
    invocation = TargetComposerInvocation(
        system_policy="p",
        cached_full_context="c",
        response_directives_json="{}",
        primary_evidence_json="[]",
        user_message="m",
    )
    with pytest.raises(FullContextResponseEvalLiveNotConfiguredError):
        adapter.generate(invocation)


def test_threshold_verdict_passes_clean_offline_summary() -> None:
    summary = {
        "outcome_match_rate": 1.0,
        "provider_call_violation_count": 0,
        "forbidden_claim_violation_count": 0,
        "pipeline_error_count": 0,
    }
    verdict = evaluate_threshold_verdict(summary)
    assert verdict["verdict"] == "PASS"


def test_cli_default_exits_live_not_configured(capsys) -> None:
    from evals.v5.run_fullcontext_response_eval import main

    code = main([])
    captured = capsys.readouterr()
    assert code == 3
    assert "LIVE_NOT_CONFIGURED" in captured.err


def test_cli_dry_run_exits_zero(capsys) -> None:
    from evals.v5.run_fullcontext_response_eval import main

    code = main(["--dry-run"])
    captured = capsys.readouterr()
    assert code == 0
    assert "total_cases" in captured.out


def test_assert_live_artifacts_absent_blocks_existing(tmp_path, monkeypatch) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(LiveArtifactExistsError):
        assert_live_artifacts_absent((raw,))

    if LIVE_RAW_ARTIFACT_PATH.exists() or LIVE_RESULT_ARTIFACT_PATH.exists():
        pytest.skip("live artifacts present in repo workspace")
