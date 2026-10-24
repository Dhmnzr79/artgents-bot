"""Successful native price cards have one writer; adverse outcomes stay grounded.

Use actual JSON/SSE, publication, persistence and follow-up context. No network.
"""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env, send
from tests.test_d2_http_contract import post
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_price_cards import cards
from tests.test_d2_price_variants import medical


def saved(db, tenant="demo"):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id=tenant, sid="cp6a"))


PAIN = 'Обезболивание подбирает врач.\n<D2_META>\n{"sources":[{"content_ref":"implantation__faq__pain.md"}]}\n</D2_META>'


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("tenant,service,offers", [
    ("demo", "classic", {"classic.one_tooth.implantium", "classic.one_tooth.impro", "classic.one_tooth.nobel"}),
    ("demo_medical", "ent_consultation", {"ent_consultation.primary", "ent_consultation.repeat"}),
    ("nikadent", "removable_dentures", {"removable_dentures.jaw.partial", "removable_dentures.jaw.full",
        "removable_dentures.jaw.acry_free", "removable_dentures.jaw.nylon"}),
])
def test_successful_pure_price_all_tenants_uses_one_call(http_env, monkeypatch, transport, tenant, service, offers):
    medical(http_env, monkeypatch)
    client, db, use, _ = http_env
    wire = Transport(message(None, price(service)))
    use(D2HttpProvider(model="offline-configured-model", transport=wire))
    body = send(client, transport, client_id=tenant, request_id="pure", q="Сколько стоит?")
    assert {row["offer_id"] for row in cards(body)[0]["price"]["rows"]} == offers
    assert not saved(db, tenant).response.resolved.information_blocks
    assert len(wire.calls) == 1 and wire.calls[0]["model"] == "offline-configured-model"
    assert wire.calls[0]["tool_choice"] == "auto"
    assert send(client, transport, client_id=tenant, request_id="pure", q="Сколько стоит?") == body
    assert len(wire.calls) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("fields", [dict(brand_id="osstem"), dict(age_group="child"),
    dict(option_id="not-an-option"), dict(volume={"extent":"full_arch"})])
def test_adverse_result_replaces_first_prose_and_sources(http_env, transport, fields):
    client, db, use, _ = http_env
    wire = Transport(message(PAIN, price(**fields)),
        message("Запрошенная цена недоступна. Возможности обезболивания обсудим с врачом."),
        message("Ответ на следующий вопрос."))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="adverse", q="Цена и обезболивание?")
    assert not cards(body)
    assert "Запрошенная цена недоступна" in body["answer"]
    assert "Обезболивание подбирает" not in body["answer"]
    plan = saved(db).response.resolved
    assert len(plan.information_blocks) == 1
    assert plan.information_blocks[0].content_ref is None
    assert len(wire.calls) == 2
    assert wire.calls[1]["tool_choice"] == "none"
    ground = json.loads(wire.calls[1]["messages"][-2]["content"])
    assert ground["price"] is None and (ground["exact_text"] or ground["failures"])
    send(client, transport, request_id="after", q="Что дальше?")
    history = wire.calls[2]["messages"][1]["content"]
    assert "Запрошенная цена недоступна" in history
    assert "Обезболивание подбирает" not in history


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_partial_result_keeps_grounded_completion(http_env, transport):
    client, db, use, _ = http_env
    wire = Transport(message(PAIN, price(), price("professional_whitening")),
        message("Обезболивание обсудит врач; вторую стоимость можно спросить отдельно."))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, q="Имплантация, отбеливание и обезболивание?")
    assert cards(body)
    assert "Обезболивание подбирает" not in body["answer"]
    assert body["answer"].count("Обезболивание обсудит") == 1
    assert any(p.status == "deferred" for p in saved(db).response.resolved.d2_request_parts)
    assert len(wire.calls) == 2
    assert json.loads(wire.calls[1]["messages"][-2]["content"])["deferred"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_mixed_price_contact_sources_and_unique_identity(http_env, transport):
    client, db, use, _ = http_env
    raw = PAIN.replace('"sources":', '"actions":[{"name":"show_contacts","arguments":{"contact_fields":["contact_address"]}}],"sources":')
    wire = Transport(message(raw, price(brand_id="nobel_biocare")))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, q="Цена Nobel, больно ли и где клиника?")
    plan = saved(db).response.resolved
    assert len(wire.calls) == 1
    assert {row["offer_id"] for row in cards(body)[0]["price"]["rows"]} == {"classic.one_tooth.nobel"}
    assert body["answer"].count("Обезболивание подбирает") == 1
    assert plan.information_blocks[0].content_ref == "implantation__faq__pain.md"
    assert len(plan.d2_contact_blocks) == 1
    assert body["answer"].count(plan.d2_contact_blocks[0].display_text) == 1
    identities = [p.request_id for p in plan.d2_request_parts]
    assert len(identities) == len(set(identities))


@pytest.mark.parametrize("text", [None, "", '<D2_META>\n{"sources":[{"content_ref":"implantation__faq__pain.md"}]}\n</D2_META>'])
def test_empty_informational_text_does_not_trigger_a_repair_call(http_env, text):
    # This proves the call boundary, NOT that an empty mixed answer is useful.
    # Missing mixed prose must be caught by a later authorized live quality test.
    client, db, use, _ = http_env
    wire = Transport(message(text, price()))
    use(D2HttpProvider(transport=wire))
    body = send(client, q="Цена и больно ли?")
    assert cards(body) and not saved(db).response.resolved.information_blocks
    assert len(wire.calls) == 1


def test_invalid_tool_does_not_publish_otherwise_valid_first_prose(http_env):
    client, db, use, _ = http_env
    wire = Transport(message(PAIN, price(source_client_id="foreign")))
    use(D2HttpProvider(transport=wire))
    assert post(client).status_code == 400
    assert saved(db) is None and len(wire.calls) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_nobel_price_one_tooth_warranty_complete_dialogue(http_env, transport):
    client, db, use, _ = http_env
    target = {"type":"topic", "id":"implantation"}
    wire = Transport(message("Устанавливаем Nobel Biocare."),
        message(None, dict(target=target, brand_id="nobel_biocare")),
        message(None, dict(target=target, brand_id="nobel_biocare", volume={"extent":"one_tooth"})),
        message("Гарантия производителя на имплант и гарантия клиники различаются."))
    use(D2HttpProvider(transport=wire))
    send(client, transport, request_id="brand", q="Nobel ставите?")
    overview = send(client, transport, request_id="price", q="А сколько стоит?")
    assert {r["offer_id"] for r in cards(overview)[0]["price"]["rows"]} == {
        "classic.one_tooth.nobel", "all_on_4.jaw.nobel", "all_on_6.jaw.nobel"}
    one = send(client, transport, request_id="one", q="Один зуб")
    assert {r["offer_id"] for r in cards(one)[0]["price"]["rows"]} == {
        "classic.one_tooth.nobel", "one_stage.one_tooth.nobel"}
    assert len(wire.calls) == 3
    warranty = send(client, transport, request_id="warranty", q="А гарантия?")
    assert not cards(warranty) and len(wire.calls) == 4
    history = wire.calls[3]["messages"][1]["content"]
    assert "classic.one_tooth.nobel" in history and "one_stage.one_tooth.nobel" in history
    assert "Implantium" not in one["answer"]
    assert saved(db).response.rendered_text == warranty["answer"]
