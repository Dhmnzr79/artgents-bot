"""PRE-CODE checker for FINAL_RESPONSE_LATENCY_OBSERVABILITY / PERF-0 (Phase 1 only)."""

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
    / "FINAL_RESPONSE_LATENCY_OBSERVABILITY_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "d381bc9"
MILESTONE = "FINAL_RESPONSE_LATENCY_OBSERVABILITY"


def test_seam_audit_exists_and_covers_pipeline_stages() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "Ingress",
        "Turn Planner",
        "Medical Boundary",
        "Composer",
        "Semantic Verifier",
        "presentation/widget",
        "orchestrate_done",
        "turn_timing.py",
        "time_to_first_composer_token",
        "not_available",
        "verifier_turn",
        "latency_ms",
        "total_ms",
        "structured_capability",
        "clinic_contact",
        "service_availability",
        "log_llm_usage",
        "cached_tokens",
        "call_type",
        "STOP",
    ):
        assert phrase in text, phrase
    for section in (
        "## Master seam table",
        "## Findings",
        "## Existing vs. missing metrics",
        "## Implementation allowlist",
        "## Acceptance matrix",
    ):
        assert section in text, section


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert f"# TASK — {MILESTONE} / PERF-0 (governance)" in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT INSTRUMENTATION" in task
    assert "test_final_response_latency_observability_governance.py" in task


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


def test_required_metrics_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} / PERF-0 (governance)")[-1]
    section_lower = section.lower()
    for phrase in (
        "time_to_first_local_status",
        "time_to_first_server_event",
        "time_to_first_composer_token",
        "time_to_first_meaningful_text",
        "http/sse complete",
        "cache hit/miss",
        "monotonic",
        "request_id",
    ):
        assert phrase in section_lower, phrase


def test_forbidden_phase1_actions_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "pipeline optimization",
        "real streaming",
        "boundary bypass",
        "verifier context",
        "provider prewarm",
        "answer cache",
        "ux redesign",
        "frozen artifact",
        "tsc-c",
        "tsc-d",
        "ingress + planner merge",
    ):
        assert phrase in combined, phrase


def test_acceptance_matrix_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} / PERF-0 (governance)")[-1]
    for n in range(1, 12):
        assert f"| {n} |" in section
    for label in (
        "clinic_contact",
        "service_availability",
        "medical_handoff",
        "terminal",
        "deterministic",
        "semantic",
        "/ask/stream",
    ):
        assert label.lower() in section.lower(), label


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        f"# TASK — {MILESTONE} / PERF-0 (governance)"
    )[-1]
    for path in (
        "core/turn_timing.py",
        "orchestration/pre_resolver_turn.py",
        "ingress_gate.py",
        "orchestration/planner_turn.py",
        "core/target_runtime_turn.py",
        "core/target_composer_executor.py",
        "core/target_response_verifier.py",
        "core/target_runtime_widget.py",
        "app.py",
        "orchestration/finalize_turn.py",
        "static/widget/api.js",
        "static/widget/widget.js",
        "tests/test_final_response_latency_observability_implementation.py",
    ):
        assert path in section, path


def test_verifier_boundary_composer_policy_unchanged_in_phase1() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "no verification logic" in combined.lower() or "NO VERIFIER CONTEXT CHANGE" in combined
    assert "KEEP unchanged" in combined


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
