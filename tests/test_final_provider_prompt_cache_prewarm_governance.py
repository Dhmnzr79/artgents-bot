"""PRE-CODE checker for FINAL_PROVIDER_PROMPT_CACHE_PREWARM / PERF-3 (Phase 1 only).

Enforces: governance-only phase (no product prewarm modules exist yet, no provider calls
of any kind), the seam audit proves prefix identity via verbatim reuse of the existing
Composer/Verifier message builders (not a parallel implementation), the fingerprint design
covers all required components with self-updating content hashes, Composer/Verifier are
proven-separate namespaces, fail-open/retry=0/hard-budget/no-import-time-call rules are
documented, no PII/session/answer-cache, log_llm_usage reuse (no second usage logger), the
two-gate rollout (implementation GO + separate LIVE/LLM permission) is documented, and the
exact Phase 2 allowlist is present.
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
    / "FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "897cdb7"
MILESTONE = "FINAL_PROVIDER_PROMPT_CACHE_PREWARM"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-3 (governance)"

# Phase 2 files -- must NOT exist yet in this governance-only phase. Their presence would
# mean product implementation started before PRE-CODE + a separate owner GO.
_FORBIDDEN_PRODUCT_FILES = (
    _REPO_ROOT / "contracts" / "target_prompt_cache_fingerprint.py",
    _REPO_ROOT / "core" / "target_prompt_cache_prewarm.py",
    _REPO_ROOT / "scripts" / "prewarm_prompt_cache.py",
    _REPO_ROOT / "tests" / "test_final_provider_prompt_cache_prewarm_implementation.py",
)


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "build_composer_sdk_messages",
        "build_verifier_sdk_messages",
        "TARGET_COMPOSER_SYSTEM_POLICY",
        "TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY",
        "cached_full_context",
        "corpus_text",
        "cached_tokens",
        "log_llm_usage",
        "WERKZEUG_RUN_MAIN",
        "gunicorn",
        "fail-open",
        "retry=0",
        "MESSAGE_SERIALIZATION_VERSION",
        "STOP",
    ):
        assert phrase in text, phrase
    for section in (
        "## 1. Producer/consumer map",
        "## 2. Exact current Composer message prefix",
        "## 3. Exact current Semantic Verifier message prefix",
        "## 4. Static/dynamic boundary",
        "## 5. Cache-key / fingerprint design",
        "## 6. Invalidation table",
        "## 7. What a prewarm call would actually send",
        "## 8. What the provider actually caches",
        "## 9. Deployment / reloader / multi-worker audit",
        "## 10. Cost / call budget",
        "## 11. Failure semantics",
        "## 12. Options comparison (A–E)",
        "## Selected:",
        "## 13. Implementation allowlist",
        "## 14. Acceptance matrix",
    ):
        assert section in text, section


def test_no_explicit_cache_api_claim_is_evidenced_not_guessed() -> None:
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "RULED OUT, not supported" in text
    assert "cache_control" in text


def test_composer_verifier_separate_namespaces_proven() -> None:
    """Must be stated as empirically confirmed, not merely a cautious default."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "Confirmed empirically, not assumed" in text
    assert "diverge" in text.lower()


def test_fingerprint_components_documented() -> None:
    section = _task_section()
    for phrase in (
        "client_id",
        "model",
        "role",
        "corpus",
        "sha256",
        "MESSAGE_SERIALIZATION_VERSION",
    ):
        assert phrase in section, phrase


def test_ttl_and_model_alias_explicitly_flagged_unknown() -> None:
    """Rule 18: unknown TTL/aliasing must be explicitly documented, never invented."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "unknown" in text.lower()
    assert "TTL" in text
    assert "not assumed" in text.lower() or "not invent" in text.lower() or "not guessed" in text.lower()


def test_import_time_and_reloader_rules_documented() -> None:
    section = _task_section()
    combined = section.lower()
    for phrase in (
        "_startup_check",
        "__main__",
        "werkzeug_run_main",
        "gunicorn",
    ):
        assert phrase in combined, phrase


def test_fail_open_retry_zero_and_hard_budget_documented() -> None:
    section = _task_section()
    combined = section.lower()
    assert "fail-open" in combined
    assert "retry=0" in combined or "retry = 0" in combined
    assert "budget" in combined


def test_no_pii_session_or_answer_cache_documented() -> None:
    section = _task_section()
    combined = section.lower()
    for phrase in ("sid", "session", "pii", "answer-cache", "телефон"):
        assert phrase in combined, phrase


def test_log_llm_usage_reuse_documented() -> None:
    section = _task_section()
    assert "log_llm_usage" in section
    assert "второй usage logger" in section or "second usage logger" in section.lower()


def test_two_gate_rollout_documented() -> None:
    """Implementation GO is not enough -- a separate LIVE/LLM permission is required too."""
    section = _task_section()
    assert "Two-gate rollout" in section or "two-gate" in section.lower()
    assert "LIVE" in section
    assert "A9" in section or "S66" in section


def test_option_d_not_selected_with_reasoning() -> None:
    """D must be explicitly rejected with the already-observed-implicit-caching reasoning."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "not selected" in text.lower()
    assert "already been observed" in text or "already appear" in text


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT IMPLEMENTATION" in task
    assert "test_final_provider_prompt_cache_prewarm_governance.py" in task


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
        "live / llm / provider calls",
        "composer/verifier prompt change",
        "answer-cache",
        "streaming text",
        "boundary changes",
        "ingress + planner merge",
        "tsc-c",
        "tsc-d",
    ):
        assert phrase in combined, phrase


def test_acceptance_matrix_documented() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    for n in range(1, 25):
        assert f"| {n} |" in audit, n
    for label in (
        "cold request",
        "warm cache hit",
        "cache miss after corpus change",
        "composer/verifier namespaces",
        "duplicate",
        "reloader",
        "multiworker",
        "fail-open",
        "retry=0",
        "hard call budget",
        "zero real provider calls",
        "dry-run",
        "pii",
        "answer persistence",
        "cached_tokens",
        "stale fingerprint",
    ):
        assert label.lower() in audit.lower(), label


def test_implementation_allowlist_present() -> None:
    section = _task_section()
    for path in (
        "contracts/target_prompt_cache_fingerprint.py",
        "core/target_prompt_cache_prewarm.py",
        "scripts/prewarm_prompt_cache.py",
        "app.py",
        "tests/test_final_provider_prompt_cache_prewarm_implementation.py",
    ):
        assert path in section, path


def test_composer_verifier_source_files_kept_unchanged_in_phase1_docs() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "KEEP unchanged" in combined
    assert "target_composer_executor.py" in combined
    assert "target_response_verifier.py" in combined


def test_product_prewarm_modules_not_created_yet() -> None:
    for path in _FORBIDDEN_PRODUCT_FILES:
        assert not path.is_file(), f"Phase 2 file created too early: {path}"


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
