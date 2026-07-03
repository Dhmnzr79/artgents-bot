"""Unit tests for composer parity eval asserts (stage 3.0, no LLM)."""

from __future__ import annotations

import json
import os

from evals.v5.composer_parity import (
    should_skip_legacy_retrieval_checks,
    validate_composer_parity,
)

_EVAL_DEMO = os.path.join(os.path.dirname(__file__), "..", "evals", "v5", "demo")


def _load_cases(name: str) -> list[dict]:
    path = os.path.join(_EVAL_DEMO, name)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("cases") or [])


def test_composer_parity_passes_on_matching_composer_meta():
    row = {
        "composer_parity": {
            "expected_answer_path": "composer",
            "expected_service_id": "all_on_4",
            "expected_packet_aspects": ["price"],
            "expected_packet_amounts": [318000, 368000],
            "require_numeric_gate_pass": True,
            "require_forbidden_claims_empty": True,
        }
    }
    meta = {
        "answer_path": "composer",
        "matched_service_id": "all_on_4",
        "answer_plan": {"aspects": ["price"]},
        "numeric_fact_gate": {"action": "pass"},
        "forbidden_claim_hits": [],
    }
    answer = "All-on-4 от 318 000 и 368 000 ₽ за челюсть."
    assert validate_composer_parity(row=row, answer=answer, meta=meta) is None


def test_composer_parity_fails_missing_amounts():
    row = {
        "composer_parity": {
            "expected_packet_amounts": [318000],
            "require_numeric_gate_pass": False,
        }
    }
    meta = {"answer_path": "composer"}
    reason = validate_composer_parity(row=row, answer="цена по запросу", meta=meta)
    assert reason is not None
    assert "missing_packet_amounts" in reason


def test_expect_not_composer_fails_when_composer_fires():
    row = {"composer_parity": {"expect_not_composer": True}}
    meta = {"answer_path": "composer"}
    reason = validate_composer_parity(row=row, answer="x", meta=meta)
    assert reason is not None
    assert "deterministic" in reason


def test_skip_legacy_doc_checks_only_on_composer_path():
    row = {"composer_parity": {"expected_answer_path": "composer"}}
    assert should_skip_legacy_retrieval_checks(
        meta={"answer_path": "composer"}, row=row
    )
    assert not should_skip_legacy_retrieval_checks(
        meta={"answer_path": "single_source"}, row=row
    )


def test_product_suites_define_composer_parity():
    for fname in ("smoke.json", "risk.json", "golden.json"):
        for case in _load_cases(fname):
            cid = str(case.get("id") or "")
            parity = case.get("composer_parity")
            assert isinstance(parity, dict), f"{fname} {cid}: missing composer_parity"
            if parity.get("expect_not_composer"):
                assert parity["expect_not_composer"] is True
            else:
                assert parity.get("expected_answer_path") == "composer", (
                    f"{fname} {cid}: migratable case needs expected_answer_path=composer"
                )
