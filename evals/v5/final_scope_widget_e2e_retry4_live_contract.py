"""Frozen contract for FINAL scope/widget E2E retry4 live runtime eval."""

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
from evals.v5.final_scope_widget_e2e_retry3_live_contract import (
    FROZEN_RETRY3_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY3_LIVE_STDOUT_SIZE,
    assert_frozen_retry3_live_artifacts_unchanged,
)
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
    prepare_json_artifact_payload,
    sha256_file_hex,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

MEASUREMENT_ID = "final_scope_widget_e2e_retry4"
SUITE_ID = "final_scope_widget_e2e_retry4"
PARENT_MEASUREMENT_ID = "final_scope_widget_e2e_retry3"

MAX_PROVIDER_CALLS = 34
MAX_INGRESS_CALLS = 5
MAX_PLANNER_CALLS = 5
MAX_BOUNDARY_CALLS = 8
MAX_COMPOSER_CALLS = 8
MAX_VERIFIER_CALLS = 8

EXPECTED_FREE_TEXT_PLANNER_CALLS = 5
TYPED_UI_TURNS_NO_PLANNER = frozenset({2, 6, 7})

MANUAL_REVIEW_RUBRIC: dict[int, str] = {
    1: "compact_overview",
    2: "full_arch_prices",
    6: "concise_stage_clarification",
    7: "crown_price",
}

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_audit.log"
LIVE_STDOUT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry4_live_stdout.log"

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

FROZEN_RETRY4_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_attempt.json": (
        "3459868df40d47c841ad2ef4eacb38a69be7bb73b42694af30279940dfabc0df"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_call_ledger.jsonl": (
        "1028f978742ed84480a9f6d22c0b86110bbcecfd3115ccfd55d19c4d9c7112ae"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_live_stdout.log": (
        "4e140d20b4ffee4abdcf23998e9391ae6e2bf4ac23a1082b20c8a483ddac60eb"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_result.json": (
        "8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_raw.json": (
        "8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_manifest.json": (
        "46f5ea55537e3514dd8b40d44f37d08f60a4324646aabbecc74d444acc1fba90"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_manual_review.json": (
        "4bd76e3eb73d25b2002fcb078ce536b7b4acf7ffade8098e86bb0dc570bb2459"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry4_audit.log": (
        "2f55b8991b2775e02f798daf948057bd8d7f73208a66993be18d772a43a0ac2a"
    ),
}

FROZEN_RETRY4_LIVE_STDOUT_SIZE = 1_064_490

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


def build_retry4_attempt_marker_payload(
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
    payload["manual_review_rubric"] = {
        str(turn): criterion for turn, criterion in sorted(MANUAL_REVIEW_RUBRIC.items())
    }
    return payload


def assert_retry4_live_artifacts_absent() -> None:
    assert_live_artifacts_absent(DEFAULT_LIVE_ARTIFACT_PATHS)


def assert_frozen_retry4_live_artifacts_unchanged() -> None:
    for rel, expected in FROZEN_RETRY4_LIVE_ARTIFACT_SHA256.items():
        path = _REPO_ROOT / rel
        if not path.is_file():
            raise HarnessConfigError(f"frozen retry4 artifact missing: {rel}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen retry4 artifact sha256 mismatch for {rel}: "
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
    "FROZEN_RETRY4_LIVE_ARTIFACT_SHA256",
    "FROZEN_RETRY4_LIVE_STDOUT_SIZE",
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
    "MANUAL_REVIEW_RUBRIC",
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
    "assert_frozen_retry3_live_artifacts_unchanged",
    "assert_frozen_retry4_live_artifacts_unchanged",
    "assert_frozen_s62_live_artifacts_unchanged",
    "assert_frozen_s63_live_artifacts_unchanged",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "assert_retry4_live_artifacts_absent",
    "build_manual_review_seed",
    "build_retry4_attempt_marker_payload",
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
