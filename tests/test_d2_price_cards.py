"""Real JSON/SSE price cards, authenticated selection and receipt-derived scope."""
import pytest
import json

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation, forbidden


def cards(body):
    return [part for part in body["ui"]["body_parts"] if part["kind"] == "price_card"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_selection_exact_offer_context_detail_and_replay(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, q="Цена классической имплантации?"), transport)
    card = cards(first)[0]
    assert [(row["offer_id"], row["amount"]) for row in card["price"]["rows"]] == [
        ("classic.one_tooth.implantium", 76200)]
    assert all(row["billing_unit"] == "tooth_package" for row in card["price"]["rows"])
    assert all("КТ" in " ".join(row["condition_texts"]) for row in card["price"]["rows"])
    expected_choices = ["price_select:classic.one_tooth.implantium",
                        "price_select:classic.one_tooth.impro", "price_select:classic.one_tooth.nobel"]
    assert [c["reply_id"] for c in card["choices"]] == expected_choices
    with D2DialogueStore(db) as store:
        initial = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert initial.response.resolved.finalized_commercial_ids.price_offer_ids == ("classic.one_tooth.implantium",)
        assert initial.response.resolved.d2_request_parts[0].discussion_scope.brand_id == "implantium"
    text_parts = " ".join(part["text"] for part in first["ui"]["body_parts"] if part["kind"] == "text")
    assert "76" not in text_parts and "85" not in text_parts
    fake.generate = forbidden
    args = dict(request_id="choose", q="", ref="price_select:classic.one_tooth.impro",
                ui_revision=first["revision"])
    selected = _body(send(client, **args), transport)
    assert [row["offer_id"] for row in cards(selected)[0]["price"]["rows"]] == ["classic.one_tooth.impro"]
    assert cards(selected)[0]["price"]["rows"][0]["amount"] == 85200
    assert [c["reply_id"] for c in cards(selected)[0]["choices"]] == expected_choices
    assert _body(send(client, **args), transport) == selected
    assert len(fake.inputs) == 1
    detail = _body(send(client, request_id="detail", q="", ref="price_detail:includes",
                        ui_revision=selected["revision"]), transport)
    assert "Implantium" not in detail["answer"] and "Nobel" not in detail["answer"]
    assert "Impro" in detail["answer"]
    with D2DialogueStore(db) as store:
        completed = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert completed.response.resolved.d2_price_detail_blocks[0].rows[0].offer_id == "classic.one_tooth.impro"
    fake.generate = FakeProvider.generate.__get__(fake)
    fake.raw = raw(explanation("Продолжаем обсуждать выбранный вариант."))
    _body(send(client, request_id="next", q="А сколько это длится?"), transport)
    ordinary = fake.inputs[-1].context.ordinary
    assert ordinary.discussion_scope.brand_id == "impro"
    assert [ref.offer_id for ref in ordinary.d2_shown_price_offer_refs] == ["classic.one_tooth.impro"]
    assert len(fake.inputs) == 2


@pytest.mark.parametrize("first_price", [True, False])
def test_compound_answer_keeps_order_without_duplicate_price(http_env, first_price):
    client, _, use, _ = http_env
    p = price("professional_whitening", "service", request_id="r1" if first_price else "r2")
    c = {"kind": "contact", "request_id": "r2" if first_price else "r1", "contact_fields": ["contact_address"]}
    use(FakeProvider(raw(*( [p, c] if first_price else [c, p] ))))
    response = post(client, q="Цена отбеливания и адрес?")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    parts = body["ui"]["body_parts"]
    assert cards(body)[0]["price"]["rows"][0]["mode"] == "from"
    assert cards(body)[0]["price"]["rows"][0]["min_amount"] == 18000
    kinds = [part["kind"] for part in parts]
    address_idx = next(i for i, part in enumerate(parts) if "Адрес" in part.get("text", ""))
    assert (kinds.index("price_card") < address_idx) == first_price
    assert "18" not in " ".join(part.get("text", "") for part in parts)


@pytest.mark.parametrize("ref", ["price_select:classic.one_tooth.foreign", "price_select:all_on_4.jaw.implantium"])
def test_unpublished_offer_is_rejected_before_provider(http_env, ref):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client).get_json()
    fake.generate = forbidden
    rejected = post(client, request_id="forged", q="", ref=ref, ui_revision=first["revision"])
    assert rejected.status_code == 400
    assert len(fake.inputs) == 1


