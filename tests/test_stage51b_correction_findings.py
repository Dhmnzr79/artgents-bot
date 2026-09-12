"""Stage 5.1B correction pass tests for Checker findings F1–F6."""

from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.authored_service_alternative import AuthoredServiceAlternative
from contracts.response_schema import ResponseSchemaBundle
from contracts.ui_service_action import build_ui_service_ref
from core.one_call_prompt_contract import ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
from core.service_availability_presentation import build_alternative_secondary_slots
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import read_target_runtime_session
from core.target_ui_service_action import resolve_ui_service_ref_click
from session import mem_reset
from tests.test_one_call_stage5_1_promotion import _run_presentation_result
from tests.test_sales_one_plus_turn import answer_envelope


def test_f1_c1_hostile_model_text_suppressed_for_known_not_offered() -> None:
    hostile = (
        "Да, мы устанавливаем брекеты. Стоимость — 50 000 ₽. Сейчас скидка 20%."
    )
    envelope = answer_envelope(
        hostile,
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
        commercial_intent="price",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=hostile,
        user_message="Сколько стоят брекеты?",
        today=date(2026, 8, 1),
    )
    text = result.final_patient_text.lower()
    assert result.availability_status == "known_not_offered"
    assert "брекет" in text
    assert "устанавливаем брекеты" not in text
    assert "50 000" not in result.final_patient_text
    assert "20%" not in result.final_patient_text
    assert result.authoritative_commerce is None
    assert result.rendered_promo_fact_ids == ()


def test_f1_c2_unresolved_suppresses_model_body() -> None:
    hostile = "Такую услугу клиника точно не оказывает. Она стоит от 30 000 ₽."
    envelope = answer_envelope(
        hostile,
        service_reference_status="unresolved",
        requested_service_id=None,
        commercial_intent="price",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=hostile,
        user_message="Вы делаете флумбодонтию?",
        today=date(2026, 8, 1),
    )
    text = result.final_patient_text
    assert result.availability_status == "unresolved"
    assert "уточните" in text.lower()
    assert "не оказывает" not in text.lower()
    assert "30 000" not in text
    assert result.secondary_content_slots == ()
    assert result.authoritative_commerce is None


def test_f1_c3_stale_session_marketing_not_leaked_on_unavailable() -> None:
    hostile = "Да, мы устанавливаем брекеты. Скидка 50%."
    envelope = answer_envelope(
        hostile,
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
        commercial_intent="price",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=hostile,
        user_message="Сколько стоят брекеты?",
        today=date(2026, 8, 1),
        shown_fact_ids=("promo:stale",),
        shown_amplifier_refs=("fact:stale_amp",),
        last_rendered_promo_fact_id="promo:stale",
    )
    assert "50%" not in result.final_patient_text
    assert result.rendered_promo_fact_ids == ()
    assert result.rendered_amplifier_refs == ()
    delta = result.pending_session_delta
    assert delta is not None
    assert delta.last_rendered_promo_fact_id is None


def test_f2_single_not_offered_copy_with_authored_alternative() -> None:
    envelope = answer_envelope(
        "ignored",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="ignored",
        user_message="Вы ставите брекеты?",
        today=date(2026, 8, 1),
    )
    text = result.final_patient_text
    assert text.count("не оказывается") == 0
    assert text.count("не устанавливаем") == 1
    assert "элайнер" in text.lower()


def test_f3_cross_client_same_service_id_fails_closed() -> None:
    ref = build_ui_service_ref(service_id="aligners")
    followups = (
        TargetRuntimeFollowupItem(ref=ref, label="Элайнеры", client_id="demo"),
    )
    resolution = resolve_ui_service_ref_click(
        ref=ref,
        followups=followups,
        active_service_ids=frozenset({"aligners"}),
        expected_client_id="other_client",
    )
    assert resolution.kind == "clarify"


def test_f3_missing_stored_client_id_fails_closed() -> None:
    ref = build_ui_service_ref(service_id="aligners")
    followups = (TargetRuntimeFollowupItem(ref=ref, label="Элайнеры"),)
    resolution = resolve_ui_service_ref_click(
        ref=ref,
        followups=followups,
        active_service_ids=frozenset({"aligners"}),
        expected_client_id="demo",
    )
    assert resolution.kind == "clarify"


def test_f4_prompt_contract_contains_semantic_rules_and_examples() -> None:
    prompt = ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    assert "service_reference_status" in prompt
    assert "requested_service_id" in prompt
    assert "Classify all closed semantic controls" in prompt
    assert "«Вы ставите брекеты?»" in prompt
    assert "«Сколько стоят брекеты?»" in prompt
    assert "«Что такое брекеты?»" in prompt
    assert "«Вы делаете флумбодонтию?»" in prompt
    assert "ordinary microfact without a named service" in prompt
    assert "Classify commercial_intent and promotion_scope only" not in prompt


def test_f5_braces_aliases_exclude_query_phrases() -> None:
    from core.target_client_data import load_target_client_data

    catalog = ServiceReferenceCatalogSnapshot.from_bundle(
        load_target_client_data("demo").bundle
    )
    payload = json.loads(catalog.canonical_json)
    braces = next(row for row in payload["services"] if row["service_id"] == "braces")
    aliases = {str(item).casefold() for item in braces["aliases"]}
    forbidden = {
        "ставите брекеты",
        "установка брекетов",
        "сколько стоят брекеты",
        "цена брекетов",
    }
    assert forbidden.isdisjoint(aliases)
    assert "брекеты" in aliases


