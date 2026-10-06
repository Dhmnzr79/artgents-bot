"""CP6a endpoint scenarios: request identity, tenant and lead/privacy."""

from __future__ import annotations

import threading

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from session import mem_add_user, mem_get, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only, envelope_clinic_policy_only,
)
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events


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


def test_sse_disconnect_before_work_and_after_commit_replays_without_provider(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))

    before = post_sse(client, sid="before-close", request_id="once", buffered=False)
    assert next(before.response).decode().startswith("event: status\n")
    before.close()
    assert fake.inputs == []
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="before-close")) is None
    recovered = post(client, sid="before-close", request_id="once")
    assert recovered.status_code == 200 and len(fake.inputs) == 1

    after = post_sse(client, sid="after-close", request_id="once", buffered=False)
    assert next(after.response).decode().startswith("event: status\n")
    assert next(after.response).decode().startswith("event: typing\n")
    after.close()  # D2 has committed; ui/done never reached this client.
    assert len(fake.inputs) == 2
    replay = post(client, sid="after-close", request_id="once")
    assert replay.status_code == 200 and len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="after-close")).state.revision == 1


def test_sse_lead_effect_and_cross_transport_replay(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "sse-lead"
    assert sse_events(post_sse(client, sid=sid, request_id="book", q="Хочу записаться"))[-1][0] == "done"
    assert sse_events(post_sse(client, sid=sid, request_id="name", q="Анна"))[-1][0] == "done"
    submitted = sse_events(post_sse(client, sid=sid, request_id="phone",
                                    q="+7 999 123 45 67"))
    assert [kind for kind, _ in submitted] == ["status", "typing", "ui", "done"]
    assert submitted[2][1]["lead_effect"]["status"] == "demo_stub"
    assert len(fake.inputs) == 1

    def duplicate_effect(*_args, **_kwargs):
        raise AssertionError("effect updated on replay")
    monkeypatch.setattr(D2DialogueStore, "update_lead_effect", duplicate_effect)
    assert post(client, sid=sid, request_id="phone", q="+7 999 123 45 67").get_json() == submitted[2][1]
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid=sid)).state.revision == 3


def test_sse_tenant_isolation_and_frozen_replay(http_env):
    client, db, use_provider, tmp_path = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    demo = sse_events(post_sse(client, sid="shared-tenant", request_id="same",
                               client_id="demo"))[2][1]
    nika = sse_events(post_sse(client, sid="shared-tenant", request_id="same",
                               client_id="nikadent"))[2][1]
    assert demo["client_id"] == "demo" and nika["client_id"] == "nikadent"
    assert len(fake.inputs) == 2
    (tmp_path / "clients" / "demo" / "clinic_policies.yaml").write_text(
        "policies: {}\n", encoding="utf-8"
    )
    replay = post(client, sid="shared-tenant", request_id="same", client_id="demo")
    assert replay.get_json() == demo and len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="shared-tenant")).state.revision == 1
        assert store.read(SessionKey(client_id="nikadent", sid="shared-tenant")).state.revision == 1
