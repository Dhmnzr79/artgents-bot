"""Contract tests for FINAL_LOCAL_EVIDENCE_PACKAGE_OFFLINE_EVAL / PERF-7C.

Covers: the frozen matrix's shape and governance discipline (118 synthetic scenarios across the 18
required classes, no generated-answer field anywhere, canonical demo-pack authority only), the
runner's determinism (two independent runs produce byte-identical categorical/source-ID results),
the result artifact's anonymization (no raw query/answer/SID/PII/contact value anywhere), the
binding PASS verdict itself, and a small **integration subset** that proves compatibility with the
real production materialization chain (`materialize_target_composer_request`) for a handful of
scenarios -- not all ~118, per the brief's explicit scope note.

No Composer/Verifier/Planner/Boundary/Ingress call anywhere in this file. No LLM, no network, no
provider transport, no Flask/server.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from contracts.response_schema import TargetStrategyMatch  # noqa: E402
from contracts.response_schema_refs import (  # noqa: E402
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.doctor_schema_refs import (  # noqa: E402
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs  # noqa: E402
from contracts.target_response_policy import TargetResponsePolicyRequest  # noqa: E402
from core.doctor_schema_loader import load_doctor_catalog  # noqa: E402
from core.response_schema_kb_index import build_response_schema_kb_refs  # noqa: E402
from core.response_schema_loader import load_response_schema_bundle  # noqa: E402
from core.service_consultation_source import build_service_consultation_values  # noqa: E402
from core.target_cached_full_context import build_target_cached_full_context  # noqa: E402
from core.target_composer_request import materialize_target_composer_request  # noqa: E402
from core.target_evidence_package_builder import build_target_evidence_package  # noqa: E402
from core.target_lexical_paragraph_index import build_target_lexical_paragraph_index  # noqa: E402
from core.target_response_policy import build_target_response_spec  # noqa: E402
from core.target_spec_offline_response_package import (  # noqa: E402
    assemble_target_spec_offline_response_package,
)

sys.path.insert(0, str(_REPO_ROOT / "evals" / "v5"))
from run_perf7c_local_evidence_package_eval import run_eval  # noqa: E402

MATRIX_PATH = _REPO_ROOT / "evals" / "v5" / "perf7c_local_evidence_package_eval_matrix.json"
RUNNER_PATH = _REPO_ROOT / "evals" / "v5" / "run_perf7c_local_evidence_package_eval.py"
RESULT_PATH = _REPO_ROOT / "docs" / "evidence" / "performance" / "perf7c_local_evidence_package_eval_result.json"
AUDIT_PATH = _REPO_ROOT / "docs" / "evidence" / "performance" / "PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md"
GOVERNANCE_BASELINE_HEAD = "75ce5f9"

_REQUIRED_CLASSES = {
    "exact_service", "broad_service", "price", "doctor", "contacts", "parking",
    "sterilization_safety", "own_fresh_ct", "treatment_plan_other_clinic", "pain_fear",
    "marketing_concern", "comparison", "cross_topic", "explicit_followup_price",
    "new_independent_service", "unknown_wording", "no_matching_fact", "medically_risky_personal",
}


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _result() -> dict:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------------
# Matrix shape / governance discipline
# --------------------------------------------------------------------------------------------


def test_matrix_exists_and_is_within_100_to_150_scenarios() -> None:
    assert MATRIX_PATH.is_file()
    matrix = _matrix()
    assert 100 <= len(matrix["scenarios"]) <= 150
    assert matrix["scenario_count"] == len(matrix["scenarios"])


def test_matrix_covers_all_18_required_classes() -> None:
    matrix = _matrix()
    classes = {s["scenario_class"] for s in matrix["scenarios"]}
    assert classes == _REQUIRED_CLASSES
    assert len(_REQUIRED_CLASSES) == 18


def test_matrix_class_counts_are_never_reduced_to_hide_a_class() -> None:
    matrix = _matrix()
    counts: dict[str, int] = {}
    for s in matrix["scenarios"]:
        counts[s["scenario_class"]] = counts.get(s["scenario_class"], 0) + 1
    assert counts == matrix["class_target_counts"]
    for cls, count in counts.items():
        assert count >= 4, (cls, count)


def test_matrix_never_stores_generated_answer_or_pii_fields() -> None:
    matrix = _matrix()
    raw = json.dumps(matrix, ensure_ascii=False)
    forbidden_field_names = ("generated_answer", "composer_answer", "candidate_text", "session_id", "sid")
    for scenario in matrix["scenarios"]:
        assert set(scenario.keys()) == {
            "scenario_id", "scenario_class", "synthetic_query", "builder_input", "expected", "rationale",
        }
        for name in forbidden_field_names:
            assert name not in scenario
    # No literal phone/whatsapp/address display value from clinic_policies.yaml anywhere in the matrix.
    import yaml

    policies = yaml.safe_load((_REPO_ROOT / "clients" / "demo" / "clinic_policies.yaml").read_text(encoding="utf-8"))
    contact = policies.get("contact", {})
    for value in contact.values():
        if isinstance(value, str) and value.strip():
            assert value not in raw, value


def test_matrix_scenario_ids_unique_and_deterministically_ordered() -> None:
    matrix = _matrix()
    ids = [s["scenario_id"] for s in matrix["scenarios"]]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids, key=lambda i: int(i.split("_")[0][1:]))


def test_matrix_builder_input_refs_use_only_real_canonical_ids() -> None:
    """Every offer/doctor/fact ref in the matrix must resolve against the real demo pack --
    proves scenarios are grounded in canonical authority, not invented IDs (except the
    deliberately-fake fact ids in the no_matching_fact class, which must NOT resolve)."""

    target_root = _REPO_ROOT / "clients" / "demo" / "target_response"
    bundle = load_response_schema_bundle(target_root)
    doctors = load_doctor_catalog(_REPO_ROOT / "clients" / "demo" / "doctor_catalog.json")
    real_offer_ids = {o.offer_id for o in bundle.offers}
    real_fact_ids = set(bundle.facts)
    real_doctor_ids = set(doctors.doctors)

    matrix = _matrix()
    for scenario in matrix["scenarios"]:
        for block in scenario["builder_input"]["evidence_blocks"]:
            if block["kind"] == "offer":
                offer_id = block["ref"].removeprefix("offer:")
                assert offer_id in real_offer_ids, (scenario["scenario_id"], offer_id)
            elif block["kind"] == "doctor":
                doctor_id = block["ref"].removeprefix("doctor:")
                assert doctor_id in real_doctor_ids, (scenario["scenario_id"], doctor_id)
            elif block["kind"] == "commercial_fact":
                fact_id = block["ref"].removeprefix("fact:")
                if scenario["scenario_class"] != "no_matching_fact":
                    assert fact_id in real_fact_ids, (scenario["scenario_id"], fact_id)
        if scenario["scenario_class"] == "no_matching_fact":
            for fake_fid in scenario["builder_input"]["spec"]["required_fact_ids"]:
                assert fake_fid not in real_fact_ids, (scenario["scenario_id"], fake_fid)


# --------------------------------------------------------------------------------------------
# Runner determinism / isolation
# --------------------------------------------------------------------------------------------


def test_runner_is_deterministic_across_two_independent_runs() -> None:
    first = run_eval("demo", MATRIX_PATH)
    second = run_eval("demo", MATRIX_PATH)

    def _strip_timing(result: dict) -> dict:
        stripped = json.loads(json.dumps(result))
        for scenario in stripped["scenarios"]:
            scenario.pop("timing_ms", None)
        stripped["metrics"].pop("builder_ms_p50", None)
        stripped["metrics"].pop("builder_ms_p95", None)
        return stripped

    assert _strip_timing(first) == _strip_timing(second)


def test_runner_module_makes_no_network_or_provider_imports() -> None:
    import ast

    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"requests", "httpx", "openai", "anthropic", "flask", "sqlite3", "socket"}
    assert not (imported & forbidden), imported & forbidden


def test_runner_module_never_imports_composer_verifier_planner_boundary() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "target_composer_executor",
        "target_response_verifier",
        "turn_planner",
        "medical_boundary",
        "ingress",
    ):
        assert forbidden not in source, forbidden


# --------------------------------------------------------------------------------------------
# Result artifact sanitization + PASS verdict
# --------------------------------------------------------------------------------------------


def test_result_artifact_exists_and_holds_only_permitted_fields() -> None:
    assert RESULT_PATH.is_file()
    result = _result()
    for scenario in result["scenarios"]:
        assert set(scenario.keys()) == {
            "scenario_id", "scenario_class", "verdict", "actual_completeness_status",
            "actual_fallback_reason", "actual_estimated_tokens", "actual_package_fingerprint",
            "timing_ms", "builder_exception",
        }


def test_result_artifact_never_contains_raw_query_or_contact_values() -> None:
    raw = RESULT_PATH.read_text(encoding="utf-8")
    assert "synthetic_query" not in raw
    matrix = _matrix()
    for scenario in matrix["scenarios"]:
        assert scenario["synthetic_query"] not in raw, scenario["scenario_id"]
    import yaml

    policies = yaml.safe_load((_REPO_ROOT / "clients" / "demo" / "clinic_policies.yaml").read_text(encoding="utf-8"))
    contact = policies.get("contact", {})
    for value in contact.values():
        if isinstance(value, str) and value.strip():
            assert value not in raw, value


_KNOWN_LEXICAL_RELEVANCE_DEFECT_SCENARIO_IDS = {
    "s051_treatment_plan_other_clinic",
    "s053_treatment_plan_other_clinic",
    "s054_treatment_plan_other_clinic",
    "s055_treatment_plan_other_clinic",
    "s056_treatment_plan_other_clinic",
    "s083_cross_topic",
    "s084_cross_topic",
    "s099_unknown_wording",
    "s100_unknown_wording",
    "s101_unknown_wording",
}


def test_result_verdict_is_lexical_relevance_defect_found() -> None:
    """PERF-7C correction: the original PASS verdict was wrong (circular evaluation -- see
    docs/evidence/performance/PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md). This asserts the
    corrected, honest verdict -- not a weakened criterion. The three other binding-PASS counters
    (session contamination, structured-ID mismatch, Builder exceptions) remain proven at zero,
    proving the correction is scoped exactly to the lexical-relevance defect, nothing broader."""

    result = _result()
    assert result["metrics"]["critical_false_narrow_count"] == 10
    assert result["metrics"]["session_contamination_count"] == 0
    assert result["metrics"]["structured_id_mismatch_count"] == 0
    assert result["metrics"]["builder_exception_count"] == 0
    assert result["binding_pass"] is False
    assert result["verdict"] == "PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND"
    assert set(result["critical_false_narrow_scenario_ids"]) == _KNOWN_LEXICAL_RELEVANCE_DEFECT_SCENARIO_IDS
    assert set(result["lexical_relevance_defect_scenario_ids"]) == _KNOWN_LEXICAL_RELEVANCE_DEFECT_SCENARIO_IDS


def test_all_10_flagged_scenarios_verdict_is_irrelevant_lexical_target() -> None:
    result = _result()
    by_id = {s["scenario_id"]: s for s in result["scenarios"]}
    for scenario_id in _KNOWN_LEXICAL_RELEVANCE_DEFECT_SCENARIO_IDS:
        assert by_id[scenario_id]["verdict"] == "critical_false_narrow_irrelevant_lexical_target", scenario_id
        assert by_id[scenario_id]["actual_completeness_status"] == "insufficient_widened", scenario_id


def test_relevance_gated_scenarios_never_silently_accept_an_unlisted_target() -> None:
    """General rule, not just the 10 known cases: for every scenario whose expected
    ``lexical_target_options`` is a list (possibly empty), an actual ``insufficient_widened``
    outcome must either land in the allowed set (verdict ``match_expected_widened``) or be flagged
    ``critical_false_narrow_irrelevant_lexical_target`` -- never the old soft
    ``unexpected_scoped_target``-only bucket with no critical flag."""

    matrix = {s["scenario_id"]: s for s in _matrix()["scenarios"]}
    result = _result()
    for scenario_result in result["scenarios"]:
        scenario = matrix[scenario_result["scenario_id"]]
        if scenario["expected"]["lexical_target_options"] is None:
            continue
        if scenario_result["actual_completeness_status"] != "insufficient_widened":
            continue
        assert scenario_result["verdict"] in {
            "match_expected_widened",
            "critical_false_narrow_irrelevant_lexical_target",
        }, (scenario["scenario_id"], scenario_result["verdict"])


def test_empty_allowed_target_scenarios_can_never_match_as_widened() -> None:
    """Scenarios whose independently-derived relevant-document set is empty (cross_topic/
    unknown_wording defect scenarios) can never legitimately produce ``match_expected_widened`` --
    by construction, no document was judged relevant, so any widened result is automatically the
    critical defect verdict."""

    matrix = {s["scenario_id"]: s for s in _matrix()["scenarios"]}
    result = _result()
    by_id = {s["scenario_id"]: s for s in result["scenarios"]}
    for scenario in matrix.values():
        if scenario["expected"]["lexical_target_options"] == []:
            actual = by_id[scenario["scenario_id"]]
            assert actual["verdict"] != "match_expected_widened", scenario["scenario_id"]


def test_treatment_plan_relevant_authority_is_clinic_consultation_doc() -> None:
    """Grounds the corrected expectation in canonical authority, not in search output: the
    consultation MD is the one genuinely relevant document for "plan from another clinic"
    questions, per its own authored frontmatter alias."""

    import frontmatter

    consultation_path = _REPO_ROOT / "clients" / "demo" / "md" / "clinic__info__consultation.md"
    with open(consultation_path, encoding="utf-8-sig") as handle:
        post = frontmatter.load(handle)
    aliases = post.metadata.get("aliases") or []
    assert any("план лечения" in alias for alias in aliases), aliases

    matrix = {s["scenario_id"]: s for s in _matrix()["scenarios"]}
    for scenario_id in (
        "s051_treatment_plan_other_clinic",
        "s053_treatment_plan_other_clinic",
        "s055_treatment_plan_other_clinic",
        "s056_treatment_plan_other_clinic",
    ):
        assert matrix[scenario_id]["expected"]["lexical_target_options"] == ["clinic__info__consultation.md"]


def test_result_matches_matrix_scenario_count() -> None:
    result = _result()
    matrix = _matrix()
    assert result["matrix_scenario_count"] == len(matrix["scenarios"])
    assert len(result["scenarios"]) == len(matrix["scenarios"])


def test_all_exact_structured_scenarios_recall_exact_required_ids() -> None:
    """Binding PASS criterion, checked directly: every scenario whose expected outcome required a
    specific offer/fact/doctor/policy id actually recalled it exactly (never "any offer/doctor
    present")."""

    matrix = {s["scenario_id"]: s for s in _matrix()["scenarios"]}
    result = _result()
    for scenario_result in result["scenarios"]:
        scenario = matrix[scenario_result["scenario_id"]]
        expected = scenario["expected"]
        if scenario_result["actual_completeness_status"] not in {"complete", "insufficient_widened"}:
            continue
        if any(
            expected[key]
            for key in (
                "expected_offer_ids", "expected_fact_ids", "expected_doctor_ids", "expected_policy_sections",
            )
        ):
            assert scenario_result["verdict"] in {"match_expected_complete", "match_expected_widened"}, (
                scenario["scenario_id"], scenario_result["verdict"]
            )


def test_all_fallback_expected_scenarios_actually_fell_back_or_matched_two_way_expectation() -> None:
    matrix = {s["scenario_id"]: s for s in _matrix()["scenarios"]}
    result = _result()
    for scenario_result in result["scenarios"]:
        scenario = matrix[scenario_result["scenario_id"]]
        expected = scenario["expected"]
        if expected["acceptable_completeness_status"] == ["fullcontext_fallback"]:
            assert scenario_result["actual_completeness_status"] == "fullcontext_fallback", scenario["scenario_id"]


# --------------------------------------------------------------------------------------------
# Audit document
# --------------------------------------------------------------------------------------------


def test_audit_document_exists_and_states_corrected_verdict() -> None:
    assert AUDIT_PATH.is_file()
    text = AUDIT_PATH.read_text(encoding="utf-8")
    assert "PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND" in text
    assert "critical false-narrow" in text.lower() or "critical_false_narrow" in text.lower()
    # The withdrawn PASS claim must be documented as withdrawn, not silently deleted.
    assert "PERF7C_OFFLINE_PACKAGE_EVAL_PASS" in text
    lowered = text.lower()
    assert "withdrawn" in lowered or "superseded" in lowered or "wrong" in lowered
    for scenario_id in _KNOWN_LEXICAL_RELEVANCE_DEFECT_SCENARIO_IDS:
        short_id = scenario_id.split("_", 1)[0]  # e.g. "s051"
        assert short_id in text, short_id


def test_audit_document_no_client_pack_change_disclosed() -> None:
    text = AUDIT_PATH.read_text(encoding="utf-8").lower()
    assert "no live" in text
    assert "no client-pack change" in text or "clients/**" in text.lower()


# --------------------------------------------------------------------------------------------
# Integration subset -- real materialize_target_composer_request pipeline (not all ~118)
# --------------------------------------------------------------------------------------------

_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_MD_ROOT = _DEMO_ROOT / "md"
_BUNDLE = load_response_schema_bundle(_TARGET_ROOT)
_DOCTORS = load_doctor_catalog(_DEMO_ROOT / "doctor_catalog.json")
_KB_REFS = build_response_schema_kb_refs(_MD_ROOT)
_DOCTOR_INDEX = DoctorCatalogExternalIndex(service_ids=tuple(_BUNDLE.services), kb_refs=_KB_REFS)
assert validate_doctor_catalog_external_refs(_DOCTORS, _DOCTOR_INDEX) is None
_EXTERNAL_INDEX = ResponseSchemaExternalIndex(kb_refs=_KB_REFS, doctor_refs=build_doctor_source_refs(_DOCTORS))
assert validate_response_schema_external_refs(_BUNDLE, _EXTERNAL_INDEX) is None
_CONSULTATIONS = build_service_consultation_values(_MD_ROOT)
assert validate_service_consultation_refs(_CONSULTATIONS, _BUNDLE.services) is None
_FULL_CONTEXT = build_target_cached_full_context(_MD_ROOT)
_LEXICAL_INDEX = build_target_lexical_paragraph_index(_MD_ROOT)


def _real_materialize(
    *, service_id: str | None, allowed_topics: tuple[str, ...],
    requested_components: tuple[str, ...], user_message: str,
):
    policy_request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": service_id,
            "tone_key": "commercial_warm",
            "allowed_topics": allowed_topics,
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "requested_components": requested_components,
            "primary_component": requested_components[0] if requested_components else None,
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )
    spec = build_target_response_spec(policy_request)
    bound_package = assemble_target_spec_offline_response_package(
        _BUNDLE, _DOCTORS, _EXTERNAL_INDEX, _CONSULTATIONS, spec=spec, brand_term=None,
        strategy_context=TargetStrategyMatch(family="implantology", extent="full_arch"),
        semantic_context="service", today=date(2026, 7, 31), md_root=_MD_ROOT,
        include_initial_block=False, include_consultation_close=False, include_cta=False,
        marketing_scenarios=(), shown_fact_ids=(), shown_amplifier_refs=(), shown_consultation_value_refs=(),
        turn_topic=None, effective_scope=None, client_id="demo",
    )
    return materialize_target_composer_request(
        bound_package, _BUNDLE, _DOCTORS, _CONSULTATIONS, user_message=user_message,
        md_root=_MD_ROOT, client_id="demo",
    )


