from __future__ import annotations

import pytest

from contracts.answer_plan import AnswerPlan
from core.answer_packet import assemble_answer_packet


def test_assemble_composite_price_pain_cards(monkeypatch):
    monkeypatch.setenv("ANSWER_PACKET_ASSEMBLER_ON", "1")
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="classic",
        topic="implantation",
        append=["price_offer"],
        plan_reason="composite",
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="classic",
    )
    aspects = {c.aspect for c in packet.cards if c.aspect}
    kinds = {c.kind for c in packet.cards}
    assert "price" in aspects and "pain" in aspects
    assert "price" in kinds and "content" in kinds
    pain_card = next(c for c in packet.cards if c.aspect == "pain")
    assert pain_card.source_ref == "implantation__faq__pain.md#korotko"


def test_promo_suppressed_on_pain_primary_aspect():
    plan = AnswerPlan(
        aspects=["pain"],
        primary_aspect="pain",
        service_id="classic",
        topic="implantation",
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="classic",
    )
    assert not any(c.kind == "promo" for c in packet.cards)
    assert packet.promo_decisions
    assert any(d.reason == "aspect_blocked" for d in packet.promo_decisions)


def test_promo_suppressed_on_composite_price_pain():
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="all_on_4",
    )
    assert not any(c.kind == "promo" for c in packet.cards)
    assert any(d.reason == "aspect_blocked" for d in packet.promo_decisions)


def test_promo_allowed_on_price_overview_aspect():
    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="classic",
        topic="implantation",
        append=["price_offer"],
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="classic",
    )
    promo_cards = [c for c in packet.cards if c.kind == "promo"]
    assert promo_cards
    assert all(c.promo_decision == "allowed" for c in promo_cards)


def test_assembler_adds_cta_and_buttons_for_service():
    plan = AnswerPlan(
        aspects=["price"],
        primary_aspect="price",
        service_id="classic",
        topic="implantation",
        append=["price_offer"],
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="classic",
    )
    assert any(c.kind == "cta" and c.cta_key == "doctor" for c in packet.cards)
    buttons = next(c for c in packet.cards if c.kind == "buttons")
    assert buttons.button_refs


def test_build_and_publish_uses_snapshot_when_flag_off(monkeypatch):
    monkeypatch.setattr("config.ANSWER_PACKET_ASSEMBLER_ON", False)
    app = pytest.importorskip("flask").Flask(__name__)
    plan = AnswerPlan(aspects=["price", "payment"], service_id="classic", append=["payment_terms"])
    with app.test_request_context("/"):
        from flask import request

        from core.answer_packet_snapshot import build_and_publish_answer_packet

        request.ctx = {}
        packet = build_and_publish_answer_packet(plan, client_id="demo")
        assert packet.snapshot_stage == "plan"
        assert not packet.promo_decisions


def test_build_and_publish_uses_assembler_when_flag_on(monkeypatch):
    monkeypatch.setattr("config.ANSWER_PACKET_ASSEMBLER_ON", True)
    app = pytest.importorskip("flask").Flask(__name__)
    plan = AnswerPlan(
        aspects=["pain"],
        primary_aspect="pain",
        service_id="classic",
        topic="implantation",
    )
    with app.test_request_context("/"):
        from flask import request

        from core.answer_packet_snapshot import build_and_publish_answer_packet

        request.ctx = {}
        packet = build_and_publish_answer_packet(
            plan,
            client_id="demo",
            route="retrieval_chunk",
            service_id="classic",
        )
        assert packet.snapshot_stage == "assembled"
        assert packet.promo_decisions
