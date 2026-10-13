"""Ordinary card conversation has no detail command; clicks stay exact."""
import json
import pytest
from pydantic import TypeAdapter, ValidationError
from contracts.d2_dialogue_result import D2DialogueResult, ClarifiedOperation
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from tests.d2_ci_http import FakeProvider, http_env, raw, send, explanation, completed_context
from tests.test_d2_price_cards import cards
from tests.test_d2_sim2_dialogues import forbidden


def price(service="classic", **kwargs):
    return dict(kind="price", request_id="r1", target={"type": "service", "id": service}, **kwargs)


def completed(db):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))


def test_detail_is_not_a_model_or_pending_operation():
    schema = json.dumps(D2DialogueResult.model_json_schema())
    assert "price_detail" not in schema
    with pytest.raises(ValidationError):
        D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [
            dict(kind="price_detail", request_id="r1", price_detail_aspect="includes")]})
    with pytest.raises(ValidationError):
        TypeAdapter(ClarifiedOperation).validate_python(dict(kind="price_detail", request_id="r1",
            price_detail_aspect="includes", clarification={"missing": "service", "choices": ["classic", "sinus_lift"]}))


@pytest.mark.parametrize("offer_id", ["generic_fixed", "option_a_from"])
def test_verified_detail_allows_generic_and_default_active_options(offer_id):
    from contracts.d2_dialogue_result import DetailOperation
    from contracts.response_plan import D2PriceDetailUiAction
    from core.response_plan_materialization import _d2_price_detail_offer_ids
    from tests.test_d2_independent_request_parts import _sources_ab
    sources = _sources_ab()
    action = D2PriceDetailUiAction(source_client_id="demo", reply_id="price_detail:includes",
        aspect="includes", service_id="service_one", offer_ids=(offer_id,))
    operation = DetailOperation(kind="price_detail", request_id="r1", price_detail_aspect="includes")
    assert _d2_price_detail_offer_ids(operation, sources=sources, selected_action=action) == (offer_id,)


