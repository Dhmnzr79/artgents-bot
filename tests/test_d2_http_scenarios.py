"""CP6a endpoint scenarios: request identity, tenant and lead/privacy."""

from __future__ import annotations

import threading

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from session import mem_add_user, mem_get, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only, envelope_clinic_policy_only,
)
from tests.test_d2_http_contract import FakeProvider, http_env, post


def test_two_concurrent_turns_only_one_commits(http_env):
    client, db, use_provider, _ = http_env
    entered = threading.Event()
    release = threading.Event()
    fake = FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry"))
    original = fake.generate

    def paused(request):
        entered.set()
        assert release.wait(10)
        return original(request)

    fake.generate = paused
    use_provider(fake)
    first = []

    def run_first():
        first.append(post(client, sid="race", request_id="first"))

    worker = threading.Thread(target=run_first)
    worker.start()
    assert entered.wait(10)
    second = post(client, sid="race", request_id="second", q="Ещё вопрос")
    assert second.status_code == 409
    release.set()
    worker.join(10)
    assert not worker.is_alive()
    assert first[0].status_code == 200
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="race")).state.revision == 1


def test_same_sid_isolated_between_tenants(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    demo = post(client, sid="same", request_id="same", client_id="demo")
    nika = post(client, sid="same", request_id="same", client_id="nikadent")
    assert demo.status_code == nika.status_code == 200
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="same")) is not None
        assert store.read(SessionKey(client_id="nikadent", sid="same")) is not None
    assert demo.get_json()["client_id"] == "demo"
    assert nika.get_json()["client_id"] == "nikadent"


def test_legacy_ordinary_history_is_not_imported(http_env):
    client, db, use_provider, _ = http_env
    with session_client_scope("demo"):
        mem_add_user("old-session", "Старый разговор про виниры")
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    response = post(client, sid="old-session", request_id="new", q="Можно ли детям?")
    assert response.status_code == 200
    assert len(fake.inputs) == 1
    assert "Старый разговор" not in fake.inputs[0].context.model_dump_json()
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="old-session")).state.revision == 1


def test_booking_name_pending_question_phone_and_replay(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "private-lead"
    booking = post(client, sid=sid, request_id="book", q="Хочу записаться")
    assert booking.status_code == 200
    name = post(client, sid=sid, request_id="name", q="Анна")
    pending = post(client, sid=sid, request_id="pending", q="А сколько длится прием?")
    phone = post(client, sid=sid, request_id="phone", q="+7 999 123 45 67")
    assert all(response.status_code == 200 for response in (name, pending, phone))
    assert len(fake.inputs) == 1
    assert all("Анна" not in item.user_message and "999 123" not in item.user_message
               for item in fake.inputs)
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert not state.get("profile", {}).get("phone")  # existing owner clears PII on submit
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        assert store.read(key).state.revision == 4
        raw = " ".join(row[0] or "" for row in store._connection.execute(
            "SELECT payload FROM d2_dialogue UNION ALL SELECT payload FROM d2_turn_request"))
        assert "Анна" not in raw and "999" not in raw
        effect = store._connection.execute(
            "SELECT payload FROM d2_turn_request WHERE client_id='demo' AND sid=? AND request_id='phone'",
            (sid,)).fetchone()[0]
        assert '"status":"demo_stub"' in effect
    def duplicate_effect(*_args, **_kwargs):
        raise AssertionError("effect receipt updated twice")
    monkeypatch.setattr(D2DialogueStore, "update_lead_effect", duplicate_effect)
    replay = post(client, sid=sid, request_id="phone", q="+7 999 123 45 67")
    assert replay.get_json() == phone.get_json()
    assert len(fake.inputs) == 1
