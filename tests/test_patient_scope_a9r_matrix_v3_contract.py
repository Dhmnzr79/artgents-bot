from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

_MATRIX_V2 = Path("evals/v5/demo/patient_scope_a9r_matrix_v2.json")
_MATRIX_V3 = Path("evals/v5/demo/patient_scope_a9r_matrix_v3.json")
_V2_BLOB = "6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57"
_V3_BLOB = "8ccd9bdc140a192981fcc48ad7ed0367a40b0a84"
_STAGE_02_ID = "a9r_stage_02_natural_tooth_present"


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_a9r_v2_matrix_blob_still_frozen() -> None:
    assert _git_blob_hash(_MATRIX_V2) == _V2_BLOB


def test_a9r_v3_matrix_blob_frozen() -> None:
    assert _git_blob_hash(_MATRIX_V3) == _V3_BLOB


def test_a9r_v3_schema_and_stage_02_label_fix() -> None:
    matrix = _load(_MATRIX_V3)
    assert matrix["schema_version"] == "a9r.patient_scope_authority_prep.v3"
    assert matrix["scoring_contract"]["live_eval_gate"] == "A9R2b"
    stage_02 = next(case for case in matrix["cases"] if case["id"] == _STAGE_02_ID)
    assert stage_02["expected_effective_scope"]["extent"] == "one_tooth"
    assert stage_02["expected_effective_scope"]["stage"] == "natural_tooth_present"


def test_a9r_v3_live_cases_use_a9r2b_phase() -> None:
    matrix = _load(_MATRIX_V3)
    live_cases = [case for case in matrix["cases"] if case["id"].startswith("a9r_") and case.get("phase", "").endswith("_live")]
    assert len(live_cases) == 16
    assert all(case["phase"] == "a9r2b_live" for case in live_cases)


def test_a9r_v3_deep_equal_v2_except_metadata_and_stage_02_extent() -> None:
    v2 = _load(_MATRIX_V2)
    v3 = _load(_MATRIX_V3)
    v2_norm = copy.deepcopy(v2)
    v3_norm = copy.deepcopy(v3)
    for matrix in (v2_norm, v3_norm):
        matrix.pop("schema_version", None)
        matrix.pop("immutable_prior_artifacts", None)
        matrix["scoring_contract"] = copy.deepcopy(matrix["scoring_contract"])
        matrix["scoring_contract"].pop("live_eval_gate", None)
        for case in matrix["cases"]:
            if case.get("phase") in ("a9r2_live", "a9r2b_live"):
                case["phase"] = "__live_phase__"
            if case["id"] == _STAGE_02_ID:
                case["expected_effective_scope"]["extent"] = "__normalized_extent__"
                case["rationale"] = "__normalized_rationale__"
    assert v2_norm == v3_norm


def test_a9r_v3_lists_v2_matrix_as_immutable_prior() -> None:
    matrix = _load(_MATRIX_V3)
    assert "evals/v5/demo/patient_scope_a9r_matrix_v2.json" in matrix["immutable_prior_artifacts"]
