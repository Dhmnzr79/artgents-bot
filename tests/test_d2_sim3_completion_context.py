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
from tests.d2_ci_http import completed_context, send


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
    {"kind": "commercial_fact", "request_id": "r1", "target": {"type": "clinic"}, "promotion_scope": "general"}])
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


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_current_offers_come_from_completions_after_price_leaves_history(http_env, transport):
    client, db, use, _ = http_env
    target = {"type": "service", "id": "classic"}
    fake = use(FakeProvider(raw(price("classic", "service", brand_id="implantium", volume=_volume()))))
    send(client, transport, request_id="price", q="Цена одного зуба Implantium?")
    fake.raw = raw(explanation("Приживление занимает несколько месяцев.", target=target,
                               brand_id="implantium", volume=_volume()))
    send(client, transport, request_id="duration", q="Сколько длится?")
    expected = fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs
    assert [r.offer_id for r in expected] == ["classic.one_tooth.implantium"]
    for i in range(4):
        fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_address"]})
        send(client, transport, request_id=f"address{i}", q="Где клиника?")
        assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs == expected
    fake.raw = raw({"kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes"})
    answer = send(client, transport, request_id="includes", q="А что входит?")
    context = fake.inputs[-1].context.ordinary
    assert all(p.parts[0].kind == "contact" for p in context.dialogue_pairs)
    assert context.d2_shown_price_offer_refs == expected
    assert "Implantium" in answer["answer"] and "Nobel" not in answer["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        assert "d2_shown_price_offer_refs" not in store.read(key).state.model_dump()
        assert completed_context(store, key).ordinary.d2_shown_price_offer_refs == expected
    count = len(fake.inputs)
    assert send(client, transport, request_id="includes", q="А что входит?") == answer
    assert len(fake.inputs) == count


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("next_kind", ["missing_policy", "content", "pending", "mixed"])
def test_old_offers_do_not_survive_changed_or_ambiguous_discussion(http_env, transport, next_kind):
    client, db, use, tmp = http_env
    if next_kind == "missing_policy":
        from tests.test_d2_policy_route_fixes import update_rules
        update_rules(tmp, lambda rules: rules["policies"].pop("no_dms"))
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send(client, transport, request_id="price", q="Цена имплантации?")
    if next_kind == "missing_policy":
        blocks = [price("caries", "service", payment_scheme="dms",
                        payment_scheme_intent="requested_payment")]
    elif next_kind == "content":
        blocks = [explanation("О винирах.", target={"type": "service", "id": "veneers"})]
    elif next_kind == "pending":
        blocks = [clarify("content")]
    else:
        blocks = [price("classic", "service"),
                  {"kind": "price_detail", "request_id": "r2", "target": {"type": "service", "id": "all_on_4"},
                   "price_detail_aspect": "includes"}]
    fake.raw = raw(*blocks)
    answer = send(client, transport, request_id="change", q="Другой вопрос об услуге")
    if next_kind == "missing_policy":
        assert "недостаточно информации" in answer["answer"]
        assert answer["ui"]["projected_commercial_ids"]["price_offer_ids"] == []
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        context = completed_context(store, key).ordinary
        assert context.d2_shown_price_offer_refs == ()
        if next_kind == "missing_policy":
            assert context.discussion_scope.service_id == "caries"
    fake.raw = raw(explanation("Продолжение."))
    send(client, transport, request_id="next", q="А подробнее?")
    assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs == ()


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_doctors_published_names_and_order_are_available_to_followup(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "doctors", "request_id": "r1",
        "target": {"type": "service", "id": "classic"}})))
    first = send(client, transport, request_id="doctors", q="Кто проводит имплантацию?")
    fake.raw = raw(explanation("Можно подробнее обсудить опыт врача."))
    send(client, transport, request_id="second", q="Расскажите о втором из перечисленных")
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert pair.parts[0].kind == "doctors"
    assert pair.assistant_text == first["answer"]
    names = ["Кузнецов", "Орлов", "Волков"]
    assert all(name in pair.assistant_text for name in names)
    assert [pair.assistant_text.index(n) for n in names] == sorted(pair.assistant_text.index(n) for n in names)


@pytest.mark.parametrize("defect", ["foreign", "duplicate", "revision", "owner", "scope"])
def test_derived_current_refs_reject_invalid_latest_receipt(http_env, defect):
    from types import SimpleNamespace
    from core.d2_completion_context import _current_offers
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send(client, request_id="price", q="Цена имплантации?")
    fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_address"]})
    send(client, request_id="contact", q="Адрес?")
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        context = completed_context(store, key)
        record = store.read(key)
        latest = store.read_latest_completion(key)
    refs = latest.context.ordinary.d2_shown_price_offer_refs
    assert refs
    if defect in {"foreign", "duplicate", "scope"}:
        bad = (refs[0].model_copy(update={"source_client_id": "foreign"}),) if defect == "foreign" else (
            (refs[0], refs[0]) if defect == "duplicate" else (refs[0].model_copy(update={"service_id": "all_on_4"}),))
        ordinary = latest.context.ordinary.model_copy(update={"d2_shown_price_offer_refs": bad})
        latest = latest.model_copy(update={"context": latest.context.model_copy(update={"ordinary": ordinary})})
    elif defect == "revision":
        latest = latest.model_copy(update={"committed_revision": context.source_revision - 1})
    else:
        latest = latest.model_copy(update={"context": latest.context.model_copy(update={
            "session_key": SessionKey(client_id="foreign", sid=key.sid)})})
    with pytest.raises(ValueError):
        _current_offers(context, SimpleNamespace(state=record.state),
            SimpleNamespace(read_latest_completion=lambda _key: latest), context.ordinary.discussion_scope)


@pytest.mark.parametrize("update", [{"scope": "clinic"}, {"service_id": None},
    {"discussion_scope": None}, {"status": "deferred"},
    {"content_ref": "doctor.md"}, {"content_publication": "model_prose"}])
def test_doctors_result_requires_exact_service_provenance(update):
    from contracts.response_plan import D2ResolvedRequestPart
    from pydantic import ValidationError
    payload = {"request_id": "r1", "kind": "doctors", "status": "answered",
        "scope": "service", "service_id": "classic", "discussion_scope": {
            "target": {"type": "service", "id": "classic"}}}
    with pytest.raises(ValidationError):
        D2ResolvedRequestPart.model_validate({**payload, **update})


def test_missing_detail_rows_are_not_current_offer_authority():
    from types import SimpleNamespace as N
    from core.d2_completion_context import _published_offers
    valid = N(source_client_id="demo", offer_id="valid", service_id="classic", missing=False)
    missing = N(source_client_id="demo", offer_id="gap", service_id="classic", missing=True)
    result = N(d2_price_block=None, d2_price_detail_blocks=(N(rows=(valid, missing)),))
    assert [r.offer_id for r in _published_offers(result)] == ["valid"]


def test_absent_scope_never_authorizes_old_refs():
    from types import SimpleNamespace as N
    from core.d2_completion_context import _current_offers
    def forbidden(_key):
        raise AssertionError("no lookup without current scope")
    assert _current_offers(N(), N(state=N(clarify_pending=False)),
        N(read_latest_completion=forbidden), None) == ()
