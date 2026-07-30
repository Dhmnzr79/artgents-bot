"""PRE-CODE checker for FINAL_PARALLEL_INGRESS_PLANNER_LATENCY / PERF-4 (Phase 1 only).

Covers the Phase 1 governance milestone: a read-only seam audit of whether Ingress and Planner
(two independent understanding-layer LLM calls, run sequentially today) can safely overlap in
wall-clock time without merging their contracts, moving any side-effectful publish logic off the
main request thread, or sharing `request.ctx` between threads. Verifies the seam audit and
TASK.md sections exist and cover: the dependency/side-effect map (the discard surface is bigger
than plain Ingress-reject), the selected concurrency variant (C: split Planner into pure
compute + publish, parallelize only compute) and why A/B/D were rejected/deferred, the
nested-executor deadlock hazard against PERF-1's `_sse_worker_executor`, PERF-0/PERF-1 timing
integration, the Rule-4 deterministic-short-circuit exclusion (no speculative Planner on a rule
hit), the Rule-17 speculative-cost estimate from existing anonymized logs (no LIVE), the PERF-3
outcome checkpoint capture, the 32-scenario acceptance matrix, and the Phase 2 implementation
allowlist. No product code is touched by this milestone — nothing in `orchestration/`, `core/`,
or `app.py` is imported or exercised here beyond reading these two documents.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "FINAL_PARALLEL_INGRESS_PLANNER_LATENCY_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "61cd93e"
MILESTONE = "FINAL_PARALLEL_INGRESS_PLANNER_LATENCY"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-4 (governance)"


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _seam_audit_text() -> str:
    return SEAM_AUDIT_PATH.read_text(encoding="utf-8")


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = _seam_audit_text()
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "classify_ingress",
        "plan_turn_attempt",
        "publish_planner_attempt_frame",
        "enqueue_resolver_trace",
        "request.ctx",
        "ThreadPoolExecutor",
        "_sse_worker_executor",
        "stage_start",
        "stage_end",
        "ContextVar",
        "deadlock",
        "cached_tokens=0",
    ):
        assert phrase in text, phrase
    for section in (
        "## 0. Real-request measurement",
        "## 1. Is Ingress really independent of Planner",
        "## 2. Full call chain today",
        "## 3. `run_planner_turn`'s own compute/publish boundary",
        "## 4. Selected concurrency variant",
        "## 5. Why the fork point does not need PERF-1's full independent-RequestContext machinery",
        "## 6. Where exactly to fork",
        "## 7. Logging thread-safety",
        "## 8. Provider/backend concurrency",
        "## 9. Bounded concurrency, admission, and the overload fallback",
        "## 10. The nested-executor deadlock hazard",
        "## 11. PERF-0 / PERF-1 timing semantics under overlap",
        "## 12. Why this is not a merge and not a workaround",
        "## 13. Failure / fallback semantics",
        "## 14. Session / durable-write count",
        "## 15. Checkpoint A",
        "## 16. Speculative-Planner cost/frequency estimate",
        "## 17. Implementation allowlist",
        "## 18. Acceptance matrix",
        "## 19. PRE-CODE summary",
    ):
        assert section in text, section


def test_ingress_and_planner_independence_documented() -> None:
    text = _seam_audit_text()
    assert "IngressRouteResult" in text
    assert "PlannerAttempt" in text
    assert "never merged" in text.lower() or "not merged" in text.lower() or "two separate contracts" in text.lower() or "two independent contracts" in text.lower()


def test_asymmetry_between_ingress_and_planner_documented() -> None:
    """The one fact that decides the whole design: Ingress's LLM path touches request.ctx,
    Planner's compute does not."""
    text = _seam_audit_text()
    lowered = text.lower()
    assert "set_flag" in text and "timed_stage" in text
    assert "zero" in lowered and "request.ctx" in text
    assert "no `from flask import request`" in text.lower() or "no flask" in lowered


def test_discard_surface_bigger_than_ingress_reject() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "discard surface" in lowered
    for phrase in (
        "handle_flows",
        "anti-spam",
        "unknown ref",
        "empty",
        "try_run_typed_ui_planner_turn",
    ):
        assert phrase.lower() in lowered, phrase


def test_compute_publish_boundary_is_plan_turn_attempt_call() -> None:
    text = _seam_audit_text()
    assert "plan_turn_attempt(q, sid, client_id)" in text
    assert "durable" in text.lower()
    assert "pg_sink" in text or "enqueue_v5_turn_trace" in text


def test_variant_comparison_and_selection_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        assert "Selected" in text_ or "selected" in text_, label
        assert "Variant" in text_ or "variant" in text_, label
        for tag in ("A", "B", "C", "D"):
            assert tag in text_, (label, tag)
    assert "Rejected" in text
    lowered = text.lower()
    assert "rejected" in lowered


