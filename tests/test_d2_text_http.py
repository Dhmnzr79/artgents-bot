"""Text-tail response through the real HTTP and SSE runtime, offline only."""
import json
from types import SimpleNamespace
import pytest
from tests.test_d2_text_reply import action
from tests.d2_ci_http import FakeProvider, http_env, send, click
from tests.test_d2_price_cards import cards
from tests.test_d2_card_conversation import completed
from tests.test_d2_sim2_dialogues import forbidden


def reply(text=None, *actions, sources=None):
    if not actions and sources is None:
        return text or ""
    metadata={"actions":list(actions)}
    if sources is not None:
        metadata["sources"]=list(sources)
    return (text or "")+"\n<D2_META>\n"+json.dumps(metadata,ensure_ascii=False)+"\n</D2_META>"


def price(service="classic", **args):
    return action("show_price", target={"type":"service", "id":service}, **args)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_plain_text_price_then_followups_and_new_subject(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply("Да, используем Nobel.")))
    first = send(client, transport, request_id="brand", q="Вы ставите Nobel?")
    assert "используем Nobel" in first["answer"]
    fake.raw = reply(None, price(brand_id="nobel_biocare", volume={"extent":"one_tooth"}))
    body = send(client, transport, request_id="price", q="Сколько стоит на один зуб?")
    row = cards(body)[0]["price"]["rows"][0]
    assert row["offer_id"] == "classic.one_tooth.nobel"
    assert "используем Nobel" in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text
    for i, question in enumerate(["Это всё включено?", "А гарантия?", "А больно?", "Где вы?"]):
        fake.raw = reply(f"Ответ по базе {i}.")
        body = send(client, transport, request_id=f"text{i}", q=question)
        assert f"Ответ по базе {i}." in body["answer"]
        assert cards(body) == []
        if i == 0:
            history = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
            assert [o.offer_id for o in history.offers] == [row["offer_id"]]
            for text in (*row["includes"], *row["excludes"], *row["stages"]):
                assert text in history.assistant_text
    fake.raw = reply(None, price("professional_whitening"))
    body = send(client, transport, request_id="new", q="А отбеливание сколько?")
    assert cards(body)[0]["price"]["rows"][0]["service_id"] == "professional_whitening"
    assert len(fake.inputs) == 7


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("bad", [{"name":"show_price","arguments":"{"}, action("price_detail", price_detail_aspect="includes")])
def test_bad_action_preserves_text_and_history(http_env, transport, bad):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply("Гарантия описана в договоре.", bad)))
    body = send(client, transport, request_id="bad", q="А гарантия?")
    assert "Гарантия описана в договоре." in body["answer"]
    assert cards(body) == []
    assert completed(db).response.resolved.d2_result_status == "degraded"
    fake.raw = reply("Продолжение.")
    send(client, transport, request_id="next", q="Подробнее?")
    assert "Гарантия описана в договоре." in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_card_buttons_and_tab_no_model_then_text(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply(None, price("sinus_lift", option_id="open"))))
    body = send(client, transport, request_id="price", q="Цена открытого синус-лифтинга?")
    assert cards(body)[0]["price"]["rows"][0]["offer_id"] == "sinus_lift.one_site.open"
    fake.generate = forbidden
    body = click(client, body, "price_select:sinus_lift.one_site.closed", request_id="tab", transport=transport)
    assert cards(body)[0]["price"]["rows"][0]["offer_id"] == "sinus_lift.one_site.closed"
    assert len(fake.inputs) == 1
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = reply("Объяснение выбранной карточки.")
    send(client, transport, request_id="aftertab", q="Это всё включено?")
    assert fake.inputs[-1].context.ordinary.dialogue_pairs[-1].offers[0].offer_id == "sinus_lift.one_site.closed"


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("aspect", ["includes", "stages"])
def test_published_detail_button_no_model_and_replay(http_env, transport, aspect):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply(None, price(brand_id="nobel_biocare", volume={"extent":"one_tooth"}))))
    body = send(client, transport, request_id="price")
    ref = f"price_detail:{aspect}"
    assert ref in {q["reply_id"] for q in body["ui"]["quick_replies"]}
    fake.generate = forbidden
    args = dict(request_id="detail", q="", ref=ref, ui_revision=body["revision"])
    detail = send(client, transport, **args)
    block = completed(db).response.resolved.d2_price_detail_blocks[0]
    assert block.rows[0].offer_id == "classic.one_tooth.nobel"
    assert block.aspect == aspect
    assert send(client, transport, **args) == detail
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_source_click_plain_reply_and_following_history(http_env, transport):
    client, db, use, _ = http_env
    ref = "implantation__faq__pain.md"
    fake = use(FakeProvider(reply("Расскажу про страх боли.", sources=[{"content_ref":ref,"target":{"type":"topic", "id":"implantation"}}])))
    body = send(client, transport, request_id="pain", q="Боюсь боли.")
    links = [q["reply_id"] for q in body["ui"]["quick_replies"] if q["reply_id"].startswith(ref + "#")]
    assert links
    fake.raw = reply("Объяснение раздела про обезболивание.")
    body = click(client, body, links[0], request_id="follow", transport=transport)
    assert fake.inputs[-1].known_task is not None
    assert "Объяснение раздела" in body["answer"]
    fake.raw = reply("Да, Nobel есть.")
    send(client, transport, request_id="nobel", q="Вы ставите Nobel?")
    assert "Объяснение раздела" in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_handoff_suppresses_price_prose_and_booking(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(reply("SHOULD_NOT_APPEAR", price(), action("start_booking"), action("handoff"))))
    body = send(client, transport, request_id="handoff", q="Болит зуб, цена?")
    assert "SHOULD_NOT_APPEAR" not in body["answer"]
    assert cards(body) == []
    assert completed(db).lead_effect.status == "not_requested"


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("kind", ["show_price", "start_booking"])
def test_child_policy_guards_keep_action_path(http_env, transport, kind):
    client, db, use, _ = http_env
    use(FakeProvider(reply(None, action(kind, target={"type":"service", "id":"classic"}, age_group="child", context="current_care"))))
    body = send(client, transport, request_id="child", q="Запись или цена ребёнку?")
    assert cards(body) == []
    assert "дет" in body["answer"].lower() or "взросл" in body["answer"].lower()
    assert completed(db).lead_effect.status == "not_requested"


