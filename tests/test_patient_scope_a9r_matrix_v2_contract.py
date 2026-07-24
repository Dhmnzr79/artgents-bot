from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

_MATRIX_V1 = Path("evals/v5/demo/patient_scope_a9r_matrix.json")
_MATRIX_V2 = Path("evals/v5/demo/patient_scope_a9r_matrix_v2.json")
_V1_BLOB = "36d137112007a3fb0a96ad0759aa111af6115a35"
_V2_BLOB = "6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57"
_TYPO_CASE_ID = "a9r_typo_01_chelyust"
_TYPO_QUESTION_V2 = "Сколько стоит имплантация всей чилюсти?"


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_a9r_v1_matrix_blob_unchanged() -> None:
    assert _git_blob_hash(_MATRIX_V1) == _V1_BLOB


def test_a9r_v2_matrix_blob_frozen() -> None:
    assert _git_blob_hash(_MATRIX_V2) == _V2_BLOB


def test_a9r_v2_schema_and_typo_fix() -> None:
    matrix = _load(_MATRIX_V2)
    assert matrix["schema_version"] == "a9r.patient_scope_authority_prep.v2"
    typo = next(case for case in matrix["cases"] if case["id"] == _TYPO_CASE_ID)
    assert typo["question"] == _TYPO_QUESTION_V2
    assert typo["expected_effective_scope"]["extent"] == "full_arch"


def test_a9r_v2_deep_equal_v1_except_schema_and_typo_question() -> None:
    v1 = _load(_MATRIX_V1)
    v2 = _load(_MATRIX_V2)
    v1_norm = copy.deepcopy(v1)
    v2_norm = copy.deepcopy(v2)
    for matrix in (v1_norm, v2_norm):
        matrix.pop("schema_version", None)
        matrix.pop("immutable_prior_artifacts", None)
        typo = next(case for case in matrix["cases"] if case["id"] == _TYPO_CASE_ID)
        typo["question"] = "__normalized_typo_question__"
    assert v1_norm == v2_norm


def test_a9r_v2_other_cases_unchanged_from_v1() -> None:
    v1_cases = {case["id"]: case for case in _load(_MATRIX_V1)["cases"]}
    v2_cases = {case["id"]: case for case in _load(_MATRIX_V2)["cases"]}
    assert set(v1_cases) == set(v2_cases)
    assert len(v1_cases) == 22
    for case_id, v1_case in v1_cases.items():
        if case_id == _TYPO_CASE_ID:
            continue
        assert v2_cases[case_id] == v1_case


def test_a9r_v2_typo_case_fields_other_than_question_unchanged() -> None:
    v1_typo = next(case for case in _load(_MATRIX_V1)["cases"] if case["id"] == _TYPO_CASE_ID)
    v2_typo = next(case for case in _load(_MATRIX_V2)["cases"] if case["id"] == _TYPO_CASE_ID)
    v1_copy = copy.deepcopy(v1_typo)
    v2_copy = copy.deepcopy(v2_typo)
    v1_copy["question"] = "__normalized__"
    v2_copy["question"] = "__normalized__"
    assert v1_copy == v2_copy


def test_a9r_v2_lists_v1_matrix_as_immutable_prior() -> None:
    matrix = _load(_MATRIX_V2)
    assert "evals/v5/demo/patient_scope_a9r_matrix.json" in matrix["immutable_prior_artifacts"]