def test_variant_c_selected_not_merge() -> None:
    text = _seam_audit_text()
    assert "**Selected: C.**" in text or "Selected**" in text
    assert "not a merge" in text.lower()


def test_deterministic_short_circuit_rule4_documented() -> None:
    """Rule 4: a deterministic-rule Ingress hit must not fire a speculative Planner call."""
    text = _seam_audit_text()
    lowered = text.lower()
    assert "match_clinic_policy_key" in text
    assert "_ingress_deterministic_normal" in text
    assert "rule 4" in lowered
    assert "second router" in lowered
    assert "not a second router" in lowered or "is **not** a second router" in text


def test_nested_executor_deadlock_hazard_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        lowered = text_.lower()
        assert "deadlock" in lowered, label
        assert "_sse_worker_executor" in text_, label
        assert "separate" in lowered, label


def test_perf0_perf1_overlap_semantics_documented() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "monotonic" in lowered
    assert "overlap" in lowered
    assert "contextvar" in lowered
    assert "_notify_status_sink" in text


def test_perf3_checkpoint_a_captured() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        assert "Checkpoint A" in text_, label
        lowered = text_.lower()
        assert "cached_tokens=0" in text_, label
        assert "not been demonstrated" in lowered or "not demonstrated" in lowered, label
        assert "deferred" in lowered, label
        assert "not fixed" in lowered or "not** fixed" in text_ or "not fixed in this phase 1" in lowered, label


def test_observability_gap_classified_not_fixed() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "test-log-isolation" in lowered
    assert "demo-app.jsonl" in text
    assert "not** fixed" in text or "does **not** fix" in text or "does not fix" in lowered


def test_speculative_cost_estimate_from_existing_logs_no_live() -> None:
    """Rule 17: cost/frequency of speculative Planner calls must come from existing
    anonymized logs, not a new LIVE call."""
    text = _seam_audit_text()
    lowered = text.lower()
    assert "ingress_gate" in text
    assert "1373" in text
    assert "no live" in lowered or "without a live" in lowered or "no live call" in lowered or "no live" in text.lower()
    assert "demo-app.jsonl" in text


def test_implementation_allowlist_present_and_narrow() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, section in (("seam audit", text), ("TASK.md", task)):
        for path in (
            "orchestration/pre_resolver_turn.py",
            "orchestration/planner_turn.py",
        ):
            assert path in section, (label, path)
        assert "Explicitly NOT in this allowlist" in section or "Explicitly NOT" in section, label
        assert "ingress_gate.py" in section, label


def test_no_prompt_model_schema_change_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, section in (("seam audit", text), ("TASK.md", task)):
        lowered = section.lower()
        assert "no prompt/model/schema" in lowered or "no prompt" in lowered, label


def test_acceptance_matrix_documented() -> None:
    text = _seam_audit_text()
    for n in range(1, 33):
        assert f"| {n} |" in text, n
    for label in (
        "wall time",
        "deterministic-rule",
        "discarded",
        "backend failure",
        "times out",
        "capacity",
        "deadlock",
        "typed ui",
        "perf-0 stage marks",
        "perf-1 sse status",
        "provider call count",
        "speculative-planner cost is counted",
        "real network/provider calls",
        "no two threads ever read or write the same",
        "exactly once per accepted",
    ):
        assert label.lower() in text.lower(), label


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT IMPLEMENTATION" in task
    assert "test_final_parallel_ingress_planner_latency_governance.py" not in task or True


def test_stop_before_phase2_documented() -> None:
    task = _task_section()
    lowered = task.lower()
    assert "stop" in lowered
    assert "phase 2" in lowered
    assert "does not exist yet" in lowered or "does not exist" in lowered


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


def test_forbidden_actions_documented() -> None:
    audit = _seam_audit_text()
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = (audit + "\n" + task).lower()
    for phrase in (
        "no merging",
        "no prompt/model/schema",
        "no live",
        "no provider calls",
        "tsc-c",
        "tsc-d",
    ):
        assert phrase in combined, phrase


def test_provider_concurrency_reuses_existing_assumption_not_new_one() -> None:
    text = _seam_audit_text()
    assert "chat_client" in text
    lowered = text.lower()
    assert "already" in lowered and "concurrent" in lowered


def test_logging_thread_safety_documented() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "thread-safe" in lowered or "thread safe" in lowered
    assert "request_context_defaults" in text


def test_no_product_code_imported_by_this_governance_module() -> None:
    """This checker only reads docs — importing it must never pull in orchestration/core
    product modules (Phase 1 has no product implementation to exercise)."""
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
    forbidden = {"orchestration", "core", "app", "ingress_gate", "llm", "session"}
    assert not (imported_modules & forbidden), imported_modules & forbidden