def test_family_context_hostile_model_price_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = ResponseSchemaBundle.model_validate(
        {
            "services": {
                "all_on_4": {
                    "name": "All-on-4",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "selection": {"mode": "context"},
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": {},
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 3,
                    "max_amplifiers_per_turn": 2,
                    "max_scenarios_per_turn": 2,
                },
                "priority_service_promos": {},
                "promotion_overview": {"ordered_fact_refs": []},
                "scenario_rules": {},
                "cta_contexts": {"default": "callback"},
            },
            "family_prices": {
                "version": 1,
                "records": [
                    {
                        "family_price_id": "implantology_from",
                        "topic": "implantation",
                        "price": {
                            "mode": "from",
                            "min_amount": 35000,
                            "currency": "RUB",
                            "billing_unit": "implant",
                        },
                        "applies_to_service_ids": ["all_on_4"],
                        "approved_context": "Ориентир по имплантации",
                    }
                ],
            },
        }
    )
    from dataclasses import replace

    from core.target_runtime_client_context import load_target_runtime_client_context

    context = replace(
        load_target_runtime_client_context("demo"),
        bundle=bundle,
        consultation_values=(),
    )
    hostile = "All-on-4 стоит от 35 000 ₽."
    envelope = answer_envelope(
        hostile,
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        service_id="all_on_4",
        commercial_intent="price",
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=hostile,
        user_message="Сколько стоит All-on-4?",
        today=date(2026, 8, 1),
        context_override=context,
    )
    assert "All-on-4 стоит от 35 000" not in result.final_patient_text
    assert "за один имплант" in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER in result.final_patient_text
    assert result.authoritative_commerce is None


def test_f6_braces_price_full_widget_path(monkeypatch: pytest.MonkeyPatch, flask_app) -> None:
    from core.provider_call_budget import (
        http_provider_budget_scope,
        record_provider_call_outcome,
        reserve_provider_call,
    )

    hostile = "Брекеты стоят 50 000 ₽ со скидкой 20%."
    envelope_json = answer_envelope(
        hostile,
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
        commercial_intent="price",
    )

    class _Backend:
        call_count = 0

        def generate(self, _invocation, /):
            type(self).call_count += 1
            call_index = reserve_provider_call(model="fake-test", source="sales_fast")
            record_provider_call_outcome(call_index=call_index, outcome="success")
            return envelope_json

    backend = _Backend()
    mem_reset("s-braces-price")
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Сколько стоят брекеты?",
            "sid": "s-braces-price",
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"request_id": "rid"}
        with http_provider_budget_scope(request_id="rid", sales_one_plus_on=True):
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid="s-braces-price",
                user_message="Сколько стоят брекеты?",
                backend=backend,
            )

    assert backend.call_count == 1
    assert outcome.provider_calls == 1
    payload = outcome.widget.payload
    answer = str(payload.get("answer") or "")
    assert outcome.widget.kind == "materialized"
    assert "брекет" in answer.lower()
    assert "50 000" not in answer
    assert "20%" not in answer
    assert "элайнер" in answer.lower()
    assert "195\u00a0000" in answer
    quick = payload.get("quick_replies") or []
    alt_ref = build_ui_service_ref(service_id="aligners")
    assert any(item.get("ref") == alt_ref for item in quick)
    session = read_target_runtime_session("s-braces-price")
    stored = next((item for item in session.followups if item.ref == alt_ref), None)
    assert stored is not None
    assert stored.client_id == "demo"
    assert session.last_service_id is None


def test_f6_unresolved_full_widget_path_not_terminal(monkeypatch: pytest.MonkeyPatch, flask_app) -> None:
    hostile = "Такую услугу клиника точно не оказывает. Она стоит от 30 000 ₽."
    envelope_json = answer_envelope(
        hostile,
        service_reference_status="unresolved",
        requested_service_id=None,
        commercial_intent="price",
    )

    class _Backend:
        call_count = 0

        def generate(self, _invocation, /):
            type(self).call_count += 1
            return envelope_json

    backend = _Backend()
    mem_reset("s-unresolved")
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Вы делаете флумбодонтию?",
            "sid": "s-unresolved",
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"request_id": "rid"}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid="s-unresolved",
            user_message="Вы делаете флумбодонтию?",
            backend=backend,
        )

    answer = str(outcome.widget.payload.get("answer") or "")
    assert outcome.widget.kind == "materialized"
    assert "уточните" in answer.lower()
    assert "30 000" not in answer
    assert "не оказывает" not in answer.lower()


def test_two_authored_alternatives_use_service_labels_in_clinic_order() -> None:
    from core.target_client_data import load_target_client_data

    bundle = load_target_client_data("demo").bundle
    authored = AuthoredServiceAlternative(
        requested_service_id="braces",
        alternative_service_ids=("aligners", "professional_whitening"),
        approved_text="Брекеты мы не устанавливаем.",
    )
    slots = build_alternative_secondary_slots(
        bundle,
        alternative_service_ids=authored.alternative_service_ids,
    )
    assert len(slots) == 2
    assert slots[0].label == bundle.services["aligners"].name
    assert slots[1].label == bundle.services["professional_whitening"].name
    assert slots[0].label != bundle.services["braces"].name
    assert slots[1].label != bundle.services["braces"].name
    assert slots[0].ref == build_ui_service_ref(service_id="aligners")
    assert slots[1].ref == build_ui_service_ref(service_id="professional_whitening")


@pytest.fixture
def flask_app():
    import app as app_module

    return app_module.app
