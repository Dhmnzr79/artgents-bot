"""CP6a: the real JSON endpoint returns a durable D2 completion."""

from __future__ import annotations

import json
import shutil
import socket
import sqlite3
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from tests.d1r_envelope_fixtures import envelope_adult_booking_only, envelope_clinic_policy_only


ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    def __init__(self, raw: str):
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture
def http_env(monkeypatch, tmp_path):
    clients = tmp_path / "clients"
    for tenant in ("demo", "nikadent"):
        shutil.copytree(ROOT / "clients" / tenant, clients / tenant)
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(logs))
    monkeypatch.setenv("D2_CLIENTS_ROOT", str(clients))
    db = tmp_path / "d2.sqlite"
    monkeypatch.setenv("D2_DIALOGUE_DB_PATH", str(db))
    import session
    session.clear_session_store_cache()
    session_db = tmp_path / "sessions"
    session_db.mkdir()
    monkeypatch.setattr(session, "sqlite_path_for_client",
                        lambda client: str(session_db / f"{client}.sqlite"))
    import core.client_config_loader as config_loader
    monkeypatch.setattr(config_loader, "_REPO_ROOT", str(tmp_path))
    import config
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    import app
    import core.d2_http_adapter as adapter

    def forbidden(*_args, **_kwargs):
        raise AssertionError("offline network/provider forbidden")

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    real_connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve())
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)

    def use_provider(fake):
        monkeypatch.setattr(adapter, "D2HttpProvider", lambda: fake)
        return fake

    yield app.app.test_client(), db, use_provider, tmp_path
    session.clear_session_store_cache()


def post(client, *, sid="cp6a", request_id="r1", q="Можно ли детям?", client_id="demo", **extra):
    return client.post("/ask", json={"sid": sid, "request_id": request_id,
                                     "q": q, "client_id": client_id, **extra})


def post_sse(client, *, sid="cp6a", request_id="r1", q="Можно ли детям?",
             client_id="demo", buffered=True, **extra):
    return client.post("/ask/stream", json={"sid": sid, "request_id": request_id,
                                            "q": q, "client_id": client_id, **extra},
                       buffered=buffered)


def sse_events(response):
    frames = response.get_data(as_text=True).split("\n\n")
    return [(lines[0][7:], json.loads(lines[1][6:]))
            for frame in frames if (lines := frame.splitlines()) and len(lines) >= 2]


def test_endpoint_persists_exact_final_text_ui_actions_and_replays(http_env):
    client, db, use_provider, tmp_path = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    first = post(client)
    assert first.status_code == 200
    body = first.get_json()
    assert body["answer"]
    assert body["actions"]["quick_replies"] == body["ui"]["quick_replies"]
    assert len(fake.inputs) == 1
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)
        assert session._connect().execute(
            "SELECT count(*) FROM sessions WHERE sid='cp6a'").fetchone()[0] == 0
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        record = store.read(key)
        assert record.state.revision == body["revision"] == 1
        saved = store.reserve_request(key, request_id="r1",
            request_fingerprint=store._connection.execute(
                "SELECT request_fingerprint FROM d2_turn_request WHERE client_id=? AND sid=? AND request_id=?",
                ("demo", "cp6a", "r1")).fetchone()[0]).completed
        assert saved.response.rendered_text == body["answer"]
        assert saved.response.ui_projection.model_dump(mode="json") == body["ui"]
    # Freeze is durable: even a changed tenant pack cannot reselect the reply.
    (tmp_path / "clients" / "demo" / "clinic_policies.yaml").write_text(
        "policies: {}\n", encoding="utf-8"
    )
    assert post(client).get_json() == body
    assert len(fake.inputs) == 1
    conflict = post(client, q="Другой вопрос")
    assert conflict.status_code == 409
    assert post(client, cta_action="lead").status_code == 400
    assert post(client, request_id="legacy-ref", ref="legacy:price").status_code == 400
    assert len(fake.inputs) == 1


def test_invalid_provider_and_commit_failure_have_no_final_result(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider("{invalid"))
    response = post(client, sid="bad", request_id="invalid")
    assert response.status_code != 200
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="bad")) is None
    fake.raw = envelope_clinic_policy_only("no_pediatric_dentistry")
    def fail_commit(*_args, **_kwargs):
        raise RuntimeError("commit refused")
    monkeypatch.setattr(D2DialogueStore, "complete", fail_commit)
    response = post(client, sid="failed", request_id="commit")
    assert response.status_code == 503
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="failed")) is None
        assert store._connection.execute(
            "SELECT count(*) FROM d2_turn_request WHERE sid='failed'").fetchone()[0] == 0


def test_lead_commit_failure_restores_existing_owner(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    use_provider(FakeProvider(envelope_adult_booking_only()))
    def fail_commit(*_args, **_kwargs):
        raise RuntimeError("commit refused")
    monkeypatch.setattr(D2DialogueStore, "complete", fail_commit)
    assert post(client, sid="lead-fail", request_id="lead-fail", q="Хочу записаться").status_code == 503
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("lead-fail") == (False, False)
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="lead-fail")) is None


