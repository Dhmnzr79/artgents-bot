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
from evals.v5.fullcontext_verifier_replay_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    AUTOMATED_ACCEPTANCE_GATES,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    FROZEN_SOURCE_RESULT_SHA256,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MEASUREMENT_ID,
    MEASUREMENT_ID_LIVE,
    MODEL_RECOMMENDATION,
    OWNER_APPROVED_SEMANTIC_MODEL,
    REPLAY_MATRIX_HASH,
    REPLAY_MATRIX_PATH,
    TERMINAL_CONTROL_CASE_ID,
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactWriteError,
    aggregate_replay_metrics,
    assert_attempt_marker_absent,
    assert_replay_live_artifacts_absent,
    build_manual_review_seed,
    evaluate_automated_verdict,
    evaluate_final_verdict,
    load_candidate_text,
    load_replay_matrix,
    load_replay_matrix_v2,
    prepare_json_artifact_payload,
    prepare_replay_live_run,
    replay_case_by_id,
    replay_provider_call_violation,
    score_replay_case,
    sha256_file_hex,
    validate_frozen_source_pins,
    DEFAULT_V2_LIVE_ARTIFACT_PATHS,
    REPLAY_MATRIX_V2_HASH,
    REPLAY_MATRIX_V2_PATH,
    MEASUREMENT_ID_V2,
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
    semantic_backend: object,
    offline_mode: bool = True,
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
    score = (
        score_replay_case(
            replay_case=replay_case,
            observed_decision=observed_decision,
            semantic_payload=semantic_payload,
        )
        if not is_terminal
        else None
    )
    decision_match = (
        score.decision_match
        if score is not None
        else observed_decision == "terminal_boundary_uncertain"
    )
    false_block = score.false_block if score is not None else False
    missed_block = score.missed_block if score is not None else False
    blocking_kind_match = score.blocking_kind_match if score is not None else True
    composer_provider_calls = getattr(composer_backend, "provider_call_count", 0)
    verifier_provider_calls = getattr(semantic_backend, "provider_call_count", 0)
    composer_invocations = getattr(composer_backend, "invocation_count", 0)
    semantic_invocations = getattr(semantic_backend, "invocation_count", 0)
    provider_violation = replay_provider_call_violation(
        is_terminal=is_terminal,
        composer_provider_calls=composer_provider_calls,
        verifier_provider_calls=verifier_provider_calls,
        composer_invocations=composer_invocations,
        verifier_invocations=semantic_invocations,
        offline_mode=offline_mode,
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
        "composer_invocation_count": composer_invocations,
        "semantic_invocation_count": semantic_invocations,
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
            composer_invocations - 1,
            semantic_invocations - 1,
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


def _live_backend_factory(
    replay_spec: dict[str, Any],
    *,
    call_ledger_path: Path,
    attempt_marker_path: Path,
) -> Callable[[dict[str, Any]], tuple[FrozenCandidateComposerBackend, object]]:
    from evals.v5.fullcontext_verifier_replay_live_backend import (
        FullContextVerifierReplayLiveSemanticBackend,
    )

    def factory(v2_case: dict[str, Any]) -> tuple[FrozenCandidateComposerBackend, object]:
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
            FullContextVerifierReplayLiveSemanticBackend(
                case_id=case_id,
                model=OWNER_APPROVED_SEMANTIC_MODEL,
                call_ledger_path=call_ledger_path,
                attempt_marker_path=attempt_marker_path,
            ),
        )

    return factory


def run_replay_harness(
    *,
    backend_factory: Callable[[dict[str, Any]], tuple[FrozenCandidateComposerBackend, object]],
    replay_spec: dict[str, Any] | None = None,
    artifact_paths: Sequence[Path] | None = None,
    preflight_exclude_paths: Sequence[Path] | None = None,
    offline_mode: bool = True,
    measurement_id: str = MEASUREMENT_ID,
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
                offline_mode=offline_mode,
            )
        )

    summary = summarize_replay_results(
        case_results,
        replay_spec=replay,
        measurement_id=measurement_id,
        live_run=not offline_mode,
    )
    return {"summary": summary, "case_results": case_results}


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
    return run_replay_harness(
        backend_factory=backend_factory,
        replay_spec=replay_spec,
        artifact_paths=artifact_paths,
        preflight_exclude_paths=preflight_exclude_paths,
        offline_mode=True,
    )


