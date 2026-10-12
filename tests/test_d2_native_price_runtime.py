"""Native price selection, one frozen result, final prose, and actual HTTP history."""
import json
from types import SimpleNamespace as NS

import pytest

from core.d2_live_provider import D2HttpProvider, price_tool
from tests.d2_ci_http import http_env, send, click
from tests.test_d2_http_contract import post, post_sse, sse_events
from tests.test_d2_price_cards import cards
from tests.test_d2_card_conversation import completed


def message(text=None, *args):
    return NS(choices=[NS(message=NS(content=text, tool_calls=[NS(
        id=f"call_{i}", function=NS(name="show_price", arguments=json.dumps(arg)),
    ) for i, arg in enumerate(args)]), finish_reason="tool_calls" if args else "stop")])


def price(service="classic", **fields):
    return dict(target={"type": "service", "id": service}, **fields)


class Transport:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        assert self.replies, "unexpected extra provider call"
        response = self.replies.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_card_mixed_followup_tab_and_replay(http_env, transport, monkeypatch):
    client, db, use, _ = http_env
    wire = Transport(message("Используем три системы имплантов."),
        message("I will answer later", price(volume={"extent": "one_tooth"})),
        message('Обезболивание обсуждается с врачом.\n<D2_META>\n{"sources":[{"content_ref":"implantation__faq__pain.md"}]}\n</D2_META>'),
        message("Условия гарантии указаны в договоре."), message("Состав выбранной карточки."))
    use(D2HttpProvider(transport=wire))
    send(client, transport, request_id="brand", q="Какие системы используете?")
    import core.response_plan_materialization as material
    original = material._d2_price_block
    frozen_calls = []
    def freeze(**kwargs):
        frozen_calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(material, "_d2_price_block", freeze)
    body = send(client, transport, request_id="price", q="А сколько на один зуб и больно ли?")
    row = cards(body)[0]["price"]["rows"][0]
    assert row["offer_id"] == "classic.one_tooth.implantium"
    assert len(frozen_calls) == 1
    assert "Обезболивание обсуждается" in body["answer"]
    assert "I will" not in body["answer"]
    tool = json.loads(wire.calls[2]["messages"][-2]["content"])
    assert tool["price"]["rows"][0]["offer_id"] == row["offer_id"]
    assert wire.calls[2]["tool_choice"] == "none"
    assert wire.calls[2]["tools"] == wire.calls[1]["tools"]
    assert completed(db).response.resolved.information_blocks[0].content_ref == "implantation__faq__pain.md"
    assert send(client, transport, request_id="price", q="А сколько на один зуб и больно ли?") == body
    assert len(wire.calls) == 3
    follow = send(client, transport, request_id="warranty", q="А гарантия?")
    assert not cards(follow)
    history = wire.calls[3]["messages"][1]["content"]
    assert row["offer_id"] in history and "I will" not in history
    for text in (*row["includes"], *row["excludes"]):
        assert text in history
    # A published historical tab restores exact scope, with no model call.
    tab = click(client, body, "price_select:classic.one_tooth.nobel", request_id="tab", transport=transport)
    assert len(wire.calls) == 4
    detail = click(client, tab, "price_detail:includes", request_id="detail", transport=transport)
    assert "В стоимость" in detail["answer"]
    assert len(wire.calls) == 4
    send(client, transport, request_id="after", q="Это всё включено?")
    assert "classic.one_tooth.nobel" in wire.calls[4]["messages"][1]["content"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fields", [{"brand_id": "osstem"}, {"age_group": "child"}, {"payment_scheme": "oms", "payment_scheme_intent": "requested_payment"}])
def test_refusal_has_one_prose_owner_and_preserves_guards(http_env, transport, fields):
    client, db, use, _ = http_env
    wire = Transport(message(None, price(**fields)), message("Этот вариант недоступен. Обезболивание обсуждается с врачом."))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="refused", q="Цена и обезболивание?")
    assert not cards(body)
    assert body["answer"].count("Этот вариант недоступен") == 1
    result = completed(db).response.resolved
    assert not result.d2_exact_text_blocks
    assert any(p.kind == "price_reference" for p in result.d2_request_parts)
    ground = json.loads(wire.calls[1]["messages"][-2]["content"])
    assert ground["exact_text"] and ground["price"] is None
    if fields.get("age_group") or fields.get("payment_scheme"):
        assert not body["ui"]["buttons"]
        assert any(p.source_results for p in result.d2_request_parts)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_only_without_duplicate_introduction(http_env, transport):
    client, db, use, _ = http_env
    wire = Transport(message("Not published", {"target": {"type": "topic", "id": "implantation"}}), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="direction", q="Сколько стоит имплантация?")
    assert cards(body)
    assert not completed(db).response.resolved.information_blocks
    assert "Not published" not in body["answer"]
    assert "introduction_text" not in wire.calls[0]["messages"][0]["content"]
    assert len(wire.calls) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("response", [RuntimeError("provider_failed"), message(None),
    message('Новый запрос\n<D2_META>\n{"actions":[{"name":"show_price","arguments":{}}]}\n</D2_META>')])
