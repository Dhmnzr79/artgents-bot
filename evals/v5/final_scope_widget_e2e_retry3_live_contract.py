"""Frozen contract for FINAL scope/widget E2E retry3 live runtime eval."""

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
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    FROZEN_RETRY1_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY2_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY2_LIVE_STDOUT_SIZE,
    VERIFIED_FORENSIC_RETRY1_STDOUT_PATH,
    VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256,
    VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_retry2_live_artifacts_unchanged,
)
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

MEASUREMENT_ID = "final_scope_widget_e2e_retry3"
SUITE_ID = "final_scope_widget_e2e_retry3"
PARENT_MEASUREMENT_ID = "final_scope_widget_e2e_retry2"

MAX_PROVIDER_CALLS = 34
MAX_INGRESS_CALLS = 5
MAX_PLANNER_CALLS = 5
MAX_BOUNDARY_CALLS = 8
MAX_COMPOSER_CALLS = 8
MAX_VERIFIER_CALLS = 8

EXPECTED_FREE_TEXT_PLANNER_CALLS = 5
TYPED_UI_TURNS_NO_PLANNER = frozenset({2, 6, 7})

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_audit.log"
LIVE_STDOUT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry3_live_stdout.log"

DEFAULT_LIVE_ARTIFACT_PATHS = (
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_AUDIT_LOG_PATH,
    LIVE_STDOUT_LOG_PATH,
)

FROZEN_RETRY3_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_attempt.json": (
        "c3f4fe0cab32ac0a4e94c3b140f10f415036c6f34cffc8463975be47920e66d8"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_call_ledger.jsonl": (
        "1eeed9f6682e849020e54a51db8a0502046b69993ebc8f5bf74350d6a321dbd4"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_live_stdout.log": (
        "1b74cc08844a02c540231167fe91dfac25a5f0edeee441442c550633107b7e49"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_result.json": (
        "bbab70c9e55392d037921c091a1ed75c26cf06a6673d9d3181cbe650d3c1fb81"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_raw.json": (
        "bbab70c9e55392d037921c091a1ed75c26cf06a6673d9d3181cbe650d3c1fb81"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_manifest.json": (
        "c64e4054e5107c88e0ad69478100b6310fd4ea2ea41021034e535d5caa3cb3d3"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_manual_review.json": (
        "8ebd862da11c437f74f1f1cafd491786f9a03191562a0de9fd21f651bb59d3f5"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry3_audit.log": (
        "f333a52f3a707f8ed8ff1249bf9075acadc34195d146ffbaddc1b81899ebbea4"
    ),
}

FROZEN_RETRY3_LIVE_STDOUT_SIZE = 536_241

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


def build_retry3_attempt_marker_payload(
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
    payload["max_provider_calls"] = MAX_PROVIDER_CALLS
    payload["role_budget_caps"] = {
        "ingress": MAX_INGRESS_CALLS,
        "planner": MAX_PLANNER_CALLS,
        "medical_boundary": MAX_BOUNDARY_CALLS,
        "composer": MAX_COMPOSER_CALLS,
        "semantic_verifier": MAX_VERIFIER_CALLS,
    }
    return payload


def assert_retry3_live_artifacts_absent() -> None:
    assert_live_artifacts_absent(DEFAULT_LIVE_ARTIFACT_PATHS)


def assert_frozen_retry3_live_artifacts_unchanged() -> None:
    for rel, expected in FROZEN_RETRY3_LIVE_ARTIFACT_SHA256.items():
        path = _REPO_ROOT / rel
        if not path.is_file():
            raise HarnessConfigError(f"frozen retry3 artifact missing: {rel}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen retry3 artifact sha256 mismatch for {rel}: "
                f"expected={expected} actual={actual}"
            )


__all__ = [
    "ALLOWED_PROVIDER_ROLES",
    "ATTEMPT_MARKER_EXISTS_CODE",
    "AuthorityEnvError",
    "CLIENT_ID",
    "DEFAULT_LIVE_ARTIFACT_PATHS",
    "EXPECTED_FREE_TEXT_PLANNER_CALLS",
    "FROZEN_RETRY1_LIVE_ARTIFACT_SHA256",
    "FROZEN_RETRY2_LIVE_ARTIFACT_SHA256",
    "FROZEN_RETRY2_LIVE_STDOUT_SIZE",
    "FROZEN_RETRY3_LIVE_ARTIFACT_SHA256",
    "FROZEN_RETRY3_LIVE_STDOUT_SIZE",
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
    "LIVE_STDOUT_LOG_PATH",
    "LiveArtifactExistsError",
    "MAX_BOUNDARY_CALLS",
    "MAX_COMPOSER_CALLS",
    "MAX_HTTP_TURNS",
    "MAX_INGRESS_CALLS",
    "MAX_PLANNER_CALLS",
    "MAX_PROVIDER_CALLS",
    "MAX_VERIFIER_CALLS",
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
    "TYPED_UI_TURNS_NO_PLANNER",
    "TURNS_PATH",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_PATH",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_authority_env_before_import",
    "assert_frozen_preflight_abort_artifacts_unchanged",
    "assert_frozen_retry1_live_artifacts_unchanged",
    "assert_frozen_retry2_live_artifacts_unchanged",
    "assert_frozen_s62_live_artifacts_unchanged",
    "assert_frozen_s63_live_artifacts_unchanged",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "assert_frozen_retry3_live_artifacts_unchanged",
    "assert_retry3_live_artifacts_absent",
    "build_manual_review_seed",
    "build_retry3_attempt_marker_payload",
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
