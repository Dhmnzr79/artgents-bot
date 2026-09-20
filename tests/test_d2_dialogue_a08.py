"""S2-V0 integration: only the raw provider is fake; the transition is real."""

import json
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_session import ResponsePlanSessionRevisionConflict
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


PACK = Path(__file__).parent / "fixtures" / "d2_a08"
NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
KEY = SessionKey(client_id="clinic_a", sid="a08")
FIRST = "Нет одного зуба, сколько стоит восстановить?"
SECOND = "А протезирование?"


def raw_price(topic, *, reported=False, continuity="same", subject_id="s1", relation="self"):
    # Synthetic provider JSON, not a parsed envelope or downstream seed.
    return json.dumps(production_envelope_template(
        commercial_intent="price", primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": subject_id, "relation": relation, "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": subject_id,
                "context": "general_information", "topic_id": topic, "service_id": None,
                "statement_mode": "question", "situation": {
                    "scope_commitment": "reported" if reported else "unknown",
                    "extent": "one_tooth" if reported else "unknown",
                    "tooth_count": 1 if reported else None, "jaw": "unknown",
                    "continuity": continuity,
                },
            }],
        },
    ), ensure_ascii=False)


class RawFakeProvider:
    def __init__(self, raw):
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden in S2-V0")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@contextmanager
def observed_route():
    """Observe actual calls; do not replace parser, binding, resolver or store."""
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_", "core.target_composer", "core.target_runtime_",
            "core.response_plan_composer_executor", "core.target_session_selection",
            "core.one_call_runtime", "core.one_call_presentation", "core.response_plan_session",
            "core.target_offer_projection", "core.target_service_selection", "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        assert module != "session", "second ordinary memory called"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def run(store, raw, *, key=KEY, message=FIRST, now=NOW, clients_root=PACK):
    provider = RawFakeProvider(raw)
    outcome = run_d2_dialogue_turn(session_key=key, user_message=message, provider=provider,
                                  clients_root=clients_root, store=store, now=now)
    assert len(provider.inputs) == 1
    return outcome, provider.inputs[0]


def offer_ids(turn):
    return tuple(row.offer_id for row in turn.response.resolved.d2_price_block.rows)


def test_a08_real_two_turn_route_survives_store_reopen(tmp_path):
    database = tmp_path / "dialogue.sqlite"
    clients = tmp_path / "clients"
    shutil.copytree(PACK / "clinic_a", clients / "clinic_a")
    with observed_route() as calls:
        with D2DialogueStore(database) as store:
            first, invocation1 = run(
                store, raw_price("implantation", reported=True, continuity="new"), clients_root=clients,
            )
            saved1 = store.read(KEY)
            assert first.committed_revision == 1
            assert invocation1.context.freshness == "unknown"
            assert offer_ids(first) == ("implant_one",)
            assert saved1.state.situation_state.extent == "one_tooth"
            assert saved1.state.situation_state.tooth_count == 1
            assert saved1.state.situation_state.situation_owner_id not in {None, "s1"}
            assert saved1.activity.last_user_turn_at == NOW
        # A new connection and backend. No seed, state, envelope or sources
        # passed into the second turn; not even the first outcome is an input.
        with D2DialogueStore(database) as store:
            second, invocation2 = run(store, raw_price("prosthetics", subject_id="s7"),
                                      message=SECOND, now=NOW + timedelta(seconds=30), clients_root=clients)
            saved2 = store.read(KEY)
            tables = store._connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert tables == [("d2_dialogue",)]
    assert invocation2.user_message == SECOND
    assert invocation2.context.freshness == "fresh"
    assert invocation2.context.source_revision == 1
    assert invocation2.context.ordinary.situation_state == saved1.state.situation_state
    assert second.focus.source_revision == 1
    assert second.focus.cross_topic_carry.source_situation == saved1.state.situation_state
    assert second.focus.cross_topic_carry.destination_topic_id == "prosthetics"
    assert offer_ids(second) == ("prosthetic_one",)
    decision = second.response.resolved.d2_price_scope_decision
    assert decision.reason == "known_situation" and decision.applied_extent == "one_tooth"
    text = second.response.rendered_text
    assert "Протезирование одного зуба" in text
    assert "17 000" in text.replace("\u00a0", " ").replace("\u202f", " ")
    assert "объём" not in text and "?" not in text
    assert "Восстановление" not in text and "нескольких" not in text
    assert second.response.ui_projection.projected_commercial_ids.price_offer_ids == ("prosthetic_one",)
    assert not second.response.ui_projection.quick_replies
    assert saved2.state.revision == 2
    assert saved2.state.active_topic.topic_id == "prosthetics"
    assert saved2.state.shown_options_snapshot.service_ids == ("prosthetics",)
    assert saved2.state.situation_state.extent == "one_tooth"
    assert saved2.state.situation_state.situation_owner_id == saved1.state.situation_state.situation_owner_id
    assert saved2.activity.last_user_turn_at == NOW + timedelta(seconds=30)
    for function in ("parse_production_envelope_json", "project_d2_session_context",
                     "bind_d1r_envelope_to_d2_context", "seed_d2_plan_focus",
                     "build_d2_snapshot_sources", "resolve_d2_envelope_response"):
        assert sum(name == function for _, name in calls) == 2, function
    assert ("core.response_plan_materialization", "_d2_cross_topic_applied_extent") in calls