def test_completion_failure_never_commits_partial_price(http_env, transport, response):
    client, db, use, _ = http_env
    wire = Transport(message("Предыдущий ответ."), message(None, price()), response)
    use(D2HttpProvider(transport=wire))
    send(client, transport, request_id="before", q="Расскажите")
    previous = completed(db)
    result = (post if transport == "json" else post_sse)(client, request_id="failed", q="Цена?")
    if transport == "json":
        assert result.status_code == (503 if isinstance(response, RuntimeError) or response.choices[0].message.content is None else 400)
    else:
        events = dict(sse_events(result))
        assert "error" in events and "ui" not in events
    assert completed(db) == previous
    assert len(wire.calls) == 3


@pytest.mark.parametrize("bad", [{"target": "classic"}, price(option_id=7), price(clarification=None)])
def test_broken_tool_args_not_repaired(http_env, bad):
    client, db, use, _ = http_env
    wire = Transport(message(None, bad))
    use(D2HttpProvider(transport=wire))
    assert post(client).status_code == 400
    assert len(wire.calls) == 1
    assert completed(db) is None


def test_invalid_optional_sources_preserve_final_prose(http_env):
    client, db, use, _ = http_env
    wire = Transport(message(None, price()), message('Объяснение.\n<D2_META>\n{"sources":[{"target":"broken"}]}\n</D2_META>'))
    use(D2HttpProvider(transport=wire))
    body = send(client, request_id="sources")
    assert cards(body) and "Объяснение." in body["answer"]
    assert completed(db).response.resolved.information_blocks[0].content_ref is None


def test_native_tool_schema_and_no_tail_price_path():
    from contracts.d2_dialogue_result import parse_d2_text_reply
    schema = price_tool()["function"]
    assert "strict" not in schema
    assert "kind" not in schema["parameters"]["properties"]
    assert "request_id" not in schema["parameters"]["properties"]
    raw = '<D2_META>\n{"actions":[{"name":"show_price","arguments":{"target":{"type":"service","id":"classic"}}}]}\n</D2_META>'
    with pytest.raises(ValueError):
        parse_d2_text_reply(raw, active_service_ids={"classic"})


@pytest.mark.parametrize("args,offer", [
    (price(brand_id="nobel_biocare", volume={"extent": "one_tooth"}), "classic.one_tooth.nobel"),
    (price("sinus_lift", option_id="open"), "sinus_lift.one_site.open"),
])
def test_native_parameters_select_exact_offer(http_env, args, offer):
    client, db, use, _ = http_env
    wire = Transport(message(None, args), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, request_id="exact")
    assert cards(body)[0]["price"]["rows"][0]["offer_id"] == offer
    assert len(wire.calls) == 2


