"""Offline harness for S52 FullContext verifier-only replay preparation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.target_medical_boundary import TargetMedicalBoundaryResult
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.target_boundary_enforced_fullcontext_response import (
    run_target_offline_boundary_enforced_fullcontext_response,
)
from core.target_response_verifier import TargetResponseVerificationError
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.fullcontext_verifier_replay_backend import (
    FrozenCandidateComposerBackend,
    FullContextVerifierReplayLiveNotConfiguredError,
    FullContextVerifierReplayTransportError,
    IssueBasedFakeSemanticBackend,
    owner_label_fake_assessment,
)
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from evals.v5.fullcontext_verifier_replay_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    AUTOMATED_ACCEPTANCE_GATES,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    FROZEN_SOURCE_RESULT_SHA256,
    LIVE_ATTEMPT_MARKER_PATH,
    MEASUREMENT_ID,
    MODEL_RECOMMENDATION,
    REPLAY_MATRIX_HASH,
    REPLAY_MATRIX_PATH,
    TERMINAL_CONTROL_CASE_ID,
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactWriteError,
    aggregate_replay_metrics,
    assert_attempt_marker_absent,
    assert_replay_live_artifacts_absent,
    build_attempt_marker_payload,
    classify_replay_decision,
    create_attempt_marker_exclusive,
    evaluate_automated_verdict,
    evaluate_final_verdict,
    load_candidate_text,
    load_replay_matrix,
    load_v2_case,
    prepare_json_artifact_payload,
    replay_case_by_id,
    replay_provider_call_violation,
    validate_frozen_source_pins,
)
from evals.v5.run_fullcontext_response_eval import _load_pipeline_context


def _serialize_raw_payload(payload: object) -> object:
    if type(payload) is str:
        return payload
    if is_dataclass(payload):
        return asdict(payload)
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "__dict__") and isinstance(payload.__dict__, dict):
        return {
            key: value
            for key, value in payload.__dict__.items()
            if not key.startswith("_")
        }
    return repr(payload)


def _required_blocking_kinds_satisfied(
    *,
    replay_case: dict[str, Any],
    semantic_payload: object,
    observed_decision: str,
) -> bool:
    required = replay_case.get("required_blocking_issue_kinds") or []
    if observed_decision != "block":
        return not required
    if not isinstance(semantic_payload, dict):
        return False
    issues = semantic_payload.get("issues")
    if not isinstance(issues, (list, tuple)):
        return False
    blocking_kinds = {
        issue.get("kind")
        for issue in issues
        if isinstance(issue, dict) and issue.get("kind") in {
            "unsupported_clinic_claim",
            "personal_medical_conclusion",
            "material_external_medical_claim",
        }
    }
    return any(kind in blocking_kinds for kind in required)


def _semantic_payload_from_backend(semantic_backend: object) -> object:
    captures = getattr(semantic_backend, "captures", None)
    if not captures:
        return None
    last = captures[-1]
    raw = getattr(last, "raw_backend_payload", last)
    return _serialize_raw_payload(raw)


def classify_observed_replay_decision(
    result: object,
    error: BaseException | None = None,
) -> tuple[str, str | None]:
    if error is not None:
        if type(error) is TargetResponseVerificationError:
            code = getattr(error, "code", None)
            if code == "target_verifier_semantic_rejected":
                return "block", code
        return "error", getattr(error, "code", type(error).__name__)
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        return "pass", result.verified.verification_status
    if type(result).__name__ == "TargetMedicalBoundaryTerminalEnforcement":
        return "terminal_boundary_uncertain", None
    return "error", "unexpected_result"


def run_replay_case(
    *,
    replay_case: dict[str, Any],
    v2_case: dict[str, Any],
    index: int,
    v2_spec: dict[str, Any],
    context: dict[str, object],
    composer_backend: FrozenCandidateComposerBackend,
    semantic_backend: IssueBasedFakeSemanticBackend,
) -> dict[str, Any]:
    is_terminal = v2_case["case_id"] == TERMINAL_CONTROL_CASE_ID
    allowlist = v2_spec["turn_frame_allowlist"]
    turn_frame = build_turn_frame_from_raw(
        v2_case["turn_frame_raw"],
        allowed_topics=frozenset(allowlist["allowed_topics"]),
        allowed_service_ids=frozenset(allowlist["allowed_service_ids"]),
    )
    boundary = TargetMedicalBoundaryResult.model_validate(v2_case["boundary_result"])
    policy = v2_case["policy_envelope"]
    pipeline_error: BaseException | None = None
    result: object | None = None
    try:
        result = run_target_offline_boundary_enforced_fullcontext_response(
            turn_frame,
            boundary,
            context["bundle"],  # type: ignore[arg-type]
            context["doctor_catalog"],  # type: ignore[arg-type]
            context["external_index"],  # type: ignore[arg-type]
            context["consultation_values"],  # type: ignore[arg-type]
            tone_key=policy["tone_key"],
            allowed_topics=tuple(policy["allowed_topics"]),
            forbidden_topics=tuple(policy["forbidden_topics"]),
            required_fact_ids=tuple(policy["required_fact_ids"]),
            allow_marketing_facts=bool(policy["allow_marketing_facts"]),
            allow_consultation_close=bool(policy["allow_consultation_close"]),
            allow_cta=bool(policy["allow_cta"]),
            min_topic_confidence=float(policy["min_topic_confidence"]),
            min_service_confidence=float(policy["min_service_confidence"]),
            min_intent_confidence=float(policy["min_intent_confidence"]),
            brand_term=context["brand_term"],  # type: ignore[arg-type]
            strategy_context=context["strategy_context"],  # type: ignore[arg-type]
            semantic_context=str(context["semantic_context"]),
            today=context["today"],  # type: ignore[arg-type]
            md_root=context["md_root"],  # type: ignore[arg-type]
            cached_full_context=context["cached_full_context"],  # type: ignore[arg-type]
            include_initial_block=bool(context["include_initial_block"]),
            include_consultation_close=bool(context["include_consultation_close"]),
            include_cta=bool(context["include_cta"]),
            user_message=str(v2_case["user_message"]).strip(),
            tone=context["tone"],  # type: ignore[arg-type]
            composer_backend=composer_backend,
            semantic_backend=semantic_backend,
        )
    except Exception as error:
        pipeline_error = error

    observed_decision, reason_code = classify_observed_replay_decision(
        result if pipeline_error is None else None,
        pipeline_error,
    )
    expected_decision = replay_case["expected_decision"] if not is_terminal else None
    semantic_payload = _semantic_payload_from_backend(semantic_backend)
    metrics = (
        classify_replay_decision(observed=observed_decision, expected=expected_decision)  # type: ignore[arg-type]
        if not is_terminal
        else None
    )
    blocking_kind_match = (
        _required_blocking_kinds_satisfied(
            replay_case=replay_case,
            semantic_payload=semantic_payload,
            observed_decision=observed_decision,
        )
        if not is_terminal
        else True
    )
    decision_match = (
        bool(metrics.decision_match and blocking_kind_match)
        if metrics is not None
        else observed_decision == "terminal_boundary_uncertain"
    )
    false_block = bool(metrics.false_block) if metrics else False
    missed_block = bool(metrics.missed_block or (metrics and not blocking_kind_match and expected_decision == "block")) if metrics else False
    composer_provider_calls = composer_backend.provider_call_count
    verifier_provider_calls = semantic_backend.provider_call_count
    provider_violation = replay_provider_call_violation(
        is_terminal=is_terminal,
        composer_provider_calls=composer_provider_calls,
        verifier_provider_calls=verifier_provider_calls,
        composer_invocations=composer_backend.invocation_count,
        verifier_invocations=semantic_backend.invocation_count,
        offline_mode=True,
    )
    response_text: str | None = None
    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        response_text = result.verified.text
    elif pipeline_error is not None and type(pipeline_error) is TargetResponseVerificationError:
        response_text = composer_backend.candidate_text

    malformed = observed_decision == "error" and reason_code not in {
        "target_verifier_semantic_rejected",
    }
    transport_error = isinstance(pipeline_error, FullContextVerifierReplayTransportError)
    backend_failure = pipeline_error is not None and not transport_error and malformed

    row: dict[str, Any] = {
        "index": index,
        "case_id": v2_case["case_id"],
        "terminal_control": is_terminal,
        "blast_radius_group": replay_case.get("blast_radius_group"),
        "expected_decision": expected_decision,
        "observed_decision": observed_decision,
        "observed_outcome": observed_decision if is_terminal else observed_decision,
        "decision_match": decision_match,
        "blocking_kind_match": blocking_kind_match,
        "false_block": false_block,
        "missed_block": missed_block,
        "composer_invocation_count": composer_backend.invocation_count,
        "semantic_invocation_count": semantic_backend.invocation_count,
        "composer_provider_call_count": composer_provider_calls,
        "verifier_provider_call_count": verifier_provider_calls,
        "provider_call_violation": provider_violation,
        "response_text": response_text,
        "pipeline_error_code": reason_code if pipeline_error else None,
        "composer_raw_payload": _serialize_raw_payload(
            composer_backend.captures[-1].raw_backend_payload
            if composer_backend.captures
            else None
        ),
        "semantic_raw_payload": semantic_payload,
        "malformed": malformed,
        "transport_error": transport_error,
        "backend_failure": backend_failure,
        "invalid_offending_span": reason_code == "target_verifier_semantic_output_invalid",
        "retry_count": max(
            0,
            composer_backend.invocation_count - 1,
            semantic_backend.invocation_count - 1,
        ),
        "status": "OK"
        if decision_match and not provider_violation
        else "REVIEW",
    }
    return row


def _owner_label_backend_factory(
    replay_spec: dict[str, Any],
) -> Callable[
    [dict[str, Any]],
    tuple[FrozenCandidateComposerBackend, IssueBasedFakeSemanticBackend],
]:
    def factory(v2_case: dict[str, Any]) -> tuple[FrozenCandidateComposerBackend, IssueBasedFakeSemanticBackend]:
        case_id = v2_case["case_id"]
        if case_id == TERMINAL_CONTROL_CASE_ID:
            return (
                FrozenCandidateComposerBackend("unused"),
                IssueBasedFakeSemanticBackend(),
            )
        replay_case = replay_case_by_id(replay_spec, case_id)
        candidate_text = load_candidate_text(case_id=case_id, replay_case=replay_case)
        return (
            FrozenCandidateComposerBackend(candidate_text),
            IssueBasedFakeSemanticBackend(
                case_id=case_id,
                assessment_for_case=owner_label_fake_assessment,
            ),
        )

    return factory


def run_offline_replay_harness(
    *,
    backend_factory: Callable[
        [dict[str, Any]],
        tuple[FrozenCandidateComposerBackend, IssueBasedFakeSemanticBackend],
    ],
    replay_spec: dict[str, Any] | None = None,
    artifact_paths: Sequence[Path] | None = None,
    preflight_exclude_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    replay = replay_spec or load_replay_matrix()
    from evals.v5.fullcontext_response_eval_contract import load_v2_matrix

    v2_spec = load_v2_matrix()
    context = _load_pipeline_context(v2_spec)
    if artifact_paths is not None:
        excluded = {path.resolve() for path in (preflight_exclude_paths or ())}
        preflight_paths = tuple(
            path for path in artifact_paths if path.resolve() not in excluded
        )
        assert_replay_live_artifacts_absent(tuple(preflight_paths))

    if len({case["case_id"] for case in replay["cases"]}) != 19:
        raise HarnessConfigError("replay matrix must contain 19 unique materializable cases")

    v2_by_id = {case["case_id"]: case for case in v2_spec["cases"]}
    case_results: list[dict[str, Any]] = []
    for index, case_id in enumerate(
        [TERMINAL_CONTROL_CASE_ID]
        + [case["case_id"] for case in replay["cases"]]
    ):
        v2_case = v2_by_id[case_id]
        replay_case = (
            replay_case_by_id(replay, case_id)
            if case_id != TERMINAL_CONTROL_CASE_ID
            else {"blast_radius_group": None, "expected_decision": None}
        )
        composer, semantic = backend_factory(v2_case)
        case_results.append(
            run_replay_case(
                replay_case=replay_case,
                v2_case=v2_case,
                index=index,
                v2_spec=v2_spec,
                context=context,
                composer_backend=composer,
                semantic_backend=semantic,
            )
        )

    summary = summarize_replay_results(case_results, replay_spec=replay)
    return {"summary": summary, "case_results": case_results}


def summarize_replay_results(
    case_results: Sequence[dict[str, Any]],
    *,
    replay_spec: dict[str, Any],
) -> dict[str, Any]:
    metrics = aggregate_replay_metrics(list(case_results))
    summary = {
        "measurement_id": MEASUREMENT_ID,
        "matrix_git_blob_hash": REPLAY_MATRIX_HASH,
        "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
        **metrics,
        "proposed_automated_acceptance_gates": dict(AUTOMATED_ACCEPTANCE_GATES),
        "model_recommendation": dict(MODEL_RECOMMENDATION),
    }
    automated = evaluate_automated_verdict(summary)
    summary["automated_verdict"] = automated
    summary["final_verdict"] = evaluate_final_verdict(automated)
    summary["manual_review_required"] = True
    summary["suite_id"] = replay_spec["suite_id"]
    return summary


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(serialized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as error:
        raise LiveArtifactWriteError(
            f"live artifact already exists; silent overwrite forbidden: {path}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument("--matrix", default=str(REPLAY_MATRIX_PATH))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate matrix and artifact guards only; no pipeline execution",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Reserved for future verifier-only live eval (blocked in S52)",
    )
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="Allow live prep when attempt marker exists (owner approval only)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        validate_frozen_source_pins()
        replay_spec = load_replay_matrix(path=Path(args.matrix))
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    try:
        assert_attempt_marker_absent(
            LIVE_ATTEMPT_MARKER_PATH,
            owner_override=args.owner_override_attempt_marker,
        )
        assert_replay_live_artifacts_absent(DEFAULT_LIVE_ARTIFACT_PATHS)
    except (AttemptMarkerExistsError, LiveArtifactWriteError) as error:
        print(f"ARTIFACT_GUARD: {error}", file=sys.stderr)
        return 4

    if args.dry_run:
        payload = {
            "measurement_id": MEASUREMENT_ID,
            "matrix_git_blob_hash": REPLAY_MATRIX_HASH,
            "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
            "materializable_case_count": 19,
            "terminal_control_case_id": TERMINAL_CONTROL_CASE_ID,
            "dry_run": True,
            "proposed_automated_acceptance_gates": dict(AUTOMATED_ACCEPTANCE_GATES),
            "model_recommendation": dict(MODEL_RECOMMENDATION),
            "artifact_paths": {path.name: str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.live:
        print("LIVE_NOT_CONFIGURED", file=sys.stderr)
        return 3

    print("LIVE_NOT_CONFIGURED", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
