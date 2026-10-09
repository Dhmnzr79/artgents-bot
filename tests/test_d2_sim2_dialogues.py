"""Combined SIM-1/2 through actual transports with offline raw model output."""
from core.d2_completion_context import discussion_scope
import json
from datetime import datetime, timedelta, timezone

from tests.d2_ci_http import completed_context

import pytest

from contracts.response_plan import SessionKey
from contracts.d2_session_context import D2SessionActivity
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_document_click_task_http import _body


@pytest.fixture(autouse=True)
def show_internal_failures(monkeypatch):
    import core.d2_http_adapter as adapter
    original = adapter.run_d2_dialogue_turn
    def traced(**kwargs):
        try:
            return original(**kwargs)
        except Exception:
            import traceback
            traceback.print_exc()
            raise
    monkeypatch.setattr(adapter, "run_d2_dialogue_turn", traced)


def raw(*blocks, outcome="dialogue"):
    return json.dumps({"outcome": outcome, "blocks": blocks}, ensure_ascii=False)


def explanation(text="Связный ответ о лечении.", **extra):
    return {"kind": "content", "request_id": "r1", "content_text": text, **extra}


def price(target="implantation", target_kind="topic", **extra):
    return {"kind": "price", "request_id": "r1", "target": {"type": target_kind, "id": target}, **extra}


def clarify(kind="price"):
    op = {"kind": kind, "request_id": "r1"}
    if kind == "content":
        op["pending_question"] = "Как проходит выбранная процедура?"
    return {**op, "clarification": {"missing": "service", "choices": ["classic", "all_on_4"]}}


def forbidden(*_args, **_kwargs):
    raise AssertionError("known price must not call provider")


def doctors(service="classic", request_id="r1"):
    return {"kind": "doctors", "request_id": request_id, "target": {"type": "service", "id": service}}


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_doctors_catalog_replay_and_next_turn_focus(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("professional_whitening", "service"))))
    send = post if transport == "json" else post_sse
    _body(send(client, q="Сколько стоит отбеливание?"), transport)
    fake.raw = raw(doctors())
    args = dict(request_id="doctors", q="Кто проводит классическую имплантацию?")
    answer = _body(send(client, **args), transport)
    for name in ("Кузнецов", "Орлов", "Волков"):
        assert name in answer["answer"]
    for name in ("Фёдорова", "Морозова", "Григорьев"):
        assert name not in answer["answer"]
    assert len([b for b in answer["ui"]["buttons"] if b["action_kind"] == "cta"]) == 1
    assert _body(send(client, **args), transport) == answer
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).state
        assert discussion_scope(store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved).service_id == "classic"
        assert "situation_state" not in state.model_dump()
        assert state.clarify_task is None
    fake.raw = raw(explanation("Можно обсудить врача на консультации."))
    _body(send(client, request_id="next", q="А как записаться к нему?"), transport)
    assert fake.inputs[-1].context.ordinary.discussion_scope.service_id == "classic"


@pytest.mark.parametrize("other_service,expected_scope", [("classic", "service"), ("professional_whitening", "mixed")])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("scoped_prose", [False, True])
def test_doctors_preserves_independent_price_contact_and_prose(http_env, other_service, expected_scope, reverse, scoped_prose):
    client, db, use, _ = http_env
    blocks = [doctors(), price(other_service, "service", request_id="r2"),
              {"kind": "contact", "request_id": "r3", "contact_fields": ["contact_phone"]},
              explanation("Независимое объяснение из базы.", request_id="r4",
                          **({"target": {"type": "service", "id": "classic"}} if scoped_prose else {}))]
    if not scoped_prose:
        expected_scope = "mixed"
    if reverse:
        blocks.reverse()
    use(FakeProvider(raw(*blocks)))
    response = post(client, q="Кто проводит имплантацию? И цена, телефон, как проходит лечение?")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert "Орлов" in body["answer"] and "Независимое объяснение" in body["answer"]
    with D2DialogueStore(db) as store:
        record = store.read(SessionKey(client_id="demo", sid="cp6a"))
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        assert resolved.response_scope == expected_scope
        assert [p.request_id for p in resolved.d2_request_parts] == [b["request_id"] for b in blocks]
        assert all(row.service_id == other_service for row in resolved.d2_price_block.rows)
        assert resolved.d2_contact_blocks[0].display_text in body["answer"]
        assert len([b for b in resolved.ui_plan.buttons if b.action_kind == "cta"]) == 1
        assert any(b.action_kind == "contact" for b in resolved.ui_plan.buttons)
        assert discussion_scope(resolved) is None if expected_scope == "mixed" else discussion_scope(resolved).service_id == "classic"


