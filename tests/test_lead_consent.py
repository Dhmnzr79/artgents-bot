"""Real JSON/SSE consent entry, bypass protection and non-contact durable proof."""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from contracts.lead_consent import LeadConsentDefinition
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.lead_consent import lead_consent_definition
from session import mem_get, session_client_scope
from tests.d2_ci_http import FakeProvider, http_env, send, click
from tests.test_d2_text_reply import response, action
from tests.test_nikadent_technical_onboarding import private_offline_environment


def booking(client, fake, transport="json", *, sid="consent", request_id="book", tenant="nikadent"):
    fake.raw = response(actions=[action("start_booking", age_group="adult")])
    return send(client, transport, client_id=tenant, sid=sid, request_id=request_id, q="Хочу записаться")


def accept(client, body, transport="json", *, sid="consent", request_id="accepted"):
    return click(client, body, "lead:consent_accept", client_id="nikadent", sid=sid,
                 request_id=request_id, transport=transport)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_consent_before_slots_and_submission_with_durable_proof(http_env, monkeypatch, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    smtp = MagicMock()
    connect = MagicMock()
    connect.return_value.__enter__.return_value = smtp
    monkeypatch.setattr("core.lead_email._connect_smtp", connect)
    first = booking(client, fake, transport)
    prompt = first["ui"]["lead_consent"]
    assert prompt["consent_url"] == "https://nikadent41.ru/personal-data-consent/"
    assert prompt["policy_url"] == "https://nikadent41.ru/privacy-policy-2/"
    assert "имени и телефона" in prompt["checkbox_text"]
    for index, text in enumerate(["Анна", "+79001234567", "да", "Какие врачи принимают?"]):
        first = send(client, transport, client_id="nikadent", sid="consent", request_id=f"bypass{index}", q=text)
        assert first["ui"]["lead_consent"]
        with session_client_scope("nikadent"):
            state = mem_get("consent")
            assert not state["profile"].get("name") and not state["profile"].get("phone")
    named = accept(client, first, transport)
    assert named["ui"]["lead_consent"] is None and named["answer"] != first["answer"]
    with session_client_scope("nikadent"):
        assert mem_get("consent")["lead_intent"] == "collecting_name"
    before = len(fake.inputs)
    send(client, transport, client_id="nikadent", sid="consent", request_id="name", q="Анна")
    final = send(client, transport, client_id="nikadent", sid="consent", request_id="phone", q="+79001234567")
    assert final["lead_effect"]["status"] == "sent"
    assert len(fake.inputs) == before == 1
    smtp.send_message.assert_called_once()
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="nikadent", sid="consent")
        saved = store.read_completion(key, "accepted")
        assert saved.consent_receipt.accepted_at.tzinfo is not None
        assert saved.consent_receipt.definition.version == "2026-10-15-v1"
        assert store.read_completion(key, "phone").lead_consent_request_id == "accepted"
        for record in [saved, store.read_completion(key, "phone"), store.read(key)]:
            assert "Анна" not in record.model_dump_json()
            assert "79001234567" not in record.model_dump_json()
        context = json.dumps(fake.inputs[0].context.model_dump(mode="json"))
        assert "consent_receipt" not in context and "personal-data-consent" not in context
    with session_client_scope("nikadent"):
        assert not mem_get("consent").get("lead_consent_request_id")


