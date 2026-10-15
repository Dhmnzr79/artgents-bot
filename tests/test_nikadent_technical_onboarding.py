"""Current HTTP/SSE -> existing SMTP with private slots and durable receipts."""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, send
from tests.test_d2_text_reply import response, action


def begin(client, fake, *, client_id="demo", sid="lead", phone=False, transport="json"):
    fake.raw = response(actions=[action("start_booking", age_group="adult")])
    send(client, transport, client_id=client_id, sid=sid, request_id="book", q="Хочу записаться")
    if phone:
        send(client, transport, client_id=client_id, sid=sid, request_id="name", q="Анна")


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
def test_nikadent_accepted_slots_send_once_and_replay_without_private_data(http_env, monkeypatch, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    smtp = MagicMock()
    connect = MagicMock()
    connect.return_value.__enter__.return_value = smtp
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    begin(client, fake, client_id="nikadent", sid="nika-lead", phone=True, transport=transport)
    args = dict(client_id="nikadent", sid="nika-lead", request_id="phone", q="8 (900) 123-45-67")
    body = send(client, transport, **args)
    assert body["lead_effect"]["status"] == "sent"
    assert "свяжется" in body["answer"]
    assert send(client, transport, **args) == body
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "gothica@mail.ru"
    assert "Никадент" in message.get_content()
    assert "Анна" in message.get_content() and "+79001234567" in message.get_content()
    assert len(fake.inputs) == 1
    from session import mem_get, session_client_scope
    with session_client_scope("nikadent"):
        private = mem_get("nika-lead")
        assert private["lead_intent"] == "none"
        assert not private["profile"].get("name") and not private["profile"].get("phone")
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="nikadent", sid="nika-lead")
        saved = store.read_completion(key, "phone")
        assert saved.response.rendered_text == body["answer"]
        assert saved.response.ui_projection.model_dump(mode="json") == body["ui"]
        for text in (saved.model_dump_json(), store.read(key).model_dump_json()):
            assert "Анна" not in text and "79001234567" not in text


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
    begin(client, fake, client_id="nikadent", sid="failed-lead", phone=True, transport=transport)
    args = dict(client_id="nikadent", sid="failed-lead", request_id="phone", q="+79001234567")
    body = send(client, transport, **args)
    assert body["lead_effect"]["status"] == expected_status
    assert phrase in body["answer"] and "свяжется" not in body["answer"]
    assert send(client, transport, **args) == body
    assert connect.call_count == (1 if failure == "smtp" else 0)
    with D2DialogueStore(db) as store:
        saved = store.read_completion(SessionKey(client_id="nikadent", sid="failed-lead"), "phone")
        assert saved.response.rendered_text == body["answer"]
        assert saved.lead_effect.status == expected_status


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_demo_submission_keeps_stub_and_never_connects_smtp(http_env, monkeypatch, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider("unused"))
    connect = MagicMock(side_effect=AssertionError("demo cannot send email"))
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    begin(client, fake, sid="shared-id", phone=True, transport=transport)
    body = send(client, transport, sid="shared-id", request_id="phone", q="+79001234567")
    assert body["lead_effect"]["status"] == "demo_stub"
    connect.assert_not_called()
    begin(client, fake, client_id="nikadent", sid="shared-id", phone=True, transport=transport)
    monkeypatch.delenv("SMTP_PASSWORD")
    other = send(client, transport, client_id="nikadent", sid="shared-id", request_id="phone", q="+79007654321")
    assert other["lead_effect"]["status"] == "failed"
    assert other["client_id"] == "nikadent" and body["client_id"] == "demo"


def test_commit_failure_does_not_send_and_restores_private_slot(http_env, monkeypatch):
    client, _, use, _ = http_env
    fake = use(FakeProvider("unused"))
    begin(client, fake, client_id="nikadent", sid="commit", phone=True)
    connect = MagicMock()
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    monkeypatch.setattr(D2DialogueStore, "complete", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("commit failed")))
    response = client.post("/ask", json={"client_id":"nikadent", "sid":"commit", "request_id":"phone", "q":"+79001234567"})
    assert response.status_code == 503
    connect.assert_not_called()
    from session import session_client_scope, mem_get
    with session_client_scope("nikadent"):
        state = mem_get("commit")
        assert state["lead_intent"] == "collecting_phone"
        assert state["profile"]["name"] == "Анна" and not state["profile"].get("phone")


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
        assert "nikadent" in body["avatarUrl"]
    assert client.get("/api/widget-config?client_id=nikadent", headers={"Origin":"https://unrelated.invalid"}).status_code == 403


def test_test_panel_uses_selected_pack_config():
    harness = Path(__file__).parent/"js/nikadent_panel_harness.mjs"
    result = subprocess.run(["node", "--experimental-vm-modules", str(harness)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
