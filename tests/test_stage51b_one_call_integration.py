"""Stage 5.1B ONE_CALL integration scenarios for braces/aligners."""

from __future__ import annotations

from datetime import date

from contracts.ui_service_action import build_ui_service_ref
from tests.test_one_call_stage5_1_promotion import _run_presentation_result
from tests.test_sales_one_plus_turn import answer_envelope


def test_braces_availability_question_shows_not_offered_and_alternative() -> None:
    envelope = answer_envelope(
        "Брекеты помогают выровнять зубы.",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Брекеты помогают выровнять зубы.",
        user_message="Вы ставите брекеты?",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert result.availability_status == "known_not_offered"
    assert "не устанавливаем" in result.final_patient_text.lower()
    assert "элайнер" in result.final_patient_text.lower()
    assert result.rendered_alternative_service_ids == ("aligners",)
    assert any(
        slot.ref == build_ui_service_ref(service_id="aligners")
        for slot in result.secondary_content_slots
    )


def test_braces_price_request_labels_alternative_price() -> None:
    from contracts.effective_scope import EffectiveScope
    from core.service_availability_presentation import build_alternative_price_lines
    from core.target_runtime_client_context import load_target_runtime_client_context
    from core.target_strategy_context import strategy_match_from_effective_scope

    context = load_target_runtime_client_context("demo")
    effective_scope = EffectiveScope(
        extent="unknown",
        jaw="unknown",
        stage=None,
        topic=None,
        source="unknown",
        provenance="test",
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family="orthodontics",
    )
    lines = build_alternative_price_lines(
        context.bundle,
        alternative_service_ids=("aligners",),
        doctor_catalog=context.doctor_catalog,
        strategy_context=strategy_context,
    )
    assert len(lines) == 1
    assert "195" in lines[0]
    assert "элайнер" in lines[0].lower()


def test_braces_informational_question_keeps_not_offered_authority() -> None:
    envelope = answer_envelope(
        "Брекеты — это ортодонтическая конструкция.",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Брекеты — это ортодонтическая конструкция.",
        user_message="Что такое брекеты?",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert "не устанавливаем" in result.final_patient_text.lower()


def test_unknown_service_is_unresolved_not_not_offered() -> None:
    envelope = answer_envelope(
        "Расскажу про услугу.",
        service_reference_status="unresolved",
        requested_service_id=None,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Расскажу про услугу.",
        user_message="Вы делаете флумбодонтию?",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert result.availability_status == "unresolved"
    assert "не оказывается" not in result.final_patient_text.lower()
    assert result.secondary_content_slots == ()


def test_active_aligners_reference_is_offered() -> None:
    envelope = answer_envelope(
        "Элайнеры — прозрачные капы для выравнивания зубов.",
        service_reference_status="resolved",
        requested_service_id="aligners",
        service_id="aligners",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Элайнеры — прозрачные капы для выравнивания зубов.",
        user_message="Расскажите про элайнеры",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert result.availability_status == "offered"
    assert result.requested_service_id == "aligners"
