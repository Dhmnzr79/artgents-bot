"""PRE-CODE checker for FULLCONTEXT_PRESENTATION_PARITY governance (Phase 1 only)."""

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
    / "FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "50c6cf9"


def test_seam_audit_exists_and_covers_presentation_gaps() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for gap in ("Gap A", "Gap B", "Gap C", "Gap D", "Gap E", "Gap F", "Gap G"):
        assert gap in text
    assert "Choice menu" in text or "choice menu" in text
    assert "max 4" in text.lower() or "≤4" in text
    assert "secondary" in text.lower() and "2 slot" in text.lower()
    assert "used_doc_ids" in text or "source identity" in text.lower()
    assert "normalize_policy_payload" in text
    assert "video=None" in text or "video" in text.lower()
    assert "situation.show=False" in text or "situation" in text.lower()
    assert "marketing_scenarios=()" in text or "marketing_scenarios" in text
    assert "semantic_context" in text
    assert "consultation_value" in text
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()
    assert "NO PRODUCT CHANGE" in text or "NO LIVE" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FULLCONTEXT_PRESENTATION_PARITY" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_fullcontext_presentation_parity_governance.py" in text
    assert "choice menu" in text.lower() or "Choice menu" in text
    assert "max 4" in text.lower() or "до 4" in text
    assert "secondary" in text.lower()
    for n in range(1, 29):
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
    for doc_text in (marketing_arch, foundation, arch_target):
        assert "4" in doc_text and ("choice" in doc_text.lower() or "выбор" in doc_text.lower())
    assert "FULLCONTEXT_PRESENTATION_PARITY" in (
        _REPO_ROOT / "docs" / "ARCHITECTURE_CONVERGENCE.md"
    ).read_text(encoding="utf-8")
    assert "FULLCONTEXT_PRESENTATION_PARITY" in (
        _REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "FULLCONTEXT_PRESENTATION_PARITY" in (
        _REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md"
    ).read_text(encoding="utf-8")


def test_consultation_value_applicability_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "intentionally not applicable to generic content-only fullcontext",
        "validator gap remains",
        "automatic `consultation_value`",
        "exact выбора service/option",
        "generic faq/info/comparison",
        "не должен",
        "получать `consultation_value`",
        "прямой вопрос о консультации",
        "не automatic consultation close",
        "не занимает automatic marketing/amplifier slots",
        "не должна расширять applicability",
        "произвольные `used_doc_ids`",
    )
    for phrase in required:
        assert phrase in combined, phrase

def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
