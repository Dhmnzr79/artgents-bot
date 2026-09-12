"""PRE-CODE checker for FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION (Phase 1)."""

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
    / "marketing"
    / "FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "225ee56"
MILESTONE = "FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION"


def test_seam_audit_exists_and_covers_contact_and_marketing_seams() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "Seam A",
        "Seam B",
        "Seam E",
        "clinic_contact:address",
        "resolve_bound_marketing_flags",
        "include_initial_block",
        "shown_amplifier_refs",
        "allowed_topics",
        "TargetScenarioRule",
        "clinic_policies.yaml",
        "natural wrapper",
        "turn_topic",
        "select_target_marketing",
        "ContextVar",
        "Fake Planner",
        "STOP",
    ):
        assert phrase in text, phrase


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert f"# TASK — {MILESTONE} (governance)" in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO IMPLEMENTATION" in task


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


def test_contact_value_verification_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "clinic_policies.yaml",
        "canonical",
        "address_display",
        "clinic_contact",
        "natural wrapper",
        "unicode",
        "no fuzzy",
        "address+parking",
        "unrequested",
        "data-gap",
        "fallback",
        "phone",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_marketing_scenario_activation_normative() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "include_initial_block",
        "marketing_scenarios",
        "shown_amplifier_refs",
        "pain_fear",
        "result_reliability",
        "doctor_trust",
        "allowed_topics",
        "targetscenariorule",
        "service_id=none",
        "direct",
        "no regex",
        "boundary",
        "none",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_planner_semantic_prompt_rules_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "direct price question",
        "direct duration question",
        "direct warranty question",
        "direct doctor question",
        "expressed cost concern",
        "expressed pain concern",
        "expressed reliability concern",
        "marketing_scenarios=[]",
    ):
        assert phrase in combined, phrase


def test_acceptance_verification_layers_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} (governance)")[-1]
    for label in (
        "Verification layers",
        "Producer",
        "Runtime activation",
        "Evidence",
        "Session",
        "P+R+E+S",
        "phone natural wrapper",
        "address natural wrapper",
        "pain concern",
        "reliability concern",
        "direct price question",
        "initial block OFF + scenario ON",
        "shown_amplifier_refs",
        "/ask/stream",
        "not acceptable for layer p",
        "run_planner_turn",
    ):
        assert label.lower() in section.lower(), label


def test_turn_topic_wiring_and_no_contextvar_bypass_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    for path in (
        "core/target_offline_response_package.py",
        "core/target_offline_response_assembly.py",
        "core/target_response_evidence.py",
        "assemble_target_offline_response_package",
    ):
        assert path in combined, path
    assert "ContextVar" in combined or "contextvar" in combined.lower()


def test_fake_planner_not_producer_proof_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "Fake Planner" in combined or "fake Planner" in combined
    assert "turn_planner_llm" in combined


def test_acceptance_matrix_30_scenarios_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} (governance)")[-1]
    # Rows 12–30 plus contacts 1–11
    assert "| 30 |" in section
    for label in (
        "phone natural wrapper",
        "address natural wrapper",
        "pain concern",
        "reliability concern",
        "direct price question",
        "initial block off + scenario on",
        "shown_amplifier_refs",
        "/ask/stream",
    ):
        assert label.lower() in section.lower(), label


def test_widget_faithful_test_contour_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    for phrase in (
        "_orchestrate_ask_turn",
        "build_composer_sdk_messages",
        "/ask/stream",
        "provider boundary",
    ):
        assert phrase in combined, phrase


def test_presentation_limits_preserved() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "choice",
        "secondary",
        "price-detail",
        "shown_amplifier_refs",
        "marketing facts",
    ):
        assert phrase in combined, phrase


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        f"# TASK — {MILESTONE} (governance)"
    )[-1]
    for path in (
        "core/target_response_verifier.py",
        "core/target_presentation_turn_projection.py",
        "core/target_marketing_selector.py",
        "core/target_offline_response_package.py",
        "core/target_offline_response_assembly.py",
        "core/target_response_evidence.py",
        "core/turn_planner_llm.py",
        "contracts/response_schema.py",
        "clients/demo/target_response/marketing.yaml",
        "tests/test_turn_planner_llm.py",
        "tests/test_turn_planner_wiring.py",
        "tests/test_final_contact_value_verification_and_marketing_scenario_activation_implementation.py",
    ):
        assert path in section, path


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
