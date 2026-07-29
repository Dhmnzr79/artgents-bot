"""PRE-CODE checker for FINAL_PROVIDER_PROMPT_CACHE_PREWARM / PERF-3 (Phase 1 only).

Covers the governance correction, second revision (attempt lifecycle): separates cache
identity -- (client_id, model, role, static_prefix_hash, fingerprint), descriptive/audit
data only -- from an owner-authorized live attempt, identified by a separate, explicit,
immutable attempt_id. Exactly one run-level attempt marker exists per CLI invocation, keyed
by attempt_id alone (never by client_id/role/fingerprint -- that was the flaw the prior
revision had: a permanent per-fingerprint marker would block every future legitimate
re-warm after an unknown provider TTL expired, forever). Composer and Verifier calls for
one attempt land in the same shared ledger. Reusing the same attempt_id is forbidden; a new
attempt_id for an unchanged fingerprint is fully supported (with a new owner GO). Crashed or
partial attempts remain permanently consumed -- no --force, no reclaim, no delete mechanism
exists anywhere.

Also covers the first revision's correction (manual CLI only): Phase 2 scope is narrowed to
Option B (owner-controlled CLI) alone -- Option C (automatic startup prewarm) is explicitly
deferred to a separate future milestone, with no app.py change, no runtime flag, and no
startup/background hook anywhere in this milestone's implementation allowlist. Provider
cache terminology is corrected (provider-side state at DashScope/Qwen, not process-local).

Also enforces: no product prewarm/CLI/attempt modules exist yet, no provider calls of any
kind, the seam audit proves prefix identity via verbatim reuse of the existing
Composer/Verifier message builders, Composer/Verifier are proven-separate namespaces, live
budget <= 2 with retry=0 and abort-on-mismatch, dry-run makes zero provider calls and creates
zero artifacts, no PII/session/answer-cache, log_llm_usage reuse (no second usage logger),
and the two-gate rollout (implementation GO + separate future LIVE/LLM permission) is
documented.
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
    _REPO_ROOT / "contracts" / "target_prompt_cache_attempt.py",
    _REPO_ROOT / "core" / "target_prompt_cache_prewarm.py",
    _REPO_ROOT / "scripts" / "prewarm_prompt_cache.py",
    _REPO_ROOT / "tests" / "test_final_provider_prompt_cache_prewarm_implementation.py",
)


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _implementation_allowlist_block(section: str) -> str:
    """Text of the '## Allowlist (implementation ...)' subsection only."""
    start = section.index("## Allowlist (implementation")
    rest = section[start:]
    next_header = rest.index("\n## ", 1)
    return rest[:next_header]


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
        "static_prefix_hash",
        "ledger",
        "--live",
        "STOP",
    ):
        assert phrase in text, phrase
    for section in (
        "## Governance correction",
        "## 1. Producer/consumer map",
        "## 2. Exact current Composer message prefix",
        "## 3. Exact current Semantic Verifier message prefix",
        "## 4. Static/dynamic boundary",
        "## 5. Cache-key / fingerprint design",
        "## 6. Invalidation table",
        "## 7. What the CLI actually sends and records",
        "## 8. What the provider actually caches",
        "## 9. Deployment / reloader / multi-worker",
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


def test_provider_cache_not_called_process_local() -> None:
    """Governance correction: cache is provider-side (DashScope/Qwen), not process-local;
    a Flask restart does not by itself cold the cache."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    assert "provider-side" in normalized
    assert "not process-local" in normalized or "not anything local to this" in normalized
    assert "does not, by itself" in normalized or "does not by itself" in normalized


def test_fingerprint_components_documented() -> None:
    section = _task_section()
    for phrase in (
        "client_id",
        "model",
        "role",
        "static_prefix_hash",
        "corpus",
        "PROMPT_TEMPLATE_VERSION",
        "MESSAGE_SERIALIZATION_VERSION",
    ):
        assert phrase in section, phrase


