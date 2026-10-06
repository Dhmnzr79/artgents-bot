"""Multiple frozen details and mixed booking through actual HTTP completions."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body


def raw(*blocks):
    return json.dumps({"outcome": "dialogue", "blocks": blocks}, ensure_ascii=False)


def detail(request_id, aspect, service="all_on_4", brand="nobel_biocare"):
    return dict(kind="price_detail", request_id=request_id,
                target={"type": "service", "id": service},
                brand_id=brand, price_detail_aspect=aspect)


def content(request_id="r1"):
    return dict(kind="content", request_id=request_id,
                target={"type": "service", "id": "classic"},
                content_text="Установку проводят с местной анестезией.")


def saved(db):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("with_price", [False, True])
def test_both_details_publish_exact_facts_and_project_all_aspects(http_env, transport, with_price):
    client, db, use, _ = http_env
    blocks = [detail("r2", "includes"), detail("r3", "stages")]
    if with_price:
        blocks.insert(0, dict(kind="price", request_id="r1",
            target={"type": "service", "id": "all_on_4"}, brand_id="nobel_biocare"))
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    args = dict(request_id="compound", q="Что входит в All-on-4 Nobel и как оплачивается?")
    body = _body(send(client, **args), transport)
    plan = saved(db).response.resolved
    assert [b.request_id for b in plan.d2_price_detail_blocks] == ["r2", "r3"]
    assert [b.aspect for b in plan.d2_price_detail_blocks] == ["includes", "stages"]
    assert plan.d2_result_status == "complete"
    assert all({r.offer_id for r in b.rows} == {"all_on_4.jaw.nobel"} for b in plan.d2_price_detail_blocks)
    for block in plan.d2_price_detail_blocks:
        for row in block.rows:
            for value in (*row.includes, *row.excludes, *row.stages):
                assert value in body["answer"]
    assert body["answer"].index("В стоимость входят") < body["answer"].index("Оплата по этапам")
    if with_price:
        assert plan.d2_price_block.rows[0].amount == 428000
        assert "428" in body["answer"]
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1
    fake.raw = raw({"kind": "off_topic", "request_id": "r1"})
    _body(send(client, request_id="follow", q="Следующий вопрос"), transport)
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert pair.detail_aspects == ("includes", "stages")
    assert [r.offer_id for r in pair.offers] == ["all_on_4.jaw.nobel"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_different_detail_services_preserve_refs_without_arbitrary_ui_or_focus(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(detail("r1", "includes"),
                               detail("r2", "stages", "classic", "implantium"))))
    send = post if transport == "json" else post_sse
    body = _body(send(client, request_id="mixed", q="Состав All-on-4 Nobel и оплата классической Implantium"), transport)
    assert len(saved(db).response.resolved.d2_price_detail_blocks) == 2
    assert body["ui"]["quick_replies"] == []
    fake.raw = raw({"kind": "off_topic", "request_id": "r1"})
    _body(send(client, request_id="next", q="Продолжение"), transport)
    context = fake.inputs[-1].context.ordinary
    assert context.discussion_scope is None
    assert {r.offer_id for r in context.dialogue_pairs[-1].offers} == {
        "all_on_4.jaw.nobel", "classic.one_tooth.implantium"}


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_one_unavailable_detail_keeps_other_and_explanation(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(detail("r1", "includes"),
        dict(kind="price_detail", request_id="r2", price_detail_aspect="stages"), content("r3"))))
    send = post if transport == "json" else post_sse
    body = _body(send(client, request_id="gap", q="Что входит и этапы другого варианта?"), transport)
    plan = saved(db).response.resolved
    assert plan.d2_result_status == "degraded"
    assert len(plan.d2_price_detail_blocks) == 1
    assert {p.request_id: p.status for p in plan.d2_request_parts} == {
        "r1": "answered", "r2": "unavailable", "r3": "answered"}
    assert "Уточните, для какой услуги" in body["answer"]
    assert content()["content_text"] in body["answer"]
    assert "В стоимость входят" in body["answer"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("booking_first", [False, True])
def test_answer_precedes_name_prompt_and_existing_intake_owns_next_turn(http_env, transport, booking_first):
    client, db, use, _ = http_env
    booking = dict(kind="booking", request_id="r2", age_group="adult")
    blocks = [booking, content()] if booking_first else [content(), booking]
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    args = dict(request_id="info-book", q="Расскажите об анестезии и запишите меня")
    body = _body(send(client, **args), transport)
    assert body["answer"].index(content()["content_text"]) < body["answer"].index("Как к вам обращаться")
    assert [p.request_id for p in saved(db).response.resolved.d2_request_parts] == ["r1", "r2"]
    assert body["ui"]["buttons"] == body["ui"]["quick_replies"] == []
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1
    name = _body(send(client, request_id="name", q="Денис"), transport)
    assert "телефон" in name["answer"].casefold()
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fields", [{"age_group": "child"}, {"age_group": "adult", "context": "past_history"}])
def test_booking_block_or_unclear_keeps_information_and_does_not_collect_name(http_env, transport, fields):
    client, _, use, _ = http_env
    use(FakeProvider(raw(content(), dict(kind="booking", request_id="r2", **fields))))
    send = post if transport == "json" else post_sse
    body = _body(send(client, request_id="not-booked", q="Расскажите и запишите"), transport)
    assert content()["content_text"] in body["answer"]
    assert "Как к вам обращаться" not in body["answer"]
    assert "детск" in body["answer"].casefold() if fields["age_group"] == "child" else "Уточните" in body["answer"]
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)


def test_materialization_failure_does_not_start_booking(http_env):
    client, _, use, _ = http_env
    bad = detail("r1", "stages")
    bad["price_detail_offer_id"] = "foreign-offer"
    use(FakeProvider(raw(bad, dict(kind="booking", request_id="r2", age_group="adult"))))
    response = post(client, request_id="fail-before-lead", q="Детали и запись")
    assert response.status_code == 400
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_additions_precede_booking_prompt(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(
        dict(kind="price", request_id="r1", target={"type": "service", "id": "classic"},
             brand_id="implantium"),
        dict(kind="booking", request_id="r2", age_group="adult"))))
    send = post if transport == "json" else post_sse
    args = dict(request_id="price-book", q="Сколько стоит классическая имплантация Implantium и запишите меня")
    body = _body(send(client, **args), transport)
    plan = saved(db).response.resolved
    assert plan.promo_blocks
    assert plan.d2_price_booster_block is not None
    assert plan.d2_also_list_block is not None
    name_pos = body["answer"].index("Как к вам обращаться")
    for block in plan.promo_blocks:
        assert body["answer"].index(block.display_text) < name_pos
    assert body["answer"].index("Удобный способ оплаты") < name_pos
    assert body["answer"].index("Перед лечением доступна диагностика") < name_pos
    assert body["answer"].endswith(plan.d2_exact_text_blocks[-1].display_text)
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1


def test_commit_failure_restores_lead_after_information_was_built(http_env, monkeypatch):
    client, _, use, _ = http_env
    use(FakeProvider(raw(content(), dict(kind="booking", request_id="r2", age_group="adult"))))
    def fail(*args, **kwargs):
        raise ValueError("d2_test_commit_failure")
    monkeypatch.setattr(D2DialogueStore, "complete", fail)
    assert post(client, request_id="commit-fail", q="Расскажите и запишите").status_code == 400
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity("cp6a") == (False, False)


def test_legacy_receipt_is_rejected_without_rewriting_database(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(detail("r1", "includes"))))
    args = dict(request_id="old-receipt", q="Состав All-on-4 Nobel")
    assert post(client, **args).status_code == 200
    import sqlite3
    with sqlite3.connect(db) as con:
        row = con.execute("SELECT payload FROM d2_turn_request WHERE request_id=?", (args["request_id"],)).fetchone()
        payload = json.loads(row[0])
        resolved = payload["response"]["resolved"]
        resolved["d2_price_detail_block"] = resolved.pop("d2_price_detail_blocks")[0]
        legacy = json.dumps(payload, ensure_ascii=False)
        con.execute("UPDATE d2_turn_request SET payload=? WHERE request_id=?", (legacy, args["request_id"]))
        state_before = con.execute("SELECT payload FROM d2_dialogue").fetchone()[0]
    assert post(client, **args).status_code == 400
    assert len(fake.inputs) == 1
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT payload FROM d2_turn_request WHERE request_id=?", (args["request_id"],)).fetchone()[0] == legacy
        assert con.execute("SELECT payload FROM d2_dialogue").fetchone()[0] == state_before
