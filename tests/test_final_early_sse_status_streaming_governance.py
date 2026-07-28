"""PRE-CODE checker for FINAL_EARLY_SSE_STATUS_STREAMING / PERF-1 (Phase 1 only)."""

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
    / "FINAL_EARLY_SSE_STATUS_STREAMING_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "228ee28"
MILESTONE = "FINAL_EARLY_SSE_STATUS_STREAMING"


def test_seam_audit_exists_and_covers_mechanism_comparison() -> None:
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
        "_orchestrate_ask_turn",
        "_sse_service_reply",
        "_dispatch_orchestration_sse",
        "request.ctx",
        "threading.local",
        "bind_session_client",
        "pg_sink.py",
        "queue.Queue",
        "test_request_context",
        "text_delta",
        "STOP",
    ):
        assert phrase in text, phrase
    for section in (
        "### A —",
        "### B —",
        "### C —",
        "### D —",
        "## Chosen target mechanism",
        "## Normative behavior",
        "## Acceptance matrix",
        "## Implementation allowlist",
    ):
        assert section in text, section


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert f"# TASK — {MILESTONE} / PERF-1 (governance)" in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT IMPLEMENTATION" in task
    assert "test_final_early_sse_status_streaming_governance.py" in task


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


def test_chosen_mechanism_is_b_with_reasoning() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} / PERF-1 (governance)")[-1]
    combined = section.lower()
    for phrase in (
        "background worker thread",
        "bounded",
        "guaranteed",
        "bind_session_client",
        "test_request_context",
        "run_target_fullcontext_runtime_turn",
    ):
        assert phrase.lower() in combined, phrase


def test_forbidden_phase1_actions_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    for phrase in (
        "composer token streaming",
        "text_delta",
        "boundary bypass",
        "verifier change",
        "prewarm",
        "answer cache",
        "ingress + planner merge",
        "ux redesign",
        "frozen artifact",
        "tsc-c",
        "tsc-d",
    ):
        assert phrase in combined, phrase


def test_acceptance_matrix_documented() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    section = task.split(f"# TASK — {MILESTONE} / PERF-1 (governance)")[-1]
    for n in range(1, 17):
        assert f"| {n} |" in section
    for label in (
        "structured contacts",
        "typed ui",
        "terminal",
        "exception",
        "/ask/stream",
        "disconnect",
        "pii",
    ):
        assert label.lower() in section.lower(), label


def test_implementation_allowlist_present() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(
        f"# TASK — {MILESTONE} / PERF-1 (governance)"
    )[-1]
    for path in (
        "app.py",
        "core/turn_timing.py",
        "static/widget/api.js",
        "static/widget/widget.js",
        "tests/test_final_early_sse_status_streaming_implementation.py",
    ):
        assert path in section, path


def test_ask_endpoint_and_session_kept_unchanged_in_phase1_docs() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "KEEP unchanged" in combined
    assert "/ask" in combined


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
