"""Governance tests for frozen architecture comparison matrix."""

from __future__ import annotations

import json

from evals.v5.arch_compare.arch_compare_contract import (
    EXPECTED_SCENARIO_COUNT,
    EXPECTED_TURN_COUNT,
    FROZEN_MATRIX_DIGEST,
    MATRIX_SCHEMA,
    matrix_digest_sha256,
)
from evals.v5.arch_compare.arch_compare_matrix import (
    assert_frozen_matrix_unchanged,
    build_matrix_document,
    frozen_matrix_digest,
    load_matrix_document,
    matrix_json_path,
    parse_scenario_specs,
)


def test_build_matrix_matches_frozen_file() -> None:
    built = build_matrix_document()
    on_disk = json.loads(matrix_json_path().read_bytes().decode("utf-8"))
    assert on_disk["schema"] == MATRIX_SCHEMA
    assert on_disk["scenarios"] == built["scenarios"]


def test_matrix_digest_pin() -> None:
    assert frozen_matrix_digest() == FROZEN_MATRIX_DIGEST


def test_matrix_arithmetic() -> None:
    specs = parse_scenario_specs()
    assert len(specs) == EXPECTED_SCENARIO_COUNT
    turn_count = sum(len(row.turns) for row in specs)
    assert turn_count == EXPECTED_TURN_COUNT


def test_frozen_matrix_unchanged_guard() -> None:
    assert_frozen_matrix_unchanged()


def test_matrix_has_no_model_patient_text() -> None:
    doc = load_matrix_document()
    serialized = json.dumps(doc, ensure_ascii=False)
    assert "patient_text" not in serialized


def test_matrix_digest_normalizes_lf_crlf_and_cr_equally() -> None:
    base = b'{"schema":"one_call_arch_compare_matrix_v1","note":"x"}'
    lf = base
    crlf = base.replace(b"\n", b"\r\n")
    cr_only = base.replace(b"\n", b"\r")
    expected = matrix_digest_sha256(lf)
    assert matrix_digest_sha256(crlf) == expected
    assert matrix_digest_sha256(cr_only) == expected


def test_matrix_digest_changes_on_content_byte() -> None:
    base = b'{"schema":"one_call_arch_compare_matrix_v1","note":"x"}'
    changed = b'{"schema":"one_call_arch_compare_matrix_v1","note":"y"}'
    assert matrix_digest_sha256(base) != matrix_digest_sha256(changed)


def test_matrix_digest_on_disk_matches_frozen_pin() -> None:
    on_disk = matrix_json_path().read_bytes()
    assert matrix_digest_sha256(on_disk) == FROZEN_MATRIX_DIGEST
    assert frozen_matrix_digest() == FROZEN_MATRIX_DIGEST
