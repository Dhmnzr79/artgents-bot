from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey, UiButtonCandidate
from contracts.response_plan_materialization import D2SourceUiAuthority, OfferConditionEvidence
from core.d2_snapshot_sources import D2SnapshotBindingError, build_d2_snapshot_sources
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response


_AS_OF = date(2026, 9, 18)


def _envelope(snapshot, view, request: dict[str, object], *, commercial_intent: str = "price"):
    payload = production_envelope_template(
        patient_text="D1R fixture.", commercial_intent=commercial_intent,
        primary_price_request_id="r1" if request["kind"] == "price" else None,
        request_understanding={"subjects": [], "requests": [request]},
    )
    return parse_production_envelope_json(
        json.dumps(payload), active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )


def _price(service_id: str = "tooth_extraction") -> dict[str, object]:
    return {
        "request_id": "r1", "kind": "price", "subject_id": None,
        "context": "general_information", "policy_ids": [], "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": None,
        "service_id": service_id, "topic_id": None, "statement_mode": "question",
    }


def test_terms_absence_and_corruption_are_distinct() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    envelope = _envelope(snapshot, view, _price())
    sources = build_d2_snapshot_sources(snapshot, model_view=view, envelope=envelope, session_key=SessionKey(client_id="demo", sid="terms"))
    outcome = resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.d2_price_block.rows[0].condition_texts == ()

    unknown = OfferConditionEvidence(source_client_id="demo", offer_id="tooth_extraction.default", completeness="unknown")
    outcome = resolve_d2_envelope_response(envelope, sources.model_copy(update={"condition_evidence_by_offer": {unknown.offer_id: unknown}}), as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "complete"

    bad_files = tuple((path, b"{broken") if path == "target_response/pricebook/services/tooth_extraction.default.json" else (path, body) for path, body in snapshot.files)
    corrupt = replace(snapshot, files=bad_files)
    with pytest.raises(Exception, match="snapshot_bundle_invalid"):
        build_d2_snapshot_sources(corrupt, model_view=view, envelope=envelope, session_key=SessionKey(client_id="demo", sid="bad"))


def test_unavailable_price_defaults_keep_content_and_cta() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    content = {
        "request_id": "r2", "kind": "content", "subject_id": None,
        "context": "general_information", "policy_ids": [], "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": "D1R fixture.",
        "content_ref": "implantation__faq__pain.md", "content_section_refs": ["a:sedatsiya-i-narkoz"],
        "service_id": "classic", "topic_id": "implantation", "statement_mode": "question",
    }
    payload = production_envelope_template(
        patient_text="D1R fixture.", commercial_intent="price", primary_price_request_id="r1",
        request_understanding={"subjects": [], "requests": [_price(), content]},
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload), active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    sources = build_d2_snapshot_sources(snapshot, model_view=view, envelope=envelope, session_key=SessionKey(client_id="demo", sid="missing"))
    payload = sources.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["active"] = False
    unavailable_sources = sources.__class__.model_validate(payload)

    outcome = resolve_d2_envelope_response(envelope, unavailable_sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "degraded"
    assert "К сожалению, у меня пока нет информации о стоимости этой услуги" in outcome.rendered_text
    assert "Седация и наркоз" in outcome.rendered_text
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["consult"]


def test_optional_ui_does_not_block_answer() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    content = {
        "request_id": "r1", "kind": "content", "subject_id": None,
        "context": "general_information", "policy_ids": [], "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": "D1R fixture.",
        "content_ref": "implantation__faq__pain.md", "content_section_refs": ["a:sedatsiya-i-narkoz"],
        "service_id": "classic", "topic_id": "implantation", "statement_mode": "question",
    }
    envelope = _envelope(snapshot, view, content, commercial_intent="none")
    sources = build_d2_snapshot_sources(snapshot, model_view=view, envelope=envelope, session_key=SessionKey(client_id="demo", sid="ui"))
    unavailable_ui = sources.model_copy(update={"d2_source_ui": ()})
    outcome = resolve_d2_envelope_response(envelope, unavailable_ui, as_of=_AS_OF)
    assert "Седация и наркоз" in outcome.rendered_text
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["price"]

    invalid = D2SourceUiAuthority(
        source_client_id="demo", content_ref="implantation__faq__pain.md",
        cta=UiButtonCandidate(source_client_id="demo", button_id="invalid", label="Broken", action_kind="contact"),
    )
    outcome = resolve_d2_envelope_response(envelope, sources.model_copy(update={"d2_source_ui": (invalid,)}), as_of=_AS_OF)
    assert "Седация и наркоз" in outcome.rendered_text
    assert any(item.code == "materialization_optional_unavailable" for item in outcome.materialization_diagnostics)


def test_tenant_view_and_source_binding() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    envelope = _envelope(snapshot, view, _price())
    with pytest.raises(D2SnapshotBindingError, match="snapshot_session_mismatch"):
        build_d2_snapshot_sources(snapshot, model_view=view, envelope=envelope, session_key=SessionKey(client_id="other", sid="x"))
    forged = replace(view, published_terms=())
    with pytest.raises(D2SnapshotBindingError, match="snapshot_view_forged"):
        build_d2_snapshot_sources(snapshot, model_view=forged, envelope=envelope, session_key=SessionKey(client_id="demo", sid="x"))

    content = {
        **_price(), "kind": "content", "content_text": "D1R fixture.",
        "content_ref": "implantation__faq__pain.md", "content_section_refs": ["a:sedatsiya-i-narkoz"],
        "service_id": "veneers", "topic_id": None,
    }
    scoped = _envelope(snapshot, view, content, commercial_intent="none")
    sources = build_d2_snapshot_sources(
        snapshot, model_view=view, envelope=scoped, session_key=SessionKey(client_id="demo", sid="scope")
    )
    outcome = resolve_d2_envelope_response(scoped, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[0].status == "answered"
    assert outcome.resolved.d2_request_parts[0].content_ref is None
    assert "D1R fixture." in outcome.rendered_text

    wrong_topic = {**content, "service_id": "classic", "topic_id": "prosthetics"}
    scoped = _envelope(snapshot, view, wrong_topic, commercial_intent="none")
    sources = build_d2_snapshot_sources(
        snapshot, model_view=view, envelope=scoped, session_key=SessionKey(client_id="demo", sid="topic")
    )
    outcome = resolve_d2_envelope_response(scoped, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_request_parts[0].status == "answered"
    assert outcome.resolved.d2_request_parts[0].content_ref is None
    assert "D1R fixture." in outcome.rendered_text
