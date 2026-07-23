"""Frozen contract for S62 target FullContext HTTP live runtime eval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    LiveArtifactWriteError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
TURNS_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "s62_target_runtime_live_turns.json"
FROZEN_TURNS_HASH = hashlib.sha256(TURNS_PATH.read_bytes()).hexdigest()

MEASUREMENT_ID = "s62_target_runtime_live"
SUITE_ID = "s62_target_runtime_live"
CLIENT_ID = "demo"
MAX_HTTP_TURNS = 4
MAX_PROVIDER_CALLS = 20
MAX_INGRESS_CALLS = 4
MAX_PLANNER_CALLS = 4
MAX_BOUNDARY_CALLS = 4
MAX_COMPOSER_CALLS = 4
MAX_VERIFIER_CALLS = 4
RETRY_COUNT_MAX = 0

OWNER_APPROVED_INGRESS_MODEL = "qwen3.6-flash"
OWNER_APPROVED_PLANNER_MODEL = "qwen3.6-flash"
OWNER_APPROVED_BOUNDARY_MODEL = "qwen3.7-plus"
OWNER_APPROVED_COMPOSER_MODEL = "qwen3.7-plus"
OWNER_APPROVED_VERIFIER_MODEL = "qwen3.7-plus"

ALLOWED_PROVIDER_ROLES = frozenset(
    {
        "ingress",
        "planner",
        "medical_boundary",
        "composer",
        "semantic_verifier",
    }
)

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "s62_target_runtime_live_audit.log"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_AUDIT_LOG_PATH,
)

ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"
AutomatedVerdict = Literal["AUTOMATED_PASS", "AUTOMATED_FAIL"]
FinalVerdict = Literal["PASS", "FAIL", "PENDING_MANUAL_REVIEW"]


class ProviderRoleViolationError(HarnessConfigError):
    """Unknown or duplicate provider role in one HTTP turn."""


def load_frozen_turns(*, path: Path = TURNS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("s62 turns spec must be object")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != FROZEN_TURNS_HASH:
        raise HarnessConfigError(
            f"s62 turns hash mismatch expected={FROZEN_TURNS_HASH} actual={actual}"
        )
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) != MAX_HTTP_TURNS:
        raise HarnessConfigError("s62 turns must contain exactly 4 turns")
    return payload


def assert_live_artifacts_absent(
    paths: tuple[Path, ...] = DEFAULT_LIVE_ARTIFACT_PATHS,
) -> None:
    for path in paths:
        if path.exists():
            raise LiveArtifactExistsError(f"live artifact already exists: {path}")


def assert_attempt_marker_absent(
    path: Path = LIVE_ATTEMPT_MARKER_PATH,
    *,
    owner_override: bool = False,
) -> None:
    if path.exists() and not owner_override:
        raise AttemptMarkerExistsError(ATTEMPT_MARKER_EXISTS_CODE)


def create_attempt_marker_exclusive(
    path: Path,
    payload: dict[str, Any],
) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise AttemptMarkerExistsError(ATTEMPT_MARKER_EXISTS_CODE) from exc


def build_attempt_marker_payload(
    *,
    baseline_commit: str,
    turns_hash: str = FROZEN_TURNS_HASH,
) -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "turns_git_blob_hash": turns_hash,
        "status": "attempt_started",
        "baseline_commit": baseline_commit,
        "ingress_model": OWNER_APPROVED_INGRESS_MODEL,
        "planner_model": OWNER_APPROVED_PLANNER_MODEL,
        "boundary_model": OWNER_APPROVED_BOUNDARY_MODEL,
        "composer_model": OWNER_APPROVED_COMPOSER_MODEL,
        "verifier_model": OWNER_APPROVED_VERIFIER_MODEL,
        "max_provider_calls": MAX_PROVIDER_CALLS,
        "max_http_turns": MAX_HTTP_TURNS,
        "retry_count_max": RETRY_COUNT_MAX,
        "rerun_blocked_without_owner_approval": True,
        "started_provider_calls": 0,
        "role_counts": {role: 0 for role in sorted(ALLOWED_PROVIDER_ROLES)},
    }


def load_attempt_marker(path: Path = LIVE_ATTEMPT_MARKER_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("attempt marker must be object")
    return payload


def persist_attempt_marker(path: Path, payload: dict[str, Any]) -> None:
    serialized = prepare_json_artifact_payload(payload)
    path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def finalize_attempt_marker(
    path: Path,
    *,
    status: str,
    total_provider_calls: int,
    role_counts: dict[str, int],
) -> None:
    marker = load_attempt_marker(path)
    marker["status"] = status
    marker["completed_provider_calls"] = total_provider_calls
    marker["role_counts"] = role_counts
    persist_attempt_marker(path, marker)


def append_call_ledger_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = prepare_json_artifact_payload(entry)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(serialized, ensure_ascii=False) + "\n")


def assert_frozen_suite_unchanged() -> None:
    assert_frozen_prior_artifacts_unchanged()
    load_frozen_turns()


def build_manual_review_seed(
    *,
    turn_results: list[dict[str, Any]],
    result_sha256: str,
    baseline_commit: str,
    turns_hash: str = FROZEN_TURNS_HASH,
    provider_ledger_sha256: str,
) -> dict[str, Any]:
    return prepare_json_artifact_payload(
        {
            "measurement_id": MEASUREMENT_ID,
            "baseline_live_commit": baseline_commit,
            "turns_git_blob_hash": turns_hash,
            "result_sha256": result_sha256,
            "provider_ledger_sha256": provider_ledger_sha256,
            "final_verdict": "PENDING_MANUAL_REVIEW",
            "turns": [
                {
                    "turn": row["turn"],
                    "turn_id": row["turn_id"],
                    "endpoint": row["endpoint"],
                    "request": row.get("request"),
                    "answer_text": row.get("answer_text"),
                    "automated_turn_verdict": row.get("automated_turn_verdict"),
                    "recommended_manual_review": row.get("recommended_manual_review"),
                }
                for row in turn_results
            ],
        }
    )


__all__ = [
    "ALLOWED_PROVIDER_ROLES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "FROZEN_TURNS_HASH",
    "LIVE_ATTEMPT_MARKER_PATH",
    "LIVE_AUDIT_LOG_PATH",
    "LIVE_CALL_LEDGER_PATH",
    "LIVE_MANIFEST_ARTIFACT_PATH",
    "LIVE_MANUAL_REVIEW_ARTIFACT_PATH",
    "LIVE_RAW_ARTIFACT_PATH",
    "LIVE_RESULT_ARTIFACT_PATH",
    "MAX_PROVIDER_CALLS",
    "MEASUREMENT_ID",
    "OWNER_APPROVED_BOUNDARY_MODEL",
    "OWNER_APPROVED_COMPOSER_MODEL",
    "OWNER_APPROVED_INGRESS_MODEL",
    "OWNER_APPROVED_PLANNER_MODEL",
    "OWNER_APPROVED_VERIFIER_MODEL",
    "ProviderRoleViolationError",
    "TURNS_PATH",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "build_attempt_marker_payload",
    "build_manual_review_seed",
    "create_attempt_marker_exclusive",
    "finalize_attempt_marker",
    "load_attempt_marker",
    "load_frozen_turns",
]
