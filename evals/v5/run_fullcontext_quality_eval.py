"""Offline harness for S57 compact FullContext quality eval (no live in scope)."""

from __future__ import annotations

import argparse
import json
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
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MATRIX_PATH,
    MEASUREMENT_ID,
    MODEL_RECOMMENDATION,
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactWriteError,
    assert_attempt_marker_absent,
    assert_live_artifacts_absent,
    build_attempt_marker_payload,
    create_attempt_marker_exclusive,
    load_frozen_matrix,
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
)
from evals.v5.fullcontext_quality_eval_contract import summarize_results


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
        build_attempt_marker_payload(matrix_hash=FROZEN_MATRIX_HASH),
    )


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
        help="Reserved for future owner-approved live eval (blocked in S57)",
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
                "attempt_marker": str(LIVE_ATTEMPT_MARKER_PATH),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.offline:
        backend_factory: Callable[
            [dict[str, Any]],
            tuple[
                FullContextResponseEvalRecordingComposerBackend,
                FullContextResponseEvalRecordingSemanticBackend,
            ],
        ] = _offline_backend_factory
        result = run_offline_harness(
            backend_factory=backend_factory,
            matrix_path=matrix_path,
        )
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return 0 if result["summary"].get("automated_verdict") == "AUTOMATED_PASS" else 1

    if args.live:
        try:
            prepare_live_run(
                owner_override_attempt_marker=bool(args.owner_override_attempt_marker),
            )
        except AttemptMarkerExistsError:
            print(ATTEMPT_MARKER_EXISTS_CODE, file=sys.stderr)
            return 3
        except LiveArtifactWriteError as error:
            print(f"LIVE_ARTIFACT_EXISTS: {error}", file=sys.stderr)
            return 3

    try:
        raise FullContextResponseEvalLiveNotConfiguredError(
            "fullcontext_quality_eval_live_not_configured",
            "PENDING_OWNER_APPROVAL",
        )
    except FullContextResponseEvalLiveNotConfiguredError as error:
        print(f"LIVE_NOT_CONFIGURED: {error.code}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
