"""Frozen contract for FINAL scope/widget E2E live runtime eval."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
TURNS_PATH = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
FROZEN_TURNS_HASH = "f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f"

MEASUREMENT_ID = "final_scope_widget_e2e"
SUITE_ID = "final_scope_widget_e2e"
CLIENT_ID = "demo"
MAX_HTTP_TURNS = 8
MAX_PROVIDER_CALLS = 40
MAX_INGRESS_CALLS = 8
MAX_PLANNER_CALLS = 8
MAX_BOUNDARY_CALLS = 8
MAX_COMPOSER_CALLS = 8
MAX_VERIFIER_CALLS = 8
RETRY_COUNT_MAX = 0

REQUIRES_PLANNER_MODEL_PLUS = True

OWNER_APPROVED_INGRESS_MODEL = "qwen3.6-flash"
OWNER_APPROVED_PLANNER_MODEL = "qwen3.7-plus"
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
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_audit.log"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_AUDIT_LOG_PATH,
)

FROZEN_S62_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "s62_target_runtime_live_raw.json": (
        "1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428"
    ),
    "s62_target_runtime_live_result.json": (
        "1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428"
    ),
    "s62_target_runtime_live_manifest.json": (
        "4643a99ccb768d5863f96c286c30f8b76ee352c837064d14a7bc2e13a831f1e3"
    ),
    "s62_target_runtime_live_attempt.json": (
        "2570338b15cba9b4caf5b71c0c873c9ecb1fa8dcbca64014148665184ecfe657"
    ),
    "s62_target_runtime_live_call_ledger.jsonl": (
        "fd71c6460b4f8658dab85a2ec1c847d5ff7c2f29ab9a2d82886bf2ba98cf97a2"
    ),
    "s62_target_runtime_live_manual_review.json": (
        "9983da4ee2dcf0f9c35d4f40815a599607c87daf13846880c548052d9c885741"
    ),
    "s62_target_runtime_live_audit.log": (
        "e6a2d1e5bdc1cfe20e20dfe5d7f23c644103a97ab1eda8132346fc9616e82e02"
    ),
}

FROZEN_S63_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "s63_target_runtime_live_raw.json": (
        "503acb431f30042c482fd51c4d414639815a7c955c0e957adac28ccec741cd59"
    ),
    "s63_target_runtime_live_result.json": (
        "503acb431f30042c482fd51c4d414639815a7c955c0e957adac28ccec741cd59"
    ),
    "s63_target_runtime_live_manifest.json": (
        "17577cd2d0d0cd2a368b783626a3ed5aa95ac02633416fddd8c28e01cf0ff71e"
    ),
    "s63_target_runtime_live_attempt.json": (
        "c965b388fd4e8ae27593709535985c2e8c0553df03d1f874312577d46067080a"
    ),
    "s63_target_runtime_live_call_ledger.jsonl": (
        "9b284604d67e1b90bf636a11b645e91e540552d75e607ec7e451b5090d4808a8"
    ),
    "s63_target_runtime_live_manual_review.json": (
        "f8d8e60eaf7f74a1e09c5918030bfea8a3ea22028ba8d275ca08344137903f26"
    ),
    "s63_target_runtime_live_audit.log": (
        "b319ae23b9dbca669ff05a5cdbac0a81d5c3d6e34790e3f775d2f213a885c83a"
    ),
}

ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"
AutomatedVerdict = Literal["AUTOMATED_PASS", "AUTOMATED_FAIL"]
FinalVerdict = Literal["PASS", "FAIL", "PENDING_MANUAL_REVIEW"]


class ProviderRoleViolationError(HarnessConfigError):
    """Unknown or over-budget provider role."""


class AuthorityEnvError(HarnessConfigError):
    """Required authority env missing before config import."""


def assert_frozen_s62_live_artifacts_unchanged() -> None:
    for name, expected in FROZEN_S62_LIVE_ARTIFACT_SHA256.items():
        path = LIVE_ARTIFACTS_DIR / name
        if not path.exists():
            raise HarnessConfigError(f"frozen s62 artifact missing: {path}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen s62 artifact sha256 mismatch path={path} expected={expected} actual={actual}"
            )


def assert_frozen_s63_live_artifacts_unchanged() -> None:
    for name, expected in FROZEN_S63_LIVE_ARTIFACT_SHA256.items():
        path = LIVE_ARTIFACTS_DIR / name
        if not path.exists():
            raise HarnessConfigError(f"frozen s63 artifact missing: {path}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen s63 artifact sha256 mismatch path={path} expected={expected} actual={actual}"
            )


def load_frozen_turns(*, path: Path = TURNS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessConfigError("final_scope_widget_e2e turns spec must be object")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != FROZEN_TURNS_HASH:
        raise HarnessConfigError(
            f"turns hash mismatch expected={FROZEN_TURNS_HASH} actual={actual}"
        )
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) != MAX_HTTP_TURNS:
        raise HarnessConfigError(
            f"final_scope_widget_e2e turns must contain exactly {MAX_HTTP_TURNS} turns"
        )
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
        "requires_planner_model_plus": REQUIRES_PLANNER_MODEL_PLUS,
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
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    load_frozen_turns()


def assert_authority_env_before_import() -> None:
    planner = (os.environ.get("TURN_PLANNER_LLM_MODEL") or "").strip()
    if planner != OWNER_APPROVED_PLANNER_MODEL:
        raise AuthorityEnvError(
            f"TURN_PLANNER_LLM_MODEL must be {OWNER_APPROVED_PLANNER_MODEL!r} before import; got={planner!r}"
        )


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
            "manual_review_required": True,
            "turns": [
                {
                    "turn": row["turn"],
                    "turn_id": row["turn_id"],
                    "endpoint": row["endpoint"],
                    "sid": row.get("sid"),
                    "request": row.get("request"),
                    "answer_text": row.get("answer_text"),
                    "automated_turn_verdict": row.get("automated_turn_verdict"),
                    "recommended_manual_review": row.get("recommended_manual_review"),
                }
                for row in turn_results
            ],
        }
    )


def ledger_entries_balanced(path: Path) -> bool:
    if not path.exists():
        return False
    starts: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        sequence = int(entry.get("sequence") or 0)
        phase = str(entry.get("phase") or "")
        if phase == "call_start":
            starts[sequence] = phase
        elif phase in {"call_complete", "call_error"}:
            if sequence not in starts:
                return False
            del starts[sequence]
    return not starts


def planner_models_from_ledger(path: Path) -> list[str]:
    models: list[str] = []
    if not path.exists():
        return models
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("role") == "planner" and entry.get("phase") == "call_start":
            models.append(str(entry.get("model") or ""))
    return models


__all__ = [
    "ALLOWED_PROVIDER_ROLES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AuthorityEnvError",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "FROZEN_S62_LIVE_ARTIFACT_SHA256",
    "FROZEN_S63_LIVE_ARTIFACT_SHA256",
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
    "REQUIRES_PLANNER_MODEL_PLUS",
    "RETRY_COUNT_MAX",
    "TURNS_PATH",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_authority_env_before_import",
    "assert_frozen_s62_live_artifacts_unchanged",
    "assert_frozen_s63_live_artifacts_unchanged",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "build_attempt_marker_payload",
    "build_manual_review_seed",
    "create_attempt_marker_exclusive",
    "finalize_attempt_marker",
    "ledger_entries_balanced",
    "load_attempt_marker",
    "load_frozen_turns",
    "persist_attempt_marker",
    "planner_models_from_ledger",
]