@pytest.mark.parametrize("service", ["foreign-service", "braces"])
def test_doctors_invalid_service_does_not_publish_or_commit(http_env, service):
    client, db, use, _ = http_env
    use(FakeProvider(raw(doctors(service))))
    response = post(client, q="Кто проводит лечение?")
    assert response.status_code == 400
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="cp6a")) is None


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("information_first", [False, True])
def test_multiple_clarifications_answer_clear_part_keep_only_first_task(http_env, transport, information_first):
    client, db, use, _ = http_env
    cost = clarify()
    info = clarify("content")
    info.update(request_id="r2", pending_question="Как улучшить внешний вид улыбки?")
    info["clarification"]["choices"] = ["veneers", "professional_whitening"]
    blocks = [info, cost] if information_first else [cost, info]
    contact = {"kind": "contact", "request_id": "r3", "contact_fields": ["contact_address"]}
    blocks.insert(0 if information_first else 2, contact)
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, q="Вопрос о восстановлении, улыбке и адресе в указанном порядке."), transport)
    first_task, later = (info, cost) if information_first else (cost, info)
    assert {q["reply_id"] for q in first["ui"]["quick_replies"]} == {"service:" + id for id in first_task["clarification"]["choices"]}
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        completed = store.read_latest_completion(key).response.resolved
        assert completed.d2_contact_blocks[0].display_text in first["answer"]
        parts = {p.request_id: p for p in completed.d2_request_parts}
        assert parts[later["request_id"]].status == "deferred"
        assert completed.d2_result_status == "degraded"
        assert store.read(key).state.clarify_task.request_id == first_task["request_id"]
        notice = completed.d2_part_deferred_blocks[0].display_text
        assert notice in first["answer"]
    assert _body(send(client, q="Вопрос о восстановлении, улыбке и адресе в указанном порядке."), transport) == first
    assert len(fake.inputs) == 1
    hidden = later["clarification"]["choices"][0]
    failed = send(client, request_id="hidden", q="", ref="service:" + hidden, ui_revision=first["revision"])
    if transport == "json":
        assert failed.status_code == 400
    else:
        events = dict(sse_events(failed))
        assert events["error"]["error"] == "d2_invalid_turn" and "ui" not in events
    assert len(fake.inputs) == 1
    if information_first:
        fake.raw = json.dumps({"explanations": [{"request_id": "r2", "content_text": "Пояснение выбранных виниров."}]})
    else:
        fake.generate = forbidden
    chosen = first_task["clarification"]["choices"][0]
    args = dict(request_id="click", q="", ref="service:" + chosen, ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert "Пояснение выбранных виниров." in clicked["answer"] if information_first else "76 200" in clicked["answer"].replace("\u00a0", " ")
    assert _body(send(client, **args), transport) == clicked
    with D2DialogueStore(db) as store:
        completed = store.read_latest_completion(key).response.resolved
        assert {p.request_id for p in completed.d2_request_parts} == {first_task["request_id"]}
        assert store.read(key).state.clarify_task is None


@pytest.mark.parametrize("authored_first", [False, True])
def test_authored_availability_keeps_clear_answer_without_invented_task_menu(http_env, authored_first):
    client, db, use, _ = http_env
    explicit = clarify()
    authored = explanation("Как исправить прикус брекетами?", request_id="r2", target={"type": "service", "id": "braces"})
    blocks = [authored, explicit] if authored_first else [explicit, authored]
    fake = use(FakeProvider(raw(*blocks)))
    first = post(client, q="Брекеты и восстановление зуба в указанном порядке").get_json()
    assert "Брекеты мы не устанавливаем" in first["answer"]
    replies = {q["reply_id"] for q in first["ui"]["quick_replies"]}
    assert replies == {"service:classic", "service:all_on_4"}
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        completed = store.read_latest_completion(key).response.resolved
        assert next(p for p in completed.d2_request_parts if p.request_id == "r2").status == "answered"
        assert store.read(key).state.clarify_task.request_id == "r1"
    fake.generate = forbidden
    clicked = post(client, request_id="click", q="", ref=sorted(replies)[0], ui_revision=first["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    with D2DialogueStore(db) as store:
        assert store.read(key).state.clarify_task is None


def test_clear_price_is_answered_while_information_clarification_owns_ui(http_env):
    client, db, use, _ = http_env
    use(FakeProvider(raw(clarify("content"), price("classic", "service", request_id="r2"))))
    answer = post(client, q="Уточняемый вопрос о процедуре и точная цена имплантации.")
    assert answer.status_code == 200, answer.get_json()
    assert "76 200" in answer.get_json()["answer"].replace("\u00a0", " ")
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        assert next(p for p in result.d2_request_parts if p.request_id == "r2").status == "answered"


def test_first_price_deferral_cannot_publish_price_or_precede_active_clarification(http_env):
    from contracts.response_plan import ResolvedResponsePlan
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    assert post(client, sid="price-evidence", q="Цена классической имплантации?").status_code == 200
    with D2DialogueStore(db) as store:
        price_block = store.read_latest_completion(SessionKey(client_id="demo", sid="price-evidence")).response.resolved.d2_price_block
    later = clarify()
    later["request_id"] = "r2"
    fake.raw = raw(clarify("content"), later)
    assert post(client, q="Информационный и ценовой вопросы требуют уточнения.").status_code == 200
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
    invalid = result.model_dump()
    invalid["d2_request_parts"] = tuple(reversed(invalid["d2_request_parts"]))
    with pytest.raises(ValueError, match="d2_request_part_price_linkage_invalid"):
        ResolvedResponsePlan.model_validate(invalid)
    invalid = result.model_dump()
    invalid["d2_price_block"] = price_block.model_dump()
    offer_ids = tuple(row.offer_id for row in price_block.rows)
    invalid["finalized_commercial_ids"]["price_offer_ids"] = offer_ids
    invalid["session_delta"]["shown_price_offer_ids"] = offer_ids
    with pytest.raises(ValueError, match="d2_request_part_price_linkage_invalid"):
        ResolvedResponsePlan.model_validate(invalid)


def test_hidden_foreign_clarification_choices_are_still_rejected(http_env):
    client, _, use, _ = http_env
    later = clarify("content")
    later.update(request_id="r2")
    later["clarification"]["choices"] = ["veneers", "foreign"]
    use(FakeProvider(raw(clarify(), later, {"kind": "contact", "request_id": "r3", "contact_fields": ["contact_address"]})))
    assert post(client, q="Несколько вопросов.").status_code == 400


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("lead_phase", ["none", "active", "submitted"])
def test_old_schema_session_fails_without_reset_or_lead_loss(http_env, transport, lead_phase):
    from session import capture_lead_session_row, mem_get, session_client_scope
    active_lead = lead_phase != "none"
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "booking", "request_id": "r1",
        "age_group": "adult"})
        if active_lead else raw(explanation())))
    sid = "old-" + lead_phase
    assert post(client, sid=sid, request_id="seed", q="Хочу записаться" if active_lead else "Расскажите о клинике").status_code == 200
    if active_lead:
        assert post(client, sid=sid, request_id="name", q="Анна").status_code == 200
    if lead_phase == "submitted":
        submitted = post(client, sid=sid, request_id="phone", q="+7 999 123 45 67")
        assert submitted.status_code == 200
        assert submitted.get_json()["lead_effect"]["status"] == "demo_stub"
    with D2DialogueStore(db) as store:
        row = store._connection.execute("SELECT payload FROM d2_dialogue WHERE client_id=? AND sid=?", ("demo", sid)).fetchone()[0]
        old = json.loads(row)
        old["state"]["schema_version"] = 3
        legacy_payload = json.dumps(old, ensure_ascii=False)
        with store._connection:
            store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?", (legacy_payload, "demo", sid))
        requests_before = store._connection.execute("SELECT request_id,status,payload FROM d2_turn_request WHERE sid=? ORDER BY rowid", (sid,)).fetchall()
    with session_client_scope("demo"):
        lead_before = capture_lead_session_row(sid)
        if lead_phase == "active":
            assert json.loads(lead_before[0])["profile"]["name"] == "Анна"
            assert json.loads(lead_before[0])["lead_intent"] == "collecting_phone"
    fake.generate = forbidden
    send = post if transport == "json" else post_sse
    failed = send(client, sid=sid, request_id="old-next", q="А что дальше?")
    if transport == "json":
        assert failed.status_code == 400 and failed.get_json() == {"error": "d2_invalid_turn"}
    else:
        events = dict(sse_events(failed))
        assert events["error"]["error"] == "d2_invalid_turn"
        assert "ui" not in events
    assert len(fake.inputs) == 1
    if lead_phase == "submitted":
        replay = _body(send(client, sid=sid, request_id="phone", q="+7 999 123 45 67"), transport)
        assert replay == submitted.get_json()
        assert replay["lead_effect"]["status"] == "demo_stub"
    with session_client_scope("demo"):
        assert capture_lead_session_row(sid) == lead_before
    with D2DialogueStore(db) as store:
        assert store._connection.execute("SELECT payload FROM d2_dialogue WHERE sid=?", (sid,)).fetchone()[0] == legacy_payload
        assert store._connection.execute("SELECT request_id,status,payload FROM d2_turn_request WHERE sid=? ORDER BY rowid", (sid,)).fetchall() == requests_before
    # An explicitly different sid is an independent new conversation; no auto reset.
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = raw(explanation())
    assert post(client, sid=sid + "-new", request_id="new", q="Расскажите о клинике").status_code == 200
    with session_client_scope("demo"):
        assert capture_lead_session_row(sid) == lead_before
        fresh = mem_get(sid + "-new")
        assert not fresh["profile"].get("name")
        assert not fresh["profile"].get("phone")


