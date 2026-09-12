"""Stage 5.1B price coverage precedence tests."""

from __future__ import annotations

from contracts.response_schema import ResponseSchemaBundle
from core.service_availability_presentation import (
    append_family_context_disclaimer,
    resolve_family_price_context_with_disclaimer,
    resolve_price_coverage_kind,
)
from core.target_client_data import load_target_client_data
from core.target_family_price_resolution import family_price_applies_to_service


def _demo_bundle():
    return load_target_client_data("demo").bundle


def test_exact_numeric_for_active_service_with_offer() -> None:
    bundle = _demo_bundle()
    coverage = resolve_price_coverage_kind(bundle, service_id="aligners")
    assert coverage == "exact_numeric"


def test_no_public_price_precedence_over_family() -> None:
    bundle = _demo_bundle()
    coverage = resolve_price_coverage_kind(bundle, service_id="bone_graft")
    assert coverage == "no_public_price"


def test_family_context_when_explicit_applicability() -> None:
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
    coverage = resolve_price_coverage_kind(bundle, service_id="all_on_4")
    assert coverage == "family_context"
    context = resolve_family_price_context_with_disclaimer(bundle, "all_on_4")
    assert context is not None
    assert "35" in context
    assert "за один имплант" in context
    assert append_family_context_disclaimer("Текст.") == (
        "Текст. Это ориентир по направлению, а не цена конкретной услуги."
    )


def test_non_applicable_family_price_yields_data_gap() -> None:
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
                "classic": {
                    "name": "Classic",
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
                        "applies_to_service_ids": ["classic"],
                        "approved_context": "Ориентир по имплантации",
                    }
                ],
            },
        }
    )
    assert not family_price_applies_to_service(
        bundle.family_prices.records[0],
        "all_on_4",
    )
    coverage = resolve_price_coverage_kind(bundle, service_id="all_on_4")
    assert coverage == "data_gap"
