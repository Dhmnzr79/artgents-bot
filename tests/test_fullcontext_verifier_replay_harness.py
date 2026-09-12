from __future__ import annotations

import json

import pytest

from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from evals.v5.fullcontext_verifier_replay_backend import (
    FrozenCandidateComposerBackend,
    FullContextVerifierReplayLiveNotConfiguredError,
    FullContextVerifierReplaySemanticAdapter,
    IssueBasedFakeSemanticBackend,
    assert_backend_module_has_no_provider_imports,
    owner_label_fake_assessment,
)
from evals.v5.fullcontext_verifier_replay_contract import (
    BLAST_RADIUS_GROUPS,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    EXPECTED_BLOCK_CASE_IDS,
    LIVE_ATTEMPT_MARKER_PATH,
    AttemptMarkerExistsError,
    HarnessConfigError,
    load_candidate_text,
    load_replay_matrix,
    load_v2_case,
    replay_provider_call_violation,
)
from evals.v5.run_fullcontext_response_eval import _load_pipeline_context
from evals.v5.run_fullcontext_verifier_replay import (
    _owner_label_backend_factory,
    main as run_replay_main,
    run_offline_replay_harness,
    run_replay_case,
)
import evals.v5.run_fullcontext_verifier_replay as replay_runner


@pytest.fixture
def isolated_live_artifact_paths(tmp_path, monkeypatch):
    paths = {
        "attempt": tmp_path / "attempt.json",
        "raw": tmp_path / "raw.json",
        "result": tmp_path / "result.json",
        "ledger": tmp_path / "ledger.jsonl",
        "manifest": tmp_path / "manifest.json",
        "manual": tmp_path / "manual.json",
    }
    artifact_paths = tuple(paths.values())
    monkeypatch.setattr(replay_runner, "LIVE_ATTEMPT_MARKER_PATH", paths["attempt"])
    monkeypatch.setattr(replay_runner, "LIVE_RAW_ARTIFACT_PATH", paths["raw"])
    monkeypatch.setattr(replay_runner, "LIVE_RESULT_ARTIFACT_PATH", paths["result"])
    monkeypatch.setattr(replay_runner, "LIVE_CALL_LEDGER_PATH", paths["ledger"])
    monkeypatch.setattr(replay_runner, "LIVE_MANIFEST_ARTIFACT_PATH", paths["manifest"])
    monkeypatch.setattr(replay_runner, "LIVE_MANUAL_REVIEW_ARTIFACT_PATH", paths["manual"])
    monkeypatch.setattr(replay_runner, "DEFAULT_LIVE_ARTIFACT_PATHS", artifact_paths)
    return paths


def _replay_case(case_id: str) -> dict[str, object]:
    spec = load_replay_matrix()
    return next(item for item in spec["cases"] if item["case_id"] == case_id)


def _run_single(case_id: str, semantic: IssueBasedFakeSemanticBackend) -> dict[str, object]:
    replay_spec = load_replay_matrix()
    from evals.v5.fullcontext_response_eval_contract import load_v2_matrix

    v2_spec = load_v2_matrix()
    context = _load_pipeline_context(v2_spec)
    v2_case = load_v2_case(case_id)
    replay_case = _replay_case(case_id)
    candidate_text = load_candidate_text(case_id=case_id, replay_case=replay_case)
    composer = FrozenCandidateComposerBackend(candidate_text)
    return run_replay_case(
        replay_case=replay_case,
        v2_case=v2_case,
        index=0,
        v2_spec=v2_spec,
        context=context,
        composer_backend=composer,
        semantic_backend=semantic,
    )


def test_replay_provider_call_budget_rules() -> None:
    assert replay_provider_call_violation(
        is_terminal=True,
        composer_provider_calls=0,
        verifier_provider_calls=0,
    ) is False
    assert replay_provider_call_violation(
        is_terminal=True,
        composer_provider_calls=1,
        verifier_provider_calls=0,
    ) is True
    assert replay_provider_call_violation(
        is_terminal=False,
        composer_provider_calls=0,
        verifier_provider_calls=0,
        composer_invocations=1,
        verifier_invocations=1,
        offline_mode=True,
    ) is False
    assert replay_provider_call_violation(
        is_terminal=False,
        composer_provider_calls=0,
        verifier_provider_calls=0,
        composer_invocations=0,
        verifier_invocations=1,
        offline_mode=True,
    ) is True
    assert replay_provider_call_violation(
        is_terminal=False,
        composer_provider_calls=0,
        verifier_provider_calls=1,
        offline_mode=False,
    ) is False