@pytest.mark.parametrize("expired", [False, True])
def test_unbound_detail_asks_once_instead_of_transport_error(http_env, expired):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    if expired:
        assert post(client, q="Цена имплантации?").status_code == 200
        key = SessionKey(client_id="demo", sid="cp6a")
        with D2DialogueStore(db) as store:
            old = store.read(key).model_copy(update={"activity": D2SessionActivity(
                session_key=key, last_user_turn_at=datetime.now(timezone.utc) - timedelta(hours=1))})
            with store._connection:
                store._connection.execute("UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?",
                    (old.model_dump_json(), "demo", "cp6a"))
    fake.raw = raw({"kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes"})
    before = len(fake.inputs)
    answer = post(client, request_id="detail", q="Что входит?")
    assert answer.status_code == 200, answer.get_json()
    assert "Уточните, для какой услуги" in answer.get_json()["answer"]
    assert "Implantium" not in answer.get_json()["answer"]
    assert len(fake.inputs) == before + 1
    if expired:
        assert fake.inputs[-1].context.freshness == "expired"
        assert fake.inputs[-1].context.ordinary.discussion_scope is None


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_lead_interruption_preserves_slot_privacy_and_replay(http_env, transport):
    from lead_interrupt import LEAD_CANCEL_REF, LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
    from session import mem_get, session_client_scope
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "booking", "request_id": "r1",
        "age_group": "adult"})))
    send = post if transport == "json" else post_sse
    def call(**args):
        response = send(client, **args)
        assert response.status_code == 200, response.get_data(as_text=True)
        return _body(response, transport)
    call(request_id="book", q="Хочу записаться")
    call(request_id="name", q="Анна")
    pending = call(request_id="question", q="Меня зовут Анна, мой номер +7 999 123-45-67. Сколько стоит имплантация?")
    assert len(fake.inputs) == 1
    fake.raw = raw(price("classic", "service"))
    args = dict(request_id="answer", q="", ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    answer = call(**args)
    assert "₽" in answer["answer"]
    assert {q["reply_id"] for q in answer["ui"]["quick_replies"]} == {LEAD_RESUME_REF, LEAD_CANCEL_REF}
    assert answer["ui"]["buttons"] == [] and answer["lead_effect"]["status"] == "not_requested"
    assert "Анна" not in fake.inputs[-1].user_message and "999" not in fake.inputs[-1].user_message
    assert call(**args) == answer and len(fake.inputs) == 2
    with session_client_scope("demo"):
        state = mem_get("cp6a")
        assert state["lead_intent"] == "paused" and state["lead_resume_step"] == "collecting_phone"
        assert state["profile"]["name"] == "Анна"
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).model_dump_json()
        assert "Анна" not in state and "999" not in state
    resumed = call(request_id="resume", q="", ref=LEAD_RESUME_REF, ui_revision=answer["revision"])
    assert "телефон" in resumed["answer"].lower() and len(fake.inputs) == 2


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("reference", [
    {"target": {"type": "service", "id": "braces"}},
    {"brand_id": "ossstem", "target": {"type": "topic", "id": "implantation"}},
])
def test_authored_reference_preserves_independent_address(http_env, reverse, reference):
    client, _, use, _ = http_env
    blocks = [{"kind": "price", "request_id": "r1", **reference},
              {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}]
    if reverse:
        blocks.reverse()
    use(FakeProvider(raw(*blocks)))
    answer = post(client, q="Вопрос об услуге или бренде. И адрес?")
    assert answer.status_code == 200, answer.get_json()
    body = answer.get_json()["answer"]
    assert "элайнер" in body.lower() if "brand_id" not in reference else "Implantium" in body
    assert "адрес" in body.lower() or "ул." in body.lower() or "улиц" in body.lower()


