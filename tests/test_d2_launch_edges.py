"""Small offline launch gate for A06, A09, B07, and B02 term repetition."""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in D2 launch edges")

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve())
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


class FakeProvider:
    def __init__(self, *payloads):
        self.payloads = iter(payloads)
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return json.dumps(next(self.payloads), ensure_ascii=False)


def _part(kind, *, service_id=None, topic_id=None, **extra):
    return {
        "request_id": "r1", "kind": kind, "subject_id": None,
        "context": "general_information", "topic_id": topic_id,
        "service_id": service_id, "statement_mode": "question",
        "situation": None, **extra,
    }


def _envelope(*parts, commercial_intent="none", **extra):
    price = next((part for part in parts if part["kind"] == "price"), None)
    return production_envelope_template(
        commercial_intent=commercial_intent,
        primary_price_request_id=price["request_id"] if price else None,
        request_understanding={"subjects": [], "requests": list(parts)},
        **extra,
    )


def _store_and_clients(tmp_path):
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    return D2DialogueStore(tmp_path / "dialogue.sqlite"), clients


def _turn(store, clients, provider, sid, message, request_id):
    return run_d2_dialogue_turn(
        session_key=SessionKey(client_id="demo", sid=sid),
        user_message=message, provider=provider, clients_root=clients,
        store=store, now=NOW, request_id=request_id,
    )


def test_a06_two_topics_then_ambiguous_short_price_clarifies(tmp_path):
    price = _part("price", service_id="veneers", topic_id="prosthetics")
    content = _part(
        "content", content_ref="clinic__info__warranty.md", topic_id="clinic",
        content_text="Гарантия на импланты указана в договоре.",
        content_realization="model_prose", content_section_refs=["a:korotko"],
        content_fallback_section_ref="a:korotko",
    )
    content["request_id"] = "r2"
    provider = FakeProvider(
        _envelope(price, content, commercial_intent="price"),
        _envelope(_part("price"), commercial_intent="price"),
    )
    store, clients = _store_and_clients(tmp_path)
    with store:
        first = _turn(store, clients, provider, "edge-a06", "Сколько стоят виниры и есть ли гарантия на импланты?", "a06-1")
        second = _turn(store, clients, provider, "edge-a06", "А сколько это?", "a06-2")
        saved = store.read(SessionKey(client_id="demo", sid="edge-a06"))
    assert first.response.resolved.d2_price_block is not None
    assert "Гарантия" in first.response.rendered_text
    assert second.response.resolved.route == "CLARIFY"
    assert second.response.resolved.d2_price_block is None
    assert saved.state.clarify_pending is True
    assert len(provider.inputs) == 2


def test_a09_both_jaws_three_teeth_keeps_published_unit(tmp_path):
    part = _part("price", topic_id="implantation")
    part["subject_id"] = "s1"
    part["situation"] = {
        "scope_commitment": "reported", "extent": "few_teeth", "tooth_count": 3,
        "jaw": "both", "continuity": "unknown",
    }
    payload = _envelope(part, commercial_intent="price")
    payload["request_understanding"]["subjects"] = [
        {"subject_id": "s1", "relation": "self", "age_group": "unknown"}
    ]
    provider = FakeProvider(payload)
    store, clients = _store_and_clients(tmp_path)
    key = SessionKey(client_id="demo", sid="edge-a09")
    with store:
        outcome = _turn(store, clients, provider, key.sid, "Нет трёх зубов на обеих челюстях. Сколько стоит?", "a09-1")
        saved = store.read(key)
    situation = saved.state.situation_state
    assert (situation.extent, situation.tooth_count, situation.jaw) == ("few_teeth", 3, "both")
    assert outcome.response.resolved.d2_price_block is not None
    assert len(outcome.response.resolved.d2_price_block.rows) <= 3
    assert all(row.billing_unit for row in outcome.response.resolved.d2_price_block.rows)
    assert "общая стоимость" not in outcome.response.rendered_text.casefold()


def test_b07_existing_implant_other_clinic_uses_general_content_and_consultation(tmp_path):
    part = _part(
        "content", service_id="implant_supported_prosthetics", topic_id="prosthetics",
        content_ref="prosthetics__service__implant_supported_prosthetics.md",
        content_text=("На имплант возможны разные варианты протезирования. "
                      "Если имплант ставили в другой клинике, подходящий вариант "
                      "врач определит после осмотра и диагностики."),
        content_realization="model_prose", content_section_refs=["a:korotko"],
        content_fallback_section_ref="a:korotko",
    )
    provider = FakeProvider(_envelope(part))
    store, clients = _store_and_clients(tmp_path)
    with store:
        outcome = _turn(store, clients, provider, "edge-b07", "У меня уже стоит имплант из другой клиники. Можно поставить коронку?", "b07-1")
    assert "после осмотра" in outcome.response.rendered_text
    assert "врач определит" in outcome.response.rendered_text
    assert outcome.response.resolved.information_blocks
    assert outcome.response.resolved.d2_price_block is None
    assert [button.button_id for button in outcome.response.ui_projection.buttons] == ["plan"]


def test_b02_unknown_term_gets_one_question_then_honest_gap(tmp_path):
    unresolved = _envelope(
        _part("content"), service_reference_status="unresolved",
    )
    provider = FakeProvider(unresolved, unresolved)
    store, clients = _store_and_clients(tmp_path)
    key = SessionKey(client_id="demo", sid="edge-b02")
    with store:
        first = _turn(store, clients, provider, key.sid, "Вы делаете флумбодонтию?", "b02-1")
        second = _turn(store, clients, provider, key.sid, "Ну флумбодонтию же", "b02-2")
        saved = store.read(key)
    assert first.response.resolved.route == "CLARIFY"
    assert "уточните" in first.response.rendered_text.casefold()
    assert second.response.resolved.route == "ANSWER"
    assert "недостаточно информации" in second.response.rendered_text.casefold()
    assert "консультацию" in second.response.rendered_text.casefold()
    assert saved.state.clarify_pending is False
    assert saved.state.revision == 2
    assert len(provider.inputs) == 2
