"""PRE-CODE checker for FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW / PERF-6 (Phase 1, design only).

Covers the Phase 1 governance milestone: a read-only design of a multi-level
`service_exact -> topic -> context_group -> full` Scoped FullContext resolver and a shadow-only
(measurement, never gating) first integration. Nothing under `contracts/`, `core/`, `app.py`, or
`clients/**` is created or touched by this milestone -- this checker verifies the design documents
exist, are internally consistent, cover every required section, and that none of the Phase 2
implementation artifacts they describe exist yet. Like the PERF-5 governance checker, this module
imports no product code at all (pure filesystem/text checks) -- verified structurally at the end
of this file.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "c0dfde6"
MILESTONE = "FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-6 (governance, Phase 1)"

_LEVELS = ("service_exact", "topic", "context_group", "full")


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _seam_audit_text() -> str:
    return SEAM_AUDIT_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------
# Artifact existence / structure
# --------------------------------------------------------------------------------------------


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = _seam_audit_text()
    assert GOVERNANCE_BASELINE_HEAD in text
    for section in (
        "## 0. Baseline",
        "## 1. Producer → consumer map",
        "## 2. `field_meta.confidence`",
        "## 3. Context-group data model comparison",
        "## 4. `TargetContextScopeDecision`",
        "## 5. Level selection rules",
        "## 6. Deterministic completeness check",
        "## 7. Shadow behavior",
        "## 8. Source comparison",
        "## 9. Shadow observability",
        "## 10. Context caching preparation",
        "## 11. Estimated package sizes",
        "## 12. Honest gaps",
        "## 13. Governance acceptance matrix",
        "## 14. Phase 2 implementation allowlist",
        "## 15. Test commands",
        "## 16. STOP conditions",
    ):
        assert section in text, section


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    section = _task_section()
    for phrase in (
        "NO PRODUCT IMPLEMENTATION",
        "NO CLIENT-PACK CHANGE",
        "NO LIVE",
        "NO CONTEXT_GROUPS.JSON",
        "NO REAL COMPOSER SWITCH",
        "NO VERIFIER CHANGE",
        "NO SECOND LLM CALL",
        "NO RAG/VECTOR/EMBEDDING SEARCH",
        "NO HARDCODED SERVICE/TOPIC GRAPH",
        "NO CACHE IMPLEMENTATION",
    ):
        assert phrase in section, phrase
    for header in (
        "## Context-group data model",
        "## Resolver contract",
        "## Source closure rules",
        "## Widening algorithm",
        "## Shadow producer/consumer map",
        "## Shadow observability fields",
        "## Package fingerprint",
        "## Estimated package sizes",
        "## Honest gaps",
        "## Exact Phase 2 implementation allowlist",
        "## Acceptance matrix",
        "## Test commands",
        "## STOP conditions",
    ):
        assert header in section, header


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    authoring = (_REPO_ROOT / "docs" / "CLIENT_PACK_AUTHORING.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text
    assert "context_groups.json" in authoring
    assert "PERF-6" in authoring


# --------------------------------------------------------------------------------------------
# Design content: levels, contract, resolver rules
# --------------------------------------------------------------------------------------------


def test_all_four_levels_documented_in_order() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        assert "service_exact → topic → context_group → full" in doc, label
        for level in _LEVELS:
            assert level in doc, (label, level)


def test_context_scope_decision_contract_fields_documented() -> None:
    text = _seam_audit_text()
    for field in (
        "level",
        "reason",
        "service_id",
        "topic",
        "context_group_id",
        "included_content_refs",
        "included_offer_ids",
        "included_fact_ids",
        "included_doctor_ids",
        "included_policy_sections",
        "estimated_chars",
        "estimated_tokens",
        "package_fingerprint",
        "completeness_status",
        "widening_reason",
    ):
        assert field in text, field
    assert "TargetContextScopeDecision" in text
    assert "extra=\"forbid\"" in text or "extra='forbid'" in text
    lowered = text.lower()
    assert "no raw question" in lowered or "never a raw" in lowered or "never the referenced text" in lowered


def test_context_group_data_model_comparison_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "option a" in lowered or "selected" in lowered, label
        assert "context_groups.json" in doc, label
        assert "hardcoded" in lowered, label
        assert "rejected" in lowered, label


def test_field_meta_confidence_not_used_as_threshold() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "confidence" in lowered, label
        assert "turn_frame_from_raw.py" in doc, label
        assert "categorical" in lowered or "status" in doc, label
        assert "not calibration-worthy" in lowered or "not calibrated" in lowered or "uncalibrated" in lowered, label


def test_widening_algorithm_deterministic_and_no_repeat_composer_call() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "deterministic" in lowered, label
        assert "no repeat" in lowered or "never a repeat" in lowered or "no repeated composer call" in lowered, label


def test_shadow_never_touches_real_request_and_no_second_llm_call() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "never gating" in lowered or "log-only" in lowered or "never blocks" in lowered, label
        assert "no second llm" in lowered or "never a second llm" in lowered or "zero additional llm calls" in lowered or "no llm call" in lowered, label
        assert "shadow_hit" in doc, label
        assert "shadow_miss" in doc or "shadow miss" in lowered, label
        assert "shadow_would_widen" in doc, label


def test_invented_refs_never_expand_package() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "invented" in lowered
    assert "post-validation" in lowered or "silently dropped" in lowered
    assert "validate_used_content_refs" in text


def test_verifier_grounding_confirmed_independent_of_used_content_refs() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "independent of" in lowered or "independent of `used_content_refs`" in text
    assert "target_verifier_strict_fact_missing" in text
    assert "target_verifier_numeric_ungrounded" in text


def test_honest_gaps_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "comparison__" in doc, label
        assert "zero" in lowered, label
        assert "unreachable" in lowered or "no usable signal" in lowered, label


def test_estimated_package_sizes_documented_with_real_numbers() -> None:
    text = _seam_audit_text()
    for phrase in ("107,980", "26,995", "54,137", "13,534"):
        assert phrase in text, phrase


def test_acceptance_matrix_has_50_scenarios() -> None:
    text = _seam_audit_text()
    for n in range(1, 51):
        assert f"| {n} |" in text, n


def test_phase2_allowlist_documented_and_narrow() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        assert "target_context_scope_decision.py" in doc, label
        assert "target_context_scope_resolver.py" in doc, label
        assert "target_context_scope_shadow.py" in doc, label
        assert "does not exist" in doc.lower() or "does not exist" in doc, label
        assert "Explicitly" in doc and "NOT" in doc, label


def test_stop_conditions_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "stop" in lowered, label
        assert "phase 2" in lowered, label
        assert "owner go" in lowered, label


def test_forbidden_actions_documented() -> None:
    combined = (_seam_audit_text() + "\n" + _task_section()).lower()
    for phrase in (
        "no live",
        "embeddings",
        "second llm",
        "hardcoded",
        "cache implementation" if "cache implementation" in combined else "cached in phase 1",
    ):
        assert phrase in combined, phrase


# --------------------------------------------------------------------------------------------
# Nothing described has actually been implemented yet
# --------------------------------------------------------------------------------------------


def test_phase2_resolver_shadow_contract_files_now_exist_context_groups_still_does_not() -> None:
    """Updated after owner GO on Phase 2 implementation (see TASK.md's PERF-6 Phase 2 completion
    record). This Phase 1 design commit's own text above is left as written -- a historical
    statement of what was true at that commit -- but this *live* filesystem check must track
    current reality: the three approved resolver/shadow/contract files now exist, while
    `context_groups.json` remains a separate, still-unauthorized, later milestone (§3 of the seam
    audit) and must still not exist anywhere."""

    for relative in (
        "contracts/target_context_scope_decision.py",
        "core/target_context_scope_resolver.py",
        "core/target_context_scope_shadow.py",
    ):
        assert (_REPO_ROOT / relative).is_file(), relative
    for relative in (
        "clients/demo/target_response/context_groups.json",
        "clients/_template/target_response/context_groups.json",
    ):
        assert not (_REPO_ROOT / relative).exists(), relative


def test_no_client_pack_files_touched() -> None:
    """This governance commit must not modify anything under clients/demo/**."""

    import subprocess

    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD", "--", "clients/"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        # git not available or baseline not reachable in this environment -- do not fail the
        # whole suite on an environment limitation, but never silently pass either.
        import pytest

        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    assert changed == [], changed


def test_no_product_code_imported_by_this_governance_module() -> None:
    """This checker only reads docs/filesystem state -- importing it must never pull in
    contracts/core/app product modules (Phase 1 has no product implementation to exercise)."""

    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
    forbidden = {"contracts", "core", "app", "orchestration", "llm", "session", "verifier", "resolver"}
    assert not (imported_modules & forbidden), imported_modules & forbidden