def test_service_click_preserves_explicit_report_from_original_question(http_env):
    client, db, use, _ = http_env
    pending = clarify()
    pending.update(
        age_group="adult",
        volume={"extent": "few_teeth", "tooth_count": 3,
                   "jaw": "lower", },
    )
    fake = use(FakeProvider(raw(pending)))
    first = post(client, q="У меня нет трёх зубов снизу. Сколько восстановить?").get_json()
    fake.generate = forbidden
    clicked = post(client, request_id="click", q="", ref="service:classic", ui_revision=first["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    with D2DialogueStore(db) as store:
        situation = discussion_scope(store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved).volume
        assert situation.extent == "few_teeth" and situation.tooth_count == 3
        assert situation.jaw == "lower"


def test_deferred_second_service_prevents_false_single_focus(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"), price("veneers", "service", request_id="r2"))))
    answer = post(client, q="Сколько стоит классическая имплантация и виниры?")
    assert answer.status_code == 200, answer.get_json()
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(key).response.resolved
        assert result.response_scope == "mixed"
        assert result.d2_request_parts[1].status == "deferred"
        assert result.d2_request_parts[1].service_id == "veneers"
        assert store.read(key).state.discussion_request_id is None
    fake.raw = raw(clarify())
    assert post(client, request_id="next", q="А сколько?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope is None


@pytest.mark.parametrize("target", [{"type": "service", "id": "veneers"}, {"type": "topic", "id": "prosthetics"}])
def test_switch_discards_previous_service_price_details(http_env, target):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    assert post(client, q="Цена имплантации?").status_code == 200
    fake.raw = raw(explanation("Расскажу о протезировании.", target=target))
    assert post(client, request_id="switch", q="Расскажите о протезировании.").status_code == 200
    with D2DialogueStore(db) as store:
        assert not completed_context(store, SessionKey(client_id="demo", sid="cp6a")).ordinary.d2_shown_price_offer_refs
    fake.raw = raw(explanation("Пояснение.", request_id="r1"),
        {"kind": "price_detail", "request_id": "r2", "price_detail_aspect": "includes"})
    answer = post(client, request_id="next", q="А что входит?")
    assert answer.status_code == 200, answer.get_json()
    assert "Implantium" not in answer.get_json()["answer"]
    assert "Уточните, для какой услуги" in answer.get_json()["answer"]


@pytest.mark.parametrize("commercial", [
    {"target": {"type": "clinic"}, "promotion_scope": "general"},
    {"fact_ids": ["installment_12"], "target": {"type": "service", "id": "all_on_4"}},
])
def test_commercial_part_keeps_prose_and_published_fact_history(http_env, commercial):
    client, db, use, _ = http_env
    use(FakeProvider(raw(explanation("Независимое объяснение лечения.", target={"type": "service", "id": "all_on_4"}),
        {"kind": "commercial_fact", "request_id": "r2", **commercial})))
    answer = post(client, q="Расскажите о лечении и финансовых условиях.")
    assert answer.status_code == 200, answer.get_json()
    assert "Независимое объяснение лечения." in answer.get_json()["answer"]
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        exact = result.d2_exact_text_blocks[0]
        assert result.promo_blocks == ()
        if "fact_ids" in commercial:
            assert result.finalized_commercial_ids.requested_fact_ids == ("installment_12",)
            assert exact.requested_fact_ids == ("installment_12",)
        else:
            assert result.finalized_commercial_ids.promo_fact_ids == exact.promo_fact_ids
            assert exact.promo_fact_ids
        assert exact.display_text in answer.get_json()["answer"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_clarify_keeps_independent_answer_then_executes_saved_task(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(clarify(), explanation("Уход за дёснами: рекомендации из базы.", request_id="r2"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, sid="sim2", request_id="first", q="Сколько стоит восстановить зуб? И как ухаживать за дёснами?"), transport)
    assert "Уход за дёснами" in first["answer"]
    assert {q["reply_id"] for q in first["ui"]["quick_replies"]} == {"service:classic", "service:all_on_4"}
    with D2DialogueStore(db) as store:
        task = store.read(SessionKey(client_id="demo", sid="sim2")).state.clarify_task
        assert task.kind == "price"
        assert not hasattr(task, "request_kinds")
    fake.generate = forbidden
    args = dict(sid="sim2", request_id="click", q="", ref="service:classic", ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert "76 200" in clicked["answer"].replace("\u00a0", " ")
    assert "Уход за дёснами" not in clicked["answer"]
    assert _body(send(client, **args), transport) == clicked
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="sim2")
        completion = store.read_latest_completion(key)
        assert all(r.service_id == "classic" for r in completion.response.resolved.d2_price_block.rows)
        assert store.read(key).state.clarify_task is None
        assert "situation_state" not in store.read(key).state.model_dump()


@pytest.mark.parametrize("extent", ["one_tooth", "full_arch", "unknown"])
def test_volume_no_provider_and_followup_context(http_env, extent):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price())))
    first = post(client, sid="volume", q="Сколько стоит имплантация?").get_json()
    original = fake.generate
    fake.generate = forbidden
    clicked = post(client, sid="volume", request_id="click", q="", ref=f"volume:implantation:{extent}", ui_revision=first["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    if extent == "unknown":
        assert clicked.get_json()["answer"] == "Ничего страшного. На консультации врач поможет разобраться с объёмом лечения."
    else:
        assert "₽" in clicked.get_json()["answer"]
    fake.generate = original
    fake.raw = raw(explanation("Сроки зависят от этапов заживления."))
    assert post(client, sid="volume", request_id="next", q="А сколько займёт?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.extent == extent


@pytest.mark.parametrize("reverse", [False, True])
def test_two_prices_first_is_primary_even_when_pending(http_env, reverse):
    client, db, use, _ = http_env
    blocks = [clarify(), price("veneers", "service", request_id="r2")]
    if reverse:
        blocks.reverse()
    use(FakeProvider(raw(*blocks)))
    response = post(client, q="Две независимые цены в указанном порядке")
    assert response.status_code == 200, response.get_json()
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        parts = saved.response.resolved.d2_request_parts
        assert [p.request_id for p in parts] == [b["request_id"] for b in blocks]
        assert parts[1].status == "deferred"


@pytest.mark.parametrize("reverse", [False, True])
def test_contact_and_prose_remain_independent(http_env, reverse):
    client, _, use, _ = http_env
    blocks = [explanation("Как проходит процедура: связный ответ."),
              {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}]
    if reverse:
        blocks.reverse()
    use(FakeProvider(raw(*blocks)))
    response = post(client, q="Как проходит и где вы находитесь?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert "связный ответ" in answer and len(answer) > len(blocks[0].get("content_text", ""))


def test_reported_information_then_correction_without_price(http_env):
    client, db, use, _ = http_env
    def answer(jaw, commitment):
        return raw(explanation("Порядок восстановления обсуждается с врачом.",
            target={"type": "topic", "id": "implantation"},
            volume={"extent": "full_arch", "jaw": jaw,
                       }))
    fake = use(FakeProvider(answer("lower", "reported")))
    assert post(client, q="У меня нет зубов снизу. Как проходит восстановление?").status_code == 200
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        before = discussion_scope(store.read_latest_completion(key).response.resolved).volume
        assert before.jaw == "lower"
    fake.raw = answer("upper", "correction")
    assert post(client, request_id="correct", q="Ошибся, сверху.").status_code == 200
    with D2DialogueStore(db) as store:
        after = discussion_scope(store.read_latest_completion(key).response.resolved).volume
        assert after.jaw == "upper" and before.jaw == "lower"


def test_admin_does_not_publish_ordinary_prose(http_env):
    client, _, use, _ = http_env
    use(FakeProvider(raw(outcome="admin")))
    response = post(client, q="Нужна индивидуальная медицинская рекомендация.")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["answer"]


@pytest.mark.parametrize("field", ["contact_phone", "contact_address", "contact_hours", "contact_parking"])
def test_exact_contact_only(http_env, field):
    client, db, use, _ = http_env
    use(FakeProvider(raw({"kind": "contact", "request_id": "r1", "contact_fields": [field]})))
    answer = post(client, q="Контактный вопрос")
    assert answer.status_code == 200, answer.get_json()
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert len(saved.response.resolved.d2_contact_blocks) == 1
        assert saved.response.resolved.d2_contact_blocks[0].display_text in answer.get_json()["answer"]


@pytest.mark.parametrize("first", [
    {"kind": "clinic_policy", "request_id": "r1", "policy_ids": ["no_oms"]},
    {"kind": "price", "request_id": "r1", "target": {"type": "unresolved"}},
    {"kind": "off_topic", "request_id": "r1"},
])
@pytest.mark.parametrize("reverse", [False, True])
def test_code_owned_parts_do_not_hide_address(http_env, first, reverse):
    client, _, use, _ = http_env
    blocks = [first, {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}]
    if reverse:
        blocks.reverse()
    fake = use(FakeProvider(raw(*blocks)))
    response = post(client, q="Вопрос и адрес")
    assert response.status_code == 200, response.get_json()
    assert len(fake.inputs) == 1
    fake.raw = raw(blocks[0] if blocks[0]["kind"] == "contact" else blocks[1])
    address = post(client, sid="address", q="Где вы?").get_json()["answer"]
    assert address in response.get_json()["answer"]


@pytest.mark.parametrize("reverse", [False, True])
def test_information_clarification_is_not_converted_to_price(http_env, reverse):
    client, db, use, _ = http_env
    blocks = [clarify("content"), explanation("Независимый ответ об уходе.", request_id="r2")]
    if reverse:
        blocks.reverse()
    fake = use(FakeProvider(raw(*blocks)))
    first = post(client, q="Как проходит процедура?")
    assert first.status_code == 200, first.get_json()
    assert "Независимый ответ об уходе." in first.get_json()["answer"]
    with D2DialogueStore(db) as store:
        pending = store.read(SessionKey(client_id="demo", sid="cp6a")).state.clarify_task
        assert pending.pending_question == blocks[1 if reverse else 0]["pending_question"]
        assert not hasattr(pending, "content_text")
    fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Этапы выбранной процедуры."}]})
    clicked = post(client, request_id="click", q="", ref="service:classic", ui_revision=first.get_json()["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert "Этапы выбранной процедуры" in clicked.get_json()["answer"]
    assert fake.inputs[-1].known_task.blocks[0].target.id == "classic"
    known = fake.inputs[-1].known_task.blocks[0]
    assert known.request_id == pending.request_id
    assert known.pending_question == pending.pending_question
    assert not hasattr(known, "clarification") and not hasattr(known, "content_text")
    assert len(fake.inputs) == 2
    assert "Независимый ответ об уходе." not in clicked.get_json()["answer"]
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.d2_price_block is None
        assert store.read(SessionKey(client_id="demo", sid="cp6a")).state.clarify_task is None
    fake.raw = raw(explanation("Ответ на следующий вопрос."))
    assert post(client, request_id="next", q="А уход?").status_code == 200
    assert fake.inputs[-1].context.ordinary.clarify_task is None


def test_price_details_known_action_no_provider(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client, q="Сколько стоит классическая имплантация?").get_json()
    ref = next(q["reply_id"] for q in first["ui"]["quick_replies"] if "includes" in q["reply_id"])
    fake.generate = forbidden
    clicked = post(client, request_id="details", q="", ref=ref, ui_revision=first["revision"])
    assert clicked.status_code == 200, clicked.get_json()
    assert "входит" in clicked.get_json()["answer"].lower()


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_detail_service_clarification_executes_same_aspect_without_provider(http_env, transport):
    client, db, use, _ = http_env
    pending = {
        "kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes",
        "clarification": {"missing": "service", "choices": ["classic", "all_on_4"]},
    }
    fake = use(FakeProvider(raw(pending)))
    send = post if transport == "json" else post_sse
    first = _body(send(client, q="Что входит в выбранную процедуру?"), transport)
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        task = store.read(key).state.clarify_task
        assert task.kind == "price_detail" and task.price_detail_aspect == "includes"
        assert task.request_id == "r1" and not hasattr(task, "operation")
    fake.generate = forbidden
    args = dict(request_id="detail-click", q="", ref="service:classic", ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert _body(send(client, **args), transport) == clicked
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(key).response.resolved
        detail = result.d2_price_detail_blocks[0]
        assert detail.aspect == "includes"
        assert all(row.service_id == "classic" for row in detail.rows)
        assert result.d2_price_block is None
        assert store.read(key).state.clarify_task is None


def test_service_authenticity_before_provider(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(clarify())))
    first = post(client, q="Сколько стоит восстановление?").get_json()
    fake.generate = forbidden
    for request_id, args in [
        ("forged", {"ref": "service:veneers", "ui_revision": first["revision"]}),
        ("stale", {"ref": "service:classic", "ui_revision": first["revision"] + 1}),
        ("foreign", {"ref": "service:classic", "ui_revision": first["revision"], "client_id": "nikadent"}),
    ]:
        assert post(client, request_id=request_id, q="", **args).status_code == 400


def test_booking_stays_with_existing_lead_owner(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "booking", "request_id": "r1",
        "age_group": "adult"})))
    response = post(client, q="Хочу записаться.")
    assert response.status_code == 200, response.get_json()
    assert "Как к вам обращаться?" in response.get_json()["answer"]
    fake.generate = forbidden
    assert post(client, request_id="name", q="Денис").status_code == 200


def test_child_price_cannot_bypass_clinic_policy(http_env):
    client, db, use, _ = http_env
    use(FakeProvider(raw(price(age_group="child"))))
    response = post(client, q="Сколько стоит ребёнку?")
    assert response.status_code == 200, response.get_json()
    assert "дет" in response.get_json()["answer"].lower()
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block is None


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("extra,policy_id", [
    ({"age_group": "child", "context": "current_care"}, "no_pediatric_dentistry"),
    ({"payment_scheme": "oms", "payment_scheme_intent": "requested_payment"}, "no_oms"),
    ({"payment_scheme": "dms", "payment_scheme_intent": "requested_payment"}, "no_dms"),
    ({"brand_id": "unlisted_test_brand"}, None),
])
def test_null_price_target_retains_existing_policy_and_reference_paths(http_env, transport, extra, policy_id):
    import yaml
    client, db, use, tmp = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": None, **extra})))
    send = post if transport == "json" else post_sse
    args = dict(request_id="null-target", q="Вопрос об условиях клиники")
    body = _body(send(client, **args), transport)
    if policy_id is not None:
        rules = yaml.safe_load((tmp / "clients/demo/clinic_policies.yaml").read_text(encoding="utf-8"))
        assert rules["policies"][policy_id]["answer"].strip() in body["answer"]
    else:
        assert "недостаточно информации" in body["answer"].lower()
    if policy_id == "no_pediatric_dentistry":
        assert not any(button["action_kind"] == "cta" for button in body["ui"]["buttons"])
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.d2_price_block is None
        assert saved.response.resolved.d2_request_parts[0].kind == "price_reference"
        assert saved.lead_effect.status == "not_requested"
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1


def test_http_does_not_reconstruct_legacy_envelope(http_env, monkeypatch):
    from contracts.one_call_envelope import OneCallEnvelope
    from contracts.request_understanding import RequestUnderstanding
    import core.response_plan_materialization as materializer
    client, _, use, _ = http_env
    monkeypatch.setattr(OneCallEnvelope, "model_validate", forbidden)
    monkeypatch.setattr(RequestUnderstanding, "model_validate", forbidden)
    assert not hasattr(materializer, "resolve_d2_envelope_response")
    use(FakeProvider(raw(price(), explanation("Независимое объяснение.", request_id="r2"))))
    assert post(client, q="Цена и пояснение").status_code == 200


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_prompt_example_dialogue_and_continuation(http_env, transport, index):
    from tests.test_d2_sim2_contract import prompt_example
    client, db, use, _ = http_env
    fake = use(FakeProvider(json.dumps(prompt_example(index))))
    send = post if transport == "json" else post_sse
    question = ("Цены по имплантации", "Цена процедуры, услуга пока не определена", "Как проходит процедура, услуга пока не определена")[index]
    first = _body(send(client, q=question), transport)
    assert first["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        state = store.read(key).state
        if index == 0:
            assert state.clarify_task is None
            decision = store.read_latest_completion(key).response.resolved.d2_price_scope_decision
            assert decision.topic_id == "implantation"
        else:
            assert state.clarify_task.kind == ("price" if index == 1 else "content")
    if index == 0:
        assert "Какой объём вас интересует: один зуб, вся челюсть или пока не знаете?" in first["answer"]
    if index == 0:
        assert {b["reply_id"] for b in first["ui"]["quick_replies"]} == {
            "volume:implantation:one_tooth", "volume:implantation:full_arch", "volume:implantation:unknown"}
        fake.generate = forbidden
        args = dict(request_id="continue", q="", ref="volume:implantation:one_tooth", ui_revision=first["revision"])
    elif index == 2:
        fake.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Объяснение выбранной процедуры по материалам клиники."}]})
        args = dict(request_id="continue", q="", ref="service:classic", ui_revision=first["revision"])
    else:
        assert {b["reply_id"] for b in first["ui"]["quick_replies"]} == {"service:classic", "service:all_on_4"}
        fake.generate = forbidden
        args = dict(request_id="continue", q="", ref="service:classic", ui_revision=first["revision"])
    continued = _body(send(client, **args), transport)
    assert ("Объяснение выбранной процедуры" in continued["answer"] if index == 2
            else "76 200" in continued["answer"].replace("\u00a0", " "))
    count = len(fake.inputs)
    assert _body(send(client, **args), transport) == continued
    assert len(fake.inputs) == count
    if index in (0, 1):
        assert count == 1
    if index == 2:
        assert fake.inputs[-1].known_task.blocks[0].kind == "content"
        assert fake.inputs[-1].known_task.blocks[0].service_id == "classic"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_malformed_pending_operation_fails_without_retry_or_commit(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Общий ответ о процедуре."))))
    send = post if transport == "json" else post_sse
    _body(send(client, q="Расскажите о процедуре"), transport)
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        before = store.read(key)
    fake.raw = raw({"kind": "clarification", "request_id": "r1", "missing": "extent",
        "operation": {"type": "service", "id": "classic"}, "choices": []})
    failed = send(client, request_id="malformed", q="Сколько стоит имплантация?")
    if transport == "json":
        assert failed.status_code == 400
        assert failed.get_json()["error"] == "d2_invalid_turn"
    else:
        events = dict(sse_events(failed))
        assert events["error"]["error"] == "d2_invalid_turn" and "ui" not in events
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(key) == before


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("after_fear", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_identified_price_has_one_execution_path(http_env, transport, after_fear, mixed):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Врач проверяет обезболивание перед процедурой."))))
    send = post if transport == "json" else post_sse
    if after_fear:
        _body(send(client, request_id="fear", q="Я боюсь боли"), transport)
    blocks = [price()]
    if mixed:
        blocks.append(explanation("Независимое объяснение о восстановлении.", request_id="r2"))
    fake.raw = raw(*blocks)
    question = "Сколько стоит имплантация?" + (" И как проходит восстановление?" if mixed else "")
    first = _body(send(client, request_id="price", q=question), transport)
    assert fake.inputs[-1].user_message == question
    assert fake.inputs[-1].context.ordinary.clarify_task is None
    if after_fear:
        assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].patient_text == "Я боюсь боли"
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        completed = store.read_latest_completion(key)
        resolved = completed.response.resolved
        assert store.read(key).state.clarify_task is None
        assert resolved.d2_price_scope_decision.topic_id == "implantation"
        assert resolved.d2_price_scope_decision.service_id is None
        assert resolved.d2_price_scope_decision.reason == "overview"
        # D2-115 delegated demo overview: distinct methods, same prices/source.
        assert tuple(r.offer_id for r in resolved.d2_price_block.rows) == (
            "classic.one_tooth.implantium", "all_on_4.jaw.implantium", "all_on_6.jaw.implantium")
    assert "76 200" in first["answer"].replace("\u00a0", " ")
    if mixed:
        assert "Независимое объяснение о восстановлении." in first["answer"]
    assert {b["reply_id"] for b in first["ui"]["quick_replies"]} == {
        "volume:implantation:one_tooth", "volume:implantation:full_arch", "volume:implantation:unknown"}
    fake.generate = forbidden
    args = dict(request_id="click", q="", ref="volume:implantation:one_tooth", ui_revision=first["revision"])
    clicked = _body(send(client, **args), transport)
    assert "76 200" in clicked["answer"].replace("\u00a0", " ")
    assert _body(send(client, **args), transport) == clicked
    assert len(fake.inputs) == (2 if after_fear else 1)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_retired_price_extent_clarification_is_not_repaired(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Предыдущий ответ."))))
    send = post if transport == "json" else post_sse
    _body(send(client, q="Я боюсь боли"), transport)
    key = SessionKey(client_id="demo", sid="cp6a")
    with D2DialogueStore(db) as store:
        before = store.read(key)
    fake.raw = raw({"kind": "clarification", "request_id": "r1", "missing": "extent",
        "operation": price(), "choices": []}, explanation("Отдельная часть", request_id="r2"))
    response = send(client, request_id="retired", q="Сколько стоит имплантация?")
    if transport == "json":
        assert response.status_code == 400
    else:
        assert dict(sse_events(response))["error"]["error"] == "d2_invalid_turn"
    assert len(fake.inputs) == 2
    with D2DialogueStore(db) as store:
        assert store.read(key) == before


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_owner_finishes_missing_offer_without_model_clarification(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("veneers", "service", brand_id="implantium"),
        explanation("Независимый ответ о процедуре.", request_id="r2"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, q="Стоимость выбранной услуги и описание"), transport)
    assert "Независимый ответ о процедуре." in first["answer"]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="cp6a")
        resolved = store.read_latest_completion(key).response.resolved
        assert resolved.d2_price_block is None
        assert resolved.d2_part_failure_blocks[0].display_text in first["answer"]
        assert store.read(key).state.clarify_task is None
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("kind", ["content", "price_detail"])
def test_nonprice_parameter_clarification_is_preserved(http_env, kind):
    client, db, use, _ = http_env
    op = {"kind": "content", "request_id": "r1", "pending_question": "Как проходит выбранная процедура?"} if kind == "content" else {
        "kind": "price_detail", "request_id": "r1", "price_detail_aspect": "includes"}
    fake = use(FakeProvider(raw({**op, "clarification": {"missing": "stage", "choices": []}})))
    first = post(client, q="Информационный вопрос без необходимого этапа").get_json()
    assert "этапе лечения" in first["answer"]
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="cp6a")).state.clarify_task.kind == kind
    fake.raw = raw(explanation("Ответ с учётом уточнённого этапа.")) if kind == "content" else raw({
        **op, "target": {"type": "service", "id": "classic"}})
    response = post(client, request_id="continue", q="Уточняю этап процедуры")
    assert response.status_code == 200 and response.get_json()["answer"]
