"""Frozen contract for FINAL scope/widget E2E retry1 live runtime eval."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import (
    ALLOWED_PROVIDER_ROLES,
    ATTEMPT_MARKER_EXISTS_CODE,
    CLIENT_ID,
    FROZEN_S62_LIVE_ARTIFACT_SHA256,
    FROZEN_S63_LIVE_ARTIFACT_SHA256,
    FROZEN_TURNS_HASH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    OWNER_APPROVED_BOUNDARY_MODEL,
    OWNER_APPROVED_COMPOSER_MODEL,
    OWNER_APPROVED_INGRESS_MODEL,
    OWNER_APPROVED_PLANNER_MODEL,
    OWNER_APPROVED_VERIFIER_MODEL,
    RETRY_COUNT_MAX,
    REQUIRES_A9_PATIENT_SCOPE_AUTHORITY,
    REQUIRES_PLANNER_MODEL_PLUS,
    TURNS_PATH,
    AuthorityEnvError,
    ProviderRoleViolationError,
    append_call_ledger_entry,
    assert_attempt_marker_absent,
    assert_authority_env_before_import,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
    assert_live_artifacts_absent,
    build_attempt_marker_payload,
    build_manual_review_seed,
    create_attempt_marker_exclusive,
    finalize_attempt_marker,
    ledger_entries_balanced,
    load_attempt_marker,
    load_frozen_turns,
    persist_attempt_marker,
    planner_models_from_ledger,
)
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

MEASUREMENT_ID = "final_scope_widget_e2e_retry1"
SUITE_ID = "final_scope_widget_e2e_retry1"
PARENT_MEASUREMENT_ID = "final_scope_widget_e2e"

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry1_audit.log"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_AUDIT_LOG_PATH,
)

FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_attempt.json"
)
FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_SHA256 = (
    "1e1208ff37818109469d134b7d316176525d606aaaf5cd348d9c735713c8c7cb"
)
FROZEN_PREFLIGHT_ABORT_AUDIT_PATH = (
    _REPO_ROOT / "docs" / "evidence" / "final_scope" / "FINAL_SCOPE_WIDGET_E2E_LIVE_ATTEMPT_AUDIT.md"
)
FROZEN_PREFLIGHT_ABORT_AUDIT_SHA256 = (
    "82db98447bf72999a2a5dd9c8f3c96f849f6e957cafb1344b93444d14b44abab"
)

S69_DELETED_LEGACY_MODULES = frozenset(
    {
        "chunk_responder",
        "orchestration.ask_turn",
        "source_routing",
        "orchestration.composer_flow",
        "orchestration.price_flow",
        "orchestration.catalog_flow",
        "orchestration.patient_playbook_flow",
    }
)

S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS = (
    r"^\s*from\s+orchestration\.ask_turn\b",
    r"^\s*import\s+orchestration\.ask_turn\b",
    r"^\s*from\s+orchestration\s+import\s+ask_turn\b",
    r"^\s*from\s+orchestration\.composer_flow\b",
    r"^\s*from\s+orchestration\.price_flow\b",
    r"^\s*from\s+orchestration\.catalog_flow\b",
    r"^\s*from\s+orchestration\.patient_playbook_flow\b",
    r"^\s*import\s+chunk_responder\b",
    r"^\s*from\s+chunk_responder\b",
    r"^\s*import\s+source_routing\b",
    r"^\s*from\s+source_routing\b",
)


def build_retry1_attempt_marker_payload(
    *,
    baseline_commit: str,
    turns_hash: str = FROZEN_TURNS_HASH,
) -> dict:
    payload = build_attempt_marker_payload(
        baseline_commit=baseline_commit,
        turns_hash=turns_hash,
    )
    payload["measurement_id"] = MEASUREMENT_ID
    payload["parent_measurement_id"] = PARENT_MEASUREMENT_ID
    return payload


def assert_frozen_preflight_abort_artifacts_unchanged() -> None:
    attempt_path = FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_PATH
    if not attempt_path.exists():
        raise HarnessConfigError(f"frozen preflight-abort attempt marker missing: {attempt_path}")
    actual_attempt = sha256_file_hex(attempt_path)
    if actual_attempt != FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_SHA256:
        raise HarnessConfigError(
            "frozen preflight-abort attempt marker sha256 mismatch "
            f"expected={FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_SHA256} actual={actual_attempt}"
        )
    audit_path = FROZEN_PREFLIGHT_ABORT_AUDIT_PATH
    if not audit_path.exists():
        raise HarnessConfigError(f"frozen preflight-abort audit missing: {audit_path}")
    actual_audit = sha256_file_hex(audit_path)
    if actual_audit != FROZEN_PREFLIGHT_ABORT_AUDIT_SHA256:
        raise HarnessConfigError(
            "frozen preflight-abort audit sha256 mismatch "
            f"expected={FROZEN_PREFLIGHT_ABORT_AUDIT_SHA256} actual={actual_audit}"
        )


__all__ = [
    "ALLOWED_PROVIDER_ROLES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AuthorityEnvError",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_PATH",
    "FROZEN_PREFLIGHT_ABORT_ATTEMPT_MARKER_SHA256",
    "FROZEN_PREFLIGHT_ABORT_AUDIT_PATH",
    "FROZEN_PREFLIGHT_ABORT_AUDIT_SHA256",
    "FROZEN_S62_LIVE_ARTIFACT_SHA256",
    "FROZEN_S63_LIVE_ARTIFACT_SHA256",
    "FROZEN_TURNS_HASH",
    "HarnessConfigError",
    "LIVE_ATTEMPT_MARKER_PATH",
    "LIVE_AUDIT_LOG_PATH",
    "LIVE_CALL_LEDGER_PATH",
    "LIVE_MANIFEST_ARTIFACT_PATH",
    "LIVE_MANUAL_REVIEW_ARTIFACT_PATH",
    "LIVE_RAW_ARTIFACT_PATH",
    "LIVE_RESULT_ARTIFACT_PATH",
    "LiveArtifactExistsError",
    "MAX_HTTP_TURNS",
    "MAX_PROVIDER_CALLS",
    "MEASUREMENT_ID",
    "OWNER_APPROVED_BOUNDARY_MODEL",
    "OWNER_APPROVED_COMPOSER_MODEL",
    "OWNER_APPROVED_INGRESS_MODEL",
    "OWNER_APPROVED_PLANNER_MODEL",
    "OWNER_APPROVED_VERIFIER_MODEL",
    "PARENT_MEASUREMENT_ID",
    "ProviderRoleViolationError",
    "REQUIRES_A9_PATIENT_SCOPE_AUTHORITY",
    "REQUIRES_PLANNER_MODEL_PLUS",
    "RETRY_COUNT_MAX",
    "S69_DELETED_LEGACY_MODULES",
    "S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS",
    "SUITE_ID",
    "TURNS_PATH",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_authority_env_before_import",
    "assert_frozen_preflight_abort_artifacts_unchanged",
    "assert_frozen_s62_live_artifacts_unchanged",
    "assert_frozen_s63_live_artifacts_unchanged",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "build_manual_review_seed",
    "build_retry1_attempt_marker_payload",
    "create_attempt_marker_exclusive",
    "finalize_attempt_marker",
    "ledger_entries_balanced",
    "load_attempt_marker",
    "load_frozen_turns",
    "persist_attempt_marker",
    "planner_models_from_ledger",
    "prepare_json_artifact_payload",
    "sha256_file_hex",
]