def test_verified_detail_rejects_disabled_option():
    from contracts.d2_dialogue_result import DetailOperation
    from contracts.response_plan import D2PriceDetailUiAction
    from contracts.response_plan_materialization import MaterializationOwnershipError
    from core.response_plan_materialization import _d2_price_detail_offer_ids
    from tests.test_d2_independent_request_parts import _sources_ab
    sources = _sources_ab()
    payload = sources.model_dump()
    service = payload["material_authority"]["bundle"]["services"]["service_one"]
    offer = next(o for o in payload["material_authority"]["bundle"]["offers"] if o["offer_id"] == "option_a_from")
    for option in service["options"]:
        if option["option_id"] == offer["option_id"]:
            option["active"] = False
    sources = type(sources).model_validate(payload)
    action = D2PriceDetailUiAction(source_client_id="demo", reply_id="price_detail:includes",
        aspect="includes", service_id="service_one", offer_ids=("option_a_from",))
    operation = DetailOperation(kind="price_detail", request_id="r1", price_detail_aspect="includes")
    with pytest.raises(MaterializationOwnershipError):
        _d2_price_detail_offer_ids(operation, sources=sources, selected_action=action)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_card_followups_and_new_price_use_one_ordinary_model_answer(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price(brand_id="nobel_biocare", volume={"extent": "one_tooth"}))))
    first = send(client, transport, request_id="price", q="Сколько стоит Nobel на один зуб?")
    row = cards(first)[0]["price"]["rows"][0]
    assert row["offer_id"] == "classic.one_tooth.nobel"
    questions = ["Это всё включено?", "А гарантия?", "А больно?", "Где вы?"]
    for index, question in enumerate(questions):
        text = f"Самостоятельный ответ по базе номер {index}."
        fake.raw = raw(explanation(text))
        body = send(client, transport, request_id=f"q{index}", q=question)
        assert text in body["answer"]
        assert cards(body) == []
        assert completed(db).response.resolved.d2_price_detail_blocks == ()
        if index == 0:
            pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
            assert [r.offer_id for r in pair.offers] == [row["offer_id"]]
            assert row["price_display_text"] in pair.assistant_text
            for text in (*row["includes"], *row["excludes"], *row["stages"]):
                assert text in pair.assistant_text
            # No ordinary instruction/schema asks for the deleted operation.
            systems = "\n".join(m["content"] for m in build_d2_d1r_messages(fake.inputs[-1]) if m["role"] == "system")
            assert "price_detail" not in systems
    fake.raw = raw(price("professional_whitening"))
    body = send(client, transport, request_id="newprice", q="Сколько стоит отбеливание?")
    assert cards(body)[0]["price"]["rows"][0]["service_id"] == "professional_whitening"
    assert len(fake.inputs) == 6


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_tab_history_uses_selected_frozen_card_not_catalog_or_all_choices(http_env, transport):
    client, db, use, tmp = http_env
    fake = use(FakeProvider(raw(price("sinus_lift", option_id="open"))))
    first = send(client, transport, request_id="first")
    fake.generate = forbidden
    selected = send(client, transport, request_id="select", q="", ref="price_select:sinus_lift.one_site.closed", ui_revision=first["revision"])
    row = cards(selected)[0]["price"]["rows"][0]
    assert row["offer_id"] == "sinus_lift.one_site.closed"
    assert len(fake.inputs) == 1
    # History must read the receipt even if the authored package later changes.
    path = tmp / "clients/demo/target_response/pricebook/services/sinus_lift.one_site.closed.json"
    original = path.read_bytes()
    data = json.loads(original)
    data["package"]["includes"] = ["NEW_UNPUBLISHED_PACKAGE"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with D2DialogueStore(db) as store:
        context = completed_context(store, SessionKey(client_id="demo", sid="cp6a"))
    frozen = context.ordinary.dialogue_pairs[-1].assistant_text
    assert "NEW_UNPUBLISHED_PACKAGE" not in frozen
    for text in (*row["includes"], *row["excludes"], *row["stages"]):
        assert text in frozen
    # Tenant fingerprint protection intentionally rejects a changed database
    # during an HTTP conversation. Restore it before testing the next turn.
    path.write_bytes(original)
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = raw(explanation("Объяснение выбранной карточки."))
    send(client, transport, request_id="follow", q="Это всё включено?")
    pair = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert [r.offer_id for r in pair.offers] == [row["offer_id"]]
    assert "NEW_UNPUBLISHED_PACKAGE" not in pair.assistant_text
    for text in (*row["includes"], *row["excludes"], *row["stages"]):
        assert text in pair.assistant_text


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("aspect", ["includes", "stages"])
def test_verified_detail_button_and_replay_remain_exact_without_provider(http_env, transport, aspect):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price(brand_id="nobel_biocare", volume={"extent": "one_tooth"}))))
    first = send(client, transport, request_id="price")
    ref = f"price_detail:{aspect}"
    assert ref in {q["reply_id"] for q in first["ui"]["quick_replies"]}
    fake.generate = forbidden
    args = dict(request_id="click", q="", ref=ref, ui_revision=first["revision"])
    body = send(client, transport, **args)
    block = completed(db).response.resolved.d2_price_detail_blocks[0]
    assert block.aspect == aspect
    assert [r.offer_id for r in block.rows] == ["classic.one_tooth.nobel"]
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_removed_command_cannot_execute_or_hide_independent_prose(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Обычное объяснение по базе."),
        dict(kind="price_detail", request_id="r2", target={"type": "service", "id": "classic"}, price_detail_aspect="includes"))))
    body = send(client, transport, request_id="mixed", q="Что входит и где вы?")
    assert "Обычное объяснение по базе." in body["answer"]
    plan = completed(db).response.resolved
    assert plan.d2_price_detail_blocks == ()
    assert not cards(body)
    assert plan.d2_result_status == "degraded"
    assert plan.d2_request_parts[1].status == "unavailable"
