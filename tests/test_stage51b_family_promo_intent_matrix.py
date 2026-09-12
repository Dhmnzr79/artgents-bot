"""Stage 5.1B F8: family-only coverage vs priority promo intent matrix."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from contracts.response_schema import ResponseSchemaBundle
from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
from core.target_runtime_client_context import load_target_runtime_client_context
from tests.test_one_call_stage5_1_promotion import _run_presentation_result
from tests.test_sales_one_plus_turn import answer_envelope

_PROMO_TEXT = "При оплате в день обращения — скидка до 15% на имплантацию."


def _family_only_all_on_4_bundle() -> ResponseSchemaBundle:
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
            "facts": {
                "implant_same_day_discount": {
                    "id": "implant_same_day_discount",
                    "kind": "promo",
                    "catalog_label": "Скидка при оплате в день обращения",
                    "text_fact": _PROMO_TEXT,
                    "render_mode": "strict",
                    "active": True,
                    "allowed_service_ids": ["all_on_4"],
                },
            },
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 3,
                    "max_amplifiers_per_turn": 2,
                    "max_scenarios_per_turn": 2,
                },
                "priority_service_promos": {
                    "all_on_4": {
                        "ordered_fact_refs": ["fact:implant_same_day_discount"],
                    },
                },
                "promotion_overview": {"ordered_fact_refs": []},
                "scenario_rules": {},
                "cta_contexts": {"service": "plan", "default": "callback"},
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


def _family_context() -> object:
    bundle = _family_only_all_on_4_bundle()
    return replace(
        load_target_runtime_client_context("demo"),
        bundle=bundle,
        consultation_values=(),
    )


def _run_family_presentation(
    *,
    commercial_intent: str,
    patient_text: str = "All-on-4 — популярный протокол.",
    shown_fact_ids: tuple[str, ...] = (),
    last_rendered_promo_fact_id: str | None = None,
) -> object:
    envelope = answer_envelope(
        patient_text,
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        service_id="all_on_4",
        commercial_intent=commercial_intent,
        extent="full_arch",
        jaw="lower",
    )
    return _run_presentation_result(
        envelope_json=envelope,
        patient_text=patient_text,
        user_message="Расскажите про All-on-4",
        today=date(2026, 8, 1),
        context_override=_family_context(),
        shown_fact_ids=shown_fact_ids,
        last_rendered_promo_fact_id=last_rendered_promo_fact_id,
    )


def test_none_intent_shows_promo_not_family_price() -> None:
    result = _run_family_presentation(commercial_intent="none")
    assert result.status == "ok"
    assert result.price_coverage_kind == "family_context"
    assert _PROMO_TEXT in result.final_patient_text
    assert result.rendered_promo_fact_ids == ("implant_same_day_discount",)
    assert result.pending_session_delta is not None
    assert "implant_same_day_discount" in result.pending_session_delta.shown_fact_ids
    assert (
        result.pending_session_delta.last_rendered_promo_fact_id
        == "implant_same_day_discount"
    )
    assert "35\u00a0000" not in result.final_patient_text
    assert "за один имплант" not in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER not in result.final_patient_text
    assert result.family_price_context is None


def test_none_intent_repeat_turn_does_not_re_show_promo() -> None:
    first = _run_family_presentation(commercial_intent="none")
    second = _run_family_presentation(
        commercial_intent="none",
        shown_fact_ids=("implant_same_day_discount",),
        last_rendered_promo_fact_id="implant_same_day_discount",
    )
    assert first.rendered_promo_fact_ids == ("implant_same_day_discount",)
    assert second.rendered_promo_fact_ids == ()
    assert _PROMO_TEXT not in second.final_patient_text


def test_price_intent_shows_family_context_without_promo_or_card() -> None:
    hostile = "All-on-4 стоит от 35 000 ₽ со скидкой 20%."
    result = _run_family_presentation(
        commercial_intent="price",
        patient_text=hostile,
    )
    assert result.status == "ok"
    assert "35\u00a0000" in result.final_patient_text
    assert "за один имплант" in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER in result.final_patient_text
    assert result.authoritative_commerce is None
    assert result.rendered_promo_fact_ids == ()
    assert "15%" not in result.final_patient_text
    assert "20%" not in result.final_patient_text


@pytest.mark.parametrize(
    "commercial_intent",
    ["payment", "included", "promotion"],
)
def test_non_price_intents_do_not_leak_family_amount(
    commercial_intent: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.one_call_presentation_pass.resolve_price_coverage_kind",
        lambda *_args, **_kwargs: "family_context",
    )
    envelope_kwargs: dict[str, object] = {
        "service_reference_status": "resolved",
        "requested_service_id": "all_on_4",
        "service_id": "all_on_4",
        "commercial_intent": commercial_intent,
        "extent": "full_arch",
        "jaw": "lower",
    }
    if commercial_intent == "promotion":
        envelope_kwargs["promotion_scope"] = "service"
    envelope = answer_envelope(
        "All-on-4 — популярный протокол.",
        **envelope_kwargs,
    )
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text="All-on-4 — популярный протокол.",
        user_message="Расскажите про All-on-4",
        today=date(2026, 8, 1),
        context_override=replace(
            load_target_runtime_client_context("demo"),
            consultation_values=(),
        ),
    )
    assert result.status == "ok"
    assert result.price_coverage_kind == "family_context"
    assert "Ориентир по имплантации" not in result.final_patient_text
    assert "за один имплант" not in result.final_patient_text
    assert FAMILY_CONTEXT_DISCLAIMER not in result.final_patient_text
    assert result.family_price_context is None
