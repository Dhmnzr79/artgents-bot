"""Parameterized cross-turn regression for explicit service price lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.ui_scope_action import build_ui_scope_ref
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_scope_aware_selection import run_target_scope_aware_selection
from tests.test_final_explicit_service_price_lookup_boundary_implementation import (
    _session_extent_scope,
)

TARGET_ROOT = Path("clients/demo/target_response")
DOCTOR_CATALOG = Path("clients/demo/doctor_catalog.json")

_SESSION_EXTENTS = ("one_tooth", "few_teeth", "full_arch")


def _priced_topic_services() -> list[tuple[str, str]]:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    rows: list[tuple[str, str]] = []
    for service_id, service in bundle.services.items():
        if not service.active or service.content_ref is None:
            continue
        if not (
            service.content_ref.startswith("implantation__")
            or service.content_ref.startswith("prosthetics__")
        ):
            continue
        context = build_service_data_context(bundle, doctors, service_id)
        if not any(offer.active for offer in context.offers):
            continue
        topic = (
            "prosthetics"
            if service.content_ref.startswith("prosthetics__")
            else "implantation"
        )
        rows.append((topic, service_id))
    return sorted(rows, key=lambda item: (item[0], item[1]))


_PRICED_TOPIC_SERVICES = _priced_topic_services()


@pytest.mark.parametrize("session_extent", _SESSION_EXTENTS)
@pytest.mark.parametrize("topic,service_id", _PRICED_TOPIC_SERVICES)
def test_cross_turn_session_extent_explicit_lookup_materializes_offers(
    session_extent: str,
    topic: str,
    service_id: str,
) -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG)
    scope = _session_extent_scope(session_extent, topic=topic)
    selection = run_target_scope_aware_selection(
        bundle,
        doctors,
        effective_scope=scope,
        topic=topic,
        explicit_service_id=service_id,
    )
    assert selection.kind != "no_applicable_services"
    offers = selection.offers_by_service_id.get(service_id, ())
    assert offers, f"{service_id} under session {session_extent} must not be empty"
    for offer in offers:
        assert offer.price.mode in {"fixed", "from", "range", "no_public_price"}
        if offer.price.mode == "no_public_price":
            assert offer.price.approved_text
            continue
        unit = getattr(offer.price, "billing_unit", None)
        assert unit is not None


def test_cross_turn_matrix_covers_demo_priced_catalog() -> None:
    assert len(_PRICED_TOPIC_SERVICES) >= 10
    topics = {topic for topic, _ in _PRICED_TOPIC_SERVICES}
    assert topics == {"implantation", "prosthetics"}