def test_a08_demo_tenant_pack_supplies_direction_prices_through_snapshot(tmp_path):
    """CP2: the real demo pack, not the test fixture, owns A08 price data."""
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    key = SessionKey(client_id="demo", sid="a08-demo")

    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        first, _ = run(
            store, raw_price("implantation", reported=True, continuity="new"),
            key=key, clients_root=clients,
        )
        second, _ = run(
            store, raw_price("prosthetics", subject_id="s7"), key=key,
            message=SECOND, now=NOW + timedelta(seconds=30), clients_root=clients,
        )

    assert offer_ids(first) == (
        "classic.one_tooth.impro",
        "classic.one_tooth.implantium",
        "classic.one_tooth.nobel",
    )
    assert all(row.source_client_id == "demo" for row in first.response.resolved.d2_price_block.rows)
    assert all(row.billing_unit == "tooth_package" for row in first.response.resolved.d2_price_block.rows)
    assert "КТ при необходимости и временная коронка — отдельно" in first.response.rendered_text
    assert offer_ids(second) == ("implant_supported_prosthetics.default",)
    assert second.response.resolved.d2_price_block.rows[0].source_client_id == "demo"
    assert second.response.resolved.d2_price_block.rows[0].billing_unit == "tooth"
    assert "Хирургическая установка импланта и КТ — отдельно" in second.response.rendered_text
    assert second.response.resolved.d2_price_scope_decision.applied_extent == "one_tooth"


@pytest.mark.parametrize("mode", ["expired", "other_session", "new_situation", "unknown_continuity"])
def test_no_carry_without_fresh_same_situation(tmp_path, mode):
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, raw_price("implantation", reported=True, continuity="new"))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        second, _ = run(store, raw_price("prosthetics", continuity={
            "new_situation": "new", "unknown_continuity": "unknown",
        }.get(mode, "same")), message=SECOND,
            key=SessionKey(client_id="clinic_a", sid="other") if mode == "other_session" else KEY,
            now=NOW + timedelta(seconds=1800 if mode == "expired" else 30))
    assert second.focus.cross_topic_carry is None
    assert second.response.resolved.d2_price_scope_decision.applied_extent is None
    # Authored order, deliberately many-teeth first, makes lost carry observable.
    assert offer_ids(second) == ("prosthetic_many", "prosthetic_one")


def test_no_raw_message_semantic_inference(tmp_path):
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, raw_price("implantation", reported=True, continuity="new"), message="opaque input X")
        second, _ = run(store, raw_price("prosthetics"), message="opaque input Y", now=NOW + timedelta(seconds=1))
    assert offer_ids(second) == ("prosthetic_one",)