def test_actual_provider_never_requests_tools_or_wrapper_and_known_task_is_plain_text(http_env):
    from core.d2_live_provider import D2HttpProvider
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply("Ответ.")))
    send(client, request_id="capture")
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Plain answer", tool_calls=[]))])
    provider = D2HttpProvider(transport=transport)
    assert provider.generate(fake.inputs[0]) == "Plain answer"
    assert "response_format" not in calls[0]
    assert not {"tools","tool_choice","response_format"}.intersection(calls[0])
    assert "D2_RESULT_SCHEMA" not in calls[0]["messages"][0]["content"]
    from dataclasses import replace
    from contracts.d2_dialogue_result import D2ExplanationTask, AuthorizedExplanationOperation
    known = D2ExplanationTask(blocks=(AuthorizedExplanationOperation(kind="content", request_id="r1", pending_question="Explain"),))
    assert provider.generate(replace(fake.inputs[0], known_task=known)) == "Plain answer"
    assert "tools" not in calls[1] and "response_format" not in calls[1]
    assert len(calls) == 2



@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("shape", ["single", "same", "different", "invalid", "mixed_scope", "none"])
def test_source_slots_preserve_promo_followup_and_scope(http_env, transport, shape):
    from core.d2_completion_context import discussion_scope
    client, db, use, _ = http_env
    ref = "implantation__faq__pain.md"
    source = {"content_ref":ref,"target":{"type":"topic","id":"implantation"}}
    sources = {
        "single": (source,), "same": (source, source),
        "different": (source, {"content_ref":"clinic__info__warranty.md"}),
        "invalid": (source, "{"),
        "mixed_scope": (source, {"content_ref":ref}),
        "none": (),
    }[shape]
    fake = use(FakeProvider(reply("Единое объяснение.", sources=sources)))
    body = send(client, transport, request_id="source", q="Расскажите про боль при имплантации.")
    assert body["answer"].count("Единое объяснение.") == 1
    resolved = completed(db).response.resolved
    promos = resolved.finalized_commercial_ids.promo_fact_ids
    assert bool(promos) == (shape == "single")
    links = [q for q in body["ui"]["quick_replies"] if q["reply_id"].startswith(ref + "#")]
    assert bool(links) == (shape in {"single", "same", "mixed_scope"})
    scope = discussion_scope(resolved)
    assert (scope is not None and scope.topic_id == "implantation") == (shape in {"single", "same"})
    fake.raw = reply("Продолжение.")
    send(client, transport, request_id="next", q="Ещё вопрос.")
    context = fake.inputs[-1].context.ordinary
    assert context.dialogue_pairs[-1].assistant_text.count("Единое объяснение.") == 1
    if shape in {"different", "invalid", "mixed_scope"}:
        assert context.discussion_scope is None


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_text_price_order_and_exact_amount(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(reply("Сначала объяснение.", price(brand_id="nobel_biocare", volume={"extent":"one_tooth"}))))
    body = send(client, transport, request_id="mixed", q="Расскажите и сколько стоит?")
    assert body["answer"].startswith("Сначала объяснение.")
    assert cards(body)[0]["price"]["rows"][0]["offer_id"] == "classic.one_tooth.nobel"
    assert [p.kind for p in completed(db).response.resolved.d2_request_parts] == ["content", "price"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_rejected_first_price_does_not_select_second(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(reply("Ответ сохранён.", {"name":"show_price","arguments":"{"}, price("professional_whitening"))))
    body = send(client, transport, request_id="two", q="Две цены?")
    assert "Ответ сохранён." in body["answer"]
    assert not cards(body)
    parts = completed(db).response.resolved.d2_request_parts
    assert [p.status for p in parts] == ["answered", "unavailable", "deferred"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unknown_brand_no_card_and_text_survives(http_env, transport):
    client, db, use, _ = http_env
    use(FakeProvider(reply("Объяснение из базы.", price(brand_id="osstem", volume={"extent":"one_tooth"}))))
    body = send(client, transport, request_id="brand", q="Цена Osstem?")
    assert "Объяснение из базы." in body["answer"]
    assert not cards(body)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_booking_private_intake_stays_outside_model(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply(None, action("start_booking", age_group="adult"))))
    body = send(client, transport, request_id="booking", q="Хочу записаться.")
    assert len(fake.inputs) == 1
    fake.generate = forbidden
    body = send(client, transport, request_id="name", q="Анна")
    assert len(fake.inputs) == 1
    assert not cards(body)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_natural_clarification_is_only_text_and_history(http_env, transport):
    client, db, use, _ = http_env
    question = "О какой процедуре вы спрашиваете?"
    fake = use(FakeProvider(reply(question)))
    body = send(client, transport, request_id="clarify", q="Как проходит процедура?")
    assert question in body["answer"]
    assert not any(q["reply_id"].startswith("service:") for q in body["ui"]["quick_replies"])
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).state
    assert state.clarify_task is None
    assert not state.clarify_pending
    fake.raw = reply("Расскажу об имплантации по материалам клиники.")
    body = send(client, transport, request_id="answer", q="Про имплантацию.")
    assert question in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text
    assert "Расскажу об имплантации" in body["answer"]
    assert not cards(body)
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_clarification_preserves_brand_volume_and_click(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(reply(None, action("show_price",
        brand_id="nobel_biocare", volume={"extent":"one_tooth"},
        clarification={"missing":"service", "choices":["classic", "sinus_lift"]}))))
    body = send(client, transport, request_id="clarify", q="Сколько стоит Nobel на один зуб?")
    fake.generate = forbidden
    selected = click(client, body, "service:classic", request_id="select", transport=transport)
    row = cards(selected)[0]["price"]["rows"][0]
    assert row["offer_id"] == "classic.one_tooth.nobel"
    assert len(fake.inputs) == 1
    from tests.d2_ci_http import completed_context
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    with D2DialogueStore(db) as store:
        context = completed_context(store, SessionKey(client_id="demo", sid="cp6a"))
    assert [o.offer_id for o in context.ordinary.dialogue_pairs[-1].offers] == [row["offer_id"]]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_mixed_booking_keeps_text_and_private_name_outside_provider(http_env, transport):
    client, db, use, _ = http_env
    fake=use(FakeProvider(reply("Объяснение консультации.",action("start_booking",age_group="adult"))))
    body=send(client,transport,q="Расскажите и запишите.",request_id="book")
    assert "Объяснение консультации." in body["answer"]
    assert "имя" in body["answer"].lower() or "обращаться" in body["answer"].lower()
    fake.generate=forbidden
    send(client,transport,q="Анна",request_id="name")
    assert len(fake.inputs)==1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_stale_and_foreign_actions_cannot_bypass_provider_boundary(http_env, transport):
    from tests.test_d2_http_contract import post,post_sse,sse_events
    client,_,use,_=http_env
    fake=use(FakeProvider(reply(None,price(volume={"extent":"one_tooth"}))))
    original=send(client,transport,q="Цена импланта?",request_id="price")
    fake.generate=forbidden
    current=click(client,original,"price_select:classic.one_tooth.nobel",request_id="tab",transport=transport)
    request=post if transport=="json" else post_sse
    for name,args in [("stale",dict(ref="price_detail:includes",ui_revision=original["revision"])),
                      ("foreign",dict(client_id="nikadent",ref="price_select:classic.one_tooth.nobel",ui_revision=current["revision"]))]:
        rejected=request(client,q="",request_id=name,**args)
        if transport=="json": assert rejected.status_code==400
        else:
            events=dict(sse_events(rejected))
            assert events["error"]["error"]=="d2_invalid_turn" and "ui" not in events
    assert len(fake.inputs)==1
