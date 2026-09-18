from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_snapshot_sources import D2SnapshotBindingError, build_d2_snapshot_sources
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui


_AS_OF = date(2026, 9, 18)


def _request(
    request_id: str,
    kind: str,
    *,
    service_id: str | None = None,
    topic_id: str | None = None,
    content_ref: str | None = None,
    section_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": kind,
        "subject_id": None,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested",
        "contact_fields": [],
        "content_text": "Нужен точный материал." if kind == "content" else None,
        "content_ref": content_ref,
        "content_section_refs": section_refs or [],
        "service_id": service_id,
        "topic_id": topic_id,
        "statement_mode": "question",
    }


def _parsed_demo_envelope(*requests: dict[str, object]):
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    price_ids = [item["request_id"] for item in requests if item["kind"] == "price"]
    payload = production_envelope_template(
        patient_text="Служебный D1R текст.",
        commercial_intent="price" if price_ids else "none",
        primary_price_request_id=price_ids[0] if price_ids else None,
        request_understanding={"subjects": [], "requests": list(requests)},
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
    )
    sources = build_d2_snapshot_sources(
        snapshot,
        model_view=view,
        envelope=envelope,
        session_key=SessionKey(client_id="demo", sid="c7-demo"),
    )
    return snapshot, envelope, sources


@pytest.mark.parametrize(
    ("service_id", "expected_minimum"),
    (("tooth_extraction", 4_500), ("professional_whitening", 18_000), ("veneers", 35_000)),
)
def test_real_simple_prices_without_metadata(service_id: str, expected_minimum: int) -> None:
    _, envelope, sources = _parsed_demo_envelope(_request("r1", "price", service_id=service_id))

    outcome = resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_price_block is not None
    row = outcome.resolved.d2_price_block.rows[0]
    assert row.mode == "from"
    assert row.min_amount == expected_minimum
    assert "всё включено" not in outcome.rendered_text.lower()
    assert [button.button_id for button in outcome.ui_projection.buttons] == ["price"]


def test_real_implant_terms_are_preserved() -> None:
    _, envelope, sources = _parsed_demo_envelope(_request("r1", "price", service_id="classic", topic_id="implantation"))

    outcome = resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)

    assert outcome.resolved.d2_price_block is not None
    impro = next(row for row in outcome.resolved.d2_price_block.rows if row.offer_id == "classic.one_tooth.impro")
    assert impro.amount == 85_200
    assert "имплант + постоянная коронка" in impro.display_text
    assert "Хирургический этап: 54200 RUB" in "\n".join(impro.condition_texts)
    assert "Ортопедический этап (коронка): 31000 RUB" in "\n".join(impro.condition_texts)
    assert impro.amount == 85_200


def test_real_content_below_korotko() -> None:
    _, envelope, sources = _parsed_demo_envelope(
        _request(
            "r1", "content", service_id="classic", topic_id="implantation",
            content_ref="implantation__faq__pain.md", section_refs=["a:sedatsiya-i-narkoz"],
        ),
        _request(
            "r2", "content", service_id="classic", topic_id="implantation",
            content_ref="implantation__faq__pain.md", section_refs=["a:kakuyu-anesteziyu-ispolzuyut"],
        ),
    )

    outcome = resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)

    assert len(outcome.resolved.information_blocks) == 2
    assert "Седация и наркоз" in outcome.resolved.information_blocks[0].display_text
    assert "Какую анестезию используют" in outcome.resolved.information_blocks[1].display_text
    assert outcome.resolved.information_blocks[0].source_section_refs == ("a:sedatsiya-i-narkoz",)
    assert outcome.ui_projection.video is not None
    assert outcome.ui_projection.video.video_id == "pain-doctor-explains"


@pytest.mark.parametrize("reverse", (False, True))
def test_real_price_and_section_are_ordered(reverse: bool) -> None:
    price = _request("r1", "price", service_id="classic", topic_id="implantation")
    content = _request(
        "r2", "content", service_id="classic", topic_id="implantation",
        content_ref="implantation__faq__pain.md", section_refs=["a:sedatsiya-i-narkoz"],
    )
    _, envelope, sources = _parsed_demo_envelope(*(([content, price]) if reverse else ([price, content])))

    outcome = resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)

    assert outcome.resolved.d2_request_parts[0].request_id == ("r2" if reverse else "r1")
    assert outcome.rendered_text.index("85 200 ₽") < outcome.rendered_text.index("Седация и наркоз") if not reverse else outcome.rendered_text.index("Седация и наркоз") < outcome.rendered_text.index("85 200 ₽")
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [button.button_id for button in outcome.ui_projection.buttons] == ["consult"]


def test_overview_readiness_is_not_optional_ui() -> None:
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    payload = production_envelope_template(
        patient_text="Служебный D1R текст.", commercial_intent="price", primary_price_request_id="r1",
        request_understanding={"subjects": [], "requests": [_request("r1", "price", topic_id="implantation")]},
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False), active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog, commercial_fact_catalog=view.commercial_fact_catalog,
    )
    with pytest.raises(D2SnapshotBindingError, match="direction_overview_not_configured"):
        build_d2_snapshot_sources(snapshot, model_view=view, envelope=envelope, session_key=SessionKey(client_id="demo", sid="overview"))


def test_real_path_never_calls_legacy_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.response_plan_composer_executor as composer_executor
    import core.response_plan_materialization as materialization
    import core.sales_one_plus_live_backend as live_backend

    _, envelope, sources = _parsed_demo_envelope(_request("r1", "price", service_id="tooth_extraction"))

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("outside the isolated D2 path")

    monkeypatch.setattr(composer_executor, "execute_composer_decision", forbidden)
    monkeypatch.setattr(materialization, "resolve_materialized_response", forbidden)
    monkeypatch.setattr(live_backend, "chat_completions_create", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    outcome = materialization.resolve_d2_envelope_response(envelope, sources, as_of=_AS_OF)
    assert render_response_text(outcome.resolved) == outcome.rendered_text
    assert project_response_ui(outcome.resolved) == outcome.ui_projection