@pytest.mark.parametrize("raw", ["not JSON", {}, raw_price("prosthetics", relation="other")])
def test_invalid_provider_or_out_of_scope_input_does_not_commit(tmp_path, raw):
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, raw_price("implantation", reported=True, continuity="new"))
        before = store.read(KEY)
        with pytest.raises(ValueError):
            run(store, raw, message=SECOND, now=NOW + timedelta(seconds=30))
        assert store.read(KEY) == before


def test_clinics_with_same_sid_do_not_share_context_or_prices(tmp_path):
    clients = tmp_path / "clients"
    shutil.copytree(PACK / "clinic_a", clients / "clinic_a")
    shutil.copytree(PACK / "clinic_a", clients / "clinic_b")
    price_path = clients / "clinic_b" / "target_response/pricebook/services/prosthetic_one.json"
    payload = json.loads(price_path.read_text(encoding="utf-8"))
    payload["price"]["amount"] = 23000
    price_path.write_text(json.dumps(payload), encoding="utf-8")
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, raw_price("implantation", reported=True, continuity="new"), clients_root=clients)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        b, _ = run(store, raw_price("prosthetics"), key=SessionKey(client_id="clinic_b", sid="a08"),
                   message=SECOND, now=NOW + timedelta(seconds=30), clients_root=clients)
        a, _ = run(store, raw_price("prosthetics"), message=SECOND,
                   now=NOW + timedelta(seconds=30), clients_root=clients)
    assert b.focus.cross_topic_carry is None
    assert offer_ids(b) == ("prosthetic_many", "prosthetic_one")
    assert b.response.resolved.d2_price_block.rows[1].amount == 23000
    assert all(row.source_client_id == "clinic_b" for row in b.response.resolved.d2_price_block.rows)
    assert offer_ids(a) == ("prosthetic_one",)
    assert a.response.resolved.d2_price_block.rows[0].amount == 17000


@pytest.mark.parametrize("fault", ["missing", "foreign_offer", "duplicate_topic", "foreign_service", "inactive"])
def test_direction_prices_require_valid_production_binding(tmp_path, fault):
    clients = tmp_path / "clients"
    shutil.copytree(PACK / "clinic_a", clients / "clinic_a")
    config = clients / "clinic_a" / "target_response/d2_direction_prices.json"
    payload = json.loads(config.read_text(encoding="utf-8"))
    if fault == "missing":
        config.unlink()
    else:
        if fault == "foreign_offer":
            payload["directions"][0]["offer_ids"] = ["prosthetic_one"]
        elif fault == "foreign_service":
            payload["directions"][0]["service_ids"] = ["nonexistent"]
        elif fault == "duplicate_topic":
            payload["directions"].append(payload["directions"][0])
        else:
            offer = config.parent / "pricebook/services/implant_one.json"
            offer_payload = json.loads(offer.read_text(encoding="utf-8"))
            offer_payload["active"] = False
            offer.write_text(json.dumps(offer_payload), encoding="utf-8")
        config.write_text(json.dumps(payload), encoding="utf-8")
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        with pytest.raises(ValueError, match="direction_"):
            run(store, raw_price("implantation", reported=True), clients_root=clients)
        assert store.read(KEY) is None


def test_stale_store_commit_cannot_overwrite_state_or_activity(tmp_path):
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, raw_price("implantation", reported=True, continuity="new"))
        saved = store.read(KEY)
        with pytest.raises(ResponsePlanSessionRevisionConflict):
            store.commit(saved, expected_revision=0)
        assert store.read(KEY) == saved


def test_failed_write_keeps_first_turn_state_and_activity_together(tmp_path):
    database = tmp_path / "dialogue.sqlite"
    with D2DialogueStore(database) as store:
        run(store, raw_price("implantation", reported=True, continuity="new"))
        before = store.read(KEY)
        store._connection.execute(
            "CREATE TRIGGER fail_second BEFORE UPDATE ON d2_dialogue "
            "BEGIN SELECT RAISE(ABORT, 'test_disk_failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="test_disk_failure"):
            run(store, raw_price("prosthetics"), message=SECOND, now=NOW + timedelta(seconds=30))
    with D2DialogueStore(database) as store:
        assert store.read(KEY) == before
