"""Frozen contract for A9R2b patient-scope planner live eval (pre-live prep)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.a9r2_patient_scope_live_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    LIVE_CASE_COUNT,
    MAX_PLANNER_CALLS,
    RETRY_COUNT_MAX,
    AxisOutcome,
    AutomatedVerdict,
    FinalVerdict,
    NEGATIVE_AMBIGUOUS_CATEGORIES,
    POSITIVE_CATEGORIES,
    SCORABLE_AXES,
    _git_blob_hash,
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
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_V3_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "patient_scope_a9r_matrix_v3.json"
MATRIX_V3_BLOB = "8ccd9bdc140a192981fcc48ad7ed0367a40b0a84"

MEASUREMENT_ID = "a9r2b_patient_scope_live"
SUITE_ID = "a9r2b_patient_scope_live"
CLIENT_ID = "demo"
OWNER_APPROVED_PLANNER_MODEL = "qwen3.6-flash"
LIVE_PHASE = "a9r2b_live"

PROPOSED_GATES: dict[str, Any] = {
    "wrong_non_unknown_axis_count": {"max": 0},
    "material_false_positive_axis_count": {"max": 0},
    "correction_success_rate": {"min": 1.0},
    "positive_axis_recall": {"min": 0.85},
    "composite_exact_turn_rate": {"min": 0.85},
    "malformed_projection_count": {"max": 0},
    "transport_provider_error_count": {"max": 0},
    "planner_calls": {"max": MAX_PLANNER_CALLS},
    "retry_count": {"max": RETRY_COUNT_MAX},
}

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "a9r2b_patient_scope_live_call_ledger.jsonl"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
)

FROZEN_A9R2B_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "a9r2b_patient_scope_live_raw.json": (
        "19cad2154c9fb654cc29e7cf337ede05ee361bd266aa7509f7687b4137c876a0"
    ),
    "a9r2b_patient_scope_live_result.json": (
        "9a91a66d3a23b0beb2f6936ebe9d44e431a98ee3cb09a6e3b7960e2271fd83ba"
    ),
    "a9r2b_patient_scope_live_attempt.json": (
        "5616d6a4a10a9b7945c9a63a1dbb6014d7759a48cf91faa974f990f2e778baec"
    ),
    "a9r2b_patient_scope_live_call_ledger.jsonl": (
        "6a69c518b6dd5b0311616c3ac22b6d0a839c4e7853c486bd1df18fd0387efddb"
    ),
}

OFFICIAL_A9R2B_LIVE_VERDICT = "AUTOMATED_FAIL"
OFFICIAL_A9R2B_STATUS = "A9R2B_NOT_PASSED"


def assert_frozen_a9r2b_live_artifacts_unchanged() -> None:
    for name, expected in FROZEN_A9R2B_LIVE_ARTIFACT_SHA256.items():
        path = LIVE_ARTIFACTS_DIR / name
        if not path.exists():
            raise HarnessConfigError(f"frozen A9R2b live artifact missing: {path}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen A9R2b live artifact sha256 mismatch path={path} expected={expected} actual={actual}"
            )


def assert_matrix_v3_frozen() -> None:
    if _git_blob_hash(MATRIX_V3_PATH) != MATRIX_V3_BLOB:
        raise HarnessConfigError("frozen A9R v3 matrix blob mismatch")


def load_frozen_matrix_v3() -> dict[str, Any]:
    assert_matrix_v3_frozen()
    payload = json.loads(MATRIX_V3_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "a9r.patient_scope_authority_prep.v3":
        raise HarnessConfigError("A9R v3 matrix schema_version mismatch")
    return payload


def iter_live_planner_calls(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for case in matrix.get("cases", []):
        if case.get("phase") != LIVE_PHASE:
            continue
        case_id = str(case["id"])
        category = str(case.get("category") or "")
        topic = str(case.get("topic") or "")
        if "turns" in case:
            for index, turn in enumerate(case["turns"]):
                calls.append(
                    {
                        "call_id": f"{case_id}:turn{index + 1}",
                        "case_id": case_id,
                        "turn_index": index,
                        "category": category,
                        "topic": topic,
                        "question": str(turn["question"]),
                        "expected_scope": dict(turn["expected_effective_scope"]),
                        "session_write": turn.get("session_write"),
                        "must_not_keep_prior": turn.get("must_not_keep_prior"),
                        "forbidden_inferences": list(case.get("forbidden_inferences") or []),
                        "is_correction_turn": index > 0,
                    }
                )
        else:
            calls.append(
                {
                    "call_id": case_id,
                    "case_id": case_id,
                    "turn_index": 0,
                    "category": category,
                    "topic": topic,
                    "question": str(case["question"]),
                    "expected_scope": dict(case["expected_effective_scope"]),
                    "session_write": case.get("session_write"),
                    "must_not_keep_prior": None,
                    "forbidden_inferences": list(case.get("forbidden_inferences") or []),
                    "is_correction_turn": False,
                }
            )
    if len({call["case_id"] for call in calls}) != LIVE_CASE_COUNT:
        raise HarnessConfigError(
            f"live case count mismatch expected={LIVE_CASE_COUNT} actual={len({call['case_id'] for call in calls})}"
        )
    if len(calls) != MAX_PLANNER_CALLS:
        raise HarnessConfigError(
            f"planner call budget mismatch expected={MAX_PLANNER_CALLS} actual={len(calls)}"
        )
    return calls


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
    return payload


__all__ = [
    "AC2_MATERIAL_AXES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AutomatedVerdict",
    "AxisOutcome",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "FinalVerdict",
    "FROZEN_A9R2B_LIVE_ARTIFACT_SHA256",
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
    "OFFICIAL_A9R2B_LIVE_VERDICT",
    "OFFICIAL_A9R2B_STATUS",
    "POSITIVE_CATEGORIES",
    "PROPOSED_GATES",
    "RETRY_COUNT_MAX",
    "SCORABLE_AXES",
    "SUITE_ID",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_live_artifacts_absent",
    "assert_frozen_a9r2b_live_artifacts_unchanged",
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
