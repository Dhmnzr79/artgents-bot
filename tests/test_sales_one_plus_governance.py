"""Historical ONE_CALL helpers and frozen admin fixtures, not current D2 wiring.

Keep helper-accounting and preserved fixture evidence. Cancelled app wrapper,
planner flag and old-model backend wiring assertions were retired at cleanup60.10.
Current invocation/quota/model checks live in native D2 HTTP suites.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.one_call_stage2_fixture import (
    load_stage2_cases,
    normative_boundary_ref,
)

_LOCK_DOC = Path("docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md")
_FIXTURE_PATH = Path("tests/fixtures/one_call_stage2_cases.json")


def test_stage1_provider_budget_wiring_is_present() -> None:
    text = Path("core/provider_call_budget.py").read_text(encoding="utf-8")
    assert "ONE_CALL_LOCKED" in text
    assert "ProviderCallLegacyBlocked" in text
    assert "http_provider_budget_scope" in text


def test_chat_completions_create_reserves_before_transport() -> None:
    llm_text = Path("llm.py").read_text(encoding="utf-8")
    assert "reserve_provider_call" in llm_text
    assert "record_provider_call_outcome" in llm_text


def test_normative_answer_admin_boundary_is_documented() -> None:
    lock_text = _LOCK_DOC.read_text(encoding="utf-8")
    assert "Нормативная граница ANSWER / ADMIN" in lock_text
    assert "будущие" in lock_text.lower() or "будущие" in lock_text
    assert "текущие" in lock_text.lower() or "текущие" in lock_text
    assert "blanket" in lock_text.lower() or "любое медицинское слово" in lock_text
    assert normative_boundary_ref() in lock_text or "Нормативная граница ANSWER / ADMIN" in lock_text
    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture.get("normative_boundary_ref")


def test_frozen_admin_matrix_cases_follow_normative_answer_admin_table() -> None:
    """Checkpoint 1e: fixture a02 still records admin outcome, but active path is model-owned.

    a01/a03: general medical FAQ → model ANSWER. Future sales fears (f01–f03)
    must stay ANSWER.
    """
    from core.local_problem_gate import decide_local_problem_gate

    cases = load_stage2_cases(_FIXTURE_PATH)
    by_id = {case.case_id: case for case in cases}

    for case_id in ("a01", "a03"):
        case = by_id[case_id]
        assert case.expected_decision == "answer"
        assert case.execution_layer == "model"
        assert case.protected_category is None

    case = by_id["a02"]
    assert case.expected_decision == "admin"
    assert decide_local_problem_gate(case.user_message).decision == "pass"

    for case_id in ("f01", "f02", "f03"):
        case = by_id[case_id]
        assert case.expected_decision == "answer"
        assert case.protected_category is None
