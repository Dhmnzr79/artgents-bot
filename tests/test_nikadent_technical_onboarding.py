"""Current HTTP/SSE opens a private form; /lead sends with durable receipts."""
import json
import subprocess
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, send, click
from tests.test_d2_text_reply import response, action
from tests.test_widget_booking_form import form_payload


def begin(client, fake, *, client_id="demo", sid="lead", transport="json"):
    fake.raw = response(actions=[action("start_booking", age_group="adult")])
    booking = send(client, transport, client_id=client_id, sid=sid, request_id="book", q="Хочу записаться")
    assert booking["ui"]["booking_form"] is True
    assert booking["ui"]["lead_consent"] is None
    assert not booking["ui"]["quick_replies"]
    return form_payload(client, tenant=client_id, sid=sid, request_id="submit", name="Анна", phone="8 (900) 123-45-67")


def saved_form(db, tenant, sid):
    with D2DialogueStore(db) as store:
        status, payload = store._connection.execute(
            "SELECT status,payload FROM d2_turn_request WHERE client_id=? AND sid=? AND request_id='submit'",
            (tenant, sid)).fetchone()
        assert status == "form_complete"
        # Contact fields never enter a receipt or ordinary dialogue state/completion.
        assert "Анна" not in payload and "79001234567" not in payload
        key = SessionKey(client_id=tenant, sid=sid)
        assert store.read_completion(key, "submit") is None
        assert "Анна" not in store.read(key).model_dump_json()
        return json.loads(payload)


@pytest.fixture(autouse=True)
def private_offline_environment(monkeypatch):
    import core.client_config_loader as loader
    for key in ("_FEATURES_CACHE", "_TONE_CACHE", "_UI_CACHE", "_LEAD_CACHE", "_BRAND_CACHE", "_TXT_CACHE"):
        monkeypatch.setattr(loader, key, {})
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")
    for key, value in {"SMTP_HOST": "smtp.invalid", "SMTP_PORT": "465",
                       "SMTP_USER": "sender@example.invalid", "SMTP_PASSWORD": "offline-only",
                       "SMTP_FROM": "sender@example.invalid"}.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_nikadent_private_form_sends_once_and_replay_without_private_data(http_env, monkeypatch, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    smtp = MagicMock()
    connect = MagicMock()
    connect.return_value.__enter__.return_value = smtp
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    payload = begin(client, fake, client_id="nikadent", sid="nika-lead", transport=transport)
    result = client.post("/lead", json=payload)
    assert result.status_code == 200
    body = result.get_json()
    assert body["status"] == "sent" and body["ok"]
    assert "свяжется" in body["message"]
    assert client.post("/lead", json=payload).get_json() == body
    assert client.post("/lead", json={**payload, "phone": "+79007654321"}).status_code == 409
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "gothica@mail.ru, vikadent2025@mail.ru"
    assert "Никадент" in message.get_content()
    assert "Анна" in message.get_content() and "+79001234567" in message.get_content()
    assert len(fake.inputs) == 1
    from session import mem_get, session_client_scope
    with session_client_scope("nikadent"):
        private = mem_get("nika-lead")
        assert private["lead_intent"] == "none"
        assert not private["profile"].get("name") and not private["profile"].get("phone")
    receipt = saved_form(db, "nikadent", "nika-lead")
    assert receipt["status"] == "sent" and receipt["message"] == body["message"]
    assert receipt["consent_receipt"]["client_id"] == "nikadent"


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("failure, expected_status, phrase", [
    ("missing", "failed", "Не удалось отправить"),
    ("smtp", "unknown", "Подтверждение отправки"),
])
def test_failed_or_ambiguous_email_is_saved_truthfully_without_resend(http_env, monkeypatch, transport, failure, expected_status, phrase):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    connect = MagicMock(side_effect=OSError("offline smtp error"))
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    if failure == "missing":
        monkeypatch.delenv("SMTP_PASSWORD")
    payload = begin(client, fake, client_id="nikadent", sid="failed-lead", transport=transport)
    result = client.post("/lead", json=payload)
    assert result.status_code == 200
    body = result.get_json()
    assert body["status"] == expected_status and not body["ok"]
    assert phrase in body["message"] and "свяжется" not in body["message"]
    assert client.post("/lead", json=payload).get_json() == body
    assert connect.call_count == (1 if failure == "smtp" else 0)
    receipt = saved_form(db, "nikadent", "failed-lead")
    assert receipt["status"] == expected_status and receipt["message"] == body["message"]
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_demo_submission_keeps_stub_and_never_connects_smtp(http_env, monkeypatch, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider("unused"))
    connect = MagicMock(side_effect=AssertionError("demo cannot send email"))
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    payload = begin(client, fake, sid="shared-id", transport=transport)
    body = client.post("/lead", json=payload).get_json()
    assert body["status"] == "demo_stub" and body["ok"]
    connect.assert_not_called()
    other_payload = begin(client, fake, client_id="nikadent", sid="shared-id", transport=transport)
    other_payload["phone"] = "+79007654321"
    monkeypatch.delenv("SMTP_PASSWORD")
    other = client.post("/lead", json=other_payload).get_json()
    assert other["status"] == "failed" and not other["ok"]
    assert client.post("/lead", json=payload).get_json() == body
    assert client.post("/lead", json=other_payload).get_json() == other
    assert len(fake.inputs) == 2
    connect.assert_not_called()


def test_commit_failure_before_effect_does_not_send_or_save_private_fields(http_env, monkeypatch):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    payload = begin(client, fake, client_id="nikadent", sid="commit")
    connect = MagicMock()
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    monkeypatch.setattr(D2DialogueStore, "save_form_pending", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("commit failed")))
    result = client.post("/lead", json=payload)
    assert result.status_code == 500
    connect.assert_not_called()
    with D2DialogueStore(db) as store:
        assert not store._connection.execute("SELECT 1 FROM d2_turn_request WHERE request_id='submit'").fetchone()
    from session import session_client_scope, mem_get
    with session_client_scope("nikadent"):
        state = mem_get("commit")
        assert state["lead_intent"] == "none"
        assert not state["profile"].get("name") and not state["profile"].get("phone")
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_current_nikadent_model_input_has_own_contacts_and_doctors(http_env, transport):
    client, _, use, root = http_env
    fake = use(FakeProvider("Ответ по материалам НикаДент."))
    send(client, transport, client_id="nikadent", q="Где вы находитесь и какие врачи принимают?")
    request = fake.inputs[0]
    assert request.model_view.client_id == "nikadent"
    contacts = yaml.safe_load((root/"clients/nikadent/clinic_policies.yaml").read_text(encoding="utf-8"))["contact"]
    facts = json.loads(request.model_view.clinic_policy_catalog_json)["contact_facts"]
    assert [b["address_display"] for b in facts["branches"]] == [b["address_display"] for b in contacts["branches"]]
    prompt = build_d2_d1r_messages(request)[0]["content"]
    assert "doctors__doctor__lavrenov.md" in prompt
    assert "doctors__doctor__kuznetsov.md" not in prompt
    assert "APPROVED MD:doctors__doctor__kadiev.md" in prompt