@pytest.mark.parametrize(
    "service_id,allowed_topics,requested_components,expected_content_ref",
    [
        ("classic", ("implantation",), ("content",), "implantation__service__classic.md"),
        ("all_on_4", ("implantation",), ("content", "price"), "implantation__service__all_on_4.md"),
        ("tomography", ("clinic",), ("price",), None),
        ("veneers", ("prosthetics",), ("content",), "prosthetics__service__veneers.md"),
        ("periodontitis", ("periodontology",), ("doctors",), None),
    ],
)
def test_integration_subset_real_materialized_request_compatible_with_builder(
    service_id, allowed_topics, requested_components, expected_content_ref
) -> None:
    """Proves build_target_evidence_package accepts a REAL materialize_target_composer_request
    output (real evidence_blocks shape, real spec) -- not just the matrix's hand-built typed
    fixtures. Not all ~118 scenarios go through this, per the brief's explicit scope note."""

    request = _real_materialize(
        service_id=service_id,
        allowed_topics=allowed_topics,
        requested_components=requested_components,
        user_message="Расскажите подробнее",
    )
    package = build_target_evidence_package(request, _LEXICAL_INDEX, _FULL_CONTEXT, md_root=_MD_ROOT)
    assert package.completeness_status == "complete"
    if expected_content_ref:
        assert expected_content_ref in package.selected_md_refs


def test_integration_subset_no_client_pack_change() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{GOVERNANCE_BASELINE_HEAD}..HEAD", "--", "clients/"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    assert changed == [], changed
