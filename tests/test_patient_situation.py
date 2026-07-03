"""Patient situation detection — Slice 1 unit tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from core.patient_situation import detect_patient_situation

ONE_TOOTH_CASES = [
    "нет одного зуба",
    "нужно поставить один зуб",
    "сколько стоит восстановить один зуб",
    "удалили зуб, хочу имплант",
    "удалили шестёрку, хочу восстановить",
    "хочу закрыть промежуток",
]

FULL_ARCH_CASES = [
    "нет зубов вообще",
    "нет всех зубов",
    "нужно восстановить всю челюсть",
    "зубов почти не осталось",
]

UPPER_JAW_CASES = [
    "нет зубов на верхней челюсти",
    "верхняя челюсть",
    "сказали мало кости сверху",
]

PROSTHETIC_STAGE_CASES = [
    "имплант уже стоит, нужна коронка",
    "нужно поставить коронку на имплант",
    "протез на имплантах",
    "уже вкручен имплант, нужна коронка",
]

BONE_DEFICIT_CASES = [
    "мало кости",
    "нужен синус-лифтинг",
    "можно без костной пластики",
    "сказали кости мало",
]

EXTRACTION_IMPLANT_CASES = [
    "нужно удалить зуб и поставить имплант",
    "можно сразу после удаления",
]

URGENT_CASES = [
    "сломался зуб",
    "болит зуб",
    "срочно удалить",
    "можно сегодня",
]

GENERIC_IMPLANT_CASES = [
    "что такое имплантация",
    "какие есть виды имплантации",
    "хочу имплант, с чего начать",
]

UNKNOWN_VAGUE_CASES = [
    "имплант",
    "зуб",
    "помогите",
]

BROAD_RESTORE_TOOTH_CASES = [
    "хочу восстановить зуб",
    "сколько стоит восстановить зуб",
    "нужно восстановить зуб",
]


@pytest.mark.parametrize("question", ONE_TOOTH_CASES)
def test_one_tooth_missing(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "one_tooth_missing"
    assert result.patient_scope == "one_tooth"
    assert result.source == "rule_based"
    assert result.confidence >= 0.8
    assert result.evidence
    assert "all_on_4" in result.exclude_service_ids


@pytest.mark.parametrize("question", FULL_ARCH_CASES)
def test_full_arch_missing(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "full_arch_missing"
    assert result.patient_scope == "full_jaw"
    assert result.confidence >= 0.85


@pytest.mark.parametrize("question", UPPER_JAW_CASES)
def test_upper_jaw_missing_or_complex(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "upper_jaw_missing_or_complex"
    assert result.patient_scope == "upper_jaw"


@pytest.mark.parametrize("question", PROSTHETIC_STAGE_CASES)
def test_existing_implant_prosthetic_stage(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "existing_implant_prosthetic_stage"
    assert result.patient_scope == "prosthetic_stage"
    assert "implant_supported_prosthetics" in result.preferred_service_ids


@pytest.mark.parametrize("question", BONE_DEFICIT_CASES)
def test_bone_deficit_or_grafting(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind in {"bone_deficit_or_grafting", "upper_jaw_missing_or_complex"}
    assert result.patient_scope in {"adjunct", "upper_jaw"}
    assert result.next_best_action in {"ct", "consult"}


@pytest.mark.parametrize("question", EXTRACTION_IMPLANT_CASES)
def test_extraction_then_implant(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "extraction_then_implant"
    assert result.patient_scope == "one_tooth"


@pytest.mark.parametrize("question", URGENT_CASES)
def test_urgent_problem(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "urgent_problem"
    assert result.patient_scope == "urgent"
    assert result.next_best_action == "urgent_booking"


@pytest.mark.parametrize("question", GENERIC_IMPLANT_CASES)
def test_generic_implant_interest(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "generic_implant_interest"
    assert result.patient_scope == "generic"


@pytest.mark.parametrize("question", BROAD_RESTORE_TOOTH_CASES)
def test_broad_restore_tooth_not_full_arch(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind != "full_arch_missing"
    assert result.patient_scope != "full_jaw"


@pytest.mark.parametrize("question", UNKNOWN_VAGUE_CASES)
def test_unknown_vague(question: str) -> None:
    result = detect_patient_situation(question)
    assert result.kind == "unknown"
    assert result.should_clarify is True


def test_indirect_vague_location_should_clarify() -> None:
    result = detect_patient_situation("пустое место сбоку")
    assert result.kind == "unknown"
    assert result.should_clarify is True
    assert result.clarify_question


def test_chew_side_ambiguous_few_teeth() -> None:
    result = detect_patient_situation("нечем жевать справа")
    assert result.kind == "few_teeth_missing"
    assert result.should_clarify is True


def test_price_intent_sets_cue_and_next_action() -> None:
    result = detect_patient_situation("сколько стоит восстановить один зуб")
    assert result.cues.intent == "price"
    assert result.next_best_action == "price_estimate"


def test_choose_solution_intent() -> None:
    result = detect_patient_situation("Что мне подойдет, если нет одного зуба?")
    assert result.kind == "one_tooth_missing"
    assert result.cues.intent == "choose_solution"
    assert result.next_best_action == "consult"


def test_composable_profile_for_upper_full_arch_bone_deficit() -> None:
    result = detect_patient_situation("Нет зубов на верхней челюсти, мало кости, что посоветуете?")
    assert result.problem == "missing_teeth"
    assert result.extent == "full_arch"
    assert result.jaw == "upper"
    assert "bone_deficit" in result.modifiers
    assert result.cues.intent == "choose_solution"


def test_semantic_llm_can_fill_non_literal_choose_solution(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_classify(_q: str, *, client_id: str | None = None, sid: str | None = None):
        return {
            "intent": "choose_solution",
            "problem": "missing_teeth",
            "extent": "full_arch",
            "jaw": "unknown",
            "modifiers": [],
            "confidence": 0.88,
        }

    monkeypatch.setitem(
        sys.modules,
        "core.patient_situation_llm",
        SimpleNamespace(classify_patient_situation_semantic=fake_classify),
    )

    result = detect_patient_situation("Я запутался, какой вариант лечения выбрать", client_id="demo")

    assert result.kind == "full_arch_missing"
    assert result.problem == "missing_teeth"
    assert result.extent == "full_arch"
    assert result.cues.intent == "choose_solution"
    assert "semantic_llm_profile" in result.evidence


def test_semantic_llm_does_not_turn_direct_service_explain_into_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_classify(_q: str, *, client_id: str | None = None, sid: str | None = None):
        return {
            "intent": "choose_solution",
            "problem": "missing_teeth",
            "extent": "full_arch",
            "jaw": "unknown",
            "modifiers": [],
            "confidence": 0.9,
        }

    monkeypatch.setitem(
        sys.modules,
        "core.patient_situation_llm",
        SimpleNamespace(classify_patient_situation_semantic=fake_classify),
    )

    result = detect_patient_situation("Расскажите про All-on-4", client_id="demo")

    assert result.cues.intent != "choose_solution"


def test_no_doc_id_in_result() -> None:
    result = detect_patient_situation("нет одного зуба")
    dumped = result.model_dump()
    assert "doc_id" not in dumped
    assert "file" not in dumped


def test_session_context_accepted_not_required() -> None:
    from contracts.patient_situation import PatientSituationSessionContext

    result = detect_patient_situation(
        "а сколько?",
        session_context=PatientSituationSessionContext(last_question="нет одного зуба"),
    )
    assert result.kind in {"unknown", "one_tooth_missing"}
