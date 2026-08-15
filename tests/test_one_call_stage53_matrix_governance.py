"""Governance tests for frozen Stage 5.3 multiclient matrix."""

from __future__ import annotations

import hashlib
import json

from evals.v5.stage53.one_call_stage53_contract import (
    EXPECTED_CASE_COUNT,
    EXPECTED_CASE_IDS,
    EXPECTED_DEMO_CASE_COUNT,
    EXPECTED_HTTP_TURN_COUNT,
    EXPECTED_MULTI_TURN_SESSION_COUNT,
    EXPECTED_NIKADENT_CASE_COUNT,
    EXPECTED_ONE_CALL_SINGLE_TURN_COUNT,
    EXPECTED_SINGLE_TURN_CASE_COUNT,
    EXPECTED_TOTAL_FAKE_PROVIDER_CALLS,
    EXPECTED_ZERO_CALL_SINGLE_TURN_COUNT,
    FROZEN_MATRIX_SHA256,
    MATRIX_SCHEMA,
)
from evals.v5.stage53.one_call_stage53_matrix import (
    account_client_for_case,
    assert_frozen_matrix_unchanged,
    assert_matrix_arithmetic,
    build_matrix_document,
    frozen_matrix_sha256,
    load_matrix_document,
    matrix_json_path,
    parse_case_specs,
)


def test_build_matrix_document_matches_expected_case_ids() -> None:
    doc = build_matrix_document()
    case_ids = [row["case_id"] for row in doc["cases"]]
    assert case_ids == list(EXPECTED_CASE_IDS)
    assert len(case_ids) == EXPECTED_CASE_COUNT


def test_build_matrix_arithmetic() -> None:
    doc = build_matrix_document()
    assert_matrix_arithmetic(doc)


def test_frozen_matrix_file_exists_and_matches_builder() -> None:
    path = matrix_json_path()
    assert path.is_file()
    on_disk = json.loads(path.read_bytes().decode("utf-8"))
    built = build_matrix_document()
    assert on_disk["schema"] == MATRIX_SCHEMA
    assert on_disk["cases"] == built["cases"]


def test_frozen_matrix_sha256_pin() -> None:
    assert FROZEN_MATRIX_SHA256
    actual = frozen_matrix_sha256()
    assert actual == FROZEN_MATRIX_SHA256


def test_frozen_matrix_governance_contract() -> None:
    assert FROZEN_MATRIX_SHA256
    assert_frozen_matrix_unchanged()
    assert_matrix_arithmetic()


def test_matrix_contract_arithmetic_constants() -> None:
    specs = parse_case_specs()
    assert len(specs) == EXPECTED_CASE_COUNT
    multi = sum(1 for case in specs if len(case.turns) > 1)
    single = len(specs) - multi
    assert single == EXPECTED_SINGLE_TURN_CASE_COUNT
    assert multi == EXPECTED_MULTI_TURN_SESSION_COUNT
    turns = sum(len(case.turns) for case in specs)
    assert turns == EXPECTED_HTTP_TURN_COUNT
    demo = sum(
        1
        for case in specs
        if account_client_for_case(case.case_id, case.client_id) == "demo"
    )
    nika = sum(
        1
        for case in specs
        if account_client_for_case(case.case_id, case.client_id) == "nikadent"
    )
    assert demo == EXPECTED_DEMO_CASE_COUNT
    assert nika == EXPECTED_NIKADENT_CASE_COUNT
    zero_single = sum(
        1
        for case in specs
        if len(case.turns) == 1 and case.turns[0].provider_calls == 0
    )
    one_single = sum(
        1
        for case in specs
        if len(case.turns) == 1 and case.turns[0].provider_calls == 1
    )
    assert zero_single == EXPECTED_ZERO_CALL_SINGLE_TURN_COUNT
    assert one_single == EXPECTED_ONE_CALL_SINGLE_TURN_COUNT
    total_calls = sum(turn.provider_calls for case in specs for turn in case.turns)
    assert total_calls == EXPECTED_TOTAL_FAKE_PROVIDER_CALLS


def test_matrix_sha_changes_when_document_changes() -> None:
    doc = build_matrix_document()
    payload = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    sha = hashlib.sha256(payload).hexdigest()
    assert len(sha) == 64
