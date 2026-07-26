"""PRE-CODE checker for FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION governance."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION_SEAM_AUDIT.md"
)

COMMITTED_RETRY1_STDOUT = (
    _REPO_ROOT / "evals" / "v5" / "artifacts" / "final_scope_widget_e2e_retry1_live_stdout.log"
)
UNTRACKED_RETRY1_STDOUT = (
    _REPO_ROOT / "evals" / "v5" / "artifacts" / "_retry1_live_run_stdout.txt"
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

FROZEN_COMMITTED_STDOUT_SIZE = 328_159


def test_seam_audit_exists() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "T2" in text and "T5" in text
    assert "dispatch_target_turn_frame_response" in text


def test_frozen_retry1_live_artifacts_unchanged() -> None:
    for rel, expected in FROZEN_RETRY1_LIVE_ARTIFACT_SHA256.items():
        path = _REPO_ROOT / rel
        assert path.is_file(), f"missing frozen artifact: {rel}"
        actual = sha256_file_hex(path)
        assert actual == expected, f"sha256 mismatch for {rel}: {actual}"


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()


def test_untracked_retry1_stdout_forensic_removed_after_retry2_checkpoint() -> None:
    """Forensic UTF-16 duplicate verified @ RETRY2 pre-live; file must not remain."""
    assert not UNTRACKED_RETRY1_STDOUT.exists()
    assert COMMITTED_RETRY1_STDOUT.is_file()
    assert COMMITTED_RETRY1_STDOUT.stat().st_size == FROZEN_COMMITTED_STDOUT_SIZE
    assert sha256_file_hex(COMMITTED_RETRY1_STDOUT) == (
        FROZEN_RETRY1_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry1_live_stdout.log"
        ]
    )
