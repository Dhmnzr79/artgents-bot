"""CP5-B13a assembled common-route proof for a simple published service price."""

from __future__ import annotations

import json
import shutil
import socket
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 20, 13, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="b13-simple-price")


def raw_caries_price() -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "price",
                    "subject_id": None,
                    "context": "general_information",
                    "topic_id": "treatment",
                    "service_id": "caries",
                    "statement_mode": "question",
                    "situation": None,
                }],
            },
        ),
        ensure_ascii=False,
    )


class RawFakeProvider:
    def __init__(self) -> None:
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return raw_caries_price()


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-B13a")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@contextmanager
def observed_common_route():
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_",
            "core.target_composer",
            "core.target_runtime_",
            "core.response_plan_composer_executor",
            "core.target_session_selection",
            "core.one_call_runtime",
            "core.one_call_presentation",
            "core.response_plan_session",
            "core.target_offer_projection",
            "core.target_service_selection",
            "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        if module == "session":
            assert frame.f_code.co_name == "current_session_client_id", (
                f"unexpected session use on ordinary D2 route: {frame.f_code.co_name}"
            )
            return

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def test_b13_simple_direct_price_uses_common_route_and_demo_snapshot(tmp_path):
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    provider = RawFakeProvider()

    with observed_common_route() as calls:
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=KEY,
                user_message="Сколько стоит лечение кариеса?",
                provider=provider,
                clients_root=clients,
                store=store,
                now=NOW,
            )
            saved = store.read(KEY)

    assert len(provider.inputs) == 1
    assert provider.inputs[0].context.freshness == "unknown"
    assert provider.inputs[0].model_view.client_id == "demo"
    price = outcome.response.resolved.d2_price_block
    assert price is not None
    assert [(row.offer_id, row.mode, row.min_amount, row.billing_unit) for row in price.rows] == [
        ("caries.default", "from", 6_500, "tooth"),
    ]
    assert all(row.source_client_id == "demo" for row in price.rows)
    assert outcome.response.resolved.d2_price_scope_decision is None
    assert not outcome.response.resolved.promo_blocks
    assert not outcome.response.ui_projection.quick_replies
    assert "от 6 500" in outcome.response.rendered_text.replace("\u00a0", " ").replace("\u202f", " ")
    assert "за лечение одного зуба; зависит от глубины поражения и объёма пломбирования" in outcome.response.rendered_text
    assert "всё включено" not in outcome.response.rendered_text.lower()
    assert saved.state.revision == 1
    assert saved.state.active_topic.topic_id == "treatment"
    assert saved.state.situation_state is None
    assert saved.state.shown_options_snapshot.service_ids == ("caries",)
    for function in (
        "parse_production_envelope_json",
        "project_d2_session_context",
        "bind_d1r_envelope_to_d2_context",
        "seed_d2_plan_focus",
        "build_d2_snapshot_sources",
        "resolve_d2_envelope_response",
    ):
        # The early lead/spam gate and provider input each project context.
        expected = 2 if function == "project_d2_session_context" else 1
        assert sum(name == function for _, name in calls) == expected, function