def summarize_replay_results(
    case_results: Sequence[dict[str, Any]],
    *,
    replay_spec: dict[str, Any],
    measurement_id: str = MEASUREMENT_ID,
    live_run: bool = False,
    matrix_hash: str = REPLAY_MATRIX_HASH,
) -> dict[str, Any]:
    metrics = aggregate_replay_metrics(list(case_results))
    summary = {
        "measurement_id": measurement_id,
        "matrix_git_blob_hash": matrix_hash,
        "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
        **metrics,
        "proposed_automated_acceptance_gates": dict(AUTOMATED_ACCEPTANCE_GATES),
        "model_recommendation": dict(MODEL_RECOMMENDATION),
        "live_run": live_run,
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
        "--matrix-v2",
        action="store_true",
        help="Use S54 replay matrix v2 (owner-approved label corrections)",
    )
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
        if args.matrix_v2:
            replay_spec = load_replay_matrix_v2()
            matrix_hash = REPLAY_MATRIX_V2_HASH
            artifact_paths = DEFAULT_V2_LIVE_ARTIFACT_PATHS
            measurement_id = MEASUREMENT_ID_V2
        else:
            replay_spec = load_replay_matrix(path=Path(args.matrix))
            matrix_hash = REPLAY_MATRIX_HASH
            artifact_paths = DEFAULT_LIVE_ARTIFACT_PATHS
            measurement_id = MEASUREMENT_ID
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.matrix_v2 and args.live:
        print("V2_LIVE_PENDING_OWNER_APPROVAL", file=sys.stderr)
        return 3

    try:
        assert_attempt_marker_absent(
            LIVE_ATTEMPT_MARKER_PATH,
            owner_override=args.owner_override_attempt_marker,
        )
        assert_replay_live_artifacts_absent(DEFAULT_LIVE_ARTIFACT_PATHS)
        if args.matrix_v2:
            assert_replay_live_artifacts_absent(DEFAULT_V2_LIVE_ARTIFACT_PATHS)
    except (AttemptMarkerExistsError, LiveArtifactWriteError) as error:
        print(f"ARTIFACT_GUARD: {error}", file=sys.stderr)
        return 4

    if args.dry_run:
        payload = {
            "measurement_id": measurement_id,
            "matrix_git_blob_hash": matrix_hash,
            "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
            "materializable_case_count": 19,
            "terminal_control_case_id": TERMINAL_CONTROL_CASE_ID,
            "dry_run": True,
            "matrix_v2": args.matrix_v2,
            "proposed_automated_acceptance_gates": dict(AUTOMATED_ACCEPTANCE_GATES),
            "model_recommendation": dict(MODEL_RECOMMENDATION),
            "artifact_paths": {path.name: str(path) for path in artifact_paths},
        }
        if args.matrix_v2:
            payload["v2_live_status"] = "pending_owner_approval"
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.live:
        artifact_paths = DEFAULT_LIVE_ARTIFACT_PATHS
        try:
            prepare_replay_live_run(
                attempt_marker_path=LIVE_ATTEMPT_MARKER_PATH,
                artifact_paths=artifact_paths,
                owner_override_attempt_marker=args.owner_override_attempt_marker,
            )
            payload = run_replay_harness(
                backend_factory=_live_backend_factory(
                    replay_spec,
                    call_ledger_path=LIVE_CALL_LEDGER_PATH,
                    attempt_marker_path=LIVE_ATTEMPT_MARKER_PATH,
                ),
                replay_spec=replay_spec,
                artifact_paths=artifact_paths,
                preflight_exclude_paths=(LIVE_ATTEMPT_MARKER_PATH,),
                offline_mode=False,
                measurement_id=MEASUREMENT_ID_LIVE,
            )
        except AttemptMarkerExistsError as error:
            print(str(error), file=sys.stderr)
            return 5
        except (HarnessConfigError, LiveArtifactWriteError) as error:
            print(f"CONFIG_ERROR: {error}", file=sys.stderr)
            return 2

        case_results = payload["case_results"]
        verifier_calls = sum(
            row.get("verifier_provider_call_count", 0)
            for row in case_results
            if not row.get("terminal_control")
        )
        if verifier_calls > 19:
            print(
                f"CONFIG_ERROR: verifier provider call budget exceeded count={verifier_calls}",
                file=sys.stderr,
            )
            return 2

        summary = payload["summary"]
        summary["owner_approval"] = {
            "semantic_verifier_model": OWNER_APPROVED_SEMANTIC_MODEL,
            "max_verifier_provider_calls": 19,
            "max_composer_provider_calls": 0,
            "automated_gates_status": "owner_approved",
        }
        payload["summary"] = summary

        raw_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": MEASUREMENT_ID_LIVE,
                "matrix_git_blob_hash": REPLAY_MATRIX_HASH,
                "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
                "verifier_provider_call_count": verifier_calls,
                "cases": [
                    {
                        "index": row["index"],
                        "case_id": row["case_id"],
                        "composer_provider_call_count": row["composer_provider_call_count"],
                        "verifier_provider_call_count": row["verifier_provider_call_count"],
                        "composer_raw_payload": row["composer_raw_payload"],
                        "semantic_raw_payload": row["semantic_raw_payload"],
                    }
                    for row in case_results
                ],
            }
        )
        result_artifact = prepare_json_artifact_payload(payload)
        manifest_artifact = prepare_json_artifact_payload(
            {
                "measurement_id": MEASUREMENT_ID_LIVE,
                "matrix_git_blob_hash": REPLAY_MATRIX_HASH,
                "source_result_sha256": FROZEN_SOURCE_RESULT_SHA256,
                "verifier_provider_call_count": verifier_calls,
                "attempt_marker_path": str(LIVE_ATTEMPT_MARKER_PATH),
                "call_ledger_path": str(LIVE_CALL_LEDGER_PATH),
                "raw_artifact_path": str(LIVE_RAW_ARTIFACT_PATH),
                "result_artifact_path": str(LIVE_RESULT_ARTIFACT_PATH),
                "manual_review_artifact_path": str(LIVE_MANUAL_REVIEW_ARTIFACT_PATH),
            }
        )
        try:
            write_json_exclusive(LIVE_RAW_ARTIFACT_PATH, raw_artifact)
            write_json_exclusive(LIVE_RESULT_ARTIFACT_PATH, result_artifact)
            write_json_exclusive(LIVE_MANIFEST_ARTIFACT_PATH, manifest_artifact)
            result_sha256 = sha256_file_hex(LIVE_RESULT_ARTIFACT_PATH)
            manual_review = build_manual_review_seed(
                case_results=list(case_results),
                result_sha256=result_sha256,
                replay_spec=replay_spec,
            )
            write_json_exclusive(
                LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
                prepare_json_artifact_payload(manual_review),
            )
        except LiveArtifactWriteError as error:
            print(f"ARTIFACT_WRITE_ERROR: {error}", file=sys.stderr)
            return 6

        print(json.dumps(result_artifact, ensure_ascii=False, indent=2))
        return 0

    print("LIVE_NOT_CONFIGURED", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