def test_nikadent_snapshot_loads_and_widget_origins_are_exact(http_env):
    client, _, _, root = http_env
    snapshot = load_d2_tenant_snapshot("nikadent", clients_root=root/"clients")
    assert build_d2_model_view(snapshot).client_id == "nikadent"
    for origin in ("https://nikadent41.ru", "https://www.nikadent41.ru", "http://127.0.0.1:9001"):
        response = client.get("/api/widget-config?client_id=nikadent", headers={"Origin":origin})
        assert response.status_code == 200
        body = response.get_json()
        assert body["clientId"] == "nikadent" and body["demoLauncher"] is False
        assert body["avatarUrl"] == "/static/clients/nikadent/avatar.png"
        assert body["theme"]["brand"] == "#762E94"
        assert body["theme"]["promoBackground"] == "#F5EFF8"
        assert body["theme"]["promoAccent"] == "#762E94"
    assert client.get("/api/widget-config?client_id=nikadent", headers={"Origin":"https://unrelated.invalid"}).status_code == 403


def test_test_panel_uses_selected_pack_config():
    harness = Path(__file__).parent/"js/nikadent_panel_harness.mjs"
    result = subprocess.run(["node", "--experimental-vm-modules", str(harness)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Chrome/Edge launcher DOM proof")
def test_client_launcher_concept_one_browser():
    harness = Path(__file__).parent / "js/client_launcher_harness.mjs"
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True,
                            encoding="utf-8", env=os.environ.copy(), timeout=70)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