def test_frozen_composer_backend_has_no_provider_imports() -> None:
    assert_backend_module_has_no_provider_imports()
    backend = FrozenCandidateComposerBackend("candidate")
    assert backend.provider_call_count == 0


def test_owner_label_fake_passes_sixteen_cases() -> None:
    spec = load_replay_matrix()
    for case in spec["cases"]:
        if case["expected_decision"] != "pass":
            continue
        row = _run_single(
            case["case_id"],
            IssueBasedFakeSemanticBackend(
                case_id=case["case_id"],
                assessment_for_case=owner_label_fake_assessment,
            ),
        )
        assert row["observed_decision"] == "pass", case["case_id"]
        assert row["false_block"] is False, case["case_id"]


def test_owner_label_fake_blocks_three_cases() -> None:
    for case_id in sorted(EXPECTED_BLOCK_CASE_IDS):
        row = _run_single(
            case_id,
            IssueBasedFakeSemanticBackend(
                case_id=case_id,
                assessment_for_case=owner_label_fake_assessment,
            ),
        )
        assert row["observed_decision"] == "block", case_id
        assert row["missed_block"] is False, case_id
        assert row["blocking_kind_match"] is True, case_id


def test_minor_external_detail_does_not_block() -> None:
    assessment = TargetSemanticAssessment(
        issues=(
            TargetSemanticIssue(kind="minor_external_detail", offending_span="имплант"),
        )
    )
    row = _run_single(
        "fc_info_01",
        IssueBasedFakeSemanticBackend(assessment=assessment),
    )
    assert row["observed_decision"] == "pass"
    assert row["false_block"] is False


def test_wrong_blocking_kind_counts_as_missed_block() -> None:
    assessment = TargetSemanticAssessment(
        issues=(
            TargetSemanticIssue(
                kind="personal_medical_conclusion",
                offending_span="имплант",
            ),
        )
    )
    row = _run_single("fc_medical_03", IssueBasedFakeSemanticBackend(assessment=assessment))
    assert row["observed_decision"] == "block"
    assert row["missed_block"] is True
    assert row["blocking_kind_match"] is False


def test_invalid_offending_span_fail_closed() -> None:
    assessment = TargetSemanticAssessment(
        issues=(
            TargetSemanticIssue(
                kind="material_external_medical_claim",
                offending_span="NOT_IN_CANDIDATE",
            ),
        )
    )
    row = _run_single("fc_medical_03", IssueBasedFakeSemanticBackend(assessment=assessment))
    assert row["observed_decision"] == "error"
    assert row["invalid_offending_span"] is True


def test_malformed_semantic_output_fail_closed() -> None:
    class _BadSemantic:
        invocation_count = 0
        provider_call_count = 0
        captures = []

        def assess(self, invocation, /):
            self.invocation_count += 1
            self.captures.append(invocation)
            return {"issues": [{"kind": "material_external_medical_claim"}]}

    from evals.v5.fullcontext_response_eval_contract import load_v2_matrix

    v2_spec = load_v2_matrix()
    context = _load_pipeline_context(v2_spec)
    v2_case = load_v2_case("fc_info_01")
    replay_case = _replay_case("fc_info_01")
    candidate_text = load_candidate_text(case_id="fc_info_01", replay_case=replay_case)
    row = run_replay_case(
        replay_case=replay_case,
        v2_case=v2_case,
        index=0,
        v2_spec=v2_spec,
        context=context,
        composer_backend=FrozenCandidateComposerBackend(candidate_text),
        semantic_backend=_BadSemantic(),  # type: ignore[arg-type]
    )
    assert row["observed_decision"] == "error"
    assert row["malformed"] is True


def test_terminal_control_zero_provider_calls() -> None:
    replay_spec = load_replay_matrix()
    payload = run_offline_replay_harness(
        backend_factory=_owner_label_backend_factory(replay_spec),
        replay_spec=replay_spec,
    )
    terminal = next(
        row for row in payload["case_results"] if row["case_id"] == "fc_terminal_01"
    )
    assert terminal["observed_decision"] == "terminal_boundary_uncertain"
    assert terminal["composer_provider_call_count"] == 0
    assert terminal["verifier_provider_call_count"] == 0
    assert terminal["composer_invocation_count"] == 0
    assert terminal["semantic_invocation_count"] == 0
    assert payload["summary"]["terminal_control_match"] is True


