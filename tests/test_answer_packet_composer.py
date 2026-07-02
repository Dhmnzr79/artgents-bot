from __future__ import annotations

import json

from contracts.answer_packet import AnswerPacketSnapshot, PacketCard
from contracts.answer_plan import AnswerPlan
from core.answer_packet import assemble_answer_packet
from core.answer_packet_materialize import materialize_cards, render_price_fact_block
from llm import (
    build_messages_for_packet_composer,
    build_messages_for_packet_composer_fullctx,
    generate_answer_from_packet,
    generate_answer_from_packet_fullctx,
)
from retriever import get_chunk_by_ref


def test_materialize_composite_price_pain_order_and_facts():
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="all_on_4",
        topic="implantation",
        append=["price_offer"],
        plan_reason="composite",
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="all_on_4",
    )
    cards = materialize_cards(packet, client_id="demo")
    core_aspects = [c.aspect for c in cards if c.aspect in ("price", "pain")]
    assert core_aspects == ["price", "pain"]

    price_card = next(c for c in cards if c.kind == "price")
    assert price_card.verbatim is True
    assert "318 000" in price_card.text
    assert "входят" in price_card.text.lower()
    assert "4 импланта" in price_card.text

    pain_card = next(c for c in cards if c.aspect == "pain")
    assert pain_card.verbatim is False
    pain_ref = "implantation__faq__pain.md#korotko"
    chunk = get_chunk_by_ref(pain_ref, client_id="demo")
    assert chunk is not None
    chunk_text = str(chunk.get("text") or "").strip()
    assert chunk_text
    assert chunk_text in pain_card.text


def test_render_price_fact_block_all_on_4_matches_pricebook():
    block = render_price_fact_block(client_id="demo", service_id="all_on_4")
    assert block is not None
    assert "318 000" in block
    assert "368 000" in block
    assert "428 000" in block
    assert "За одну челюсть." in block


def test_materialize_skips_unresolved_ref_fail_open():
    packet = AnswerPacketSnapshot(
        cards=[
            PacketCard(
                aspect="overview",
                kind="content",
                source_ref="nonexistent__service__nope.md#korotko",
            )
        ],
        service_id="classic",
    )
    cards = materialize_cards(packet, client_id="demo")
    assert cards == []


def test_composer_messages_include_price_and_pain_blocks(monkeypatch):
    monkeypatch.setattr("llm.COMPOSER_ON", True)
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
    materialized = materialize_cards(packet, client_id="demo")
    price_text = next(c.text for c in materialized if c.kind == "price")
    pain_text = next(c.text for c in materialized if c.aspect == "pain")

    captured: dict = {}

    def _fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]

        class _Msg:
            content = json.dumps({"answer": "ok"})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("llm.chat_completions_create", _fake_create)

    answer, meta = generate_answer_from_packet(
        "Сколько стоит all-on-4 и не больно ли?",
        materialized,
        {"client_id": "demo"},
        "composer-test-sid",
    )
    assert answer == "ok"
    assert meta.get("composer_used") is True
    blob = captured["messages"][1]["content"]
    assert price_text in blob
    assert pain_text in blob
    assert "318 000" in blob


def test_build_messages_for_packet_composer_structure():
    materialized = materialize_cards(
        assemble_answer_packet(
            AnswerPlan(
                aspects=["price"],
                primary_aspect="price",
                service_id="classic",
                append=["price_offer"],
            ),
            client_id="demo",
            route="price_lookup",
            service_id="classic",
        ),
        client_id="demo",
    )
    messages = build_messages_for_packet_composer(
        "цена?",
        materialized,
        {"client_id": "demo"},
        "sid-1",
    )
    assert messages[0]["role"] == "system"
    assert "ДОСЛОВНО" in messages[1]["content"]
    assert materialized[0].text in messages[1]["content"]


def test_generate_answer_from_packet_fail_open_when_disabled(monkeypatch):
    monkeypatch.setattr("llm.COMPOSER_ON", False)
    from llm import LLM_FALLBACK_ANSWER

    answer, meta = generate_answer_from_packet("q", [], {"client_id": "demo"}, "sid-off")
    assert answer == LLM_FALLBACK_ANSWER
    assert meta.get("composer_used") is False


def test_fullctx_composer_messages_include_kb_aspects_and_price_card(monkeypatch):
    from core.knowledge_base import assemble_client_knowledge_base

    monkeypatch.setattr("llm.COMPOSER_ON", True)
    monkeypatch.setattr("llm.FULLCTX_ON", True)
    kb = assemble_client_knowledge_base("demo")
    plan = AnswerPlan(
        aspects=["price", "pain"],
        primary_aspect="price",
        service_id="professional_whitening",
        topic="whitening",
        append=["price_offer"],
    )
    packet = assemble_answer_packet(
        plan,
        client_id="demo",
        route="price_lookup",
        service_id="professional_whitening",
    )
    from core.answer_packet_materialize import materialize_deterministic_cards

    deterministic = materialize_deterministic_cards(packet, client_id="demo")
    price_text = next(c.text for c in deterministic if c.kind == "price")

    captured: dict = {}

    def _fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]

        class _Msg:
            content = json.dumps({"answer": "ok"})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("llm.chat_completions_create", _fake_create)

    answer, meta = generate_answer_from_packet_fullctx(
        "Сколько стоит отбеливание и не больно ли?",
        kb,
        ["price", "pain"],
        deterministic,
        {"client_id": "demo"},
        "fullctx-test-sid",
    )
    assert answer == "ok"
    assert meta.get("composer_used") is True
    blob = captured["messages"][1]["content"]
    assert kb in blob
    assert "price, pain" in blob
    assert price_text in blob
    assert "18 000" in blob


def test_build_messages_for_packet_composer_fullctx_structure():
    from core.knowledge_base import assemble_client_knowledge_base

    kb = assemble_client_knowledge_base("demo")
    materialized = materialize_cards(
        assemble_answer_packet(
            AnswerPlan(
                aspects=["price"],
                primary_aspect="price",
                service_id="professional_whitening",
                append=["price_offer"],
            ),
            client_id="demo",
            route="price_lookup",
            service_id="professional_whitening",
        ),
        client_id="demo",
    )
    deterministic = [c for c in materialized if c.kind == "price"]
    messages = build_messages_for_packet_composer_fullctx(
        "цена и боль?",
        kb,
        ["price", "pain"],
        deterministic,
        {"client_id": "demo"},
        "sid-2",
    )
    assert messages[0]["role"] == "system"
    user = messages[1]["content"]
    assert "База знаний клиники" in user
    assert "Ответь на аспекты: price, pain" in user
    assert "ДОСЛОВНО" in user
    assert deterministic[0].text in user
