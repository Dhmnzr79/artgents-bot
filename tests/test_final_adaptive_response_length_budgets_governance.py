"""PRE-CODE checker for FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS / PERF-5 (Phase 1 only).

Covers the Phase 1 governance milestone: a read-only seam audit of whether Composer's answer
text can adopt a soft, stage-aware length budget to speed generation and improve conversion,
without hard truncation, without a retry-for-length path, without changing Verifier policy, and
without ever dropping a required fact/price/condition to hit a budget. Verifies the seam audit
and TASK.md sections exist and cover: the full existing length-control inventory (none adaptive
today), the Verifier's confirmed length-blindness, the selected Variant A+E design (soft budget
directive + structured outline, never hard truncation, never retry-for-length), the typed
`TargetResponseLengthProfile` contract and its single canonical producer, the 7 target length
profiles and their soft-budget ranges, the profile-selection map built only from existing
structured signals, the never-touch invariant list, fail-open semantics, the observability field
plan, the Phase 2 implementation allowlist, and the 30-scenario acceptance matrix. No product
code is touched by this milestone — nothing in `contracts/`, `core/`, or `app.py` is imported or
exercised here beyond reading these two documents.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "2fe7437"
MILESTONE = "FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-5 (governance)"

_ALL_PROFILES = (
    "clarification_concise",
    "simple_faq",
    "standard_information",
    "marketing_concern",
    "broad_price_overview",
    "scoped_price",
    "comparison_or_complex",
)


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _seam_audit_text() -> str:
    return SEAM_AUDIT_PATH.read_text(encoding="utf-8")


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = _seam_audit_text()
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "TargetResponseLengthProfile",
        "select_target_response_length_profile",
        "response_directives_json",
        "must_preserve_exact",
        "target_verifier_strict_fact_missing",
        "target_verifier_numeric_ungrounded",
        "broad_family_price_directive_overlay",
        "max_price_anchors",
        "response_stage",
        "TargetResponseSpec",
        "composer_ms",
        "completion_tokens",
        "answer_chars",
    ):
        assert phrase in text, phrase
    for section in (
        "## 0. Offline baseline aggregate",
        "## 1. Existing length/structure controls",
        "## 2. `TurnFrame`, `response_stage`, `EffectiveScope`",
        "## 3. Materialization/spec package",
        "## 4. Composer prompt / directives",
        "## 5. Composer SDK messages & token caps",
        "## 6. Action context directives",
        "## 7. Marketing scenarios",
        "## 8. Required facts / `must_preserve_exact`",
        "## 9. Offers / numeric grounding",
        "## 10. `no_public_price`",
        "## 11. Verifier",
        "## 12. Presentation decision / progressive disclosure",
        "## 13. Follow-up/price/choice channels",
        "## 14. CTA",
        "## 15. Variant comparison and selected design",
        "## 16. Typed contract, canonical producer, and target length profiles",
        "## 17. Profile-selection map",
        "## 18. Invariants the length budget must never override",
        "## 19. Observability fields",
        "## 20. Implementation allowlist",
        "## 21. Acceptance matrix",
        "## 22. PRE-CODE summary",
    ):
        assert section in text, section


def test_verifier_confirmed_length_blind() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "zero length-policy hits" in lowered or "length-blind" in lowered
    assert "target_response_verifier.py" in text
    assert "is not a safety verifier" in lowered or "not a safety verifier" in lowered


def test_existing_length_controls_inventory_present() -> None:
    text = _seam_audit_text()
    for phrase in (
        "answer_chars",
        "INPUT_MAX_CHARS",
        "min_answer_chars_after_remove",
        "PREBUFFER_MAX_CHARS",
        "max_completion_tokens",
        "CHOICE_MENU_MAX",
        "SECONDARY_CONTENT_MAX",
        "PRICE_DETAIL_MAX",
    ):
        assert phrase in text, phrase
    lowered = text.lower()
    assert "none is adaptive" in lowered or "none adaptive" in lowered


def test_variant_comparison_and_selection_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        assert "Selected" in text_ or "selected" in text_, label
        assert "Variant" in text_ or "variant" in text_, label
        for tag in ("A", "B", "C", "D", "E"):
            assert tag in text_, (label, tag)
    lowered = text.lower()
    assert "rejected" in lowered
    assert "selected: a + e" in lowered or "a + e" in lowered.replace("a+e", "a + e")


def test_hard_truncation_and_retry_explicitly_rejected() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        lowered = text_.lower()
        assert "rejected outright" in lowered or "rejected" in lowered, label
        assert "truncat" in lowered, label
        assert "retry" in lowered, label


def test_typed_contract_and_single_producer_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        assert "TargetResponseLengthProfile" in text_, label
        assert "select_target_response_length_profile" in text_, label
        assert "single canonical producer" in text_.lower() or "canonical producer" in text_.lower(), label
        assert "target_response_policy.py" in text_, label


def test_all_seven_length_profiles_and_soft_budgets_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for profile in _ALL_PROFILES:
        assert profile in text, profile
        assert profile in task, profile
    for phrase in ("250", "450", "700", "650", "750", "1000", "400", "350"):
        assert phrase in text, phrase


def test_profile_selection_map_uses_only_existing_signals() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    for phrase in (
        "response_mode",
        "needs_clarification",
        "\"comparison\" in turn_frame.aspects",
        "applied_scenarios",
        "required_components",
    ):
        assert phrase in text or phrase.lower() in lowered, phrase
    assert "no new classifier" in lowered
    assert "second router" in lowered
    assert "no regex" in lowered or "no regex/phrase list" in lowered.replace(", ", "/")
    assert "question length" in lowered or "user's question length" in lowered


def test_open_boundary_honestly_flagged_not_silently_resolved() -> None:
    """simple_faq vs standard_information boundary must be flagged as unresolved, not invented."""
    text = _seam_audit_text()
    lowered = text.lower()
    assert "open point" in lowered or "not yet crisply pinned" in lowered
    assert "simple_faq" in text and "standard_information" in text


def test_never_touch_invariants_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        lowered = text_.lower()
        for phrase in (
            "must_preserve_exact",
            "no_public_price",
            "required_fact_ids",
            "source_identity",
        ):
            assert phrase in text_, (label, phrase)
        assert "correctness" in lowered
        assert "wins" in lowered


def test_fail_semantics_never_block_never_retry_never_verifier() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        lowered = text_.lower()
        assert "never blocks" in lowered or "not** fixed" in text_ or "never block" in lowered, label
        assert "never retries" in lowered or "never retry" in lowered or "no retry" in lowered, label
        assert "not a new verifier policy" in lowered or "not a safety verifier" in lowered, label
        assert "standard_information" in text_, label


def test_presentation_and_cta_non_coupling_documented() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "choice_menu_max" in lowered
    assert "cta" in lowered
    assert "never increase" in lowered or "unaffected" in lowered or "uncoupled" in lowered or "not coupled" in lowered or "never a trigger" in lowered


def test_observability_fields_documented_and_no_pii() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, text_ in (("seam audit", text), ("TASK.md", task)):
        for field in (
            "response_length_profile",
            "response_length_soft_max",
            "over_soft_budget",
            "required_content_override",
        ):
            assert field in text_, (label, field)
        lowered = text_.lower()
        assert "no pii" in lowered or "no q/answer/sid" in lowered or "no q" in lowered, label


def test_implementation_allowlist_present_and_narrow() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, section in (("seam audit", text), ("TASK.md", task)):
        assert "target_response_policy.py" in section, label
        assert "target_composer_executor.py" in section, label
        assert "Explicitly NOT in this allowlist" in section or "Explicitly NOT" in section, label
        assert "target_response_verifier.py" in section, label
        assert "target_presentation_decision.py" in section, label


def test_no_prompt_model_schema_change_beyond_the_one_composer_rule() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, section in (("seam audit", text), ("TASK.md", task)):
        lowered = section.lower()
        assert "no model change" in lowered or "no model" in lowered, label


def test_acceptance_matrix_documented() -> None:
    text = _seam_audit_text()
    for n in range(1, 31):
        assert f"| {n} |" in text, n
    for label in (
        "simple faq",
        "broad implantation",
        "one-tooth",
        "full-arch",
        "comparison",
        "no_public_price",
        "included/excluded",
        "pain_fear",
        "result_reliability",
        "marketing `time`",
        "consultation-value",
        "scope choice menu",
        "stage clarification",
        "typed ui click",
        "contacts structured-capability",
        "service-availability",
        "exceeds the profile's soft-max",
        "multiple required numeric offers",
        "source_identity",
        "missing/invalid profile",
        "over-soft-budget answer",
        "/ask` vs. `/ask/stream` parity",
    ):
        assert label.lower() in text.lower(), label


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "NO PRODUCT CHANGE" in task


def test_stop_before_phase2_documented() -> None:
    task = _task_section()
    lowered = task.lower()
    assert "stop" in lowered
    assert "phase 2" in lowered
    assert "do not exist yet" in lowered or "does not exist yet" in lowered


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
        "no live",
        "no provider calls",
        "no hard truncation",
        "no verifier policy change",
        "tsc-c",
        "tsc-d",
    ):
        assert phrase in combined, phrase


def test_offline_baseline_no_live_call_documented() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "no live call" in lowered or "no live call was made" in lowered or "no live call made" in lowered
    assert "target_fullcontext_runtime_composer" in text
    assert "prewarm" in lowered


def test_no_product_code_imported_by_this_governance_module() -> None:
    """This checker only reads docs — importing it must never pull in contracts/core/app product
    modules (Phase 1 has no product implementation to exercise)."""
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
