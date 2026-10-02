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
from core.response_plan_materialization import resolve_d2_operations


_AS_OF = date(2026, 9, 18)


def _envelope(snapshot, view, request: dict[str, object], *, commercial_intent: str = "price"):
    payload = {"outcome":"dialogue","blocks":[request]}
    return parse_production_envelope_json(json.dumps(payload), active_service_catalog=view.active_service_catalog, service_reference_catalog=view.service_reference_catalog, commercial_fact_catalog=view.commercial_fact_catalog, d2_contract=True)


def _price(service_id="tooth_extraction"):
    return {"request_id":"r1","kind":"price","target":{"type":"service","id":service_id}}


def test_terms_absence_and_corruption_are_distinct() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    envelope = _envelope(snapshot, view, _price())
    sources = build_d2_snapshot_sources(snapshot, model_view=view, operations=envelope.blocks, session_key=SessionKey(client_id='demo', sid='terms'))
    outcome = resolve_d2_operations((envelope).blocks, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.d2_price_block.rows[0].condition_texts == ("за удаление одного зуба",)

    unknown = OfferConditionEvidence(source_client_id="demo", offer_id="tooth_extraction.default", completeness="unknown")
    outcome = resolve_d2_operations((envelope).blocks, sources.model_copy(update={"condition_evidence_by_offer": {unknown.offer_id: unknown}}), as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "complete"

    bad_files = tuple((path, b"{broken") if path == "target_response/pricebook/services/tooth_extraction.default.json" else (path, body) for path, body in snapshot.files)
    corrupt = replace(snapshot, files=bad_files)
    with pytest.raises(Exception, match="snapshot_bundle_invalid"):
        build_d2_snapshot_sources(corrupt, model_view=view, operations=envelope.blocks, session_key=SessionKey(client_id='demo', sid='bad'))


def test_unavailable_price_defaults_keep_content_and_cta() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    content = {'request_id': 'r2', 'kind': 'content', 'content_text': 'D1R fixture.', 'content_ref': 'implantation__faq__pain.md', 'content_section_refs': ['a:sedatsiya-i-narkoz'], 'target': {'type': 'service', 'id': 'classic'} if 'classic' else {'type': 'topic', 'id': 'implantation'} if 'implantation' else None}
    payload = {"outcome":"dialogue","blocks":[_price(), content]}
    envelope = parse_production_envelope_json(json.dumps(payload), active_service_catalog=view.active_service_catalog, service_reference_catalog=view.service_reference_catalog, commercial_fact_catalog=view.commercial_fact_catalog, d2_contract=True)
    sources = build_d2_snapshot_sources(snapshot, model_view=view, operations=envelope.blocks, session_key=SessionKey(client_id='demo', sid='missing'))
    payload = sources.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["active"] = False
    unavailable_sources = sources.__class__.model_validate(payload)

    outcome = resolve_d2_operations((envelope).blocks, unavailable_sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "degraded"
    assert "Стоимость по вашему запросу не указана" in outcome.rendered_text
    assert "Седация и наркоз" in outcome.rendered_text
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["consult"]


def test_optional_ui_does_not_block_answer() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    content = {'request_id': 'r1', 'kind': 'content', 'content_text': 'D1R fixture.', 'content_ref': 'implantation__faq__pain.md', 'content_section_refs': ['a:sedatsiya-i-narkoz'], 'target': {'type': 'service', 'id': 'classic'} if 'classic' else {'type': 'topic', 'id': 'implantation'} if 'implantation' else None}
    envelope = _envelope(snapshot, view, content, commercial_intent="none")
    sources = build_d2_snapshot_sources(snapshot, model_view=view, operations=envelope.blocks, session_key=SessionKey(client_id='demo', sid='ui'))
    unavailable_ui = sources.model_copy(update={"d2_source_ui": ()})
    outcome = resolve_d2_operations((envelope).blocks, unavailable_ui, as_of=_AS_OF)
    assert "Седация и наркоз" in outcome.rendered_text
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["default_consult"]
    assert outcome.ui_projection.buttons[0].label == "Записаться на консультацию"

    invalid = D2SourceUiAuthority(
        source_client_id="demo", content_ref="implantation__faq__pain.md",
        cta=UiButtonCandidate(source_client_id="demo", button_id="invalid", label="Broken", action_kind="contact"),
    )
    outcome = resolve_d2_operations((envelope).blocks, sources.model_copy(update={"d2_source_ui": (invalid,)}), as_of=_AS_OF)
    assert "Седация и наркоз" in outcome.rendered_text
    assert any(item.code == "materialization_optional_unavailable" for item in outcome.materialization_diagnostics)


def test_tenant_view_and_source_binding() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    envelope = _envelope(snapshot, view, _price())
    with pytest.raises(D2SnapshotBindingError, match="snapshot_session_mismatch"):
        build_d2_snapshot_sources(snapshot, model_view=view, operations=envelope.blocks, session_key=SessionKey(client_id='other', sid='x'))
    forged = replace(view, published_terms=())
    with pytest.raises(D2SnapshotBindingError, match="snapshot_view_forged"):
        build_d2_snapshot_sources(snapshot, model_view=forged, operations=envelope.blocks, session_key=SessionKey(client_id='demo', sid='x'))

    content = {
        **_price(), "kind": "content", "content_text": "D1R fixture.",
        "content_ref": "implantation__faq__pain.md", "content_section_refs": ["a:sedatsiya-i-narkoz"],
        "target": {"type":"service","id":"veneers"},
    }
    scoped = _envelope(snapshot, view, content, commercial_intent="none")
    sources = build_d2_snapshot_sources(snapshot, model_view=view, operations=scoped.blocks, session_key=SessionKey(client_id='demo', sid='scope'))
    outcome = resolve_d2_operations((scoped).blocks, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_request_parts[0].status == "unavailable"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_content_source_missing"
    assert "недостаточно информации" in outcome.rendered_text

    wrong_topic = {**content, "target": {"type":"topic","id":"prosthetics"}}
    scoped = _envelope(snapshot, view, wrong_topic, commercial_intent="none")
    sources = build_d2_snapshot_sources(snapshot, model_view=view, operations=scoped.blocks, session_key=SessionKey(client_id='demo', sid='topic'))
    outcome = resolve_d2_operations((scoped).blocks, sources, as_of=_AS_OF)
    assert outcome.resolved.d2_request_parts[0].status == "unavailable"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_content_source_missing"
    assert "недостаточно информации" in outcome.rendered_text