def test_offline_owner_label_harness_decision_metrics() -> None:
    replay_spec = load_replay_matrix()
    payload = run_offline_replay_harness(
        backend_factory=_owner_label_backend_factory(replay_spec),
        replay_spec=replay_spec,
    )
    materializable = [
        row for row in payload["case_results"] if not row["terminal_control"]
    ]
    assert len(materializable) == 19
    assert all(row["decision_match"] for row in materializable)
    assert payload["summary"]["false_block_count"] == 0
    assert payload["summary"]["missed_block_count"] == 0
    assert payload["summary"]["decision_match_rate"] == 1.0
    assert all(not row["provider_call_violation"] for row in materializable)


def test_blast_radius_summary_covers_mass_selling_groups() -> None:
    replay_spec = load_replay_matrix()
    payload = run_offline_replay_harness(
        backend_factory=_owner_label_backend_factory(replay_spec),
        replay_spec=replay_spec,
    )
    summary = payload["summary"]["blast_radius_summary"]
    for group in BLAST_RADIUS_GROUPS:
        assert group in summary
        assert summary[group]["false_block_count"] == 0


def test_cli_dry_run_validates_matrix(capsys, isolated_live_artifact_paths) -> None:
    assert run_replay_main(["--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["materializable_case_count"] == 19


def test_default_cli_live_not_configured(capsys, isolated_live_artifact_paths) -> None:
    assert run_replay_main([]) == 3
    assert "LIVE_NOT_CONFIGURED" in capsys.readouterr().err


def test_default_cli_blocked_when_attempt_marker_exists(capsys) -> None:
    assert run_replay_main([]) == 4
    assert "ATTEMPT_MARKER_EXISTS" in capsys.readouterr().err


def test_live_flag_requires_owner_approved_wiring(
    monkeypatch,
    isolated_live_artifact_paths,
) -> None:
    monkeypatch.setattr(
        "evals.v5.run_fullcontext_verifier_replay.prepare_replay_live_run",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "evals.v5.run_fullcontext_verifier_replay.run_replay_harness",
        lambda **kwargs: {
            "summary": {"automated_verdict": {"verdict": "AUTOMATED_PASS"}},
            "case_results": [],
        },
    )
    monkeypatch.setattr(
        "evals.v5.run_fullcontext_verifier_replay.write_json_exclusive",
        lambda path, payload: None,
    )
    monkeypatch.setattr(
        "evals.v5.run_fullcontext_verifier_replay.sha256_file_hex",
        lambda path: "deadbeef",
    )
    assert run_replay_main(["--live"]) == 0


def test_semantic_adapter_requires_delegate() -> None:
    adapter = FullContextVerifierReplaySemanticAdapter()
    with pytest.raises(FullContextVerifierReplayLiveNotConfiguredError):
        adapter.assess(object())  # type: ignore[arg-type]


def test_existing_attempt_marker_blocks_default_cli(tmp_path, monkeypatch) -> None:
    marker = tmp_path / "attempt.json"
    marker.write_text("{}\n", encoding="utf-8")
    import evals.v5.run_fullcontext_verifier_replay as module

    monkeypatch.setattr(module, "LIVE_ATTEMPT_MARKER_PATH", marker)
    with pytest.raises(AttemptMarkerExistsError):
        module.assert_attempt_marker_absent(marker)


def test_existing_output_artifact_blocks_harness(tmp_path) -> None:
    artifact = tmp_path / "fullcontext_verifier_replay_live_result.json"
    artifact.write_text("{}\n", encoding="utf-8")
    replay_spec = load_replay_matrix()
    with pytest.raises(HarnessConfigError):
        run_offline_replay_harness(
            backend_factory=_owner_label_backend_factory(replay_spec),
            replay_spec=replay_spec,
            artifact_paths=(artifact,),
        )


def test_missing_candidate_case_id_fail_closed() -> None:
    with pytest.raises(HarnessConfigError, match="unknown case_id"):
        load_candidate_text(case_id="fc_does_not_exist")
