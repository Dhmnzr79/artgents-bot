"""Unit tests for composer live-eval categorization (no LLM)."""

from __future__ import annotations

from evals.v5.run_composer_live_eval import CaseRun, HardCheck, evaluate_hard_checks


def test_c6_control_group_not_composer():
    checks = evaluate_hard_checks(
        answer="price answer",
        meta={"answer_path": "price"},
        expected_path="",
        expected_composer=False,
        expected_amounts=[],
    )
    c6 = next(c for c in checks if c.name == "C6")
    assert c6.status == "PASS"


def test_c6_control_group_fails_if_composer_fired():
    checks = evaluate_hard_checks(
        answer="composed",
        meta={"answer_path": "composer"},
        expected_path="",
        expected_composer=False,
        expected_amounts=[],
    )
    c6 = next(c for c in checks if c.name == "C6")
    assert c6.status == "FAIL"


def test_known_issue_downgrades_to_known_verdict():
    run = CaseRun(
        case_id="A3",
        group="A",
        question="q",
        expected_path="composer",
        expected_aspects=["price"],
        known_issue="service_selection",
        hard_checks=[HardCheck("C1", "FAIL", "missing_amounts=[1]")],
    )
    assert run.verdict == "KNOWN"


def test_real_fail_without_known_marker():
    run = CaseRun(
        case_id="A1",
        group="A",
        question="q",
        expected_path="composer",
        expected_aspects=["price"],
        hard_checks=[HardCheck("C6", "FAIL", "not composer")],
    )
    assert run.verdict == "FAIL"
