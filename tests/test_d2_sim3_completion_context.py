"""SIM-3: receipts are the sole answer source, not a second prose memory."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from contracts.response_plan import SessionKey
from contracts.d2_session_context import D2SessionActivity
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation, clarify
from tests.test_d2_continuation_scenarios import _volume


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_two_branch_addresses_reach_next_input_in_published_order(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "contact", "request_id": "r1",
        "contact_fields": ["contact_address"]})))
    send = post if transport == "json" else post_sse
    args = dict(sid="sim3-branches", client_id="nikadent")
    first = send(client, **args, request_id="addresses", q="Где вы находитесь?")
    assert first.status_code == 200
    published = _body(first, transport)["answer"]
    fake.raw = raw(explanation("Продолжение разговора о филиалах."))
    second = send(client, **args, request_id="next", q="А второй филиал?")
    assert second.status_code == 200
    remembered = fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text
    assert remembered == published
    for text in ("Филиал 1", "Филиал 2", "Рябикова, д. 49", "Пограничная, д. 27"):
        assert text in remembered
    assert remembered.index("Рябикова, д. 49") < remembered.index("Пограничная, д. 27")


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_scope_survives_more_than_three_contact_turns_and_receipts_are_bounded(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price())))
    send = post if transport == "json" else post_sse
    sid = "sim3-long"
    first = _body(send(client, sid=sid, request_id="price", q="Сколько стоит имплантация?"), transport)
    clicked = _body(send(client, sid=sid, request_id="volume", q="",
        ref="volume:implantation:one_tooth", ui_revision=first["revision"]), transport)
    assert "76" in clicked["answer"]
    assert len(fake.inputs) == 1
    key = SessionKey(client_id="demo", sid=sid)
    for i, field in enumerate(("address", "parking", "hours", "phone")):
        fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_" + field]})
        answer = _body(send(client, sid=sid, request_id=f"contact{i}", q=f"Какой {field}?"), transport)
        assert answer["answer"]
    fake.raw = raw(explanation("Установка занимает 20–30 минут, приживление — 3–6 месяцев.",
        target={"type": "topic", "id": "implantation"}, volume=_volume()))
    args = dict(sid=sid, request_id="duration", q="А сколько займёт лечение?")
    answer = _body(send(client, **args), transport)
    context = fake.inputs[-1].context
    assert context.ordinary.discussion_scope.volume.extent == "one_tooth"
    assert context.ordinary.discussion_scope.topic_id == "implantation"
    assert len(context.ordinary.dialogue_pairs) == 3
    assert all(p.parts[0].kind == "contact" for p in context.ordinary.dialogue_pairs)
    assert all(p.assistant_text for p in context.ordinary.dialogue_pairs)
    assert "20–30" in answer["answer"]
    count = len(fake.inputs)
    assert _body(send(client, **args), transport) == answer
    assert len(fake.inputs) == count
    with D2DialogueStore(db) as store:
        state = store.read(key).state
        assert "situation_state" not in state.model_dump()
        assert state.discussion_request_id == "duration"
        assert len(state.dialogue_pairs) == 3
        assert all(not hasattr(p, "assistant_text") for p in state.dialogue_pairs)
        assert state.dialogue_pairs[-1].request_id == "duration"
        assert "recent_price_scope" not in store.read_latest_completion(key).model_dump()


@pytest.mark.parametrize("next_block", [price("all_on_4", "service"), price("professional_whitening", "service")])
def test_new_service_replaces_scope_and_never_inherits_old_extent(http_env, next_block):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price())))
    first = post(client, request_id="price", q="Цена имплантации?").get_json()
    post(client, request_id="volume", q="", ref="volume:implantation:one_tooth", ui_revision=first["revision"])
    fake.raw = raw(next_block)
    assert post(client, request_id="new", q="Цена другой услуги?").status_code == 200
    fake.raw = raw(explanation("Сроки новой услуги."))
    assert post(client, request_id="next", q="А сроки?").status_code == 200
    scope = fake.inputs[-1].context.ordinary.discussion_scope
    assert scope is None or scope.volume is None
    if scope:
        assert scope.service_id == next_block["target"]["id"]


def test_ttl_excludes_receipts_and_long_lived_scope(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price())))
    first = post(client, request_id="price", q="Цена имплантации?").get_json()
    post(client, request_id="volume", q="", ref="volume:implantation:one_tooth", ui_revision=first["revision"])
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        record = store.read(key)
        expired = record.model_copy(update={"activity": D2SessionActivity(session_key=key,
            last_user_turn_at=datetime.now(timezone.utc) - timedelta(hours=1))})
        store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
            (expired.model_dump_json(), key.client_id, key.sid))
        store._connection.commit()
    fake.raw = raw(clarify("content"))
    assert post(client, request_id="expired", q="А сроки?").status_code == 200
    context = fake.inputs[-1].context
    assert context.freshness == "expired"
    assert context.ordinary.discussion_scope is None
    assert context.ordinary.dialogue_pairs == ()


def test_price_detail_is_remembered_without_old_money_and_contact_prose_is_public(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client, request_id="price", q="Сколько стоит классическая имплантация?").get_json()
    detail = next(r["reply_id"] for r in first["ui"]["quick_replies"] if "includes" in r["reply_id"])
    assert post(client, request_id="detail", q="", ref=detail, ui_revision=first["revision"]).status_code == 200
    fake.raw = raw(explanation("Ответ о сроках."))
    assert post(client, request_id="next", q="А сроки?").status_code == 200
    pairs = fake.inputs[-1].context.ordinary.dialogue_pairs
    assert pairs[-1].detail_aspects == ("includes",)
    assert pairs[-1].offers
    serialized = json.dumps([p.model_dump(mode="json") for p in pairs], ensure_ascii=False)
    for money in ("76 200", "85 200", "101 200", "₽", "amount_rub", "rendered_text"):
        assert money not in serialized


def test_receipt_reference_cannot_read_foreign_or_inflight_result(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Ответ."))))
    assert post(client, request_id="first", q="Как проходит лечение?").status_code == 200
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        assert store.read_completion(SessionKey(client_id="nikadent", sid=key.sid), "first") is None
        assert store.read_completion(SessionKey(client_id="demo", sid="other"), "first") is None
        record = store.read(key)
        pair = record.state.dialogue_pairs[0].model_copy(update={"request_id": "missing"})
        record = record.model_copy(update={"state": record.state.model_copy(update={"dialogue_pairs": (pair,)})})
        store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
            (record.model_dump_json(), key.client_id, key.sid))
        store._connection.commit()
    before = len(fake.inputs)
    assert post(client, request_id="bad", q="А сроки?").status_code == 400
    assert len(fake.inputs) == before


def test_direct_text_extent_and_explicit_unknown_replace_old_discussion_without_patient_fact(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service", brand_id="implantium",
        volume=_volume()))))
    assert post(client, request_id="direct", q="Если имплантация одного зуба Implantium, сколько стоит?").status_code == 200
    fake.raw = raw(explanation("Сроки обсуждаемой услуги.", target={"type": "service", "id": "classic"}))
    assert post(client, request_id="next", q="А сроки?").status_code == 200
    scope = fake.inputs[-1].context.ordinary.discussion_scope
    assert (scope.service_id, scope.brand_id, scope.volume.extent) == ("classic", "implantium", "one_tooth")
    fake.raw = raw(price())
    first = post(client, request_id="overview", q="А вообще какие варианты имплантации?").get_json()
    assert post(client, request_id="unknown", q="", ref="volume:implantation:unknown", ui_revision=first["revision"]).status_code == 200
    fake.raw = raw(explanation("Общие сроки."))
    assert post(client, request_id="last", q="А сроки?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.extent == "unknown"
    with D2DialogueStore(db) as store:
        assert "situation_state" not in store.read(SessionKey(client_id="demo", sid="cp6a")).state.model_dump()


@pytest.mark.parametrize("block", [clarify("content"),
    {"kind": "clinic_policy", "request_id": "r1", "policy_ids": ["no_oms"]},
    {"kind": "commercial_fact", "request_id": "r1", "promotion_scope": "general"}])
def test_clarification_policy_and_fact_results_reach_next_model_input(http_env, block):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(block)))
    assert post(client, request_id="first", q="Расскажите об условиях клиники?").status_code == 200
    fake.raw = raw(explanation("Продолжение."))
    assert post(client, request_id="next", q="А подробнее?").status_code == 200
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert pair.parts and pair.patient_text == "Расскажите об условиях клиники?"
    if block.get("clarification") is not None:
        assert pair.parts[0].kind == "clarification"
        assert fake.inputs[-1].context.ordinary.clarify_task is not None
    elif block["kind"] == "clinic_policy":
        assert pair.parts[0].kind == "reference"
        assert pair.policy_ids == ("no_oms",)
    else:
        assert pair.parts[0].kind == "commercial_fact"
        assert pair.fact_ids
