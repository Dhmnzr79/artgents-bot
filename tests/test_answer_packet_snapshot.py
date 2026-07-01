from __future__ import annotations

import json

import pytest

from contracts.answer_plan import AnswerPlan
from core.answer_packet_snapshot import (
    answer_packet_from_ctx,
    build_answer_packet_snapshot,
    publish_answer_packet,
)
from core.answer_planner import build_answer_plan, publish_answer_plan


def test_build_answer_packet_snapshot_composite_price_payment():
    plan = build_answer_plan(
        q="Сколько стоит classic с коронкой и можно ли в рассрочку?",
        sid="pkt-1",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    packet = build_answer_packet_snapshot(plan)
    aspects = {c.aspect for c in packet.cards}
    kinds = {c.kind for c in packet.cards}
    assert "price" in aspects
    assert "payment" in aspects
    assert "price" in kinds
    assert "payment" in kinds
    assert packet.snapshot_stage == "plan"


def test_build_answer_packet_snapshot_duration_pain_content_cards():
    plan = build_answer_plan(
        q="Сколько по времени длится протезирование и больно ли это?",
        sid="pkt-2",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    packet = build_answer_packet_snapshot(plan)
    aspects = {c.aspect for c in packet.cards}
    assert aspects == {"duration", "pain"}
    assert all(c.kind == "content" for c in packet.cards)


def test_answer_packet_snapshot_json_roundtrip():
    plan = AnswerPlan(aspects=["warranty"], append=["warranty_terms"], service_id="classic")
    packet = build_answer_packet_snapshot(plan)
    raw = json.loads(packet.model_dump_json())
    assert raw["cards"][0]["source_ref"] == "clinic__info__warranty.md#korotko"
    assert raw["cards"][0]["kind"] == "warranty"


def test_publish_answer_packet_in_request_ctx():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        plan = build_answer_plan(
            q="цена и рассрочка",
            sid="pkt-ctx",
            client_id="demo",
            intent="content",
            decision=None,
            source_route=None,
        )
        publish_answer_plan(plan)
        publish_answer_packet(build_answer_packet_snapshot(plan))
        assert isinstance(request.ctx.get("answer_plan"), dict)
        packet = answer_packet_from_ctx()
        assert packet is not None
        assert len(packet.cards) >= 2


def test_apply_meta_marks_suppressed_payment_terms():
    plan = AnswerPlan(
        aspects=["price", "payment"],
        append=["price_offer", "payment_terms"],
        service_id="classic",
    )
    packet = build_answer_packet_snapshot(
        plan,
        apply_meta={"applied": ["price_offer"], "suppressed": ["payment_terms"]},
    )
    payment_cards = [c for c in packet.cards if c.kind == "payment"]
    assert payment_cards
    assert payment_cards[0].suppressed_reason == "apply_suppressed"
    assert packet.snapshot_stage == "apply"
