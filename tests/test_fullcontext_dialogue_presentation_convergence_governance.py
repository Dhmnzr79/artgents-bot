"""PRE-CODE checker for FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE governance (Phase 1 only)."""

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
    / "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "7c716df"


def test_seam_audit_exists_and_covers_dialogue_gaps() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for gap in ("Gap H", "Gap I", "Gap J", "Gap K", "Gap L", "Gap M", "Gap N"):
        assert gap in text
    assert "source identity" in text.lower() or "used_content_refs" in text
    assert "PRIMARY_EVIDENCE" in text
    assert "one navigation channel" in text.lower() or "channel mutex" in text.lower()
    assert "situation" in text.lower()
    assert "time" in text and "result_reliability" in text
    assert "canonical phone" in text.lower() or "fallback" in text.lower()
    assert "attribution_kind" in text
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()
    assert "NO PRODUCT CHANGE" in text or "NO LIVE" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_fullcontext_dialogue_presentation_convergence_governance.py" in text
    assert "Gap H" in text or "source identity sidecar" in text.lower()
    assert "channel" in text.lower()
    assert "PRIMARY_EVIDENCE" in text
    for n in range(1, 21):
        assert f"| {n} |" in text
    assert "NO LIVE" in text
    assert "NO LLM" in text
    assert "NO PRODUCT" in text.upper() or "governance only" in text.lower()


def test_owner_decision_docs_synced() -> None:
    marketing_arch = (
        _REPO_ROOT / "docs" / "MARKETING_SCENARIO_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")
    foundation = (
        _REPO_ROOT / "docs" / "MARKETING_QUESTION_FOUNDATION.md"
    ).read_text(encoding="utf-8")
    arch_target = (_REPO_ROOT / "docs" / "ARCH_TARGET_DESIGN.md").read_text(
        encoding="utf-8"
    )
    authoring = (_REPO_ROOT / "docs" / "CLIENT_PACK_AUTHORING.md").read_text(
        encoding="utf-8"
    )
    for doc_text in (marketing_arch, foundation, arch_target):
        assert "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE" in doc_text
    assert "clinic_policies.yaml" in authoring
    assert "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE" in (
        _REPO_ROOT / "docs" / "ARCHITECTURE_CONVERGENCE.md"
    ).read_text(encoding="utf-8")
    assert "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE" in (
        _REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE" in (
        _REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md"
    ).read_text(encoding="utf-8")


def test_contact_authority_and_fallback_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "primary_evidence",
        "clinic_policies.yaml",
        "clinic__info__contacts",
        "whatsapp",
        "canonical phone",
        "attribution_kind=plain",
        "composer must not invent phone",
        "consultation_value",
        "generic faq",
        "time",
        "result_reliability",
        "one response",
        "navigation channel",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_consultation_value_preserve_unchanged() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "exact service/option",
        "generic faq",
        "consultation_value",
        "do not widen",
    ):
        assert phrase in combined, phrase


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
