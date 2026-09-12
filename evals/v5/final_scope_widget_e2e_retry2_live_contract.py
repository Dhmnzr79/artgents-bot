"""Frozen contract for FINAL scope/widget E2E retry2 live runtime eval."""

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

MEASUREMENT_ID = "final_scope_widget_e2e_retry2"
SUITE_ID = "final_scope_widget_e2e_retry2"
PARENT_MEASUREMENT_ID = "final_scope_widget_e2e_retry1"

LIVE_ARTIFACTS_DIR = _REPO_ROOT / "evals" / "v5" / "artifacts"
LIVE_RAW_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_raw.json"
LIVE_RESULT_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_result.json"
LIVE_MANIFEST_ARTIFACT_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_manifest.json"
LIVE_MANUAL_REVIEW_ARTIFACT_PATH = (
    LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_manual_review.json"
)
LIVE_ATTEMPT_MARKER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_attempt.json"
LIVE_CALL_LEDGER_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_call_ledger.jsonl"
LIVE_AUDIT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_audit.log"
LIVE_STDOUT_LOG_PATH = LIVE_ARTIFACTS_DIR / "final_scope_widget_e2e_retry2_live_stdout.log"

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

FROZEN_RETRY1_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_attempt.json": (
        "283cc05bb2a35990c22cca239e4f43b42478cfdca2858ab05e327e9c33f3ed09"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_call_ledger.jsonl": (
        "2d177af4034d240bce5624424ea961caa54cf67e3df10a1337e960900a714142"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_raw.json": (
        "1cde5b97c620943456f63df374184f4f44de63ca139c9f3c0799c35dbe31ec5a"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_result.json": (
        "1cde5b97c620943456f63df374184f4f44de63ca139c9f3c0799c35dbe31ec5a"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_manifest.json": (
        "3f02f483d223fd0af80fba2bbe98c3e34c03d726128f4134021877bfda6aac6b"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_manual_review.json": (
        "1cde5b97c620943456f63df374184f4f44de63ca139c9f3c0799c35dbe31ec5a"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_audit.log": (
        "1c2205ddd11629053b806a3b1501c6336ee0bd29585c785bffdd815eb2764e92"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry1_live_stdout.log": (
        "5fa434921275aa649c7a63b018fd4236aa1e155218574f87062727a4b420bb31"
    ),
    "docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY1_LIVE_ATTEMPT_AUDIT.md": (
        "5e69af6560d9a8f5f3abb5d791c2eb16913257fc728dfe729ad3da4fc31a31d3"
    ),
}

FROZEN_RETRY2_LIVE_ARTIFACT_SHA256: dict[str, str] = {
    "evals/v5/artifacts/final_scope_widget_e2e_retry2_attempt.json": (
        "deb0e00b0fccc0d3ab6f5e65a67caaacf90677231898e10dc3e9f3893e160671"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry2_call_ledger.jsonl": (
        "db430edc71ff8e3954a83e8d8f1ee9db610755a7549b5e105986940444f460ea"
    ),
    "evals/v5/artifacts/final_scope_widget_e2e_retry2_live_stdout.log": (
        "32b6a1f45660deb171b882bcc568807a5bec6a0c2479917f10e04a48439a00aa"
    ),
}

FROZEN_RETRY2_LIVE_STDOUT_SIZE = 386_867

VERIFIED_FORENSIC_RETRY1_STDOUT_PATH = (
    LIVE_ARTIFACTS_DIR / "_retry1_live_run_stdout.txt"
)
VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256 = (
    "d3e3f159e37e94e0f04b6e1e30a6a7675a2c093c9121f72d78248813c9c3f946"
)
VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE = 634_914

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


def build_retry2_attempt_marker_payload(
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


def assert_frozen_retry1_live_artifacts_unchanged() -> None:
    for rel, expected in FROZEN_RETRY1_LIVE_ARTIFACT_SHA256.items():
        path = _REPO_ROOT / rel
        if not path.is_file():
            raise HarnessConfigError(f"frozen retry1 artifact missing: {rel}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen retry1 artifact sha256 mismatch for {rel}: expected={expected} actual={actual}"
            )


def assert_retry2_live_artifacts_absent() -> None:
    assert_live_artifacts_absent(DEFAULT_LIVE_ARTIFACT_PATHS)


def assert_frozen_retry2_live_artifacts_unchanged() -> None:
    for rel, expected in FROZEN_RETRY2_LIVE_ARTIFACT_SHA256.items():
        path = _REPO_ROOT / rel
        if not path.is_file():
            raise HarnessConfigError(f"frozen retry2 artifact missing: {rel}")
        actual = sha256_file_hex(path)
        if actual != expected:
            raise HarnessConfigError(
                f"frozen retry2 artifact sha256 mismatch for {rel}: "
                f"expected={expected} actual={actual}"
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
    "FROZEN_RETRY2_LIVE_ARTIFACT_SHA256",
    "FROZEN_RETRY2_LIVE_STDOUT_SIZE",
    "FROZEN_RETRY1_LIVE_ARTIFACT_SHA256",
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
    "REQUIRES_PLANNER_MODEL_PLUS",
    "RETRY_COUNT_MAX",
    "S69_DELETED_LEGACY_MODULES",
    "S69_FORBIDDEN_HARNESS_IMPORT_PATTERNS",
    "SUITE_ID",
    "TURNS_PATH",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_PATH",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256",
    "VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE",
    "append_call_ledger_entry",
    "assert_attempt_marker_absent",
    "assert_authority_env_before_import",
    "assert_frozen_preflight_abort_artifacts_unchanged",
    "assert_frozen_retry1_live_artifacts_unchanged",
    "assert_frozen_s62_live_artifacts_unchanged",
    "assert_frozen_s63_live_artifacts_unchanged",
    "assert_frozen_suite_unchanged",
    "assert_live_artifacts_absent",
    "assert_frozen_retry2_live_artifacts_unchanged",
    "assert_retry2_live_artifacts_absent",
    "build_manual_review_seed",
    "build_retry2_attempt_marker_payload",
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
