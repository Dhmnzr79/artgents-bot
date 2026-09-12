from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_MATRIX = Path("evals/v5/demo/patient_scope_a9r_matrix.json")
_REQUIRED_CASE_IDS = {
    "a9r_extent_01_full_arch_price_question",
    "a9r_extent_02_one_tooth_restore",
    "a9r_extent_03_few_teeth_missing",
    "a9r_jaw_01_upper",
    "a9r_jaw_02_lower",
    "a9r_jaw_03_both",
    "a9r_stage_01_implant_placed",
    "a9r_stage_02_natural_tooth_present",
    "a9r_correction_01_one_tooth_after_full_arch",
    "a9r_negative_01_all_on_4_info",
    "a9r_negative_02_all_on_4_price",
    "a9r_negative_03_implant_word_only",
    "a9r_session_01_topic_change_clears",
    "a9r_session_04_sid_isolation",
}


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _load_matrix() -> dict:
    return json.loads(_MATRIX.read_text(encoding="utf-8"))


def test_a9r_matrix_frozen_blob_hash() -> None:
    assert _git_blob_hash(_MATRIX) == "36d137112007a3fb0a96ad0759aa111af6115a35"


def test_a9r_matrix_schema_and_governance_flags() -> None:
    matrix = _load_matrix()
    assert matrix["schema_version"] == "a9r.patient_scope_authority_prep.v1"
    assert matrix["authority_decision_allowed"] is False
    assert matrix["product_path_allowed"] is False
    assert matrix["baseline_product_head"] == "aa8e6dd"
    merge = matrix["merge_contract"]
    assert merge["source_priority"][0] == "ui_scope_action"
    assert merge["uncertain_or_conflicting_must_not_overwrite_session"] is True
    scoring = matrix["scoring_contract"]
    assert scoring["no_second_llm"] is True
    assert scoring["no_regex_scope_parser"] is True
    assert scoring["no_service_name_scope_inference"] is True


def test_a9r_matrix_required_scenarios_present() -> None:
    matrix = _load_matrix()
    case_ids = {case["id"] for case in matrix["cases"]}
    missing = _REQUIRED_CASE_IDS - case_ids
    assert not missing, f"missing required A9R cases: {sorted(missing)}"


def test_a9r_matrix_does_not_modify_prior_artifact_paths() -> None:
    matrix = _load_matrix()
    immutable = set(matrix["immutable_prior_artifacts"])
    assert "evals/v5/demo/patient_scope_shadow_matrix.json" in immutable
    assert "evals/v5/demo/patient_scope_shadow_matrix_v2.json" in immutable
    assert str(_MATRIX) not in immutable


@pytest.mark.parametrize(
    "case_id,forbidden",
    [
        ("a9r_negative_01_all_on_4_info", "full_arch"),
        ("a9r_negative_02_all_on_4_price", "full_arch"),
        ("a9r_negative_03_implant_word_only", "implant_placed"),
    ],
)
def test_a9r_negative_cases_forbid_scope_inference(case_id: str, forbidden: str) -> None:
    matrix = _load_matrix()
    case = next(item for item in matrix["cases"] if item["id"] == case_id)
    assert forbidden in case.get("forbidden_inferences", [])


def test_a9r_correction_case_is_multi_turn() -> None:
    matrix = _load_matrix()
    case = next(item for item in matrix["cases"] if item["id"] == "a9r_correction_01_one_tooth_after_full_arch")
    assert len(case["turns"]) == 2
    assert case["turns"][1]["must_not_keep_prior"]["extent"] == "full_arch"
