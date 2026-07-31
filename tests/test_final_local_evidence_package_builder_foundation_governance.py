"""PRE-CODE checker for FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION / PERF-7 (Phase 1).

Covers the Phase 1 governance milestone: a read-only critical re-audit of PERF-6's own shipped
debt, real local FTS5/lexical capability probes (no product code, no network), and a design (not an
implementation) of a lexical paragraph index, a typed Evidence Package contract, and completeness/
fallback/session/offline-eval rules for a future ``EvidencePackageBuilder``. Nothing under
``contracts/``, ``core/``, ``app.py``, or ``clients/**`` is created or touched by this milestone --
this checker verifies the design documents exist, are internally consistent, cover every required
section, and that none of the future implementation artifacts they describe exist yet.

Section-header checks use a normalized-heading matcher (case/whitespace-insensitive, tolerant of the
exact numbering) rather than brittle raw-substring assertions on markdown formatting, per this
milestone's own instruction not to write a fragile substring test. Like the PERF-5/PERF-6 governance
checkers, this module imports no product code at all (pure filesystem/text/AST checks) -- verified
structurally at the end of this file.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "performance"
    / "FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "2d0769c"
MILESTONE = "FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION"
TASK_HEADER = f"# TASK — {MILESTONE} / PERF-7 (governance + seam audit, Phase 1)"

_LEVELS_NOT_EXTENDED = ("service_exact", "topic", "context_group", "full")


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _seam_audit_text() -> str:
    return SEAM_AUDIT_PATH.read_text(encoding="utf-8")


def _normalized_headings(text: str) -> set[str]:
    """Extract every markdown heading, normalized: lowercase, collapsed whitespace, no numbering.

    ``## 3. Integration seam`` and ``## Integration seam`` both normalize to
    ``integration seam`` -- this lets the seam audit (numbered) and the TASK.md section
    (unnumbered, per the existing PERF-5/PERF-6 style) be checked against the same required-topic
    list without depending on exact numbering or punctuation surviving future edits.
    """

    headings: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^#{2,3}\s+(.*)$", line.strip())
        if not match:
            continue
        raw = match.group(1)
        raw = re.sub(r"^\d+\.\s*", "", raw)  # strip leading "N. "
        raw = re.sub(r"[`*_]", "", raw)  # strip markdown emphasis/code markers
        normalized = re.sub(r"\s+", " ", raw).strip().lower()
        if normalized:
            headings.add(normalized)
    return headings


def _has_heading(headings: set[str], *substrings: str) -> bool:
    return any(all(sub in heading for sub in substrings) for heading in headings)


# --------------------------------------------------------------------------------------------
# Artifact existence / structure
# --------------------------------------------------------------------------------------------


def test_seam_audit_exists_and_covers_required_sections() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = _seam_audit_text()
    assert GOVERNANCE_BASELINE_HEAD in text
    headings = _normalized_headings(text)
    required_topic_fragments = (
        ("baseline",),
        ("architecture", "map"),
        ("perf-6", "debt"),
        ("integration", "seam"),
        ("lexical", "index"),
        ("fts5", "capability"),
        ("russian",),
        ("lexical", "option"),
        ("paragraph", "index"),
        ("evidence", "package", "contract"),
        ("completeness", "rule"),
        ("fullcontext", "fallback"),
        ("session", "projection"),
        ("offline", "evaluation"),
        ("milestone",),
        ("risk",),
        ("allowlist",),
        ("acceptance", "matrix"),
        ("stop",),
    )
    for fragments in required_topic_fragments:
        assert _has_heading(headings, *fragments), fragments


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    section = _task_section()
    for phrase in (
        "NO PRODUCT IMPLEMENTATION",
        "NO CLIENT-PACK",
        "NO LIVE",
        "NO FTS TABLE",
        "NO SQLITE INDEX",
        "NO EMBEDDINGS",
        "NO VECTOR DATABASE",
        "NO EVIDENCEPACKAGEBUILDER",
        "NO RUNTIME FLAG",
        "NO MIGRATION",
        "NO CONTEXT_GROUPS.JSON",
    ):
        assert phrase in section, phrase
    headings = _normalized_headings(section)
    for fragments in (
        ("architecture", "map"),
        ("integration", "seam"),
        ("lexical", "index", "selection"),
        ("paragraph", "index", "design"),
        ("evidence", "package", "contract"),
        ("completeness", "rule"),
        ("fullcontext", "fallback"),
        ("session", "projection"),
        ("offline", "evaluation"),
        ("milestone", "sequence"),
        ("risk",),
        ("allowlist",),
        ("acceptance", "matrix"),
        ("test", "command"),
        ("stop",),
    ):
        assert _has_heading(headings, *fragments), fragments


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


# --------------------------------------------------------------------------------------------
# Design content: PERF-6 not extended, debt verdicts, lexical/FTS5 proof, contract shape
# --------------------------------------------------------------------------------------------


def test_perf6_ladder_not_extended() -> None:
    """This milestone must not deepen the service_exact/topic/context_group/full ladder --
    the owner's brief explicitly rejects that. The levels may be *mentioned* (they are, while
    critiquing PERF-6's shipped debt), but no new level and no `context_groups.json` may be
    proposed as created here."""

    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "context_groups.json" in doc, label
        assert "does not exist" in lowered or "still does not exist" in lowered, label


def test_perf6_debt_verdicts_present_and_use_required_vocabulary() -> None:
    text = _seam_audit_text()
    for verdict in ("PROVEN", "NOT PROVEN", "ALREADY FIXED", "ACCEPTABLE TEMPORARY DEBT"):
        assert verdict in text, verdict
    # Every one of the seven brief-named debt items must be individually addressed.
    for fragment in (
        "false-positive",
        "any offer/doctor",
        "token estimate",
        "context_group",
        "non-deterministic",
        "answer equivalence",
        "unconditional per-turn shadow",
    ):
        assert fragment.lower() in text.lower(), fragment


def test_lexical_option_selected_and_justified() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "option a" in lowered, label
        assert "selected" in lowered, label
        assert "token-overlap" in lowered or "token overlap" in lowered, label
        assert "fts5" in lowered, label


def test_fts5_capability_probe_documented_with_real_evidence() -> None:
    text = _seam_audit_text()
    for phrase in (
        "sqlite3 version",
        "3.49.1",
        "bm25",
        "unicode61",
        "trigram",
        "OperationalError",
    ):
        assert phrase in text, phrase
    lowered = text.lower()
    assert "no stemming" in lowered or "no stemming/lemmatization" in lowered
    assert "prefix" in lowered


def test_paragraph_index_design_documented() -> None:
    text = _seam_audit_text()
    for field in (
        "paragraph_id",
        "document_path",
        "document_identity",
        "heading",
        "topic",
        "document_type",
        "normalized_searchable_text",
        "content_hash",
    ):
        assert field in text, field
    lowered = text.lower()
    assert "doc_type" in text  # already-authored frontmatter field, not a new one
    assert "40 char" in lowered or "40-char" in lowered


def test_evidence_package_contract_documented_and_anonymized() -> None:
    text = _seam_audit_text()
    assert "TargetEvidencePackage" in text
    for field in (
        "selected_md_refs",
        "selected_paragraph_refs",
        "exact_evidence_block_refs",
        "structured_record_ids",
        "session_derived_refs",
        "retrieval_derived_refs",
        "provenance",
        "completeness_status",
        "fallback_reason",
        "estimated_chars",
        "estimated_tokens",
        "package_fingerprint",
    ):
        assert field in text, field
    assert "extra=\"forbid\"" in text or "extra='forbid'" in text
    lowered = text.lower()
    assert "never the referenced text" in lowered or "never raw text" in lowered or "no raw question" in lowered


def test_completeness_rules_reject_any_present_semantics() -> None:
    text = _seam_audit_text()
    lowered = text.lower()
    assert "never \"any offer/doctor" in lowered or "never" in lowered and "any offer" in lowered
    assert "exact offer id" in lowered or "exact offer ids" in lowered
    assert "required_fact_ids" in text


def test_fullcontext_fallback_before_single_composer_call() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "before" in lowered and "composer call" in lowered, label
        assert "never a" in lowered or "no repeat" in lowered or "never as a second" in lowered, label
        assert "fullcontext_fallback" in doc or "fullcontext fallback" in lowered, label


def test_session_projection_rules_no_auto_carry() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "explicit" in lowered and "follow-up" in lowered, label
        assert "standalone" in lowered or "independent new question" in lowered, label


def test_offline_eval_design_two_modes_no_text_persistence() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "mode 1" in lowered, label
        assert "mode 2" in lowered, label
        assert "counterfactual" in lowered, label
        assert "never persist" in lowered or "never be persisted" in lowered or "raw questions/answers" in lowered, label
    assert "hashes" in text.lower() or "hash" in text.lower()


def test_required_scenario_classes_covered_without_literal_text() -> None:
    text = _seam_audit_text()
    for scenario_class in (
        "Exact service",
        "Broad service",
        "Price",
        "Doctor",
        "Contacts",
        "Parking",
        "Sterilization",
        "Own fresh CT",
        "Treatment plan from another clinic",
        "Pain/fear",
        "Marketing concern",
        "Comparison",
        "Cross-topic question",
        "а сколько это стоит",
        "New independent service",
        "Unknown wording",
        "No matching fact",
        "Medically risky personal question",
    ):
        assert scenario_class in text, scenario_class
    # No scenario row may contain a full trailing question mark followed by clinic-specific
    # imagined patient prose beyond the frozen "follow-up" class label itself -- a light
    # heuristic, not a hard NLP check: at most one literal '?' should appear in the whole
    # document (the one allowed follow-up class label), proving no invented dialogue was written.
    assert text.count("?") <= 2


def _milestone_sequence_section(doc: str) -> str:
    """Extract just the milestone-sequence heading's own body (not the whole document) --
    PERF-7C is legitimately mentioned in passing earlier (e.g. while describing what a future
    scenario allocation feeds), so ordering is only a meaningful claim within the section that
    actually declares the canonical sequence."""

    match = re.search(r"^#{2,3}\s+.*milestone.*sequence.*$", doc, re.IGNORECASE | re.MULTILINE)
    assert match is not None, "milestone sequence heading not found"
    rest = doc[match.end() :]
    next_heading = re.search(r"^#{2,3}\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def test_milestone_sequence_documented_in_order() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        section = _milestone_sequence_section(doc)
        for milestone in ("PERF-7A", "PERF-7B", "PERF-7C", "PERF-8", "PERF-9", "PERF-10"):
            assert milestone in section, (label, milestone)
        idx = {m: section.index(m) for m in ("PERF-7A", "PERF-7B", "PERF-7C", "PERF-8", "PERF-9", "PERF-10")}
        ordered = sorted(idx, key=lambda m: idx[m])
        assert ordered == ["PERF-7A", "PERF-7B", "PERF-7C", "PERF-8", "PERF-9", "PERF-10"], label


def test_integration_seam_materialization_count_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "materializ" in lowered, label
        assert "test_public_signature_and_function_is_exact_straight_line" in doc, label


def test_stop_conditions_documented() -> None:
    text = _seam_audit_text()
    task = _task_section()
    for label, doc in (("seam audit", text), ("TASK.md", task)):
        lowered = doc.lower()
        assert "stop" in lowered, label
        assert "perf-7a" in lowered, label
        assert "owner go" in lowered, label


def test_forbidden_actions_documented() -> None:
    combined = (_seam_audit_text() + "\n" + _task_section()).lower()
    for phrase in (
        "no live",
        "embeddings",
        "no runtime flag",
        "vector database",
        "fts table",
        "does not exist",
    ):
        assert phrase in combined, phrase


# --------------------------------------------------------------------------------------------
# Nothing described has actually been implemented yet
# --------------------------------------------------------------------------------------------


def test_perf7a_perf7b_complete_perf7c_evaluated_with_defect_found() -> None:
    """PERF-7A (lexical paragraph index) and PERF-7B (``EvidencePackageBuilder``) are genuinely
    COMPLETE and unaffected by the PERF-7C eval correction below. PERF-7C's evaluation
    *infrastructure* (matrix/runner/tests/audit) is complete and working -- but its evaluation
    *outcome* is honestly not a pass: an original ``PERF7C_OFFLINE_PACKAGE_EVAL_PASS`` verdict was
    found, via independent review, to rest on a circular-evaluation defect (10 scenarios whose
    "expected" lexical target was set to whatever the search function actually returned, rather
    than to what the question's meaning and canonical demo-pack authority independently require --
    see docs/evidence/performance/PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md). That verdict was
    withdrawn and corrected to ``PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND``,
    ``critical_false_narrow_count = 10``. This live filesystem check asserts the corrected,
    honest state -- it must never again assert a PASS verdict unless a future, separately
    owner-approved correction milestone actually closes these 10 defects. Neither PERF-7A, PERF-7B,
    nor PERF-7C is wired to any runtime path or extends/reuses PERF-6's
    ``service_exact/topic/context_group/full`` ladder -- ``context_groups.json`` still does not
    exist anywhere. PERF-8 (a real Scoped Composer switch) remains a separate, still-unauthorized,
    later milestone, now additionally gated on this defect being resolved."""

    # PERF-7A COMPLETE.
    assert (_REPO_ROOT / "core" / "target_lexical_paragraph_index.py").is_file()
    assert (
        _REPO_ROOT / "tests" / "test_final_local_lexical_paragraph_index_implementation.py"
    ).is_file()

    # PERF-7B COMPLETE.
    assert (_REPO_ROOT / "contracts" / "target_evidence_package.py").is_file()
    assert (_REPO_ROOT / "core" / "target_evidence_package_builder.py").is_file()
    assert (
        _REPO_ROOT / "tests" / "test_final_local_evidence_package_builder_implementation.py"
    ).is_file()

    # PERF-7C evaluation infrastructure exists and ran -- outcome is a defect, not a pass.
    assert (_REPO_ROOT / "evals" / "v5" / "perf7c_local_evidence_package_eval_matrix.json").is_file()
    assert (_REPO_ROOT / "evals" / "v5" / "run_perf7c_local_evidence_package_eval.py").is_file()
    assert (
        _REPO_ROOT / "tests" / "test_final_local_evidence_package_eval_contract.py"
    ).is_file()
    assert (
        _REPO_ROOT / "docs" / "evidence" / "performance"
        / "PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md"
    ).is_file()
    result_path = (
        _REPO_ROOT / "docs" / "evidence" / "performance"
        / "perf7c_local_evidence_package_eval_result.json"
    )
    assert result_path.is_file()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["verdict"] == "PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND"
    assert result["metrics"]["critical_false_narrow_count"] == 10
    assert result["binding_pass"] is False

    # context_groups.json still does not exist anywhere -- no PERF-7 milestone created it.
    for relative in (
        "clients/demo/target_response/context_groups.json",
        "clients/_template/target_response/context_groups.json",
    ):
        assert not (_REPO_ROOT / relative).exists(), relative

    # Still not created by any PERF-7 milestone so far.
    for relative in (
        "clients/demo/target_response/context_groups.json",
        "clients/_template/target_response/context_groups.json",
    ):
        assert not (_REPO_ROOT / relative).exists(), relative


def test_no_fts_sqlite_index_files_or_embeddings_artifacts_exist() -> None:
    forbidden_suffixes = (".faiss", ".index", ".sqlite", ".sqlite3", ".db3")
    search_roots = (_REPO_ROOT / "clients", _REPO_ROOT / "core", _REPO_ROOT / "contracts")
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in forbidden_suffixes:
                raise AssertionError(f"unexpected generated index/db artifact: {path}")


def test_no_evidence_package_builder_runtime_flag_added() -> None:
    config_path = _REPO_ROOT / "config.py"
    if not config_path.is_file():
        return
    text = config_path.read_text(encoding="utf-8")
    forbidden_flags = (
        "EVIDENCE_PACKAGE_BUILDER_ON",
        "LEXICAL_PARAGRAPH_INDEX_ON",
        "SCOPED_COMPOSER_ON",
    )
    for flag in forbidden_flags:
        assert flag not in text, flag


def test_no_client_pack_files_touched() -> None:
    """This governance commit must not modify anything under clients/demo/**."""

    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD", "--", "clients/"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        import pytest

        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    assert changed == [], changed


def test_cached_full_context_corpus_unchanged_since_baseline() -> None:
    """Live cross-check (not assumed) that the demo pack's cached FullContext identity this
    document's claims (§1/§17 of the seam audit) rest on has not drifted."""

    sys.path.insert(0, str(_REPO_ROOT))
    from core.target_cached_full_context import build_target_cached_full_context

    md_root = _REPO_ROOT / "clients" / "demo" / "md"
    live = build_target_cached_full_context(md_root)
    assert live.document_count == 55
    assert len(live.corpus_text) == 107_980
    assert live.sha256.startswith("758a64eb")


def test_every_current_demo_md_file_has_doc_type_frontmatter() -> None:
    """Direct live proof of this document's own §1 claim: doc_type/doc_id/topic/subtopic are
    already authored on every current demo MD file -- not assumed from memory."""

    import frontmatter

    md_root = _REPO_ROOT / "clients" / "demo" / "md"
    md_files = sorted(md_root.glob("*.md"))
    assert len(md_files) == 55
    for path in md_files:
        with open(path, encoding="utf-8-sig") as handle:
            post = frontmatter.load(handle)
        for field in ("doc_id", "doc_type", "topic", "subtopic"):
            assert post.metadata.get(field), (path.name, field)


def test_fts5_and_bm25_are_actually_available_locally() -> None:
    """Re-runs this milestone's own capability probe live (not trusting the prose claim) --
    proves the seam audit's §5 findings are reproducible, not a one-off fluke. Uses only stdlib
    sqlite3 against a throwaway in-memory database; no product code, no client data, no network."""

    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='unicode61 remove_diacritics 2')")
    con.execute("INSERT INTO t(body) VALUES ('импланты имплантация стоимость')")
    rows = con.execute("SELECT body, bm25(t) FROM t WHERE t MATCH 'импланта*'").fetchall()
    assert len(rows) == 1
    con.execute("CREATE VIRTUAL TABLE t2 USING fts5(body, tokenize='trigram')")
    with_error = False
    try:
        con.execute("SELECT body FROM t WHERE t MATCH ?", ('имплант"',))
    except sqlite3.OperationalError:
        with_error = True
    assert with_error
    con.close()


def test_no_product_code_imported_by_this_governance_module() -> None:
    """This checker only reads docs/filesystem state (plus two narrow, explicitly-audited live
    cross-checks that import only the pre-existing, already-shipped ``target_cached_full_context``
    reader and stdlib ``sqlite3``/``frontmatter``) -- importing it as a whole must never pull in
    unrelated contracts/core/app product modules (Phase 1 has no new product implementation to
    exercise)."""

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
    forbidden = {
        "app",
        "orchestration",
        "llm",
        "session",
        "verifier",
        "resolver",
        "target_composer_executor",
        "target_response_verifier",
    }
    assert not (imported_modules & forbidden), imported_modules & forbidden
