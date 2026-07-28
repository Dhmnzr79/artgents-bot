"""PRE-CODE checker for FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION (Phase 1)."""

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
    / "presentation"
    / "FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "ce256c5"
MILESTONE = "FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION"


def test_seam_audit_exists_and_covers_cta_projection_seams() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "| A |",
        "| F |",
        "| G |",
        "| H |",
        "| I |",
        "| J |",
        "implantation__faq__pain.md",
        "allow_cta=False",
        "selected_cta_key",
        "primary_content_ref",
        "read_doc_presentation_meta",
        "lead_cta_dict_from_meta",
        "build_target_runtime_widget_cta",
        "project_verified_primary_content_cta",
        "Я боюсь боли",
        "STOP",
    ):
        assert phrase in text, phrase


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert f"# TASK — {MILESTONE} (governance)" in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO IMPLEMENTATION" in task or "governance only" in task.lower()
    assert "test_final_verified_primary_content_cta_projection_governance.py" in task


def test_owner_decision_docs_synced() -> None:
    arch_target = (_REPO_ROOT / "docs" / "ARCH_TARGET_DESIGN.md").read_text(encoding="utf-8")
    convergence = (_REPO_ROOT / "docs" / "ARCHITECTURE_CONVERGENCE.md").read_text(encoding="utf-8")
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (arch_target, convergence, flags, roadmap):
        assert MILESTONE in doc_text


def test_verified_primary_cta_projection_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "validated primary_content_ref",
        "allow_cta=true",
        "do not",
        "used_content_refs",
        "marketing_scenarios",
        "lead_cta_dict_from_meta",
        "load_lead_cta_variants",
        "warning",
        "service/price",
        "priority",
        "choice",
        "secondary",
        "price-detail",
        "terminal",
        "medical handoff",
        "verifier",
        "no regex",
        "no new selector",
        "no new routes",
        "implantation__faq__pain",
        "cta_key: consult",
        "/ask/stream",
        "widget_config.json",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_global_allow_cta_not_widened() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "allow_cta=True globally" in combined or "allow_cta=True` globally" in combined
    assert "build_generic_fullcontext_content_policy_request" in combined
    assert "post-Verifier" in combined or "post-verifier" in combined.lower()


def test_acceptance_matrix_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} (governance)")[-1]
    for n in range(1, 11):
        assert f"| {n} |" in section
    for label in (
        "Я боюсь боли",
        "starter",
        "invented",
        "explicit service",
        "leadflow",
        "/ask/stream",
    ):
        assert label.lower() in section.lower(), label


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        f"# TASK — {MILESTONE} (governance)"
    )[-1]
    for path in (
        "core/target_verified_primary_content_cta_projection.py",
        "core/target_verified_response_pipeline.py",
        "core/client_config_loader.py",
        "core/target_presentation_source_identity.py",
        "core/target_runtime_widget.py",
        "tests/test_final_verified_primary_content_cta_projection_implementation.py",
    ):
        assert path in section, path


def test_verifier_unchanged_in_phase1() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "NO Verifier" in combined or "No Verifier" in combined
    assert "target_response_verifier.py" not in combined.split("implementation")[0].split(
        "Allowlist (implementation"
    )[-1] if "Allowlist (implementation" in combined else True


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
