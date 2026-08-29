"""Stage 5.1B envelope v4 service reference field tests."""

from __future__ import annotations

import json

import pytest

from contracts.one_call_envelope import OneCallEnvelope, OneCallEnvelopeReferences, required_envelope_field_names
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import (
    OneCallEnvelopeProtocolError,
    dumps_production_envelope,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_client_data import load_target_client_data
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_EXACT_CATALOG,
    _EMPTY_REF_CATALOG,
    answer_envelope,
)


def test_v4_required_field_count_and_defaults() -> None:
    template = production_envelope_template()
    assert required_envelope_field_names() == frozenset(template.keys())
    assert len(template) == 14
    assert template["service_reference_status"] == "none"
    assert template["requested_service_id"] is None


@pytest.mark.parametrize(
    "status,requested,code",
    (
        ("none", "braces", "requested_service_id_forbidden_for_none"),
        ("unresolved", "braces", "requested_service_id_forbidden_for_unresolved"),
        ("resolved", None, "requested_service_id_required_for_resolved"),
    ),
)
def test_service_reference_invariants(status: str, requested: str | None, code: str) -> None:
    payload = production_envelope_template(
        service_reference_status=status,
        requested_service_id=requested,
        patient_text="Ответ.",
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_resolved_active_reference_projects_service_id() -> None:
    payload = dumps_production_envelope(
        patient_text="Расскажите про All-on-4.",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        service_id="all_on_4",
    )
    envelope = parse_production_envelope_json(
        payload,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.service_reference_status == "resolved"
    assert envelope.requested_service_id == "all_on_4"
    assert envelope.service_id == "all_on_4"


def test_resolved_inactive_reference_accepts_null_active_service_id() -> None:
    payload = dumps_production_envelope(
        patient_text="Вы ставите брекеты?",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id=None,
    )
    envelope = parse_production_envelope_json(
        payload,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.requested_service_id == "braces"
    assert envelope.service_id is None


def test_resolved_inactive_reference_rejects_active_service_id_conflict() -> None:
    payload = dumps_production_envelope(
        patient_text="Брекеты.",
        service_reference_status="resolved",
        requested_service_id="braces",
        service_id="aligners",
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="service_id_conflict_inactive_reference"):
        parse_production_envelope_json(
            payload,
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_resolved_unknown_service_id_rejected() -> None:
    payload = dumps_production_envelope(
        patient_text="Услуга.",
        service_reference_status="resolved",
        requested_service_id="flumbodontiya",
        service_id=None,
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="requested_service_id_invalid"):
        parse_production_envelope_json(
            payload,
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_inactive_service_id_still_rejected_in_active_service_id_field() -> None:
    payload = dumps_production_envelope(
        patient_text="Ответ.",
        service_id="braces",
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="service_id_inactive"):
        parse_production_envelope_json(
            payload,
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_one_call_envelope_direct_v4_invariants() -> None:
    with pytest.raises(ValueError, match="requested_service_id_forbidden_for_none"):
        OneCallEnvelope(
            route="ANSWER",
            service_id=None,
            extent=None,
            jaw=None,
            stage=None,
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis=None,
            clarify_service_options=None,
            patient_text="Ответ.",
            service_reference_status="none",
            requested_service_id="braces",
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )


def test_reference_catalog_includes_inactive_ids() -> None:
    catalog = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
    assert "braces" in catalog.service_ids
    assert "braces" in catalog.inactive_service_ids
    assert "aligners" in catalog.active_service_ids
    assert "braces" not in catalog.active_service_ids


def test_active_catalog_excludes_inactive_ids() -> None:
    active = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
    assert "aligners" in active.active_service_ids
    assert "braces" not in active.active_service_ids


def test_blocking_and_streaming_share_v4_parser() -> None:
    payload = answer_envelope(
        "Элайнеры — прозрачные капы.",
        service_reference_status="resolved",
        requested_service_id="aligners",
        service_id="aligners",
    )
    parsed = parse_production_envelope_json(
        payload,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert parsed.requested_service_id == "aligners"
    assert parsed.service_reference_status == "resolved"
