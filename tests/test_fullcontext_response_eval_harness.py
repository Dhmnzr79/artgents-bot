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
    AUTOMATED_ACCEPTANCE_THRESHOLDS,
    CASE_SPECIFIC_RUBRIC_IDS,
    FROZEN_MATRIX_HASH,
    GLOBAL_RUBRIC_IDS,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LiveArtifactExistsError,
    assert_live_artifacts_absent,
    evaluate_automated_verdict,
    evaluate_final_verdict,
    load_frozen_matrix,
    validate_manual_review_record,
)
from evals.v5.run_fullcontext_response_eval import (
    forbidden_claim_violations,
    provider_call_violation,
    run_case,
    run_harness_with_backend_factory,
    summarize_results,
    write_json_exclusive,
)


def _case(case_id: str) -> dict[str, object]:
    spec = load_frozen_matrix()
    return next(item for item in spec["cases"] if item["case_id"] == case_id)


def _clean_automated_summary() -> dict[str, object]:
    return {
        "outcome_match_rate": 1.0,
        "materialize_verified_rate": 1.0,
        "terminal_behavior_rate": 1.0,
        "provider_call_violation_count": 0,
        "forbidden_claim_violation_count": 0,
        "pipeline_error_count": 0,
        "transport_error_count": 0,
        "malformed_response_count": 0,
        "dangerous_medical_violation_count": 0,
        "ungrounded_strict_commercial_count": 0,
        "missing_base_external_knowledge_count": 0,
        "unexpected_terminal_count": 0,
        "wrong_price_doctor_count": 0,
    }


def _manual_review_record(
    *,
    pass_all: bool = True,
    matrix_hash: str = FROZEN_MATRIX_HASH,
    result_sha256: str = "abc123",
    critical_case_id: str | None = None,
    omit_case_id: str | None = None,
    duplicate_case_id: str | None = None,
) -> dict[str, object]:
    spec = load_frozen_matrix()
    cases = []
    for matrix_case in spec["cases"]:
        if omit_case_id and matrix_case["case_id"] == omit_case_id:
            continue
        if matrix_case["expected_outcome"] == "terminal_boundary_uncertain":
            cases.append(
                {
                    "case_id": matrix_case["case_id"],
                    "review_status": "not_applicable",
                    "global_checks": {},
                    "case_specific_checks": {},
                    "critical_violation": False,
                    "notes": "",
                }
            )
            continue
        profile = matrix_case["case_specific_rubric_profile"]
        cases.append(
            {
                "case_id": matrix_case["case_id"],
                "review_status": "reviewed",
                "global_checks": {rubric_id: pass_all for rubric_id in GLOBAL_RUBRIC_IDS},
                "case_specific_checks": {
                    rubric_id: pass_all
                    for rubric_id in (
                        CASE_SPECIFIC_RUBRIC_IDS[profile] if profile is not None else ()
                    )
                },
                "critical_violation": matrix_case["case_id"] == critical_case_id,
                "notes": "",
            }
        )
    if duplicate_case_id is not None:
        duplicate = next(row for row in cases if row["case_id"] == duplicate_case_id)
        cases.append(dict(duplicate))
    return {
        "measurement_id": "s47_fullcontext_response_live_eval",
        "matrix_git_blob_hash": matrix_hash,
        "result_sha256": result_sha256,
        "reviewer": "checker",
        "reviewed_at": "2026-07-22T12:00:00Z",
        "cases": cases,
    }


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
    assert payload["summary"]["automated_verdict"]["verdict"] == "AUTOMATED_PASS"
    assert payload["summary"]["final_verdict"]["verdict"] == "PENDING_MANUAL_REVIEW"


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


def test_automated_pass_without_manual_is_pending_not_pass() -> None:
    summary = _clean_automated_summary()
    automated = evaluate_automated_verdict(summary)
    assert automated["verdict"] == "AUTOMATED_PASS"
    final = evaluate_final_verdict(summary, None, matrix_spec=load_frozen_matrix())
    assert final["verdict"] == "PENDING_MANUAL_REVIEW"


def test_incomplete_manual_review_is_pending() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(omit_case_id="fc_info_01")
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "PENDING_MANUAL_REVIEW"


def test_complete_good_manual_review_is_pass() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record()
    validate_manual_review_record(
        record,
        matrix_hash=FROZEN_MATRIX_HASH,
        result_sha256="abc123",
        matrix_spec=load_frozen_matrix(),
    )
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "PASS"


def test_manual_quality_below_threshold_is_fail() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(pass_all=False)
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "FAIL"


def test_critical_manual_violation_is_fail() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(critical_case_id="fc_medical_01")
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "FAIL"


def test_wrong_matrix_hash_is_fail_closed() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(matrix_hash="deadbeef")
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "PENDING_MANUAL_REVIEW"


def test_wrong_result_hash_is_fail_closed() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(result_sha256="wrong")
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "PENDING_MANUAL_REVIEW"


def test_duplicate_manual_reviews_are_fail_closed() -> None:
    summary = _clean_automated_summary()
    record = _manual_review_record(duplicate_case_id="fc_info_01")
    final = evaluate_final_verdict(
        summary,
        record,
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "PENDING_MANUAL_REVIEW"


def test_automated_medical_violation_is_fail() -> None:
    summary = _clean_automated_summary()
    summary["dangerous_medical_violation_count"] = 1
    final = evaluate_final_verdict(
        summary,
        _manual_review_record(),
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "FAIL"


def test_automated_commercial_violation_is_fail() -> None:
    summary = _clean_automated_summary()
    summary["ungrounded_strict_commercial_count"] = 1
    final = evaluate_final_verdict(
        summary,
        _manual_review_record(),
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "FAIL"


def test_automated_missing_base_violation_is_fail() -> None:
    summary = _clean_automated_summary()
    summary["missing_base_external_knowledge_count"] = 1
    final = evaluate_final_verdict(
        summary,
        _manual_review_record(),
        matrix_spec=load_frozen_matrix(),
        result_sha256="abc123",
    )
    assert final["verdict"] == "FAIL"


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
    assert "model_recommendation" in captured.out or "qwen3.7-plus" in captured.out


def test_assert_live_artifacts_absent_blocks_existing(tmp_path, monkeypatch) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(LiveArtifactExistsError):
        assert_live_artifacts_absent((raw,))

    if LIVE_RAW_ARTIFACT_PATH.exists() or LIVE_RESULT_ARTIFACT_PATH.exists():
        pytest.skip("live artifacts present in repo workspace")


def test_write_json_exclusive_blocks_overwrite(tmp_path) -> None:
    target = tmp_path / "result.json"
    write_json_exclusive(target, {"ok": True})
    with pytest.raises(Exception, match="already exists"):
        write_json_exclusive(target, {"ok": False})