def test_phone_commit_failure_keeps_lead_pending_without_effect(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "phone-fail"
    assert post(client, sid=sid, request_id="book", q="Хочу записаться").status_code == 200
    assert post(client, sid=sid, request_id="name", q="Анна").status_code == 200
    original_complete = D2DialogueStore.complete

    def fail_commit(*_args, **_kwargs):
        raise RuntimeError("commit refused")

    monkeypatch.setattr(D2DialogueStore, "complete", fail_commit)
    failed = post(client, sid=sid, request_id="phone", q="+7 999 123 45 67")
    assert failed.status_code == 503
    import session
    with session.session_client_scope("demo"):
        state = session.mem_get(sid)
        assert state["lead_intent"] == "collecting_phone"
        assert state["profile"]["name"] == "Анна"
        assert "phone" not in state["profile"]
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid=sid)).state.revision == 2
        assert store._connection.execute(
            "SELECT count(*) FROM d2_turn_request WHERE sid=? AND request_id='phone'",
            (sid,)).fetchone()[0] == 0
    monkeypatch.setattr(D2DialogueStore, "complete", original_complete)
    assert post(client, sid=sid, request_id="phone", q="+7 999 123 45 67").status_code == 200


def test_json_sse_parity_in_both_replay_directions(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    json_result = post(client, sid="json-first", request_id="shared").get_json()
    events = sse_events(post_sse(client, sid="json-first", request_id="shared"))
    assert [kind for kind, _ in events] == ["status", "typing", "ui", "done"]
    assert events[2][1] == json_result
    assert len(fake.inputs) == 1

    events = sse_events(post_sse(client, sid="sse-first", request_id="shared"))
    assert [kind for kind, _ in events] == ["status", "typing", "ui", "done"]
    assert post(client, sid="sse-first", request_id="shared").get_json() == events[2][1]
    assert len(fake.inputs) == 2
    conflict = sse_events(post_sse(client, sid="sse-first", request_id="shared",
                                   q="Другой вопрос"))
    assert [kind for kind, _ in conflict] == ["status", "error"]
    assert conflict[1][1]["error"] == "request_id_payload_conflict"
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="json-first")).state.revision == 1
        assert store.read(SessionKey(client_id="demo", sid="sse-first")).state.revision == 1


def test_sse_terminal_and_error_are_single_outcomes(http_env):
    client, db, use_provider, _ = http_env
    admin = json.dumps(production_envelope_template(
        route="ADMIN", patient_text=None, commercial_intent="none",
        promotion_scope="none", scenario="none", primary_price_request_id=None,
        request_understanding={"subjects": [], "requests": []},
    ), ensure_ascii=False)
    fake = use_provider(FakeProvider(admin))
    terminal = sse_events(post_sse(client, sid="terminal", request_id="terminal",
                                   q="Срочная медицинская проблема"))
    assert [kind for kind, _ in terminal] == ["status", "typing", "ui", "done"]
    assert terminal[2][1]["answer"]
    assert terminal[2][1]["ui"]["buttons"] == []
    fake.raw = "{invalid"
    error = sse_events(post_sse(client, sid="error-sse", request_id="invalid"))
    assert [kind for kind, _ in error] == ["status", "error"]
    assert error[1][1]["error"] == "parser_invalid_envelope"
    assert error[1][1]["stage"] == "parser"
    assert error[1][1]["committed"] is False
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="error-sse")) is None


def test_sse_commit_refusal_is_error_then_retry_can_complete(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    original_complete = D2DialogueStore.complete

    def fail_commit(*_args, **_kwargs):
        raise RuntimeError("commit refused")

    monkeypatch.setattr(D2DialogueStore, "complete", fail_commit)
    events = sse_events(post_sse(client, sid="sse-commit", request_id="commit"))
    assert [kind for kind, _ in events] == ["status", "error"]
    assert events[1][1]["error"] == "store_failed"
    assert events[1][1]["stage"] == "store"
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="sse-commit")) is None
    monkeypatch.setattr(D2DialogueStore, "complete", original_complete)
    assert post(client, sid="sse-commit", request_id="commit").status_code == 200
    assert len(fake.inputs) == 2


def test_sse_framing_error_preserves_saved_result_for_replay(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    import app

    def fail_framing(*_args, **_kwargs):
        raise RuntimeError("transport framing failed")

    with monkeypatch.context() as patch:
        patch.setattr(app, "_sse_typing_line", fail_framing)
        events = sse_events(post_sse(client, sid="framing", request_id="saved"))
    assert [kind for kind, _ in events] == ["status", "error"]
    assert events[1][1]["error"] == "transport_failed"
    assert events[1][1]["committed"] is True
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="framing")).state.revision == 1
    assert post(client, sid="framing", request_id="saved").status_code == 200
    assert len(fake.inputs) == 1
