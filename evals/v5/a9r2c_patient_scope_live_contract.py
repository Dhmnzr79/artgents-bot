"""Frozen contract for A9R2c patient-scope planner live eval (pre-live prep)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.a9r2b_patient_scope_live_contract import (
    LIVE_CASE_COUNT,
    LIVE_PHASE,
    MATRIX_V3_BLOB,
    MATRIX_V3_PATH,
    MAX_PLANNER_CALLS,
    RETRY_COUNT_MAX,
    assert_matrix_v3_frozen,
    iter_live_planner_calls,
    load_frozen_matrix_v3,
)
from evals.v5.a9r2_patient_scope_live_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    AxisOutcome,
    AutomatedVerdict,
    FinalVerdict,
    NEGATIVE_AMBIGUOUS_CATEGORIES,
    POSITIVE_CATEGORIES,
    SCORABLE_AXES,
    append_call_ledger_entry,
    assert_matrix_v1_frozen,
    assert_matrix_v2_frozen,
    build_manual_review_seed as _build_manual_review_seed,
    create_attempt_marker_exclusive,
    ledger_entries_balanced,
    persist_attempt_marker,
    write_json_exclusive,
)
from evals.v5.a9r2_patient_scope_live_scoring import AC2_MATERIAL_AXES
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
)

MEASUREMENT_ID = "a9r2c_patient_scope_live"
SUITE_ID = "a9r2c_patient_scope_live"
CLIENT_ID = "demo"
OWNER_APPROVED_PLANNER_MODEL = "qwen3.7-plus"

PROPOSED_GATES: dict[str, Any] = {
    "wrong_non_unknown_axis_count": {"max": 0},
    "material_false_positive_axis_count": {"max": 0},
    "correction_success_rate": {"min": 1.0},
    "positive_axis_recall": {"min": 0.85},
    "true_composite_exact_turn_rate": {"min": 0.85},
    "malformed_projection_count": {"max": 0},
    "transport_provider_error_count": {"max": 0},
    "planner_calls": {"max": MAX_PLANNER_CALLS},
    "retry_count": {"max": RETRY_COUNT_MAX},
}

_REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "a9r2c_patient_scope_live_call_ledger.jsonl"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
)

FROZEN_A9R2C_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "a9r2c_patient_scope_live_raw.json": (
        "b476dd2aab06af6be2dcfbfacabed88c1ab9a1d42dd06f8bed0c742d5345d5c5"
    ),
    "a9r2c_patient_scope_live_result.json": (
        "f5ddf7945c4c04d7d64496143c022601f82689b0bfe36e9c0e34567b66f28707"
    ),
    "a9r2c_patient_scope_live_attempt.json": (
        "8027190e23d060d4ce01dafdc6b42e34a9f956c47ad05860598bfaa28f8882b0"
    ),
    "a9r2c_patient_scope_live_call_ledger.jsonl": (
        "9c174dc3650503e3429f934570057268d066d54c84cb26f9693c618f9a8c72e2"
    ),
    "a9r2c_patient_scope_live_manual_review.json": (
        "eb00f8832345849c912e4f4d42490122bd677dca87c07c6b92b25ca30723d907"
    ),
}

OFFICIAL_A9R2C_LIVE_VERDICT = "AUTOMATED_FAIL"
OFFICIAL_A9R2C_STATUS = "A9R2C_NOT_PASSED"


def assert_frozen_a9r2c_live_artifacts_unchanged() -> None:
    from evals.v5.fullcontext_response_eval_contract import sha256_file_hex

    for name, expected in FROZEN_A9R2C_LIVE_ARTIFACT_SHA256.items():
        path = LIVE_ARTIFACTS_DIR / name
        if not path.exists():
            raise HarnessConfigError(f"frozen A9R2c live artifact missing: {path}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen A9R2c live artifact sha256 mismatch path={path} expected={expected} actual={actual}"
            )


def assert_attempt_marker_absent(
    path: Path | None = None,
    *,
    owner_override: bool = False,
) -> None:
    from evals.v5.a9r2_patient_scope_live_contract import (
        assert_attempt_marker_absent as _assert,
    )

    _assert(path or LIVE_ATTEMPT_MARKER_PATH, owner_override=owner_override)


def record_provider_call_started(path: Path | None = None) -> None:
    from evals.v5.a9r2_patient_scope_live_contract import (
        record_provider_call_started as _record,
    )

    _record(path or LIVE_ATTEMPT_MARKER_PATH)


def finalize_attempt_marker(
    path: Path,
    *,
    status: str,
    automated_verdict: AutomatedVerdict,
) -> None:
    from evals.v5.a9r2_patient_scope_live_contract import (
        finalize_attempt_marker as _finalize,
    )

    _finalize(path, status=status, automated_verdict=automated_verdict)


def load_attempt_marker(path: Path | None = None) -> dict[str, Any]:
    from evals.v5.a9r2_patient_scope_live_contract import load_attempt_marker as _load

    return _load(path or LIVE_ATTEMPT_MARKER_PATH)


def assert_live_artifacts_absent(
    *,
    exclude_paths: frozenset[Path] | None = None,
) -> None:
    excluded = {path.resolve() for path in (exclude_paths or frozenset())}
    for path in DEFAULT_LIVE_ARTIFACT_PATHS:
        if path.resolve() in excluded:
            continue
        if path.exists():
            raise LiveArtifactExistsError(f"live artifact already exists: {path}")


def build_attempt_marker_payload(
    *,
    matrix_blob: str = MATRIX_V3_BLOB,
    planner_model: str = OWNER_APPROVED_PLANNER_MODEL,
) -> dict[str, Any]:
    return prepare_json_artifact_payload(
        {
            "measurement_id": MEASUREMENT_ID,
            "suite_id": SUITE_ID,
            "matrix_blob": matrix_blob,
            "planner_model": planner_model,
            "max_planner_calls": MAX_PLANNER_CALLS,
            "retry_count_max": RETRY_COUNT_MAX,
            "provider_calls_started": 0,
            "provider_calls_completed": 0,
            "status": "in_progress",
            "abort_blocks_retry_without_owner_approval": True,
        }
    )


def build_manual_review_seed(*, automated_verdict: AutomatedVerdict) -> dict[str, Any]:
    payload = _build_manual_review_seed(automated_verdict=automated_verdict)
    payload["measurement_id"] = MEASUREMENT_ID
    payload["suite_id"] = SUITE_ID
    payload["reported_context_ruling"] = "diagnostic_only_not_authority_candidate"
    return payload


__all__ = [
    "AC2_MATERIAL_AXES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AutomatedVerdict",
    "AxisOutcome",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "FinalVerdict",
    "FROZEN_A9R2C_LIVE_ARTIFACT_SHA256",
    "LIVE_ATTEMPT_MARKER_PATH",
    "LIVE_CALL_LEDGER_PATH",
    "LIVE_CASE_COUNT",
    "LIVE_MANIFEST_ARTIFACT_PATH",
    "LIVE_MANUAL_REVIEW_ARTIFACT_PATH",
    "LIVE_PHASE",
    "LIVE_RAW_ARTIFACT_PATH",
    "LIVE_RESULT_ARTIFACT_PATH",
    "MATRIX_V3_BLOB",
    "MATRIX_V3_PATH",
    "MAX_PLANNER_CALLS",
    "MEASUREMENT_ID",
    "NEGATIVE_AMBIGUOUS_CATEGORIES",
    "OFFICIAL_A9R2C_LIVE_VERDICT",
    "OFFICIAL_A9R2C_STATUS",
    "OWNER_APPROVED_PLANNER_MODEL",
    "POSITIVE_CATEGORIES",
    "PROPOSED_GATES",
    "RETRY_COUNT_MAX",
    "SCORABLE_AXES",
    "SUITE_ID",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_frozen_a9r2c_live_artifacts_unchanged",
    "assert_live_artifacts_absent",
    "assert_matrix_v1_frozen",
    "assert_matrix_v2_frozen",
    "assert_matrix_v3_frozen",
    "build_attempt_marker_payload",
    "build_manual_review_seed",
    "create_attempt_marker_exclusive",
    "finalize_attempt_marker",
    "iter_live_planner_calls",
    "ledger_entries_balanced",
    "load_attempt_marker",
    "load_frozen_matrix_v3",
    "record_provider_call_started",
    "write_json_exclusive",
]
