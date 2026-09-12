"""PRE-CODE checker for MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH governance (Phase 1 only)."""

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
    / "MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "f556130"


def test_seam_audit_exists_and_covers_both_defects() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "KeyError" in text or 'KeyError: \'"answer"\'' in text
    assert "dispatch_field_invalid" in text
    assert "aspects_empty" in text
    assert "build_composer_sdk_messages" in text
    assert "topic == \"doctors\"" in text or "topic=doctors" in text
    assert "evals/v5/fullcontext_response_eval_live_backend" in text
    assert "NO PRODUCT" in text.upper() or "no product code" in text.lower()
    assert "NO LIVE" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split("# TASK — MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH (governance)")[-1]
    assert "MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "test_mass_composer_template_and_doctors_dispatch_governance.py" in text
    assert "build_composer_sdk_messages" in section
    assert "target_turn_frame_dispatch" in section
    for n in range(1, 21):
        assert f"| {n} |" in section
    assert "NO LIVE" in section
    assert "NO LLM" in section
    assert "NO PRODUCT" in section.upper() or "governance only" in section.lower()


def test_offline_repro_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    for phrase in (
        "KeyError",
        "dispatch_field_invalid",
        "Кто ваши врачи",
        "костная пластика",
        "target_fullcontext_error",
        "logs/demo-app.jsonl",
    ):
        assert phrase in combined, phrase


def test_forbidden_solutions_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "try/except",
        "per-route",
        "regex",
        "answer + source_identity",
        "frozen",
        "recordingbackend",
        "build_composer_sdk_messages",
    ):
        assert phrase in combined, phrase


def test_implementation_allowlist_and_runtime_matrix() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        "# TASK — MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH (governance)"
    )[-1]
    for path in (
        "core/target_runtime_llm_messages.py",
        "core/target_turn_frame_dispatch.py",
        "tests/test_mass_composer_template_and_doctors_dispatch_implementation.py",
        "tests/test_target_runtime_llm_messages.py",
    ):
        assert path in section
    for case in (
        "адрес",
        "костная пластика",
        "Кто ваши врачи",
        "price",
        "generic faq",
    ):
        assert case.lower() in section.lower()


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
