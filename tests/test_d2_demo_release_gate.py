"""Temporary 2026-10-14 demo gate on actual D2 HTTP/SSE and native provider.

Historical suites stay unchanged. Fixtures use only prose, D2_META and native
show_price, never adapt the retired envelope. Secondary tenant is synthetic:
nikadent is unfinished and is not certified by this demo gate.
"""
import json
import shutil
from pathlib import Path
import pytest
import yaml
from core.d2_live_provider import D2HttpProvider
from core.d2_dialogue_store import D2DialogueStore
from core.clinic_policies_loader import resolve_policy_text
from contracts.response_plan import SessionKey
from session import session_client_scope, mem_get, set_situation_pending
from lead_interrupt import LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events
from tests.test_d2_native_price_runtime import Transport, message, price


def reply(text="", *, actions=()):
    if not actions:return text
    return text+"\n<D2_META>\n"+json.dumps({"actions":list(actions)},ensure_ascii=False)+"\n</D2_META>"


def action(name, **arguments):
    return {"name":name,"arguments":arguments}


def call(client, transport="json", **kwargs):
    response=(post if transport=="json" else post_sse)(client,**kwargs)
    assert response.status_code==200,response.get_data(as_text=True)
    if transport=="json":body=response.get_json()
    else:
        frames=dict(sse_events(response))
        assert "error" not in frames and "done" in frames,frames
        body=frames["ui"]
    assert body["revision"]>0 and isinstance(body["ui"],dict)
    return body


@pytest.fixture
def demo_gate_env(http_env,monkeypatch):
    client,db,use,tmp=http_env
    # Valid synthetic secondary tenant, not an edit/fallback for the unfinished real pack.
    root=tmp/"clients"
    shutil.copytree(root/"demo",root/"secondary")
    path=root/"secondary/clinic_policies.yaml"
    data=yaml.safe_load(path.read_text(encoding="utf-8"))
    data["contact"]["phone_display"]="+7 (999) 000-00-01"
    data["contact"]["address_display"]="Адрес вторичной тестовой клиники"
    path.write_text(yaml.safe_dump(data,allow_unicode=True),encoding="utf-8")
    path=root/"secondary/target_response/pricebook/services/classic.one_tooth.implantium.json"
    offer=json.loads(path.read_text(encoding="utf-8"));offer["price"]["amount"]=99900
    offer["payment_stages"][-1]["amount"]=54700
    path.write_text(json.dumps(offer,ensure_ascii=False),encoding="utf-8")
    import config
    monkeypatch.setattr(config,"ALLOWED_CLIENTS",frozenset({"demo","secondary"}))
    return client,db,use,tmp


@pytest.mark.parametrize("transport",["json","sse"])
@pytest.mark.parametrize("text",["Обезболивание обсуждается с врачом.","{invalid"])
def test_current_basic_prose_replay_and_no_hidden_actions(demo_gate_env,transport,text):
    client,db,use,_=demo_gate_env
    wire=Transport(message(text));use(D2HttpProvider(transport=wire))
    args=dict(request_id="basic",q="Боюсь боли")
    body=call(client,transport,**args)
    assert body["answer"]==text
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert call(client,transport,**args)==body and len(wire.calls)==1
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo",sid="cp6a")).response.rendered_text==text


