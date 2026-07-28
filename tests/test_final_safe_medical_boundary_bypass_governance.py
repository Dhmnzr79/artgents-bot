"""PRE-CODE checker for FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS / PERF-2 (Phase 1 only).

Enforces: governance-only phase (no product resolver module exists yet), no
raw-text/regex/phrase-list/topic-hardcode bypass routing, Boundary stays required
for medical/personal scenarios, Verifier remains unconditional, exact implementation
allowlist documented, PERF-0/PERF-1 integration (stage_skipped reuse) documented, and
no demo-specific service IDs baked into the governance docs.
"""

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
    / "performance"
    / "FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "aa633f2"
MILESTONE = "FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-2 (governance)"

# Phase 2 files -- must NOT exist yet. Their presence would mean product implementation
# started before PRE-CODE + a separate owner GO, which this phase forbids.
_FORBIDDEN_PRODUCT_FILES = (
    _REPO_ROOT / "contracts" / "target_medical_boundary_requirement.py",
    _REPO_ROOT / "core" / "target_medical_boundary_requirement.py",
    _REPO_ROOT / "tests" / "test_final_safe_medical_boundary_bypass_implementation.py",
)


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "Ingress",
        "Planner",
        "Boundary",
        "Composer",
        "Verifier",
        "stage_start",
        "stage_end",
        "stage_skipped",
        "TurnFrame",
        "UiScopeAction",
        "UiStageAction",
        "needs_clarification",
        "patient_scope",
        "marketing_scenarios",
        "structured_capability",
        "resolve_structured_answer_capability",
        "STOP",
    ):
        assert phrase in text, phrase
    for section in (
        "## 1. Map:",
        "## 2. All current Boundary outcomes",
        "## 3. TurnFrame",
        "## 4. Eligibility analysis",
        "## 5. Hard exclusions",
        "## 6. False-bypass risk assessment",
        "## 7. Estimated savings",
        "## 8. Decision:",
        "## 9. Proof this is not a new router/selector",
        "## 10. Composer/Verifier remain the backstop",
        "## 11. Typed contract",
        "## 12. Implementation allowlist",
        "## 13. Acceptance matrix",
    ):
        assert section in text, section


def test_typed_contract_literal_documented() -> None:
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    for label, source in (("seam audit", text), ("TASK.md", task)):
        assert "TargetMedicalBoundaryRequirement" in source, label
        for value in (
            '"required"',
            '"bypass_governed_ui"',
            '"bypass_pure_price"',
            '"bypass_exact_faq"',
            '"not_applicable_structured"',
        ):
            assert value in source, f"{label}: {value}"
        assert "resolve_target_medical_boundary_requirement" in source, label


def test_only_governed_ui_bypass_is_eligible() -> None:
    """Pure-price and exact-FAQ must be explicitly documented as NOT eligible, never silently guessed."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "ELIGIBLE for Phase 2 implementation" in text
    assert text.count("ELIGIBLE for Phase 2 implementation") == 1
    assert "NOT eligible yet" in text
    assert text.count("NOT eligible yet") >= 2


def test_needs_clarification_blind_spot_documented() -> None:
    """Core safety finding: needs_clarification=False never proves clinical safety."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "a doctor would determine" in text
    assert "not a safety signal" in text
    assert "There is no field on `TurnFrame`" in text


def test_governed_click_structural_guarantees_documented() -> None:
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    for phrase in (
        "if not q:",
        "pre_resolver_turn.py:248",
        "core/target_typed_ui_turn_frame.py",
        "fail-closed",
        "session-bound",
    ):
        assert phrase in text, phrase


def test_no_raw_text_regex_routing_forbidden_documented() -> None:
    section = _task_section()
    for phrase in (
        "raw user text",
        "regex",
        "phrase lists",
        "topic/service hardcode",
        "confidence без typed sufficiency",
    ):
        assert phrase in section, phrase


def test_boundary_required_for_medical_scenarios_documented() -> None:
    section = _task_section()
    for phrase in (
        "suitability",
        "диагноз",
        "противопоказания",
        "medical_handoff",
        "ambiguous",
    ):
        assert phrase in section, phrase


def test_verifier_remains_unconditional_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "unconditionally" in audit
    assert "verifier_semantic" in audit
    assert "verifier_deterministic" in audit


def test_perf0_perf1_integration_documented() -> None:
    combined = SEAM_AUDIT_PATH.read_text(encoding="utf-8") + "\n" + TASK_PATH.read_text(encoding="utf-8")
    for phrase in ("stage_skipped", "turn_timing", "PERF-0", "PERF-1"):
        assert phrase in combined, phrase


def test_resolver_forbidden_from_hardcoding_demo_ids() -> None:
    """The RESOLVER's own decision must never branch on a literal demo service_id/client_id.

    Illustrative service names (e.g. "All-on-4") are expected and required in the acceptance
    matrix's human-readable scenario descriptions (per the milestone brief's own required
    scenarios) -- this checker verifies the *rule* against the resolver special-casing a demo ID
    is documented, not that the string never appears in prose.
    """
    section = _task_section()
    assert "demo-specific" in section.lower() or "конкретной demo-клиники" in section
    assert "service_id" in section
    assert "client_id" in section


def test_product_resolver_not_created_yet() -> None:
    for path in _FORBIDDEN_PRODUCT_FILES:
        assert not path.is_file(), f"Phase 2 file created too early: {path}"


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT IMPLEMENTATION" in task
    assert "test_final_safe_medical_boundary_bypass_governance.py" in task


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


def test_forbidden_phase1_actions_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "boundary prompt/policy change",
        "composer/verifier policy change",
        "new llm call",
        "text_delta",
        "cache/prewarm",
        "ingress + planner merge",
        "tsc-c",
        "tsc-d",
    ):
        assert phrase in combined, phrase


def test_acceptance_matrix_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    for n in range(1, 22):
        assert f"| {n} |" in audit, n
    for label in (
        "governed scope click",
        "governed stage click",
        "invalid/unshown ref",
        "structured",
        "boundary backend failure",
        "numeric verifier",
        "semantic verifier",
        "/ask/stream",
    ):
        assert label.lower() in audit.lower(), label


def test_implementation_allowlist_present() -> None:
    section = _task_section()
    for path in (
        "contracts/target_medical_boundary_requirement.py",
        "core/target_medical_boundary_requirement.py",
        "core/target_runtime_turn.py",
        "tests/test_final_safe_medical_boundary_bypass_implementation.py",
    ):
        assert path in section, path


def test_boundary_composer_verifier_kept_unchanged_in_phase1_docs() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "KEEP unchanged" in combined
    assert "forbidden_topics" in combined


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
