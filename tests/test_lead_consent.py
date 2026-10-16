"""Consent on the private shared form; no conversational contact collection."""
from unittest.mock import Mock
import pytest
from contracts.lead_consent import LeadConsentDefinition
from core.lead_consent import lead_consent_definition
from tests.d2_ci_http import http_env
from tests.test_widget_booking_form import form_payload


@pytest.mark.parametrize("field,value",[("policy_url","javascript:alert(1)"),
    ("consent_url","https://u:p@host.test/doc"),("checkbox_text"," "),("version","")])
def test_invalid_consent_configuration(field,value):
    definition=lead_consent_definition("nikadent").model_dump();definition[field]=value
    with pytest.raises(ValueError):LeadConsentDefinition.model_validate(definition)


def test_direct_sender_cannot_bypass_server_receipt(http_env,monkeypatch):
    from lead_service import handle_lead
    client,_,_,_=http_env
    sender=Mock(return_value="email");monkeypatch.setattr("lead_service._resolve_delivery_status",sender)
    payload=form_payload(client)
    body,status=handle_lead(payload,client_id="nikadent")
    assert status==403 and body["error_code"]=="lead_consent_required" and not sender.called
    payload["consent_receipt"]={"accepted":True}
    assert client.post("/lead",json=payload).status_code==400 and not sender.called


def test_missing_live_definition_blocks_but_stub_requires_checkbox(http_env,monkeypatch):
    import yaml
    import core.client_config_loader as loader
    monkeypatch.setattr(loader,'_LEAD_CACHE',{})
    client,_,_,tmp=http_env
    path=tmp/"clients/nikadent/lead_config.yaml";cfg=yaml.safe_load(path.read_text(encoding="utf-8"));cfg.pop("consent")
    path.write_text(yaml.safe_dump(cfg,allow_unicode=True),encoding="utf-8")
    assert client.get("/api/booking-form?client_id=nikadent").status_code==400
    payload=form_payload(client,tenant="demo");payload["consent"]["accepted"]=False
    assert client.post("/lead",json=payload).status_code==400
    payload["consent"]["accepted"]=True
    assert client.post("/lead",json=payload).get_json()["status"]=="demo_stub"


def test_stub_acceptance_never_upgrades_to_live_consent(http_env,monkeypatch):
    client,_,_,_=http_env
    payload=form_payload(client,tenant="demo")
    original=client.post("/lead",json=payload).get_json();assert original["status"]=="demo_stub"
    monkeypatch.setattr("core.lead_consent.leads_enabled",lambda _:True)
    monkeypatch.setattr("core.lead_consent.leads_mode",lambda _:"email")
    sender=Mock(return_value="email");monkeypatch.setattr("lead_service._resolve_delivery_status",sender)
    assert client.post("/lead",json=payload).get_json()==original
    changed={**payload,"request_id":"new-request"}
    assert client.post("/lead",json=changed).status_code==400 and not sender.called


def test_private_form_body_is_not_sent_to_full_http_audit(http_env,monkeypatch):
    import app
    client,_,_,_=http_env
    audit=Mock();monkeypatch.setattr(app,"full_audit",audit)
    assert client.post("/lead",json=form_payload(client,tenant="demo")).get_json()["ok"]
    assert not audit.called
