"""PRE-CODE checker for FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT (Phase 1, read-only).

Covers the Phase 1 governance milestone: a read-only audit of `clients/demo/**` content volume
and duplication (exact/near/structured methods, no embeddings/LLM), plus honest sizing of the
cached FullContext corpus and the Composer/Verifier static prefixes via the real, pure, offline
production builders (`core/target_cached_full_context.py`,
`core/target_prompt_cache_prewarm.py::build_dry_run_report`) -- the same zero-provider-call
functions the PERF-3 prewarm CLI already uses for dry-run reporting. This module legitimately
imports those two functions (only those) to *recompute* and cross-check the committed JSON
artifacts against the live pack; it makes no provider/network call and modifies nothing under
`clients/**`.

Nothing under `clients/demo/**`, `core/`, `contracts/`, `app.py`, or any other product path is
edited by this milestone -- only `docs/evidence/client_pack/**`, `TASK.md`,
`docs/FLAGS_AND_STATUS.md`, `docs/STRANGLER_ROADMAP.md`, and this test file are new/changed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from core.target_cached_full_context import build_target_cached_full_context  # noqa: E402
from core.target_prompt_cache_prewarm import build_dry_run_report  # noqa: E402

EVIDENCE_DIR = _REPO_ROOT / "docs" / "evidence" / "client_pack"
REPORT_PATH = EVIDENCE_DIR / "FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT.md"
INVENTORY_PATH = EVIDENCE_DIR / "demo_content_token_inventory.json"
CANDIDATES_PATH = EVIDENCE_DIR / "demo_content_duplicate_candidates.json"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "9073a22"
MILESTONE = "FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT"
TASK_HEADER = f"# TASK — {MILESTONE} (governance, Phase 1)"

CLIENT_ROOT = _REPO_ROOT / "clients" / "demo"
MD_ROOT = CLIENT_ROOT / "md"

_ALLOWED_CLASSES = {
    "EXACT_DUPLICATE",
    "NEAR_DUPLICATE",
    "STRUCTURED_DUPLICATE",
    "POSSIBLE_CONFLICT",
    "INTENTIONAL_DUPLICATE",
    "UI_METADATA_REPEAT",
    "REQUIRES_OWNER_REVIEW",
}
_ALLOWED_RECOMMENDATIONS = {
    "KEEP",
    "MERGE",
    "REFERENCE_CANONICAL",
    "MOVE_TO_AUTHORITY",
    "MARK_INTENTIONAL",
    "INVESTIGATE_CONFLICT",
}


def _task_section() -> str:
    return TASK_PATH.read_text(encoding="utf-8").split(TASK_HEADER)[-1]


def _report_text() -> str:
    return REPORT_PATH.read_text(encoding="utf-8")


def _inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _candidates() -> dict:
    return json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------------
# Artifact existence / TASK.md governance section
# --------------------------------------------------------------------------------------------


def test_report_exists_and_covers_required_sections() -> None:
    assert REPORT_PATH.is_file()
    text = _report_text()
    assert GOVERNANCE_BASELINE_HEAD in text
    for section in (
        "## 0. Method",
        "## 1. Token / char inventory",
        "## 2. Exact duplicates (A)",
        "## 3. Near duplicates (B)",
        "## 4. Structured duplicates and conflicts (C, D)",
        "## 5. FullContext duplication map",
        "## 6. Authority matrix",
        "## 7. Top expensive duplicate candidates",
        "## 8. Why no analysis script is committed",
        "## 9. Proposed Phase 2 script contract",
        "## 10. Cleanup acceptance matrix",
        "## 11. Exact implementation allowlist",
        "## 12. STOP conditions",
    ):
        assert section in text, section


def test_task_governance_section_present() -> None:
    task = TASK_PATH.read_text(encoding="utf-8")
    assert TASK_HEADER in task
    assert GOVERNANCE_BASELINE_HEAD in task
    section = _task_section()
    assert "NO CLIENT-PACK CHANGE" in section
    assert "NO PRODUCT CHANGE" in section
    assert "## Scope" in section
    assert "## Definitions" in section
    assert "## Authority matrix" in section
    assert "## Duplicate classes" in section
    assert "## Proposed Phase 2 script contract" in section
    assert "## Cleanup acceptance matrix" in section
    assert "## Exact implementation allowlist" in section
    assert "## STOP conditions" in section


def test_owner_decision_docs_synced() -> None:
    flags = (_REPO_ROOT / "docs" / "FLAGS_AND_STATUS.md").read_text(encoding="utf-8")
    roadmap = (_REPO_ROOT / "docs" / "STRANGLER_ROADMAP.md").read_text(encoding="utf-8")
    for doc_text in (flags, roadmap):
        assert MILESTONE in doc_text


def test_stop_conditions_documented() -> None:
    task = _task_section()
    report = _report_text()
    for text in (task, report):
        lowered = text.lower()
        assert "stop" in lowered
        assert "phase 2" in lowered
        assert "does not exist" in lowered or "not started" in lowered


# --------------------------------------------------------------------------------------------
# Forbidden-actions / no-live / no-automatic-cleanup assurances
# --------------------------------------------------------------------------------------------


def test_no_provider_network_or_embeddings_documented() -> None:
    combined = (_task_section() + "\n" + _report_text()).lower()
    for phrase in (
        "no live",
        "no provider",
        "no network",
        "no embeddings",
        "zero provider calls",
    ):
        assert phrase in combined, phrase


def test_no_automatic_deletion_or_merge_documented() -> None:
    combined = (_task_section() + "\n" + _report_text()).lower()
    assert "read-only" in combined
    assert "never auto" in combined or "not implemented" in combined or "not proposed as auto-mergeable" in combined


def test_duplicate_candidates_never_recommend_deletion() -> None:
    doc = _candidates()
    for candidate in doc["candidates"]:
        assert candidate["recommendation"] in _ALLOWED_RECOMMENDATIONS
        assert candidate["recommendation"] not in ("DELETE", "REMOVE", "AUTO_MERGE")
        assert candidate["class"] in _ALLOWED_CLASSES


def test_phase2_script_and_schema_changes_not_started() -> None:
    assert not (_REPO_ROOT / "scripts" / "audit_client_pack_dedup.py").exists()
    # No offer file may have gained a "package_ref" field this milestone proposed but did not implement.
    offers_dir = CLIENT_ROOT / "target_response" / "pricebook" / "services"
    for offer_path in offers_dir.glob("*.json"):
        data = json.loads(offer_path.read_text(encoding="utf-8"))
        assert "package_ref" not in data, offer_path


# --------------------------------------------------------------------------------------------
# Inventory JSON: schema, arithmetic consistency, and live cross-check (proves pack unchanged)
# --------------------------------------------------------------------------------------------


_REQUIRED_LAYERS = (
    "md_body",
    "md_frontmatter",
    "service_catalog",
    "offers",
    "facts",
    "doctors",
    "clinic_policies",
    "marketing",
    "consultation_content",
    "presentation_metadata",
    "cached_full_context",
    "composer_static_prefix",
    "verifier_static_prefix",
)


def test_inventory_json_has_all_required_layers() -> None:
    inv = _inventory()
    assert inv["client_id"] == "demo"
    assert "chars_div_4" in inv["tokenizer"]
    assert "NOT_exact" in inv["tokenizer"]
    layers = inv["layers"]
    # composer/verifier prefixes reuse production `_estimate_tokens` (floor chars // 4);
    # every other layer in this audit uses round(chars / 4) -- both are documented as estimates.
    floor_estimate_layers = {"composer_static_prefix", "verifier_static_prefix"}
    for layer in _REQUIRED_LAYERS:
        assert layer in layers, layer
        assert isinstance(layers[layer]["chars"], int) and layers[layer]["chars"] >= 0
        if layer in floor_estimate_layers:
            assert layers[layer]["token_estimate"] == layers[layer]["chars"] // 4
        else:
            assert layers[layer]["token_estimate"] == round(layers[layer]["chars"] / 4)


def test_inventory_arithmetic_consistent_with_per_doc_summary() -> None:
    inv = _inventory()
    per_doc = inv["per_doc_md_summary"]
    assert sum(d["frontmatter_chars"] for d in per_doc) == inv["layers"]["md_frontmatter"]["chars"]
    assert sum(d["body_chars"] for d in per_doc) == inv["layers"]["md_body"]["chars"]
    assert len(per_doc) == inv["layers"]["md_body"]["doc_count"] == inv["layers"]["md_frontmatter"]["doc_count"]


def test_inventory_raw_sum_matches_component_layers() -> None:
    inv = _inventory()
    layers = inv["layers"]
    expected = (
        layers["md_body"]["chars"]
        + layers["md_frontmatter"]["chars"]
        + layers["service_catalog"]["chars"]
        + layers["offers"]["chars"]
        + layers["facts"]["chars"]
        + layers["doctors"]["chars"]
        + layers["clinic_policies"]["chars"]
        + layers["marketing"]["chars"]
        + layers["clinic_strategy_extra"]["chars"]
        + layers["brand_catalog_extra"]["chars"]
        + layers["presentation_metadata"]["video_catalog_yaml_chars"]
    )
    assert inv["arithmetic_checks"]["raw_client_pack_sum_chars_excl_subsets"] == expected


def test_consultation_and_presentation_metadata_marked_as_subsets() -> None:
    inv = _inventory()
    assert "subset_of md_frontmatter" in inv["layers"]["consultation_content"]["note"]
    assert "subset_of md_frontmatter" in inv["layers"]["presentation_metadata"]["note"]


def test_cached_full_context_matches_live_pack_reconstruction() -> None:
    """Recomputing the corpus arithmetic from the raw files must match the committed chars/sha256
    exactly -- this is the strongest available proof that clients/demo/md/** was not touched after
    this audit was produced (byte-identical corpus), without depending on git state."""

    inv = _inventory()
    recorded = inv["layers"]["cached_full_context"]
    live = build_target_cached_full_context(MD_ROOT)
    assert live.sha256 == recorded["sha256"]
    assert len(live.corpus_text) == recorded["chars"]
    assert live.document_count == recorded["document_count"]


def test_composer_and_verifier_static_prefix_matches_live_pack() -> None:
    """Recomputes the real production Composer/Verifier static prefixes (zero provider calls,
    reused verbatim from core/target_prompt_cache_prewarm.py) and cross-checks against the
    committed hashes -- proves both the client pack AND these specific production message
    builders were not changed since the audit was produced."""

    inv = _inventory()
    dry_run = build_dry_run_report("demo")
    for role_key, role_name in (("composer_static_prefix", "composer"), ("verifier_static_prefix", "verifier")):
        recorded = inv["layers"][role_key]
        live_role = next(r for r in dry_run.roles if r.role == role_name)
        assert live_role.static_prefix_hash == recorded["sha256"]
        assert live_role.static_prefix_chars == recorded["chars"]
        assert live_role.estimated_tokens == recorded["token_estimate"]


def test_live_pack_counts_match_recorded_counts() -> None:
    inv = _inventory()
    layers = inv["layers"]
    md_files = sorted(MD_ROOT.glob("*.md"))
    assert len(md_files) == layers["md_body"]["doc_count"]

    service_catalog = json.loads((CLIENT_ROOT / "target_response" / "service_catalog.json").read_text(encoding="utf-8"))
    assert len(service_catalog) == layers["service_catalog"]["service_count"]

    offers_dir = CLIENT_ROOT / "target_response" / "pricebook" / "services"
    assert len(list(offers_dir.glob("*.json"))) == layers["offers"]["offer_count"]

    facts = json.loads((CLIENT_ROOT / "target_response" / "pricebook" / "facts.json").read_text(encoding="utf-8"))
    assert len(facts) == layers["facts"]["fact_count"]

    doctors = json.loads((CLIENT_ROOT / "doctor_catalog.json").read_text(encoding="utf-8"))
    assert len(doctors.get("doctors") or {}) == layers["doctors"]["doctor_count"]


# --------------------------------------------------------------------------------------------
# Duplicate candidates JSON: schema, methodology, and location integrity
# --------------------------------------------------------------------------------------------


def test_candidates_json_methodology_documented() -> None:
    doc = _candidates()
    methodology = doc["methodology"]
    assert "normalized_hash" in methodology["exact_duplicate"]
    near = methodology["near_duplicate"]
    assert "jaccard" in near.lower()
    assert "5-gram" in near or "5gram" in near.lower()
    assert "0.6" in near
    for key in (
        "structured_duplicate_price",
        "structured_duplicate_contact",
        "structured_duplicate_doctor",
        "structured_duplicate_marketing_fact",
        "conflict",
    ):
        assert key in methodology


def test_candidates_count_by_class_matches_candidate_list() -> None:
    doc = _candidates()
    counted: dict[str, int] = {}
    for c in doc["candidates"]:
        counted[c["class"]] = counted.get(c["class"], 0) + 1
    assert counted == doc["candidate_count_by_class"]
    assert sum(counted.values()) == len(doc["candidates"])


def test_candidates_locations_reference_existing_files() -> None:
    """Every location in every candidate must point at a real file in the repo -- proves the
    audit did not invent phantom paths."""

    doc = _candidates()
    assert len(doc["candidates"]) > 0
    for candidate in doc["candidates"]:
        assert len(candidate["locations"]) >= 1
        for loc in candidate["locations"]:
            path = _REPO_ROOT / loc["doc_path"]
            assert path.is_file(), loc["doc_path"]
            assert path.resolve().is_relative_to(_REPO_ROOT.resolve())


def test_near_duplicate_similarity_scores_respect_threshold() -> None:
    doc = _candidates()
    for candidate in doc["candidates"]:
        if candidate["class"] == "NEAR_DUPLICATE":
            assert candidate["similarity_score"] >= candidate["threshold"]
            assert candidate["threshold"] == 0.6


def test_zero_structured_duplicates_and_conflicts_honestly_reported() -> None:
    """The audit found zero cross-authority structured duplicates/conflicts on the current pack;
    this must be stated explicitly in the report (not silently omitted) per the task brief."""

    text = _report_text().lower()
    assert "0 hits" in text or "zero hits" in text
    assert "possible_conflict" in text.lower() or "possible conflict" in text


# --------------------------------------------------------------------------------------------
# Client pack validator / product smoke checks (existing repo pattern)
# --------------------------------------------------------------------------------------------


def test_validator_cli_passes_on_demo() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/validate_client_pack.py", "--client-id", "demo"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_validator_cli_passes_on_template_scaffold() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/validate_client_pack.py", "--path", "clients/_template", "--scaffold"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_no_secrets_or_full_contact_values_in_duplicate_candidates_json() -> None:
    """Contact matches should be represented as pattern hits, never full raw phone numbers,
    inside the committed JSON artifact (governance brief: no secrets/full contacts in JSON)."""

    raw = CANDIDATES_PATH.read_text(encoding="utf-8")
    assert "+7 (495)" not in raw
    assert "+7 (916)" not in raw