def test_stale_selection_cannot_replace_new_topic(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client).get_json()
    fake.raw = raw(price("professional_whitening", "service"))
    post(client, request_id="second")
    fake.generate = forbidden
    rejected = post(client, request_id="stale", q="", ref="price_select:classic.one_tooth.impro",
                    ui_revision=first["revision"])
    assert rejected.status_code == 400 and len(fake.inputs) == 2


def test_overview_keeps_original_volume_choices(http_env):
    client, _, use, _ = http_env
    use(FakeProvider(raw(price())))
    first = post(client).get_json()
    assert not cards(first)
    assert [r["reply_id"] for r in first["ui"]["quick_replies"]] == [
        "volume:implantation:one_tooth", "volume:implantation:full_arch", "volume:implantation:unknown"]
    assert "76" in first["answer"]


def test_selection_binds_exact_offer_even_when_brand_has_two_offers(http_env):
    client, db, use, tmp = http_env
    catalog = tmp / "clients/demo/target_response/pricebook/services"
    variant = json.loads((catalog / "classic.one_tooth.impro.json").read_text(encoding="utf-8"))
    variant["offer_id"] = "classic.one_tooth.impro.other"
    variant["price"]["amount"] = 86200
    variant["payment_stages"][0]["amount"] = 55200
    (catalog / "classic.one_tooth.impro.other.json").write_text(json.dumps(variant,ensure_ascii=False),encoding="utf-8")
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client, q="Цена классической имплантации?").get_json()
    assert len(cards(first)[0]["price"]["rows"]) == 1
    assert len(cards(first)[0]["choices"]) == 4
    fake.generate = forbidden
    selected = post(client, request_id="choose-other", q="",
        ref="price_select:classic.one_tooth.impro.other", ui_revision=first["revision"])
    assert selected.status_code == 200, selected.get_json()
    row = cards(selected.get_json())[0]["price"]["rows"]
    assert len(row) == 1 and row[0]["offer_id"] == variant["offer_id"] and row[0]["amount"] == 86200
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert saved.response.resolved.finalized_commercial_ids.price_offer_ids == (variant["offer_id"],)
    assert len(fake.inputs) == 1


