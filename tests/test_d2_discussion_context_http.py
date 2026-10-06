"""D2-117 whole-route evidence. Prepared outputs do not attest live comprehension."""
import json
import pytest
from contracts.response_plan import SessionKey
from contracts.d2_dialogue_result import D2DialogueResult
from core.d2_completion_context import discussion_scope
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, _booking_raw
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation


def volume(count):
    return {"extent":"one_tooth" if count == 1 else "few_teeth", "tooth_count":count, "jaw":"unknown"}


@pytest.mark.parametrize("transport", ["json","sse"])
@pytest.mark.parametrize("followup", ["А сколько времени занимает лечение?", "Сколько это длится?", "А в моём случае по срокам?"])
def test_price_then_duration_needs_no_patient_identity_and_persists_scope(http_env,transport,followup):
    client,db,use,_ = http_env
    fake = use(FakeProvider(raw(price("classic","service",volume=volume(3)))))
    send = post if transport == "json" else post_sse
    first = _body(send(client,request_id="price",q="Сколько стоит восстановить три зуба с помощью классической имплантации?"),transport)
    assert "стоимость за один зуб" in first["answer"]
    fake.raw = raw(explanation("Срок лечения зависит от этапов заживления.",
        target={"type":"service","id":"classic"},volume=volume(3),
        content_ref="implantation__faq__duration.md"))
    answer = _body(send(client,request_id="duration",q=followup),transport)
    assert answer["answer"]
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.tooth_count == 3
    key = SessionKey(client_id="demo",sid="cp6a")
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(key)
        assert discussion_scope(saved.response.resolved).volume.tooth_count == 3
        assert store.read(key).state.discussion_request_id == "duration"
        payload = store.read(key).state.model_dump()
        for removed in ("situation_state","active_service","active_topic"):
            assert removed not in payload
    assert len(fake.inputs) == 2
    assert _body(send(client,request_id="duration",q=followup),transport) == answer
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("reverse", [False,True])
def test_two_volumes_same_service_do_not_pick_first_or_last_as_current(http_env,reverse):
    client,db,use,_=http_env
    blocks=[price("classic","service",volume=volume(1)),price("classic","service",request_id="r2",volume=volume(3))]
    if reverse: blocks.reverse()
    fake=use(FakeProvider(raw(*blocks)))
    assert post(client,q="Цена одного зуба и цена трёх?").status_code == 200
    with D2DialogueStore(db) as store:
        key=SessionKey(client_id="demo",sid="cp6a")
        result=store.read_latest_completion(key).response.resolved
        assert result.d2_request_parts[1].status == "deferred"
        assert {p.discussion_scope.volume.tooth_count for p in result.d2_request_parts} == {1,3}
        assert store.read(key).state.discussion_request_id is None
    fake.raw=raw(explanation("Уточните, какой из двух объёмов обсудим."))
    assert post(client,request_id="next",q="А для этого варианта?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope is None
    assert len(fake.inputs[-1].context.ordinary.dialogue_pairs[-1].parts) == 2


@pytest.mark.parametrize("field,value", [
    ("subject",{"subject_id":"s1","relation":"self","age_group":"adult"}),
    ("situation",{"extent":"one_tooth","continuity":"same"}),
    ("continuity","same"),("scope_commitment","hypothetical"),
])
def test_removed_patient_fields_are_rejected_not_silently_adapted(field,value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        D2DialogueResult.model_validate({"outcome":"dialogue","blocks":[explanation("Ответ",**{field:value})]})


@pytest.mark.parametrize("lead_state", ["none","active","submitted"])
def test_old_schema_and_receipt_fail_before_provider_without_deleting_lead_or_rows(http_env,monkeypatch,lead_state):
    client,db,use,_=http_env
    fake=use(FakeProvider(_booking_raw() if lead_state != "none" else raw(price())))
    query="Хочу записаться" if lead_state != "none" else "Цена имплантации?"
    assert post(client,request_id="first",q=query).status_code == 200
    replay_id,replay_query="first",query
    if lead_state != "none":
        assert post(client,request_id="name",q="Анна").status_code == 200
        replay_id,replay_query="name","Анна"
    if lead_state == "submitted":
        assert post(client,request_id="phone",q="+7 999 123 45 67").status_code == 200
        replay_id,replay_query="phone","+7 999 123 45 67"
    import session
    with session.session_client_scope("demo"):
        before_lead=session.capture_lead_session_row("cp6a")
        if lead_state == "active": assert session.mem_get("cp6a")["profile"]["name"] == "Анна"
    key=SessionKey(client_id="demo",sid="cp6a")
    with D2DialogueStore(db) as store:
        if lead_state == "submitted": assert store.read_latest_completion(key).lead_effect.status == "demo_stub"
        record=store.read(key).model_dump(mode="json")
        record["state"]["schema_version"]=4
        record["state"]["situation_state"]=None
        store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE sid=?",(json.dumps(record),key.sid))
        rows=store._connection.execute("SELECT request_id,payload FROM d2_turn_request WHERE sid=?",(key.sid,)).fetchall()
        for request_id,payload in rows:
            old=json.loads(payload)
            old["focus"]={"source_session_key":key.model_dump(),"source_revision":0,"source_turn_index":0,"action":"clarify_focus"}
            store._connection.execute("UPDATE d2_turn_request SET payload=? WHERE sid=? AND request_id=?",(json.dumps(old),key.sid,request_id))
        store._connection.commit()
        before_state=store._connection.execute("SELECT * FROM d2_dialogue").fetchall()
        before_requests=store._connection.execute("SELECT * FROM d2_turn_request ORDER BY request_id").fetchall()
    def forbidden(*args,**kwargs): raise AssertionError("old SID must not call provider or send lead")
    fake.generate=forbidden
    assert post(client,request_id="new",q="А сколько времени?").status_code == 400
    assert post(client,request_id=replay_id,q=replay_query).status_code == 400
    with D2DialogueStore(db) as store:
        assert store._connection.execute("SELECT * FROM d2_dialogue").fetchall() == before_state
        assert store._connection.execute("SELECT * FROM d2_turn_request ORDER BY request_id").fetchall() == before_requests
    with session.session_client_scope("demo"):
        assert session.capture_lead_session_row("cp6a") == before_lead
    fresh=use(FakeProvider(raw(explanation("Свежий разговор."))))
    assert post(client,sid="fresh-sid",request_id="fresh",q="Как проходит лечение?").status_code == 200
    with session.session_client_scope("demo"):
        assert session.capture_lead_session_row("fresh-sid") is None
    assert fresh.inputs[0].context.ordinary.discussion_scope is None


def test_one_then_alternative_three_then_correction_has_one_current_context(http_env):
    client,db,use,_=http_env
    fake=use(FakeProvider(raw(price("classic","service",volume=volume(1)))))
    assert post(client,request_id="one",q="Цена одного зуба?").status_code == 200
    for request_id,question in [("alternative","А если три?"),("correction","Нет, всё-таки три")]:
        fake.raw=raw(price("classic","service",volume=volume(3)))
        assert post(client,request_id=request_id,q=question).status_code == 200
        with D2DialogueStore(db) as store:
            key=SessionKey(client_id="demo",sid="cp6a")
            saved=store.read_latest_completion(key)
            assert discussion_scope(saved.response.resolved).volume.tooth_count == 3
            assert store.read(key).state.discussion_request_id == request_id
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.tooth_count == 3
    assert len(fake.inputs) == 3


def test_explicit_cross_service_discussion_passes_volume_directly(http_env):
    client,db,use,_=http_env
    fake=use(FakeProvider(raw(price("classic","service",volume=volume(1)))))
    assert post(client,request_id="implant",q="Восстановление одного зуба имплантом?").status_code == 200
    fake.raw=raw(price("implant_supported_prosthetics","service",volume=volume(1)))
    assert post(client,request_id="prosthetic",q="А протезирование этого зуба?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.tooth_count == 1
    with D2DialogueStore(db) as store:
        saved=store.read_latest_completion(SessionKey(client_id="demo",sid="cp6a"))
        scope=discussion_scope(saved.response.resolved)
        assert scope.service_id == "implant_supported_prosthetics"
        assert scope.volume.tooth_count == 1
        assert all(r.service_id == scope.service_id for r in saved.response.resolved.d2_price_block.rows)


@pytest.mark.parametrize("kind", ["price","booking"])
@pytest.mark.parametrize("age,context,blocked", [("child","current_care",True),("adult","current_care",False),("unknown","current_care",False),("child","past_history",False)])
def test_clinic_age_rules_do_not_require_patient_identity(kind,age,context,blocked):
    from contracts.d2_dialogue_result import PriceOperation, BookingOperation
    from core.clinic_policy_resolver import resolve_clinic_policy_operations
    op=(PriceOperation if kind == "price" else BookingOperation)(
        kind=kind,request_id="r1",age_group=age,context=context)
    result=resolve_clinic_policy_operations(client_id="demo",operations=(op,))
    assert any(d.policy_key == "no_pediatric_dentistry" and d.outcome == "blocked" for d in result.decisions) == blocked
    if kind == "booking" and context == "past_history":
        assert result.active_booking_request_id is None
        assert any(d.reason_code == "booking_in_past_context" for d in result.decisions)


@pytest.mark.parametrize("transport", ["json","sse"])
def test_prose_source_click_keeps_frozen_scope_through_next_input(http_env,transport):
    client,db,use,_=http_env
    v={"extent":"few_teeth","tooth_count":3,"jaw":"lower"}
    ref="implantation__faq__pain.md"
    fake=use(FakeProvider(raw(explanation("Живое объяснение обезболивания.",target={"type":"service","id":"classic"},
        volume=v,brand_id="implantium",content_ref=ref,
        content_section_refs=["a:kakuyu-anesteziyu-ispolzuyut"]))))
    send=post if transport == "json" else post_sse
    first=_body(send(client,request_id="source",q="Больно ли восстановить три нижних зуба?"),transport)
    key=SessionKey(client_id="demo",sid="cp6a")
    with D2DialogueStore(db) as store:
        saved=store.read_latest_completion(key)
        assert saved.response.resolved.d2_request_parts[0].status == "answered"
        descriptor=discussion_scope(saved.response.resolved)
    reply=first["ui"]["quick_replies"][0]["reply_id"]
    fake.raw=json.dumps({"explanations":[{"request_id":"r1","content_text":"Пояснение по выбранному материалу."}]})
    args=dict(request_id="click",q="",ref=reply,ui_revision=first["revision"])
    clicked=_body(send(client,**args),transport)
    task=fake.inputs[-1].known_task.blocks[0]
    assert task.target == descriptor.target and task.volume == descriptor.volume
    assert task.brand_id == "implantium" and task.content_ref == ref
    assert _body(send(client,**args),transport) == clicked
    assert len(fake.inputs) == 2
    fake.raw=raw(explanation("Следующее объяснение."))
    assert send(client,request_id="next",q="А подробнее?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope == descriptor