def test_verified_document_click_keeps_one_text_call(http_env):
    client, db, use, _ = http_env
    wire = Transport(message('Обсудим страх боли.\n<D2_META>\n{"sources":[{"content_ref":"implantation__faq__pain.md"}]}\n</D2_META>'),
                     message("Ответ на выбранный вопрос."))
    use(D2HttpProvider(transport=wire))
    body = send(client, request_id="pain", q="Боюсь боли")
    ref = next(q["reply_id"] for q in body["ui"]["quick_replies"] if "implantation__faq__pain.md#" in q["reply_id"])
    result = click(client, body, ref, request_id="doc")
    assert "Ответ на выбранный вопрос." in result["answer"]
    assert len(wire.calls) == 2
    assert "KNOWN_TASK" in wire.calls[1]["messages"][1]["content"]
    assert "tools" not in wire.calls[1]


def test_multiple_prices_keep_existing_first_price_and_deferral(http_env):
    client, db, use, _ = http_env
    wire = Transport(message(None, price(), price("professional_whitening")), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, request_id="multiple")
    assert cards(body)[0]["price"]["rows"][0]["service_id"] == "classic"
    assert any(p.status == "deferred" for p in completed(db).response.resolved.d2_request_parts)
    assert len(wire.calls) == 2


def test_empty_refusal_completion_is_not_success(http_env):
    client, db, use, _ = http_env
    wire = Transport(message(None, price(brand_id="osstem")), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    assert post(client).status_code == 400
    assert completed(db) is None


@pytest.mark.parametrize("name,args", [("show_contacts", {"contact_fields": ["contact_address"]}),
    ("start_booking", {}), ("handoff", {})])
def test_non_price_actions_remain_available(http_env, name, args):
    client, db, use, _ = http_env
    raw = '<D2_META>\n' + json.dumps({"actions": [{"name": name, "arguments": args}]}) + '\n</D2_META>'
    wire = Transport(message(raw))
    use(D2HttpProvider(transport=wire))
    body = send(client)
    assert body["answer"] and not cards(body)
    assert len(wire.calls) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("name,args", [("show_contacts", {"contact_fields": ["contact_address"]}),
    ("start_booking", {}), ("handoff", {})])
def test_price_tool_preserves_nonprice_siblings(http_env, transport, name, args):
    client, db, use, _ = http_env
    metadata = '\n<D2_META>\n' + json.dumps({"actions": [{"name": name, "arguments": args}]}) + '\n</D2_META>'
    wire = Transport(message(metadata, price()), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="mixed-action")
    plan = completed(db).response.resolved
    if name == "handoff":
        assert not cards(body) and len(wire.calls) == 1
        assert plan.session_delta.terminal_state == "medical_terminal"
    else:
        assert cards(body) and len(wire.calls) == 2
        if name == "show_contacts":
            assert plan.d2_contact_blocks
            assert plan.d2_contact_blocks[0].display_text in body["answer"]
        else:
            assert any(p.kind == "lead" for p in plan.d2_request_parts)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_native_price_clarification_and_verified_click(http_env, transport):
    client, db, use, _ = http_env
    wire = Transport(message(None, dict(brand_id="nobel_biocare", volume={"extent": "one_tooth"},
        clarification={"missing": "service", "choices": ["classic", "sinus_lift"]})), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="clarify", q="Сколько это стоит?")
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).state
        assert state.clarify_pending and state.clarify_task.brand_id == "nobel_biocare"
    result = click(client, body, "service:classic", request_id="select", transport=transport)
    assert cards(result)[0]["price"]["rows"][0]["offer_id"] == "classic.one_tooth.nobel"
    assert len(wire.calls) == 2
    with D2DialogueStore(db) as store:
        assert not store.read(SessionKey(client_id="demo", sid="cp6a")).state.clarify_pending