def test_ttl_and_model_alias_explicitly_flagged_unknown() -> None:
    """Rule 18: unknown TTL/aliasing must be explicitly documented, never invented."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "unknown" in text.lower()
    assert "TTL" in text
    assert "not assumed" in text.lower() or "not invent" in text.lower() or "not guessed" in text.lower()


def test_deployment_concerns_deferred_with_option_c() -> None:
    """Reloader/multi-worker/import-time concerns are documented as out of scope for this
    CLI-only milestone, deferred alongside Option C -- not solved now, not silently dropped."""
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    combined = text.lower()
    assert "not in scope for this milestone" in combined
    assert "deferred" in combined
    for phrase in ("_startup_check", "werkzeug_run_main", "gunicorn"):
        assert phrase in combined, phrase


def test_option_c_deferred_not_selected() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        assert "DEFERRED" in text, label
        lowered = text.lower()
        assert "separate future milestone" in lowered, label


def test_fail_open_retry_zero_and_hard_budget_documented() -> None:
    section = _task_section()
    combined = section.lower()
    assert "fail-open" in combined
    assert "retry=0" in combined or "retry = 0" in combined
    assert "budget" in combined
    assert "максимум 2" in section or "max" in combined


def test_live_budget_and_exclusive_ledger_documented() -> None:
    section = _task_section()
    combined = section.lower()
    assert "ledger" in combined
    assert "exclusive" in combined
    assert "1 composer" in combined or "1 verifier" in combined


def test_dry_run_zero_calls_documented() -> None:
    section = _task_section()
    combined = section.lower()
    assert "dry-run" in combined
    assert "ноль раз" in section or "zero" in combined


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
    for n in range(1, 33):
        assert f"| {n} |" in audit, n
    for label in (
        "dry-run mode",
        "attempt marker creation",
        "attempt marker required fields",
        "composer warm call",
        "verifier warm call",
        "one shared ledger per attempt",
        "total call budget",
        "reusing the same",
        "new `attempt_id`",
        "crash/partial attempt",
        "no `--force`",
        "warm response content discarded",
        "fingerprint recorded for audit only",
        "namespaces proven distinct",
        "message/token prefix identity",
        "no pii/session",
        "automatic startup prewarm not exercised",
        "stale fingerprint never considered warm",
        "attempt marker does not imply provider warmth",
    ):
        assert label.lower() in audit.lower(), label


def test_implementation_allowlist_present() -> None:
    section = _task_section()
    for path in (
        "contracts/target_prompt_cache_fingerprint.py",
        "contracts/target_prompt_cache_attempt.py",
        "core/target_prompt_cache_prewarm.py",
        "scripts/prewarm_prompt_cache.py",
        "tests/test_final_provider_prompt_cache_prewarm_implementation.py",
    ):
        assert path in section, path


def test_attempt_marker_keyed_by_attempt_id_not_fingerprint() -> None:
    """The core fix: marker path/key must be attempt_id alone, never
    client_id/role/fingerprint -- that was the flaw permanently blocking re-warms."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        normalized = " ".join(text.split()).lower()
        assert "keyed" in normalized and "attempt_id" in normalized, label
        assert (
            "not by fingerprint" in normalized
            or "not by client_id" in normalized
            or "not client_id/role/fingerprint" in normalized
            or "не по fingerprint" in normalized
            or "не по client_id" in normalized
        ), label


def test_fingerprint_stays_cache_identity_inside_marker() -> None:
    """Fingerprint is descriptive/audit data recorded inside the marker -- never the
    marker's own lookup key."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    lowered = audit.lower()
    assert "cache identity" in lowered
    assert "never used as" in lowered or "never a lookup" in lowered or "descriptive" in lowered


def test_one_marker_per_run_not_permanent_per_role_fingerprint() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    lowered = audit.lower()
    assert "one run-level attempt marker" in lowered or "run-level marker" in lowered
    assert "permanent" in lowered  # names the prior flaw explicitly, not silently


def test_new_attempt_id_enables_future_rewarm() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        normalized = " ".join(text.replace("`", "").split()).lower()
        assert (
            "new attempt_id" in normalized
            or "новым attempt_id" in normalized
            or "новый attempt_id" in normalized
            or "differently-attempt_id" in normalized
        ), label
        assert "new owner go" in normalized or "новым owner go" in normalized or "новый owner go" in normalized, label


def test_reuse_of_attempt_id_forbidden() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        lowered = text.lower()
        assert "reus" in lowered  # reusing / reused / повтор
        assert "forbidden" in lowered or "запрещен" in text.lower() or "запрещён" in text, label


def test_crash_partial_attempt_consumed() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        lowered = text.lower()
        assert "crash" in lowered, label
        assert "consumed" in lowered or "consumed" in text.lower(), label
        assert "auto-resume" in lowered or "resume" in lowered, label


def test_no_force_reclaim_delete_override() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = _task_section()
    for label, text in (("seam audit", audit), ("TASK.md", task)):
        lowered = text.lower()
        assert "--force" in lowered or "force" in lowered, label
        assert "reclaim" in lowered, label
        assert "delete" in lowered, label


def test_one_shared_ledger_for_composer_and_verifier() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    lowered = audit.lower()
    assert "one shared ledger" in lowered or "same single marker/ledger file" in lowered or "shared ledger" in lowered
    assert "not two separate" in lowered or "never two separate" in lowered


def test_attempt_marker_never_implies_provider_warmth() -> None:
    """Explicit clarification required by the correction: the marker proves only the
    fact/state of that one run -- never that the provider cache is still warm."""
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    lowered = audit.lower()
    assert "proves only" in lowered
    assert "still warm" in lowered


def test_no_app_py_or_runtime_flag_in_implementation_allowlist() -> None:
    """Governance correction: app.py, startup hooks, and runtime flags are explicitly out
    of this milestone's implementation allowlist -- only Option C's separate future
    milestone would touch those."""
    section = _task_section()
    block = _implementation_allowlist_block(section)
    assert "| `app.py`" not in block
    assert "PROMPT_CACHE_PREWARM_ENABLED" not in section
    assert "Explicitly NOT in this allowlist" in section
    assert "app.py" in section  # present only in the explicit exclusion/STOP prose, not the table


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
