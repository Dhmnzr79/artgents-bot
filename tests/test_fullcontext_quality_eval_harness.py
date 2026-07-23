from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
)
from evals.v5.fullcontext_quality_eval_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    AttemptMarkerExistsError,
    EXPECTED_LLM_CALLS,
    LIVE_ATTEMPT_MARKER_PATH,
    evaluate_final_verdict,
    load_frozen_matrix,
    prepare_json_artifact_payload,
)
from evals.v5.fullcontext_response_eval_contract import LiveArtifactWriteError
from evals.v5.run_fullcontext_quality_eval import main as run_quality_eval_main
from evals.v5.run_fullcontext_quality_eval import prepare_live_run, run_offline_harness
from evals.v5.run_fullcontext_response_eval import (
    _load_pipeline_context,
    _offline_backend_factory,
    run_case,
    write_json_exclusive,
)
from tests.test_target_fullcontext_content_response import (
    FC_MISSING_01_TEXT,
    RuleBasedSemanticBackend,
)


class _CapturingSemanticAdapter:
    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.call_count = 0
        self.captures: list[object] = []

    def assess(self, invocation: object, /) -> object:
        self.call_count += 1
        result = self._inner.assess(invocation)  # type: ignore[attr-defined]
        self.captures.append(
            type("Capture", (), {"raw_backend_payload": result})()
        )
        return result


def _semantic_backend_for_case(case_id: str) -> object:
    if case_id == "s57_missing_01":
        return _CapturingSemanticAdapter(RuleBasedSemanticBackend(mode="fc_missing_01"))
    if case_id == "s57_medical_02":
        return _CapturingSemanticAdapter(RuleBasedSemanticBackend(mode="fc_medical_03"))
    return FullContextResponseEvalRecordingSemanticBackend()


def _run_single_case(
    case_id: str,
    *,
    composer_text: str | None = None,
) -> dict[str, object]:
    spec = load_frozen_matrix()
    context = _load_pipeline_context(spec)
    case = _case(case_id)
    text = composer_text if composer_text is not None else str(case["offline_composer_stub"])
    composer = FullContextResponseEvalRecordingComposerBackend(text)
    semantic = _semantic_backend_for_case(case_id)
    return run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,  # type: ignore[arg-type]
    )


def _case(case_id: str) -> dict[str, object]:
    spec = load_frozen_matrix()
    return next(item for item in spec["cases"] if item["case_id"] == case_id)


def test_consult_case_includes_free_implant_consult_in_primary_evidence() -> None:
    result = _run_single_case("s57_consult_01")
    assert result["observed_outcome"] == "materialize_verified"
    assert result["composer_call_count"] == 1
    spec = load_frozen_matrix()
    context = _load_pipeline_context(spec)
    case = _case("s57_consult_01")
    composer = FullContextResponseEvalRecordingComposerBackend(str(case["offline_composer_stub"]))
    semantic = FullContextResponseEvalRecordingSemanticBackend()
    run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )
    evidence = json.loads(composer.captures[0].invocation.primary_evidence_json)
    assert any(
        item.get("kind") == "commercial_fact" and item.get("ref") == "fact:free_implant_consult"
        for item in evidence
    )


def test_missing_base_rejects_cross_disease_transfer() -> None:
    row = _run_single_case("s57_missing_01", composer_text=FC_MISSING_01_TEXT)
    assert row["observed_outcome"] == "pipeline_error"
    assert row["pipeline_error_code"] == "TargetResponseVerificationError"
    assert row["reason"] == "target_verifier_semantic_rejected"


def test_known_diabetes_stays_verified() -> None:
    result = _run_single_case("s57_medical_01")
    assert result["verification_status"] == "verified"


def test_pregnancy_external_extension_rejected_by_fake_semantic() -> None:
    bad_text = (
        "Беременность указана среди противопоказаний в материалах клиники. "
        "В период лактации гормональный фон замедляет заживление."
    )
    row = _run_single_case("s57_medical_02", composer_text=bad_text)
    assert row["observed_outcome"] == "pipeline_error"
    assert row["pipeline_error_code"] == "TargetResponseVerificationError"
    assert row["reason"] == "target_verifier_semantic_rejected"


@pytest.mark.parametrize(
    "case_id",
    [
        "s57_pain_01",
        "s57_info_01",
        "s57_price_01",
        "s57_payment_01",
        "s57_doctor_01",
    ],
)
def test_control_cases_do_not_false_block(case_id: str) -> None:
    result = _run_single_case(case_id)
    assert result["verification_status"] == "verified"
    assert result["provider_call_violation"] is False


