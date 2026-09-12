"""PRE-CODE checker for FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY governance (Phase 1 only)."""

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
    / "FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "525474c"
MILESTONE = "FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY"


def test_seam_audit_exists_and_covers_generic_fullcontext() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "generic_fullcontext_content",
        "dispatch_field_invalid",
        "needs_clarification",
        "одноразовые материалы",
        "2 приёма",
        "Semantic Verifier",
        "Medical Boundary",
        "allow_price=false",
        "cached FullContext",
        "content-only",
        "source identity",
        "data-gap",
        "NO LIVE",
        "NO LLM",
    ):
        assert phrase in text, phrase
    for section in (
        "## Planner authority split",
        "## Clarification policy",
        "## Phase 1 seam audit checklist",
        "## Forbidden solutions",
    ):
        assert section in text, section


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split(f"# TASK — {MILESTONE} (governance)")[-1]
    assert MILESTONE in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_generic_fullcontext_content_authority_governance.py" in text
    assert "generic_fullcontext_content" in section
    assert "needs_clarification" in section
    assert "allow_price=false" in section or "allow_price" in section
    assert "_orchestrate_ask_turn" in section
    for n in range(1, 31):
        assert f"| {n} |" in section
    assert "NO LIVE" in section
    assert "NO LLM" in section
    assert "NO IMPLEMENTATION" in section or "governance only" in section.lower()


def test_normative_generic_policy_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    for phrase in (
        "advisory",
        "structured",
        "В материалах клиники",
        "partial",
        "malformed",
        "session focus",
        "/ask",
    ):
        assert phrase.lower() in combined.lower(), phrase


def test_forbidden_solutions_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "second pipeline",
        "rag",
        "regex",
        "semantic verifier",
        "frozen",
        "live",
        "legacy fallback",
    ):
        assert phrase in combined, phrase


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        f"# TASK — {MILESTONE} (governance)"
    )[-1]
    for path in (
        "core/target_turn_frame_dispatch.py",
        "core/target_runtime_turn.py",
        "core/target_fullcontext_content_package.py",
        "tests/test_final_generic_fullcontext_content_authority_implementation.py",
    ):
        assert path in section


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
        assert MILESTONE in doc_text


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
