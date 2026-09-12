"""Offline and live harness for S57/S58 compact FullContext quality eval."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.v5.fullcontext_quality_eval_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    EXPECTED_LLM_CALLS,
    FROZEN_MATRIX_HASH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MATRIX_PATH,
    MEASUREMENT_ID,
    MODEL_RECOMMENDATION,
    OWNER_APPROVED_COMPOSER_MODEL,
    OWNER_APPROVED_VERIFIER_MODEL,
    RUN_MANIFEST_ARTIFACT_PATH,
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactWriteError,
    assert_attempt_marker_absent,
    assert_frozen_prior_artifacts_unchanged,
    assert_live_artifacts_absent,
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    load_frozen_matrix,
    summarize_results,
)
from evals.v5.fullcontext_response_eval_contract import (
    prepare_json_artifact_payload,
    sha256_file_hex,
)
from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalLiveNotConfiguredError,
    FullContextResponseEvalRecordingComposerBackend,
    FullContextResponseEvalRecordingSemanticBackend,
)
from evals.v5.run_fullcontext_response_eval import (
    _load_pipeline_context,
    _offline_backend_factory,
    run_case,
    write_json_exclusive,
)


def _git_head_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()


def run_offline_harness(
    *,
    backend_factory: Callable[
        [dict[str, Any]],
        tuple[
            FullContextResponseEvalRecordingComposerBackend,
            FullContextResponseEvalRecordingSemanticBackend,
        ],
    ],
    matrix_path: Path = MATRIX_PATH,
) -> dict[str, Any]:
    spec = load_frozen_matrix(path=matrix_path)
    context = _load_pipeline_context(spec)
    case_results = []
    for index, case in enumerate(spec["cases"]):
        composer, semantic = backend_factory(case)
        case_results.append(
            run_case(
                case=case,
                index=index,
                spec=spec,
                context=context,
                composer_backend=composer,
                semantic_backend=semantic,
            )
        )
    return {
        "summary": summarize_results(case_results),
        "case_results": case_results,
    }


def prepare_live_run(
    *,
    attempt_marker_path: Path | None = None,
    artifact_paths: Sequence[Path] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
    baseline_commit: str | None = None,
) -> None:
    marker_path = (
        LIVE_ATTEMPT_MARKER_PATH if attempt_marker_path is None else attempt_marker_path
    )
    assert_attempt_marker_absent(
        marker_path,
        owner_override=owner_override_attempt_marker,
    )
    excluded = {marker_path.resolve()}
    preflight_paths = tuple(
        path for path in artifact_paths if path.resolve() not in excluded
    )
    assert_live_artifacts_absent(preflight_paths)
    create_attempt_marker_exclusive(
        marker_path,
        build_attempt_marker_payload(
            matrix_hash=FROZEN_MATRIX_HASH,
            baseline_commit=baseline_commit or _git_head_commit(),
        ),
    )


def _live_backend_factory(
    *,
    call_ledger_path: Path,
    attempt_marker_path: Path,
) -> Callable[[dict[str, Any]], tuple[object, object]]:
    from evals.v5.fullcontext_quality_eval_live_backend import (
        FullContextQualityEvalLiveComposerBackend,
        FullContextQualityEvalLiveSemanticBackend,
    )

    def factory(case: dict[str, Any]) -> tuple[object, object]:
        case_id = str(case["case_id"])
        return (
            FullContextQualityEvalLiveComposerBackend(
                case_id=case_id,
                call_ledger_path=call_ledger_path,
                attempt_marker_path=attempt_marker_path,
                model=OWNER_APPROVED_COMPOSER_MODEL,
            ),
            FullContextQualityEvalLiveSemanticBackend(
                case_id=case_id,
                call_ledger_path=call_ledger_path,
                attempt_marker_path=attempt_marker_path,
                model=OWNER_APPROVED_VERIFIER_MODEL,
            ),
        )

    return factory


def run_live_harness(
    *,
    matrix_path: Path = MATRIX_PATH,
    attempt_marker_path: Path = LIVE_ATTEMPT_MARKER_PATH,
    call_ledger_path: Path = LIVE_CALL_LEDGER_PATH,
    raw_path: Path = LIVE_RAW_ARTIFACT_PATH,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    manifest_path: Path = RUN_MANIFEST_ARTIFACT_PATH,
    manual_review_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    artifact_paths: Sequence[Path] = DEFAULT_LIVE_ARTIFACT_PATHS,
    owner_override_attempt_marker: bool = False,
) -> dict[str, Any]:
    baseline_commit = _git_head_commit()
    prepare_live_run(
        attempt_marker_path=attempt_marker_path,
        artifact_paths=artifact_paths,
        owner_override_attempt_marker=owner_override_attempt_marker,
        baseline_commit=baseline_commit,
    )
    spec = load_frozen_matrix(path=matrix_path)
    context = _load_pipeline_context(spec)
    backend_factory = _live_backend_factory(
        call_ledger_path=call_ledger_path,
        attempt_marker_path=attempt_marker_path,
    )
    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(spec["cases"]):
        composer, semantic = backend_factory(case)
        case_results.append(
            run_case(
                case=case,
                index=index,
                spec=spec,
                context=context,
                composer_backend=composer,  # type: ignore[arg-type]
                semantic_backend=semantic,  # type: ignore[arg-type]
            )
        )

    total_llm_calls = sum(
        row["composer_call_count"] + row["semantic_call_count"] for row in case_results
    )
    composer_calls = sum(row["composer_call_count"] for row in case_results)
    verifier_calls = sum(row["semantic_call_count"] for row in case_results)
    if total_llm_calls > EXPECTED_LLM_CALLS:
        raise HarnessConfigError(
            f"live LLM call budget exceeded count={total_llm_calls} max={EXPECTED_LLM_CALLS}"
        )
    if composer_calls > MODEL_RECOMMENDATION["expected_composer_calls"]:
        raise HarnessConfigError(
            f"composer call budget exceeded count={composer_calls}"
        )
    if verifier_calls > MODEL_RECOMMENDATION["expected_verifier_calls"]:
        raise HarnessConfigError(
            f"verifier call budget exceeded count={verifier_calls}"
        )

    summary = summarize_results(case_results)
    summary["live_run"] = True
    summary["total_llm_calls"] = total_llm_calls
    summary["composer_calls"] = composer_calls
    summary["verifier_calls"] = verifier_calls
    summary["baseline_live_commit"] = baseline_commit
    summary["owner_approval"] = {
        "composer_model": OWNER_APPROVED_COMPOSER_MODEL,
        "verifier_model": OWNER_APPROVED_VERIFIER_MODEL,
        "max_llm_calls": EXPECTED_LLM_CALLS,
        "retry_count_max": 0,
        "rerun_blocked_without_owner_approval": True,
    }
    payload = {"summary": summary, "case_results": case_results}

    raw_artifact = prepare_json_artifact_payload(
        {
            "measurement_id": MEASUREMENT_ID,
            "matrix_git_blob_hash": FROZEN_MATRIX_HASH,
            "baseline_live_commit": baseline_commit,
            "total_llm_calls": total_llm_calls,
            "composer_calls": composer_calls,
            "verifier_calls": verifier_calls,
            "cases": [
                {
                    "index": row["index"],
                    "case_id": row["case_id"],
                    "composer_call_count": row["composer_call_count"],
                    "semantic_call_count": row["semantic_call_count"],
                    "composer_raw_payload": row["composer_raw_payload"],
                    "semantic_raw_payload": row["semantic_raw_payload"],
                }
                for row in case_results
            ],
        }
    )
    result_artifact = prepare_json_artifact_payload(payload)
    write_json_exclusive(raw_path, raw_artifact)
    write_json_exclusive(result_path, result_artifact)
    result_sha256 = sha256_file_hex(result_path)
    manual_seed = build_manual_review_seed(
        case_results=case_results,
        result_sha256=result_sha256,
        matrix_hash=FROZEN_MATRIX_HASH,
        matrix_spec=spec,
        baseline_commit=baseline_commit,
    )
    write_json_exclusive(manual_review_path, manual_seed)
    manifest_artifact = prepare_json_artifact_payload(
        {
            "measurement_id": MEASUREMENT_ID,
            "matrix_git_blob_hash": FROZEN_MATRIX_HASH,
            "baseline_live_commit": baseline_commit,
            "total_llm_calls": total_llm_calls,
            "composer_calls": composer_calls,
            "verifier_calls": verifier_calls,
            "attempt_marker_path": str(attempt_marker_path),
            "call_ledger_path": str(call_ledger_path),
            "raw_artifact_path": str(raw_path),
            "result_artifact_path": str(result_path),
            "manual_review_path": str(manual_review_path),
            "result_sha256": result_sha256,
            "rerun_blocked_without_owner_approval": True,
        }
    )
    write_json_exclusive(manifest_path, manifest_artifact)
    finalize_attempt_marker(
        attempt_marker_path,
        status="attempt_completed",
        total_llm_calls=total_llm_calls,
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument("--matrix", default=str(MATRIX_PATH))
    parser.add_argument("--output", default=str(LIVE_RESULT_ARTIFACT_PATH))
    parser.add_argument("--raw-output", default=str(LIVE_RAW_ARTIFACT_PATH))
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="Allow live prep when attempt marker exists (owner approval only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate matrix, contracts, artifact guards and budget only",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one owner-approved S58 live eval (9 Composer + 9 Verifier)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline harness with recording composer/semantic backends",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    matrix_path = Path(args.matrix)
    try:
        spec = load_frozen_matrix(path=matrix_path)
        assert_frozen_prior_artifacts_unchanged()
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "measurement_id": MEASUREMENT_ID,
            "matrix_git_blob_hash": FROZEN_MATRIX_HASH,
            "total_cases": len(spec["cases"]),
            "max_llm_calls": EXPECTED_LLM_CALLS,
            "dry_run": True,
            "model_recommendation": dict(MODEL_RECOMMENDATION),
            "artifact_paths": {
                "raw": str(LIVE_RAW_ARTIFACT_PATH),
                "result": str(LIVE_RESULT_ARTIFACT_PATH),
                "manifest": str(RUN_MANIFEST_ARTIFACT_PATH),
                "attempt_marker": str(LIVE_ATTEMPT_MARKER_PATH),
                "call_ledger": str(LIVE_CALL_LEDGER_PATH),
                "manual_review": str(LIVE_MANUAL_REVIEW_ARTIFACT_PATH),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.offline:
        result = run_offline_harness(
            backend_factory=_offline_backend_factory,
            matrix_path=matrix_path,
        )
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return 0 if result["summary"].get("automated_verdict") == "AUTOMATED_PASS" else 1

    if args.live:
        try:
            payload = run_live_harness(
                matrix_path=matrix_path,
                owner_override_attempt_marker=bool(args.owner_override_attempt_marker),
            )
        except AttemptMarkerExistsError:
            print(ATTEMPT_MARKER_EXISTS_CODE, file=sys.stderr)
            return 3
        except LiveArtifactWriteError as error:
            print(f"LIVE_ARTIFACT_EXISTS: {error}", file=sys.stderr)
            return 3
        except HarnessConfigError as error:
            print(f"CONFIG_ERROR: {error}", file=sys.stderr)
            return 2
        except Exception as error:
            print(f"LIVE_ABORT: {type(error).__name__}: {error}", file=sys.stderr)
            return 5

        summary = payload["summary"]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        automated = summary.get("automated_verdict")
        final = summary.get("final_verdict")
        print(f"AUTOMATED_VERDICT: {automated}", file=sys.stderr)
        print(f"FINAL_VERDICT: {final}", file=sys.stderr)
        return 0 if automated == "AUTOMATED_PASS" else 4

    try:
        raise FullContextResponseEvalLiveNotConfiguredError(
            "fullcontext_quality_eval_live_not_configured",
            "use --live for owner-approved S58 run or --offline/--dry-run",
        )
    except FullContextResponseEvalLiveNotConfiguredError as error:
        print(f"LIVE_NOT_CONFIGURED: {error.code}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