def test_wrong_price_is_rejected() -> None:
    spec = load_frozen_matrix()
    context = _load_pipeline_context(spec)
    case = _case("s57_price_01")
    composer = FullContextResponseEvalRecordingComposerBackend(
        "All-on-4 в клинике стоит от 999 999 рублей за одну челюсть."
    )
    semantic = FullContextResponseEvalRecordingSemanticBackend()
    row = run_case(
        case=case,
        index=0,
        spec=spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert row["observed_outcome"] == "pipeline_error"
    assert row["pipeline_error_code"] == "TargetResponseVerificationError"
    assert row["reason"] == "target_verifier_numeric_ungrounded"


def test_wrong_doctor_fact_is_rejected() -> None:
    row = _run_single_case(
        "s57_doctor_01",
        composer_text=(
            "Кузнецов Дмитрий Андреевич выполнил более 5000 имплантаций."
        ),
    )
    assert row["observed_outcome"] == "pipeline_error"
    assert row["pipeline_error_code"] == "TargetResponseVerificationError"
    assert row["reason"] == "target_verifier_numeric_ungrounded"


def test_wrong_clinic_fact_is_rejected() -> None:
    row = _run_single_case(
        "s57_info_01",
        composer_text=(
            "All-on-4 — протокол на четырёх имплантах. "
            "Приживаемость имплантов в клинике составляет 99.99%."
        ),
    )
    assert row["observed_outcome"] == "pipeline_error"
    assert row["pipeline_error_code"] == "TargetResponseVerificationError"
    assert row["reason"] == "target_verifier_numeric_ungrounded"


def test_one_cached_fullcontext_build_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.target_cached_full_context import TargetCachedFullContext, build_target_cached_full_context

    calls: list[Path] = []
    real = build_target_cached_full_context(Path("clients/demo/md"))

    def counted_build(md_root: Path) -> TargetCachedFullContext:
        calls.append(md_root)
        if len(calls) > 1:
            raise AssertionError("build_target_cached_full_context called more than once")
        return real

    monkeypatch.setattr(
        "evals.v5.run_fullcontext_response_eval.build_target_cached_full_context",
        counted_build,
    )
    spec = load_frozen_matrix()
    context = _load_pipeline_context(spec)
    assert len(calls) == 1
    for index, case in enumerate(spec["cases"][:2]):
        composer, semantic = _offline_backend_factory(case)
        run_case(
            case=case,
            index=index,
            spec=spec,
            context=context,
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert len(calls) == 1


def test_exactly_one_composer_and_one_verifier_per_case() -> None:
    result = run_offline_harness(backend_factory=_offline_backend_factory)
    for row in result["case_results"]:
        assert row["composer_call_count"] == 1
        assert row["semantic_call_count"] == 1
        assert row["provider_call_violation"] is False


def test_future_budget_is_nine_plus_nine() -> None:
    spec = load_frozen_matrix()
    assert spec["model_recommendation"]["expected_composer_calls"] == 9
    assert spec["model_recommendation"]["expected_verifier_calls"] == 9
    assert EXPECTED_LLM_CALLS == 18


def test_default_cli_is_live_not_configured() -> None:
    assert run_quality_eval_main([]) == 4


def test_live_flag_blocked_when_result_artifact_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "result.json"
    existing.write_text("{}\n", encoding="utf-8")
    marker = tmp_path / "attempt.json"
    from evals.v5.fullcontext_response_eval_contract import LiveArtifactExistsError

    with pytest.raises(LiveArtifactExistsError):
        prepare_live_run(
            attempt_marker_path=marker,
            artifact_paths=(existing,),
            baseline_commit="test",
        )


def test_existing_attempt_marker_blocks_before_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker = tmp_path / "attempt.json"
    marker.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        "evals.v5.run_fullcontext_quality_eval.LIVE_ATTEMPT_MARKER_PATH",
        marker,
    )
    monkeypatch.setattr(
        "evals.v5.fullcontext_quality_eval_contract.LIVE_ATTEMPT_MARKER_PATH",
        marker,
    )
    with pytest.raises(AttemptMarkerExistsError):
        prepare_live_run(attempt_marker_path=marker, artifact_paths=())


def test_artifact_exclusive_create_and_in_memory_serialization(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    payload = prepare_json_artifact_payload({"measurement_id": "s57", "cases": []})
    write_json_exclusive(path, payload)
    with pytest.raises(LiveArtifactWriteError):
        write_json_exclusive(path, payload)


def test_automated_success_stays_pending_manual_review() -> None:
    result = run_offline_harness(backend_factory=_offline_backend_factory)
    summary = result["summary"]
    assert summary["automated_verdict"] == "AUTOMATED_PASS"
    assert evaluate_final_verdict(summary, None) == "PENDING_MANUAL_REVIEW"


def test_dry_run_validates_without_provider_calls(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_quality_eval_main(["--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["total_cases"] == 9


def test_offline_harness_runs_all_nine_cases() -> None:
    result = run_offline_harness(backend_factory=_offline_backend_factory)
    assert len(result["case_results"]) == 9
    assert result["summary"]["materialize_verified_rate"] == 1.0
