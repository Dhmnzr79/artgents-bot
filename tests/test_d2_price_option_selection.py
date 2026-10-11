"""Named catalog variant opens its tab through the actual HTTP route."""
import json
import pytest
from contracts.d2_dialogue_result import PriceOperation
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation
from tests.test_d2_price_cards import cards
from tests.test_d2_sim2_dialogues import forbidden


def price(service, option=None):
    result = dict(kind="price", request_id="r1", target={"type": "service", "id": service})
    if option is not None:
        result["option_id"] = option
    return result


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service,option,offer,amount", [
    ("sinus_lift", None, "sinus_lift.one_site.closed", 42000),
    ("sinus_lift", "open", "sinus_lift.one_site.open", 68000),
    ("sinus_lift", "closed", "sinus_lift.one_site.closed", 42000),
    ("tooth_extraction", "complex", "tooth_extraction.complex", 8000),
    ("tooth_extraction", None, "tooth_extraction.default", 5000),
])
def test_named_variant_card_history_detail_and_replay(http_env, transport, service, option, offer, amount):
    client, db, use, tmp = http_env
    fake = use(FakeProvider(raw(price(service, option))))
    body = send(client, transport, request_id="first", q="Цена выбранного варианта?")
    card = cards(body)[0]
    row = card["price"]["rows"][0]
    assert row["offer_id"] == offer
    assert row["min_amount"] == amount
    authored = json.loads((tmp / f"clients/demo/target_response/pricebook/services/{offer}.json").read_text(encoding="utf-8"))
    assert row["includes"] == authored["package"].get("includes", [])
    assert row["excludes"] == authored["package"].get("excludes", [])
    assert len(card["choices"]) == 2
    with D2DialogueStore(db) as store:
        plan = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        assert plan.finalized_commercial_ids.price_offer_ids == (offer,)
        assert [o.offer_id for o in store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.trace.selected_offers] == [offer]
    fake.generate = forbidden
    assert send(client, transport, request_id="first", q="Цена выбранного варианта?") == body
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = raw(dict(kind="price_detail", request_id="r1", price_detail_aspect="includes"))
    send(client, transport, request_id="detail", q="Что входит?")
    assert [r.offer_id for r in fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs] == [offer]
    with D2DialogueStore(db) as store:
        plan = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved
        assert plan.d2_price_detail_blocks[0].rows[0].offer_id == offer


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_alternative_tab_click_is_still_server_owned(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("sinus_lift", "open"))))
    body = send(client, transport, request_id="first")
    fake.generate = forbidden
    args = dict(request_id="click", q="", ref="price_select:sinus_lift.one_site.closed", ui_revision=body["revision"])
    selected = send(client, transport, **args)
    assert cards(selected)[0]["price"]["rows"][0]["offer_id"] == "sinus_lift.one_site.closed"
    assert len(cards(selected)[0]["choices"]) == 2
    assert send(client, transport, **args) == selected
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("option", ["missing", "complex"])
def test_unknown_or_other_service_variant_never_shows_default(http_env, transport, option):
    client, _, use, _ = http_env
    use(FakeProvider(raw(price("sinus_lift", option), explanation("Самостоятельный ответ.", request_id="r2"))))
    body = send(client, transport)
    assert not cards(body)
    assert "Самостоятельный ответ." in body["answer"]
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]


@pytest.mark.parametrize("target", [None, {"type": "topic", "id": "implantation"}, {"type": "unresolved"}])
def test_variant_requires_concrete_service(target):
    with pytest.raises(ValueError):
        PriceOperation.model_validate({**price("sinus_lift", "open"), "target": target})


def test_model_catalog_contains_authored_option_names(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("sinus_lift", "open"))))
    send(client)
    catalog = json.loads(fake.inputs[0].model_view.active_service_catalog.canonical_json)
    service = next(s for s in catalog["services"] if s["service_id"] == "sinus_lift")
    assert service["options"] == [
        {"option_id": "closed", "name": "Закрытый синус-лифтинг"},
        {"option_id": "open", "name": "Открытый синус-лифтинг"},
    ]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_generic_after_explicit_variant_keeps_default_policy(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("sinus_lift", "open"))))
    send(client, transport, request_id="first")
    fake.raw = raw(price("sinus_lift"))
    body = send(client, transport, request_id="generic", q="Сколько стоит синус-лифтинг?")
    assert cards(body)[0]["price"]["rows"][0]["offer_id"] == "sinus_lift.one_site.closed"


@pytest.mark.parametrize("constraint", [{"brand_id": "nobel_biocare"}, {"volume": {"extent": "full_arch"}}])
def test_option_with_no_eligible_offer_does_not_substitute(http_env, constraint):
    client, _, use, _ = http_env
    use(FakeProvider(raw({**price("tooth_extraction", "complex"), **constraint})))
    body = send(client)
    assert not cards(body)


def test_inactive_variant_is_neither_exposed_nor_selected(http_env):
    client, _, use, tmp = http_env
    path = tmp / "clients/demo/target_response/service_catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    next(o for o in data["sinus_lift"]["options"] if o["option_id"] == "open")["active"] = False
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw(price("sinus_lift", "open"))))
    body = send(client)
    assert not cards(body)
    catalog = json.loads(fake.inputs[0].model_view.active_service_catalog.canonical_json)
    service = next(s for s in catalog["services"] if s["service_id"] == "sinus_lift")
    assert [o["option_id"] for o in service["options"]] == ["closed"]


@pytest.mark.parametrize("option", [1, [], ""])
def test_malformed_variant_is_not_dropped(option):
    with pytest.raises(ValueError):
        PriceOperation.model_validate(price("sinus_lift", option))


def test_variant_cannot_survive_service_clarification():
    with pytest.raises(ValueError):
        PriceOperation.model_validate({**price("sinus_lift", "open"),
            "clarification": {"missing": "service", "choices": ["sinus_lift", "tooth_extraction"]}})
