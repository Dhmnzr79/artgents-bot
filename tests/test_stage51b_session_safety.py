"""Stage 5.1B session safety for unavailable and unresolved references."""

from __future__ import annotations

from datetime import date

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from core.one_call_envelope_protocol import dumps_production_envelope
from core.sales_one_plus_semantic_authority import (
    bind_semantic_frame,
    governed_ui_authority_from_resolution,
    presentation_active_service_id,
    presentation_commercial_intent,
)
from core.target_client_data import load_target_client_data
from tests.test_one_call_stage5_1_promotion import _run_presentation_result
from tests.test_sales_one_plus_turn import _DEMO_CATALOG, _DEMO_REF_CATALOG, answer_envelope


def _unknown_resolution() -> ExactSalesResolution:
    authority = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    return ExactSalesResolution(None, None, None, None, None, authority, authority, authority, authority, authority)


def test_inactive_reference_nulls_active_service_for_commerce() -> None:
    governed = governed_ui_authority_from_resolution(_unknown_resolution())
    envelope_json = dumps_production_envelope(
        patient_text="Вы ставите брекеты?",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
        commercial_intent="price",
    )
    from core.one_call_envelope_protocol import parse_production_envelope_json

    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert semantic.availability_status == "known_not_offered"
    assert semantic.service_id is None
    assert presentation_active_service_id(semantic) is None
    assert presentation_commercial_intent(semantic) == "none"


def test_stale_session_promo_not_applied_for_inactive_reference() -> None:
    envelope = answer_envelope(
        "На All-on-4 действует скидка 50%.",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
        commercial_intent="none",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="На All-on-4 действует скидка 50%.",
        user_message="Сколько стоят брекеты?",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert result.availability_status == "known_not_offered"
    assert "50%" not in result.final_patient_text
    assert result.rendered_promo_fact_ids == ()


def test_stale_session_promo_not_applied_for_unresolved_reference() -> None:
    envelope = answer_envelope(
        "Скидка 50% на All-on-4.",
        service_reference_status="unresolved",
        requested_service_id=None,
        commercial_intent="none",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="Скидка 50% на All-on-4.",
        user_message="Вы делаете флумбодонтию?",
        today=date(2026, 8, 1),
    )
    assert result.status == "ok"
    assert result.availability_status == "unresolved"
    assert "50%" not in result.final_patient_text
    assert result.rendered_promo_fact_ids == ()
    assert "не вижу" in result.final_patient_text.lower()