def test_foreign_session_cannot_use_demo_price_selection(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = post(client, q="Цена классической имплантации?").get_json()
    fake.generate = forbidden
    response = post(client, client_id="nikadent", request_id="foreign", q="",
        ref="price_select:classic.one_tooth.impro", ui_revision=first["revision"])
    assert response.status_code == 400 and len(fake.inputs) == 1


def test_paused_lead_keeps_price_card_but_has_no_price_selection(http_env):
    from tests.test_d2_lead_interrupt_http import _begin, _send
    from lead_interrupt import LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF, LEAD_CANCEL_REF
    client, db, use, _ = http_env
    fake = use(FakeProvider(""))
    sid = "card-lead-pause"
    _begin(client, fake, "json", sid, phone=True)
    pending = _send(client, "json", sid=sid, request_id="question",
                    q="Меня зовут Анна, мой номер +7 999 123-45-67. Сколько стоит классическая имплантация?")
    fake.raw = raw(price("classic", "service"))
    answer = _send(client, "json", sid=sid, request_id="answer", q="",
                    ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    assert {reply["reply_id"] for reply in answer["ui"]["quick_replies"]} == {LEAD_RESUME_REF, LEAD_CANCEL_REF}
    assert len(cards(answer)[0]["price"]["rows"]) == 1
    assert cards(answer)[0]["choices"] == []
    assert "Анна" not in fake.inputs[-1].user_message and "999" not in fake.inputs[-1].user_message
    with D2DialogueStore(db) as store:
        completed = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert completed.response.resolved.ui_plan.price_select_actions == ()
        assert completed.response.resolved.ui_plan.price_detail_actions == ()
        assert "Анна" not in completed.model_dump_json()
    fake.generate = forbidden
    denied = post(client, sid=sid, request_id="bad-choice", q="",
        ref="price_select:classic.one_tooth.impro", ui_revision=answer["revision"])
    assert denied.status_code == 400


@pytest.mark.parametrize("mode,financial,expected", [
    ("fixed", {"amount":18000}, "18"),
    ("from", {"min_amount":18000}, "от 18"),
    ("range", {"min_amount":18000,"max_amount":24000}, "24"),
    ("no_public_price", {"approved_text":"Стоимость определяют после осмотра."}, "Стоимость определяют после осмотра."),
])
def test_card_uses_frozen_mode_and_scope_without_recomputing(http_env, mode, financial, expected):
    client, db, use, tmp = http_env
    filename = tmp / "clients/demo/target_response/pricebook/services/professional_whitening.default.json"
    offer = json.loads(filename.read_text(encoding="utf-8"))
    offer["price"] = {"mode":mode, **financial}
    if mode != "no_public_price":
        offer["price"].update(currency="RUB", billing_unit="procedure")
    filename.write_text(json.dumps(offer,ensure_ascii=False),encoding="utf-8")
    use(FakeProvider(raw(price("professional_whitening", "service"))))
    response = post(client, q="Цена отбеливания?")
    assert response.status_code == 200, response.get_json()
    projected = cards(response.get_json())[0]["price"]["rows"][0]
    with D2DialogueStore(db) as store:
        frozen = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block.rows[0]
    assert projected == frozen.model_dump(mode="json")
    assert projected["mode"] == mode and expected in projected["price_display_text"]
    assert projected["scope_text"] == frozen.scope_text
    assert projected["condition_texts"] == list(frozen.condition_texts)


def test_explicit_brand_and_extent_stay_on_single_card(http_env):
    client, db, use, _ = http_env
    volume = {"extent":"full_arch","tooth_count":None,"jaw":"upper"}
    use(FakeProvider(raw(price("all_on_4", "service", brand_id="nobel_biocare", volume=volume))))
    response = post(client, q="Цена All-on-4 Nobel на верхнюю челюсть?").get_json()
    card = cards(response)[0]
    assert len(card["price"]["rows"]) == 1
    assert card["price"]["rows"][0]["offer_id"] == "all_on_4.jaw.nobel"
    assert card["price"]["rows"][0]["amount"] == 428000
    assert card["price"]["rows"][0]["billing_unit"] == "jaw"
    assert card["choices"] == []
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo",sid="cp6a"))
        assert saved.response.resolved.d2_request_parts[0].discussion_scope.volume.jaw == "upper"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_tabs_switch_back_and_forth_and_only_selected_offer_enters_context(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send = post if transport == "json" else post_sse
    current = _body(send(client, q="Цена классической имплантации?"), transport)
    expected = cards(current)[0]["choices"]
    fake.generate = forbidden
    for index, (offer, amount, brand) in enumerate([
        ("classic.one_tooth.impro", 85200, "impro"),
        ("classic.one_tooth.nobel", 101200, "nobel_biocare"),
        ("classic.one_tooth.implantium", 76200, "implantium"),
    ]):
        previous = current
        args = dict(request_id=f"switch-{index}", q="", ref=f"price_select:{offer}",
                    ui_revision=previous["revision"])
        current = _body(send(client, **args), transport)
        assert cards(current)[0]["choices"] == expected
        row = cards(current)[0]["price"]["rows"]
        assert len(row) == 1 and row[0]["offer_id"] == offer and row[0]["amount"] == amount
        assert _body(send(client, **args), transport) == current
        with D2DialogueStore(db) as store:
            saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
            assert saved.response.resolved.finalized_commercial_ids.price_offer_ids == (offer,)
            assert saved.response.resolved.d2_request_parts[0].discussion_scope.brand_id == brand
        denied = send(client, request_id=f"stale-{index}", q="",
                      ref=f"price_select:{offer}", ui_revision=previous["revision"])
        if transport == "json":
            assert denied.status_code == 400
        else:
            events = dict(sse_events(denied))
            assert events["error"]["error"] == "d2_invalid_turn" and "ui" not in events
    assert len(fake.inputs) == 1
    detail = _body(send(client, request_id="includes", q="", ref="price_detail:includes",
                        ui_revision=current["revision"]), transport)
    assert "Implantium" in detail["answer"] and "Impro" not in detail["answer"] and "Nobel" not in detail["answer"]


def test_initial_opened_brand_is_available_to_next_ordinary_question(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    post(client, q="Цена классической имплантации?")
    fake.raw = raw(explanation("Ответ об открытом варианте."))
    response = post(client, request_id="followup", q="А сколько это длится?")
    assert response.status_code == 200
    ordinary = fake.inputs[-1].context.ordinary
    assert ordinary.discussion_scope.brand_id == "implantium"
    assert [ref.offer_id for ref in ordinary.d2_shown_price_offer_refs] == ["classic.one_tooth.implantium"]


@pytest.mark.parametrize("price_first", [True, False])
def test_price_owned_texts_are_distinct_from_independent_address(http_env, price_first):
    client, _, use, _ = http_env
    p = price("classic", "service", request_id="r1" if price_first else "r2")
    c = {"kind":"contact", "request_id":"r2" if price_first else "r1", "contact_fields":["contact_address"]}
    fake = use(FakeProvider(raw(*([p,c] if price_first else [c,p]))))
    first = post(client, q="Цена имплантации и адрес?").get_json()
    parts = first["ui"]["body_parts"]
    address = next(part for part in parts if "Адрес" in part.get("text", ""))
    assert address["price_owned"] is False
    financial = [part for part in parts if part.get("price_owned")]
    assert financial and all("Адрес" not in part["text"] for part in financial)
    fake.generate = forbidden
    selected = post(client, request_id="choose", q="", ref="price_select:classic.one_tooth.impro",
                    ui_revision=first["revision"]).get_json()
    assert [p for p in selected["ui"]["body_parts"] if p.get("price_owned")]
    assert len(fake.inputs) == 1


def test_explicit_brand_pool_does_not_expand_during_switch(http_env):
    client, _, use, tmp = http_env
    catalog = tmp / "clients/demo/target_response/pricebook/services"
    variant = json.loads((catalog / "classic.one_tooth.impro.json").read_text(encoding="utf-8"))
    variant["offer_id"] = "classic.one_tooth.impro.other"
    variant["price"]["amount"] = 86200
    variant["payment_stages"][0]["amount"] = 55200
    (catalog / "classic.one_tooth.impro.other.json").write_text(json.dumps(variant,ensure_ascii=False),encoding="utf-8")
    fake = use(FakeProvider(raw(price("classic", "service", brand_id="impro"))))
    first = post(client, q="Цена Impro?").get_json()
    expected = ["price_select:classic.one_tooth.impro", "price_select:classic.one_tooth.impro.other"]
    assert [c["reply_id"] for c in cards(first)[0]["choices"]] == expected
    fake.generate = forbidden
    current = post(client, request_id="choose", q="", ref=expected[1], ui_revision=first["revision"]).get_json()
    assert [c["reply_id"] for c in cards(current)[0]["choices"]] == expected
    denied = post(client, request_id="not-authorized", q="", ref="price_select:classic.one_tooth.implantium",
                  ui_revision=current["revision"])
    assert denied.status_code == 400 and len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("aspect", ["includes", "stages", "consultation"])
def test_free_text_can_repeat_information_after_card_selection(http_env, transport, aspect):
    client, db, use, _ = http_env
    send = post if transport == "json" else post_sse
    fake = use(FakeProvider(raw(price("classic", "service"))))
    first = _body(send(client, q="Цена имплантации?"), transport)
    fake.generate = forbidden
    selected = _body(send(client, request_id="choose", q="",
        ref="price_select:classic.one_tooth.impro", ui_revision=first["revision"]), transport)
    assert cards(selected)[0]["price"]["rows"][0]["offer_id"] == "classic.one_tooth.impro"
    fake.generate = FakeProvider.generate.__get__(fake)
    question = {"includes":"А что входит?", "stages":"А как оплачивается?",
                "consultation":"А консультация бесплатная?"}[aspect]
    if aspect == "consultation":
        fake.raw = raw({"kind":"commercial_fact", "request_id":"r1",
            "fact_ids":["free_implant_consult"], "promotion_scope":"none",
            "target":{"type":"service", "id":"classic"}})
    else:
        # No explicit brand/target: execution must use the opened card's receipt.
        fake.raw = raw({"kind":"price_detail", "request_id":"r1", "price_detail_aspect":aspect})
    for i in range(2):
        args = dict(request_id=f"repeat-{i}", q=question)
        answer = _body(send(client, **args), transport)
        assert not cards(answer)
        assert _body(send(client, **args), transport) == answer
        if aspect == "consultation":
            assert "по имплантации и протезированию" in answer["answer"]
            assert "КТ при необходимости оплачивается отдельно" in answer["answer"]
        else:
            assert "Impro" in answer["answer"] and "Nobel" not in answer["answer"] and "Implantium" not in answer["answer"]
            with D2DialogueStore(db) as store:
                saved = store.read_latest_completion(SessionKey(client_id="demo",sid="cp6a"))
                assert [row.offer_id for row in saved.response.resolved.d2_price_detail_blocks[0].rows] == ["classic.one_tooth.impro"]
    assert fake.inputs[1].context.ordinary.discussion_scope.brand_id == "impro"
    assert [ref.offer_id for ref in fake.inputs[1].context.ordinary.d2_shown_price_offer_refs] == ["classic.one_tooth.impro"]
    assert len(fake.inputs) == 3  # Initial ordinary price + two written follow-ups; click/replays cost zero.
