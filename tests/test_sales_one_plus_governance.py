from __future__ import annotations

import json
from pathlib import Path

from tests.one_call_stage2_fixture import (
    load_stage2_cases,
    normative_boundary_ref,
)

_LOCK_DOC = Path("docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md")
_FIXTURE_PATH = Path("tests/fixtures/one_call_stage2_cases.json")
_NORMATIVE_ADMIN_CATEGORIES = frozenset(
    {"current_symptom", "personal_medical_question"}
)


def test_stage1_provider_budget_wiring_is_present() -> None:
    text = Path("core/provider_call_budget.py").read_text(encoding="utf-8")
    assert "ONE_CALL_LOCKED" in text
    assert "ProviderCallLegacyBlocked" in text
    assert "http_provider_budget_scope" in text


def test_orchestrate_ask_turn_wraps_http_provider_budget() -> None:
    app_text = Path("app.py").read_text(encoding="utf-8")
    assert "http_provider_budget_scope" in app_text
    assert "_orchestrate_ask_turn_inner" in app_text


def test_chat_completions_create_reserves_before_transport() -> None:
    llm_text = Path("llm.py").read_text(encoding="utf-8")
    assert "reserve_provider_call" in llm_text
    assert "record_provider_call_outcome" in llm_text


def test_planner_speculation_disabled_when_sales_one_plus_on() -> None:
    planner_text = Path("core/planner_compute_executor.py").read_text(encoding="utf-8")
    pre_text = Path("orchestration/pre_resolver_turn.py").read_text(encoding="utf-8")
    assert "SALES_ONE_PLUS_ON" in planner_text
    assert "SALES_ONE_PLUS_ON" in pre_text


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
    """a01–a03: ADMIN per Lock § «Нормативная граница ANSWER / ADMIN».

    Not a blanket «medical/problematic → ADMIN» rule. Future sales fears (f01–f03)
    must stay ANSWER.
    """
    cases = load_stage2_cases(_FIXTURE_PATH)
    by_id = {case.case_id: case for case in cases}

    for case_id in ("a01", "a02", "a03"):
        case = by_id[case_id]
        assert case.expected_decision == "admin"
        assert case.protected_category in _NORMATIVE_ADMIN_CATEGORIES

    for case_id in ("f01", "f02", "f03"):
        case = by_id[case_id]
        assert case.expected_decision == "answer"
        assert case.protected_category is None

    fixture_text = _FIXTURE_PATH.read_text(encoding="utf-8")
    matrix = json.loads(fixture_text)
    local_admin_ids = {
        row["case_id"]
        for row in matrix["cases"]
        if row.get("execution_layer") == "local" and row.get("expected_decision") == "admin"
    }
    assert local_admin_ids == {"a01", "a02", "a03"}


def test_stage3a_production_stack_has_no_plus_model_fallback() -> None:
    paths = (
        Path("core/sales_one_plus_live_backend.py"),
        Path("orchestration/sales_fast_widget_turn.py"),
        Path("core/sales_fast_widget_runtime.py"),
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "qwen3.7-plus" not in text
        assert "SALES_ONE_PLUS_FLASH_MODEL" in text
