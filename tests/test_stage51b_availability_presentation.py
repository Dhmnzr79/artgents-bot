"""Stage 5.1B availability overlay presentation tests."""

from __future__ import annotations

from core.service_availability_presentation import (
    AvailabilityOverlay,
    build_availability_overlay,
)
from core.target_client_data import load_target_client_data


def _demo_bundle():
    return load_target_client_data("demo").bundle


def test_none_availability_returns_no_overlay() -> None:
    assert (
        build_availability_overlay(
            client_id="demo",
            availability_status="none",
            requested_service_id=None,
            bundle=_demo_bundle(),
        )
        is None
    )


def test_known_not_offered_overlay_uses_authored_text_only() -> None:
    overlay = build_availability_overlay(
        client_id="demo",
        availability_status="known_not_offered",
        requested_service_id="braces",
        bundle=_demo_bundle(),
    )
    assert overlay is not None
    assert overlay.not_offered_text is None
    assert overlay.unresolved_text is None
    assert len(overlay.alternative_texts) == 1
    assert "элайнер" in overlay.alternative_texts[0].lower()


def test_known_not_offered_without_authored_alternative_has_generic_only() -> None:
    from contracts.response_schema import ResponseSchemaBundle

    bundle = ResponseSchemaBundle.model_validate(
        {
            "services": {
                "inactive_only": {
                    "name": "Тестовая услуга",
                    "family": "orthodontics",
                    "roles": [],
                    "active": False,
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
            "family_prices": {"version": 1, "records": []},
        }
    )
    overlay = build_availability_overlay(
        client_id="demo",
        availability_status="known_not_offered",
        requested_service_id="inactive_only",
        bundle=bundle,
    )
    assert isinstance(overlay, AvailabilityOverlay)
    assert overlay.not_offered_text is not None
    assert "не оказывается" in overlay.not_offered_text.lower()
    assert overlay.alternative_texts == ()


def test_unresolved_overlay_has_safe_clarify_text() -> None:
    overlay = build_availability_overlay(
        client_id="demo",
        availability_status="unresolved",
        requested_service_id=None,
        bundle=_demo_bundle(),
    )
    assert overlay is not None
    assert overlay.unresolved_text
    assert "не вижу" in overlay.unresolved_text.lower()
    assert overlay.not_offered_text is None
    assert overlay.alternative_texts == ()
