from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path

import pytest

from evals.v5.patient_scope_availability_v2 import (
    NOT_APPLICABLE_STATUS,
    PRE_PLANNER_MANUAL_CONTACT_REASON,
    classify_manual_contact_not_applicable,
)


_EXPECTED = ("not_applicable", "pre_planner_manual_contact")
_HELPER_PATH = Path("evals/v5/patient_scope_availability_v2.py")


def _git_blob_hash(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def test_exact_manual_contact_without_metadata_first_is_not_applicable() -> None:
    response = {"meta": {"service_route": "ingress_manual_contact"}}

    assert classify_manual_contact_not_applicable(response) == _EXPECTED


@pytest.mark.parametrize(
    "metadata_first",
    [
        {},
        {"turn_frame_shadow_status": "missing"},
        {"unrelated_observability": True},
    ],
)
def test_manual_contact_metadata_dict_without_frame_key_is_eligible(
    metadata_first,
) -> None:
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": metadata_first,
        }
    }

    assert classify_manual_contact_not_applicable(response) == _EXPECTED


@pytest.mark.parametrize("metadata_first", [None, [], "", "malformed", 0, False])
def test_present_non_dict_metadata_first_fails_closed(metadata_first) -> None:
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": metadata_first,
        }
    }

    assert classify_manual_contact_not_applicable(response) is None


@pytest.mark.parametrize(
    "frame",
    [
        {"patient_scope": {"extent": "unknown"}},
        {},
        None,
        [],
        "malformed",
        0,
    ],
)
def test_any_present_shadow_frame_value_stays_with_caller_extraction(frame) -> None:
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": {"turn_frame_shadow": frame},
        }
    }

    assert classify_manual_contact_not_applicable(response) is None


@pytest.mark.parametrize("status", ["not_available", "degraded", " NOT_AVAILABLE ", "DeGrAdEd"])
def test_runtime_status_priority_is_preserved(status: str) -> None:
    response = {
        "meta": {
            "service_route": "ingress_manual_contact",
            "metadata_first": {"turn_frame_shadow_status": status},
        }
    }

    assert classify_manual_contact_not_applicable(response) is None


def test_route_allows_only_case_and_whitespace_normalization() -> None:
    response = {"meta": {"service_route": "  InGrEsS_MaNuAl_CoNtAcT  "}}

    assert classify_manual_contact_not_applicable(response) == _EXPECTED


@pytest.mark.parametrize(
    "service_route",
    [
        "ingress_hard_stop_non_target",
        "ingress_not_offered_policy",
        "ingress_service_not_offered",
        "ingress_normal",
        "lead_flow",
        "noise",
        "promo",
        "ref",
        "ingress_manual_contact_extra",
        "pre_ingress_manual_contact",
        "manual_contact",
        "",
        None,
    ],
)
def test_other_or_near_match_routes_are_not_reclassified(service_route) -> None:
    response = {"meta": {"service_route": service_route}}

    assert classify_manual_contact_not_applicable(response) is None


def test_ingress_route_without_exact_service_route_is_insufficient() -> None:
    response = {"meta": {"ingress_route": "manual_contact"}}

    assert classify_manual_contact_not_applicable(response) is None


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        "malformed",
        0,
        {},
        {"meta": None},
        {"meta": []},
        {"meta": "malformed"},
    ],
)
def test_non_dict_response_or_meta_fails_closed(response) -> None:
    assert classify_manual_contact_not_applicable(response) is None


def test_helper_does_not_mutate_input_or_echo_private_values() -> None:
    response = {
        "answer": "SECRET-ANSWER",
        "question": "SECRET-QUESTION",
        "history": ["SECRET-HISTORY"],
        "sid": "SECRET-SID",
        "raw_payload": {"secret": "SECRET-RAW"},
        "exception": "SECRET-EXCEPTION",
        "meta": {"service_route": "ingress_manual_contact"},
    }
    before = copy.deepcopy(response)

    result = classify_manual_contact_not_applicable(response)

    assert response == before
    assert result == _EXPECTED
    serialized = repr(result)
    for secret in (
        "SECRET-ANSWER",
        "SECRET-QUESTION",
        "SECRET-HISTORY",
        "SECRET-SID",
        "SECRET-RAW",
        "SECRET-EXCEPTION",
    ):
        assert secret not in serialized


def test_public_constants_are_exact() -> None:
    assert NOT_APPLICABLE_STATUS == "not_applicable"
    assert PRE_PLANNER_MANUAL_CONTACT_REASON == "pre_planner_manual_contact"


def test_helper_imports_only_standard_typing() -> None:
    source = _HELPER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_HELPER_PATH))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert imports == ["__future__", "typing"]
    for forbidden in (
        "flask",
        "app",
        "session",
        "planner",
        "resolver",
        "contracts",
        "client",
        "openai",
        "requests",
        "httpx",
        "os",
    ):
        assert not any(
            name == forbidden or name.startswith(f"{forbidden}.")
            for name in imports
        )


def test_runtime_product_modules_do_not_import_eval_taxonomy_helper() -> None:
    paths = sorted(Path(".").glob("*.py"))
    for root in (Path("core"), Path("contracts"), Path("orchestration")):
        paths.extend(sorted(root.rglob("*.py")))
    offenders = [
        path.as_posix()
        for path in paths
        if "patient_scope_availability_v2" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_protected_v1_harness_contract_matrix_and_first_raw_hashes_are_exact() -> None:
    assert _git_blob_hash(Path("evals/v5/run_patient_scope_shadow_eval.py")) == (
        "2898ff1d56dba3319f4121158ba98e2879cdb579"
    )
    assert _git_blob_hash(Path("tests/test_patient_scope_shadow_eval_contract.py")) == (
        "c2ed5f0655ab8e1dddda1a865ab95c50ffc797b3"
    )
    assert _git_blob_hash(Path("evals/v5/demo/patient_scope_shadow_matrix.json")) == (
        "d459073bbf8767f7ff590ece2958f7aa8cb18b25"
    )
    assert hashlib.sha256(Path("eval_patient_scope_a9_last.txt").read_bytes()).hexdigest().upper() == (
        "478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21"
    )