@pytest.mark.parametrize("transport",["json","sse"])
def test_tenant_contact_native_price_same_sid_and_replay_are_isolated(demo_gate_env,transport):
    client,db,use,tmp=demo_gate_env
    wire=Transport(message(reply(actions=[action("show_contacts",contact_fields=["contact_phone"])])),
        message(reply(actions=[action("show_contacts",contact_fields=["contact_phone"])])),
        message(None,price(brand_id="implantium")),message("<NO_TEXT>"),message(None,price(brand_id="implantium")),message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    contacts={}
    for tenant,phone,foreign in [("demo","+7 (495) 128-47-60","+7 (999) 000-00-01"),
                                ("secondary","+7 (999) 000-00-01","+7 (495) 128-47-60")]:
        body=call(client,transport,client_id=tenant,sid="shared",request_id="contacts",q="Какой телефон?")
        assert body["client_id"]==tenant and phone in body["answer"] and foreign not in body["answer"]
        contacts[tenant]=body
    for tenant,amount in [("demo",76200),("secondary",99900)]:
        args=dict(client_id=tenant,sid="shared",request_id="price",q="Цена классической имплантации?")
        body=call(client,transport,**args)
        card=next(p for p in body["ui"]["body_parts"] if p["kind"]=="price_card")
        row=card["price"]["rows"][0]
        assert row["offer_id"]=="classic.one_tooth.implantium" and row["amount"]==amount
        assert row["source_client_id"]==tenant
        assert call(client,transport,**args)==body
        assert call(client,transport,client_id=tenant,sid="shared",request_id="contacts",q="Какой телефон?")==contacts[tenant]
        with D2DialogueStore(db) as store:
            assert store.read(SessionKey(client_id=tenant,sid="shared")).state.revision==2
    assert len(wire.calls)==6
    assert wire.calls[2]["model"]==wire.calls[3]["model"]


@pytest.mark.parametrize("transport",["json","sse"])
def test_booking_pii_pending_resume_and_situation_disabled(demo_gate_env,transport):
    client,db,use,_=demo_gate_env
    wire=Transport(message(reply(actions=[action("start_booking",age_group="adult")])),message("Ответ по материалам клиники."))
    use(D2HttpProvider(transport=wire))
    first=call(client,transport,request_id="book",q="Хочу записаться")
    assert "Как к вам обращаться" in first["answer"]
    with session_client_scope("demo"):
        assert mem_get("cp6a")["lead_intent"]=="collecting_name"
        set_situation_pending("cp6a",True)
    phone=call(client,transport,request_id="name",q="Анна")
    assert phone["ui"]["composer_input_mode"]=="phone" and len(wire.calls)==1
    with session_client_scope("demo"):
        assert mem_get("cp6a")["lead_intent"]=="collecting_phone"
        assert mem_get("cp6a")["profile"]["name"]=="Анна"
        assert mem_get("cp6a")["situation_pending"] is True
    question="Меня зовут Анна, телефон +7 999 123-45-67. Как проходит лечение?"
    pending=call(client,transport,request_id="question",q=question)
    assert LEAD_PENDING_ANSWER_REF in {x["reply_id"] for x in pending["ui"]["quick_replies"]}
    assert len(wire.calls)==1
    args=dict(request_id="answer",q="",ref=LEAD_PENDING_ANSWER_REF,ui_revision=pending["revision"])
    answer=call(client,transport,**args)
    assert answer["answer"]=="Ответ по материалам клиники."
    assert call(client,transport,**args)==answer and len(wire.calls)==2
    user=wire.calls[1]["messages"][1]["content"]
    assert "Анна" not in user and "79991234567" not in user and "123-45-67" not in user
    assert "Как проходит лечение?" in user
    with session_client_scope("demo"):
        assert mem_get("cp6a")["lead_intent"]=="paused"
        assert mem_get("cp6a")["lead_resume_step"]=="collecting_phone"
    resumed=call(client,transport,request_id="resume",q="",ref=LEAD_RESUME_REF,ui_revision=answer["revision"])
    assert resumed["ui"]["composer_input_mode"]=="phone" and len(wire.calls)==2
    with session_client_scope("demo"):
        assert mem_get("cp6a")["lead_intent"]=="collecting_phone"
    submitted=call(client,transport,request_id="phone",q="+79991234567")
    assert submitted["lead_effect"]["status"]=="demo_stub"
    assert len(wire.calls)==2
    with D2DialogueStore(db) as store:
        state=store.read(SessionKey(client_id="demo",sid="cp6a")).state.model_dump_json()
        assert "79991234567" not in state and "Анна" not in state


@pytest.mark.parametrize("transport",["json","sse"])
def test_situation_commands_rejected_without_model_or_lead_mutation(demo_gate_env,transport):
    client,_,use,_=demo_gate_env
    wire=Transport();use(D2HttpProvider(transport=wire))
    response=(post if transport=="json" else post_sse)(client,request_id="old",q="",situation_action="start")
    if transport=="json":assert response.status_code==400
    else:
        frames=dict(sse_events(response));assert "error" in frames and "ui" not in frames and "done" not in frames
    assert wire.calls==[]
    with session_client_scope("demo"):assert mem_get("cp6a")["lead_intent"] not in {"collecting_name","collecting_phone"}


@pytest.mark.parametrize("transport",["json","sse"])
@pytest.mark.parametrize("kind",["price","booking"])
@pytest.mark.parametrize("policy,fields",[
 ("no_pediatric_dentistry",{"age_group":"child"}),
 ("no_oms",{"payment_scheme":"oms","payment_scheme_intent":"requested_payment"}),
 ("no_dms",{"payment_scheme":"dms","payment_scheme_intent":"requested_payment"})])
def test_policy_text_ref_guards_current_price_and_booking(demo_gate_env,transport,kind,policy,fields):
    client,_,use,tmp=demo_gate_env
    root=tmp/"clients/demo"
    rules=yaml.safe_load((root/"clinic_policies.yaml").read_text(encoding="utf-8"))
    expected=resolve_policy_text(rules["policies"][policy],lambda name:(root/"md"/name).read_text(encoding="utf-8"))
    if kind=="price":wire=Transport(message(None,price("caries",**fields)),message(expected))
    else:wire=Transport(message(reply(actions=[action("start_booking",**fields)])))
    use(D2HttpProvider(transport=wire))
    args=dict(request_id="guard",q="Условия лечения и записи")
    body=call(client,transport,**args)
    assert body["answer"]==expected
    assert not body["ui"]["buttons"] and not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert call(client,transport,**args)==body
    assert len(wire.calls)==(2 if kind=="price" else 1)
    if kind=="price":assert expected in wire.calls[1]["messages"][-2]["content"]
    with session_client_scope("demo"):assert mem_get("cp6a")["lead_intent"] not in {"collecting_name","collecting_phone"}


@pytest.mark.parametrize("transport",["json","sse"])
def test_missing_policy_text_ref_fails_before_provider(demo_gate_env,transport):
    client,_,use,tmp=demo_gate_env
    path=tmp/"clients/demo/clinic_policies.yaml"
    rules=yaml.safe_load(path.read_text(encoding="utf-8"));rules["policies"]["no_oms"]["text_ref"]="clinic__info__policies.md#missing"
    path.write_text(yaml.safe_dump(rules,allow_unicode=True),encoding="utf-8")
    wire=Transport();use(D2HttpProvider(transport=wire))
    response=(post if transport=="json" else post_sse)(client,q="Условия лечения")
    if transport=="json":assert response.status_code==400
    else:assert "error" in dict(sse_events(response)) and "ui" not in dict(sse_events(response))
    assert wire.calls==[]


def test_commit_failure_no_lead_or_final_receipt(demo_gate_env,monkeypatch):
    client,db,use,_=demo_gate_env
    wire=Transport(message(reply(actions=[action("start_booking",age_group="adult")])))
    use(D2HttpProvider(transport=wire))
    def fail(*args,**kwargs):raise RuntimeError("offline commit refused")
    monkeypatch.setattr(D2DialogueStore,"complete",fail)
    result=post(client,request_id="commit-fail",q="Хочу записаться")
    assert result.status_code==503 and result.get_json()=={"error":"d2_turn_failed"}
    with session_client_scope("demo"):assert mem_get("cp6a")["lead_intent"] not in {"collecting_name","collecting_phone"}
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo",sid="cp6a")) is None
    assert len(wire.calls)==1
