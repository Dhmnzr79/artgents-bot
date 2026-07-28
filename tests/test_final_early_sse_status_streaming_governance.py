"""PRE-CODE checker for FINAL_EARLY_SSE_STATUS_STREAMING / PERF-1 (Phase 1 only).

Covers the governance correction (worker execution context redesign): rejects
`app.test_request_context()` and `flask.copy_current_request_context` as the worker's
Flask-context mechanism, requires the corrected `contextvars` + production
`request_context()` design, bounded worker capacity, and guaranteed terminal-result
delivery to be documented before Phase 2 implementation may begin.
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
    / "FINAL_EARLY_SSE_STATUS_STREAMING_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "228ee28"
CORRECTION_HEAD = "254d859"
MILESTONE = "FINAL_EARLY_SSE_STATUS_STREAMING"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-1 (governance)"


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


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
        "## Worker execution context",
        "## Normative behavior",
        "## Acceptance matrix",
        "## Implementation allowlist",
        "## Bounded worker capacity",
        "## Guaranteed delivery of the terminal result",
    ):
        assert section in text, section


def test_governance_correction_documented() -> None:
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert CORRECTION_HEAD in text
    assert "## Governance correction" in text


def test_test_request_context_explicitly_rejected() -> None:
    """app.test_request_context() must be named and rejected, not silently used."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        assert "test_request_context" in text, label
        assert (
            "Rejected outright" in text
            or "отклонён" in text
            or "rejected" in text.lower()
        ), label


def test_copy_current_request_context_compared_and_rejected() -> None:
    """copy_current_request_context must be compared, with the shared-request.ctx reason."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "copy_current_request_context" in audit
    assert "RequestContext.copy()" in audit or "request=self.request" in audit
    task = TASK_PATH.read_text(encoding="utf-8")
    assert "copy_current_request_context" in task


def test_chosen_worker_context_design_documented() -> None:
    """The corrected design: production request_context() + contextvars, not shared state."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    for phrase in (
        "app.request_context(environ)",
        "contextvars.ContextVar",
        "core/target_composer_action_context.py",
        "hand-built minimal environ",
        "werkzeug.test",
    ):
        assert phrase in audit, phrase
    section = _task_section()
    combined = section.lower()
    for phrase in (
        "background worker thread",
        "bounded",
        "guaranteed",
        "bind_session_client",
        "run_target_fullcontext_runtime_turn",
        "app.request_context(environ)".lower(),
        "contextvar",
    ):
        assert phrase in combined, phrase


def test_finally_cleanup_of_three_bindings_documented() -> None:
    """client_id ContextVar, session thread-local, and event-sink must all reset in finally."""
    section = _task_section()
    combined = section.lower()
    for phrase in ("finally", "client_id", "session", "event-sink"):
        assert phrase in combined, phrase


def test_bounded_worker_capacity_documented() -> None:
    section = _task_section()
    combined = section.lower()
    assert "bounded worker capacity" in combined or "bounded capacity" in combined
    assert "синхронное вычисление" in section or "synchronous" in combined


def test_guaranteed_terminal_delivery_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "## Guaranteed delivery of the terminal result" in audit
    assert "lossy" in audit
    section = _task_section()
    assert "негубящий" in section or "guaranteed" in section.lower()


def test_pg_sink_precedent_correction_documented() -> None:
    """pg_sink.py must not be cited as sufficient proof — fire-and-forget vs session writes."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "not sufficient proof" in audit
    assert "fire-and-forget" in audit
    section = _task_section()
    assert "fire-and-forget" in section.lower() or "corrected framing" in section.lower()


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert CORRECTION_HEAD in task
    assert "NO PRODUCT IMPLEMENTATION" in task
    assert "test_final_early_sse_status_streaming_governance.py" in task


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
    section = _task_section()
    for n in range(1, 22):
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
    section = _task_section()
    for path in (
        "app.py",
        "core/turn_timing.py",
        "core/target_sse_worker_context.py",
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
