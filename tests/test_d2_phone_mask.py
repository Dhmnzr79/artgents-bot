"""Phone belongs to the shared form; the dialogue composer stays ordinary text."""
from unittest.mock import Mock
import pytest
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send
from tests.test_d2_native_price_runtime import Transport,message
from tests.test_widget_booking_form import form_payload


@pytest.mark.parametrize("phone",["+7 (999) 123-45-67","8 (999) 123-45-67","79991234567"])
def test_form_phone_normalizes_without_model_or_contact_turns(http_env,monkeypatch,phone):
    client,_,_,_=http_env
    delivery=Mock(return_value="email");monkeypatch.setattr("lead_service._resolve_delivery_status",delivery)
    payload=form_payload(client,phone=phone)
    assert client.post("/lead",json=payload).get_json()["ok"]
    assert delivery.call_args.kwargs["phone"]=="+79991234567"


@pytest.mark.parametrize("transport",["json","sse"])
def test_booking_response_does_not_switch_dialogue_to_phone_mode(http_env,transport):
    client,_,use,_=http_env
    raw='<D2_META>\n{"actions":[{"name":"start_booking","arguments":{"age_group":"adult"}}]}\n</D2_META>'
    wire=Transport(message(raw),message("Адрес указан на сайте клиники."));use(D2HttpProvider(transport=wire))
    body=send(client,transport)
    assert body["ui"]["booking_form"] and body["ui"]["composer_input_mode"]=="text"
    second=send(client,transport,request_id="question",q="А где вы находитесь?")
    assert second["ui"]["composer_input_mode"]=="text" and len(wire.calls)==2