def test_only_published_current_tenant_session_action_can_accept(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    first = booking(client, fake)
    args = {"client_id":"nikadent", "sid":"consent", "ref":"lead:consent_accept",
            "ui_revision":first["revision"], "q":"", "request_id":"forged"}
    for changes in [{"sid":"foreign"}, {"client_id":"demo"}, {"ui_revision":99},
                    {"ref":"lead:consent_accept:fake"}, {"consent":True}]:
        assert client.post("/ask", json={**args, **changes}).status_code in {400,403,409}
    current = send(client, client_id="nikadent", sid="consent", request_id="unchecked", q="да")
    assert client.post("/ask", json=args).status_code == 400
    with D2DialogueStore(db) as store:
        assert store.read_completion(SessionKey(client_id="nikadent",sid="consent"),"forged") is None
    accept(client, current)


def test_accept_replay_does_not_authorize_new_booking_and_cancel_allows_questions(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused"))
    first = booking(client, fake)
    named = accept(client, first)
    with D2DialogueStore(db) as store:
        original = store.read_completion(SessionKey(client_id="nikadent",sid="consent"),"accepted").consent_receipt
    send(client, client_id="nikadent", sid="consent", request_id="cancel", q="отмена")
    new = booking(client, fake, request_id="again")
    assert accept(client, first) == named
    with session_client_scope("nikadent"):
        assert mem_get("consent")["lead_intent"] == "collecting_consent"
        assert not mem_get("consent").get("lead_consent_request_id")
    cancelled = click(client,new,"lead:cancel",client_id="nikadent",sid="consent",request_id="skip")
    assert cancelled["ui"]["lead_consent"] is None
    fake.raw = "В клинике принимают врачи по базе НикаДент."
    answer = send(client, client_id="nikadent",sid="consent",request_id="ordinary",q="Какие врачи принимают?")
    assert answer["ui"]["lead_consent"] is None
    with D2DialogueStore(db) as store:
        assert store.read_completion(SessionKey(client_id="nikadent",sid="consent"),"accepted").consent_receipt == original


def test_changed_definition_invalidates_pending_action_and_active_proof(http_env, monkeypatch):
    client, _, use, _ = http_env
    fake = use(FakeProvider("unused"))
    first = booking(client, fake)
    import core.lead_consent as consent
    raw = consent.load_lead_config("nikadent").copy()
    raw["consent"] = {**raw["consent"], "version":"next-version"}
    monkeypatch.setattr(consent,"load_lead_config",lambda _id:raw)
    rejected = client.post("/ask",json={"client_id":"nikadent","sid":"consent","request_id":"changed",
        "ref":"lead:consent_accept","ui_revision":first["revision"],"q":""})
    assert rejected.status_code == 400
    with session_client_scope("nikadent"):
        assert mem_get("consent")["lead_intent"] == "collecting_consent"
    refreshed = send(client,client_id="nikadent",sid="consent",request_id="refresh",q="Продолжим")
    assert refreshed["ui"]["lead_consent"]["version"] == "next-version"
    assert accept(client,refreshed)["ui"]["lead_consent"] is None
    raw["consent"]["version"] = "third-version"
    renewed = send(client,client_id="nikadent",sid="consent",request_id="name-after-change",q="Анна")
    assert renewed["ui"]["lead_consent"]["version"] == "third-version"
    with session_client_scope("nikadent"):
        assert not mem_get("consent")["profile"].get("name")
        assert not mem_get("consent").get("lead_consent_request_id")


@pytest.mark.parametrize("stage", ["collecting_name", "collecting_phone", "paused"])
def test_slot_and_resume_states_without_durable_proof_cannot_collect(http_env,stage):
    client, _, use, _ = http_env
    fake=use(FakeProvider("must not run"))
    from session import set_lead_intent,update_profile
    with session_client_scope("nikadent"):
        set_lead_intent("bypass-state",stage)
        update_profile("bypass-state",name="Анна")
    body=send(client,client_id="nikadent",sid="bypass-state",request_id="phone",q="+79001234567")
    assert body["ui"]["lead_consent"]
    assert fake.inputs == []
    with session_client_scope("nikadent"):
        assert not mem_get("bypass-state")["profile"].get("name")
        assert not mem_get("bypass-state")["profile"].get("phone")


def test_accept_commit_failure_restores_pending_gate_without_receipt(http_env,monkeypatch):
    client, db, use, _ = http_env
    fake = use(FakeProvider("unused")); first = booking(client,fake)
    complete = D2DialogueStore.complete
    monkeypatch.setattr(D2DialogueStore,"complete",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("offline")))
    args = {"client_id":"nikadent","sid":"consent","request_id":"accept-fail",
            "ref":"lead:consent_accept","ui_revision":first["revision"],"q":""}
    assert client.post("/ask",json=args).status_code == 503
    with session_client_scope("nikadent"):
        assert mem_get("consent")["lead_intent"] == "collecting_consent"
        assert not mem_get("consent").get("lead_consent_request_id")
    with D2DialogueStore(db) as store:
        assert store.read_completion(SessionKey(client_id="nikadent",sid="consent"),"accept-fail") is None
    monkeypatch.setattr(D2DialogueStore,"complete",complete)
    assert client.post("/ask",json=args).status_code == 200


def test_direct_lead_cannot_bypass_or_forge_consent(http_env,monkeypatch):
    client, _, _, _ = http_env
    send_email = MagicMock(side_effect=AssertionError("No SMTP before consent"))
    monkeypatch.setattr("lead_service.send_lead_email",send_email)
    for extra in [{}, {"consent":True}, {"consent_receipt":{"accepted":True}}]:
        result = client.post("/lead",json={"client_id":"nikadent","sid":"direct","name":"Анна",
                                           "phone":"+79001234567",**extra})
        assert result.status_code == 403
        assert result.get_json()["error_code"] == "lead_consent_required"
    send_email.assert_not_called()


def test_demo_stays_without_consent_and_missing_real_definition_fails_closed(http_env,monkeypatch):
    client, _, use, _ = http_env
    fake=use(FakeProvider("unused"))
    assert booking(client,fake,tenant="demo")["ui"]["lead_consent"] is None
    import core.lead_consent as consent
    monkeypatch.setattr(consent,"load_lead_config",lambda _id:{})
    with pytest.raises(ValueError,match="not_configured"):
        lead_consent_definition("nikadent")


@pytest.mark.parametrize("field,value",[("policy_url","javascript:alert(1)"),
                                        ("consent_url","https://u:p@host.test/doc"),
                                        ("checkbox_text"," "),("version","")])
def test_invalid_consent_configuration(field,value):
    definition=lead_consent_definition("nikadent").model_dump();definition[field]=value
    with pytest.raises(ValueError):LeadConsentDefinition.model_validate(definition)


@pytest.mark.skipif(sys.platform != "win32",reason="Windows Chrome/Edge DOM proof")
def test_real_widget_compact_consent_dom(http_env,tmp_path):
    client, _, use, _ = http_env
    fake=use(FakeProvider("unused"));first=booking(client,fake);named=accept(client,first)
    cancelled=send(client,client_id="nikadent",sid="consent",request_id="cancel",q="отмена")
    fixture=tmp_path/"consent-ui.json"
    fixture.write_text(json.dumps({"prompt":first,"accepted":named,"cancelled":cancelled},ensure_ascii=False),encoding="utf-8")
    result=subprocess.run(["node",str(Path(__file__).parent/"js/lead_consent_harness.mjs")],
        env={**os.environ,"LEAD_CONSENT_PAYLOADS_FILE":str(fixture)},capture_output=True,text=True,encoding="utf-8",timeout=70)
    assert result.returncode==0,result.stdout+result.stderr
    assert '"passed":true' in result.stdout
