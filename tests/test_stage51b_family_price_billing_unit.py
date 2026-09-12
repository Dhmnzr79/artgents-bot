"""Stage 5.1B F7: family price billing unit presentation tests."""

from __future__ import annotations

from datetime import date

import pytest

from contracts.response_schema import ResponseSchemaBundle
from core.service_availability_presentation import (
    FAMILY_CONTEXT_DISCLAIMER,
    resolve_family_price_context_with_disclaimer,
)
from core.target_family_price_resolution import (
    _format_billing_unit,
    _format_family_level_price,
    resolve_family_price_context_for_service,
)
from tests.test_one_call_stage5_1_promotion import _run_presentation_result
from tests.test_sales_one_plus_turn import answer_envelope


def _family_bundle(
    *,
    mode: str,
    billing_unit: str,
    amount: int = 120000,
    min_amount: int = 35000,
    max_amount: int = 180000,
) -> ResponseSchemaBundle:
    if mode == "fixed":
        price = {
            "mode": "fixed",
            "amount": amount,
            "currency": "RUB",
            "billing_unit": billing_unit,
        }
    elif mode == "from":
        price = {
            "mode": "from",
            "min_amount": min_amount,
            "currency": "RUB",
            "billing_unit": billing_unit,
        }
    else:
        price = {
            "mode": "range",
            "min_amount": min_amount,
            "max_amount": max_amount,
            "currency": "RUB",
            "billing_unit": billing_unit,
        }
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "all_on_4": {
                    "name": "All-on-4",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "content_ref": "implantation__service__all_on_4.md",
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
                        "family_price_id": "implantology_family",
                        "topic": "implantation",
                        "price": price,
                        "applies_to_service_ids": ["all_on_4"],
                        "approved_context": "Ориентир по имплантации",
                    }
                ],
            },
        }
    )


@pytest.mark.parametrize(
    ("billing_unit", "expected_label"),
    [
        ("tooth", "за один зуб"),
        ("implant", "за один имплант"),
        ("tooth_package", "за лечение одного зуба под ключ"),
        ("jaw", "за одну челюсть"),
        ("both_jaws", "за обе челюсти"),
        ("procedure", "за одну процедуру"),
        ("unit", "за одну единицу"),
        ("course", "за курс лечения"),
    ],
)
def test_billing_unit_patient_labels(billing_unit: str, expected_label: str) -> None:
    assert _format_billing_unit(billing_unit) == expected_label


def test_invalid_billing_unit_fail_closed() -> None:
    with pytest.raises(ValueError, match="family_price_billing_unit_invalid"):
        _format_billing_unit("both_jaw")


def test_fixed_from_range_include_billing_unit() -> None:
    fixed = _family_bundle(mode="fixed", billing_unit="jaw", amount=120000)
    from_price = _family_bundle(mode="from", billing_unit="implant", min_amount=35000)
    range_price = _family_bundle(
        mode="range",
        billing_unit="course",
        min_amount=100000,
        max_amount=180000,
    )
    assert _format_family_level_price(fixed.family_prices.records[0].price) == (
        "120\u00a0000 ₽ за одну челюсть"
    )
    assert _format_family_level_price(from_price.family_prices.records[0].price) == (
        "от 35\u00a0000 ₽ за один имплант"
    )
    assert _format_family_level_price(range_price.family_prices.records[0].price) == (
        "от 100\u00a0000 ₽ до 180\u00a0000 ₽ за курс лечения"
    )


def test_family_context_includes_unit_and_disclaimer() -> None:
    bundle = _family_bundle(mode="from", billing_unit="implant", min_amount=35000)
    context = resolve_family_price_context_with_disclaimer(bundle, "all_on_4")
    assert context is not None
    assert "35\u00a0000" in context
    assert "за один имплант" in context
    assert "implant" not in context
    assert FAMILY_CONTEXT_DISCLAIMER in context
    raw = resolve_family_price_context_for_service(bundle, "all_on_4")
    assert raw is not None
    assert "Ориентир по имплантации" in raw
    assert "за один имплант" in raw


def test_family_price_presentation_has_no_exact_card() -> None:
    from dataclasses import replace

    from core.target_runtime_client_context import load_target_runtime_client_context

    bundle = _family_bundle(mode="from", billing_unit="implant", min_amount=35000)
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
    assert result.status == "ok"
    assert "за один имплант" in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER in result.final_patient_text
    assert result.authoritative_commerce is None
    assert result.price_coverage_kind == "family_context"
