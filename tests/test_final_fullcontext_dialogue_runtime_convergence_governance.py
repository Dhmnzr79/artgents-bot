"""PRE-CODE checker for FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE governance (Phase 1 only)."""

from __future__ import annotations

import re
from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "runtime"
    / "FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "81cf09c8"


def test_seam_audit_exists_and_covers_runtime_seams() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for seam in ("Seam A", "Seam B", "Seam C", "Seam D", "Seam E", "Seam F"):
        assert seam in text
    assert "spec_package_permission_forbidden" in text
    assert "include_initial_block" in text
    assert "provisional_spec_from_turn_frame" in text
    assert "clinic_contact" in text
    assert "target_fullcontext_verifier_blocked" in text
    assert "build_composer_sdk_messages" in text
    assert "_orchestrate_ask_turn" in text
    assert "target_pipeline_failure" in text
    assert "logs/demo-app.jsonl" in text
    assert "NO PRODUCT" in text.upper() or "NO LIVE" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split(
        "# TASK — FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE (governance)"
    )[-1]
    assert "FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_fullcontext_dialogue_runtime_convergence_governance.py" in text
    assert "spec_package_permission_forbidden" in section
    assert "include_initial_block" in section
    assert "_orchestrate_ask_turn" in section
    assert "build_composer_sdk_messages" in section
    for n in range(1, 47):
        assert f"| {n} |" in section
    assert "NO LIVE" in section
    assert "NO LLM" in section
    assert "NO PRODUCT" in section.upper() or "governance only" in section.lower()


def test_owner_decision_docs_synced() -> None:
    arch_target = (_REPO_ROOT / "docs" / "ARCH_TARGET_DESIGN.md").read_text(
        encoding="utf-8"
    )
    convergence = (
        _REPO_ROOT / "docs" / "ARCHITECTURE_CONVERGENCE.md"
    ).read_text(encoding="utf-8")
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (arch_target, convergence, flags, roadmap):
        assert "FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE" in doc_text


def test_marketing_spec_conflict_and_contact_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "provisional",
        "include_initial_block",
        "spec_package_permission_forbidden",
        "marketing_facts",
        "content-only",
        "doctors-only",
        "clinic_policies.yaml",
        "clinic_contact",
        "subaspect",
        "primary_evidence",
        "target_pipeline_failure",
        "optional marketing",
        "consult_nudge",
        "guide_router",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_widget_faithful_test_contour_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    for phrase in (
        "_orchestrate_ask_turn",
        "build_composer_sdk_messages",
        "include_initial_block=False",
        "RecordingBackend",
        "run_target_offline_turn_frame_bound_response",
        "/ask/stream",
    ):
        assert phrase in combined, phrase


def test_presentation_invariants_preserved() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "choice",
        "secondary",
        "price-detail",
        "channel mutex",
        "consultation_value",
        "bone_graft",
        "orlov",
        "volkov",
        "no_public_price",
    ):
        assert phrase in combined, phrase


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        "# TASK — FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE (governance)"
    )[-1]
    for path in (
        "core/target_runtime_turn.py",
        "core/target_contact_authority.py",
        "core/target_response_verifier.py",
        "tests/test_final_fullcontext_dialogue_runtime_convergence_implementation.py",
        "scripts/validate_client_pack.py",
    ):
        assert path in section, path


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
