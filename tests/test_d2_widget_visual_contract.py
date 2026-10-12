"""Actual frozen card data/actions backing the visual transfer; offline native wire."""
import json
import pytest
from core.d2_live_provider import D2HttpProvider
from core.d2_dialogue_store import D2DialogueStore
from contracts.response_plan import SessionKey
from tests.d2_ci_http import http_env, send, click, completed_context
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_price_cards import cards

@pytest.mark.parametrize("transport", ["json", "sse"])
def test_overview_selection_and_brand_keep_server_identity_and_history(http_env, transport):
    client, db, use, _ = http_env
    wire = Transport(message(None, dict(target={"type":"topic","id":"implantation"})),message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="overview", q="Цена имплантации?")
    card = cards(body)[0]
    refs = {c["reply_id"] for c in [*card["choices"],*card["service_choices"]]}
    for row in card["price"]["rows"]:
        assert "price_select:"+row["offer_id"] in refs
    selected = click(client, body, "price_select:classic.one_tooth.implantium", request_id="method", transport=transport)
    assert not cards(selected)[0]["overview"]
    nobel = click(client, selected, "price_select:classic.one_tooth.nobel", request_id="brand", transport=transport)
    row = cards(nobel)[0]["price"]["rows"][0]
    assert row["offer_id"] == "classic.one_tooth.nobel" and row["amount"] == 101200
    assert len(wire.calls) == 2
    with D2DialogueStore(db) as store:
        ctx = completed_context(store, SessionKey(client_id="demo",sid="cp6a"))
        assert "101" in ctx.ordinary.dialogue_pairs[-1].assistant_text
        assert all(line in ctx.ordinary.dialogue_pairs[-1].assistant_text for line in row["includes"])
    assert click(client, selected, "price_select:classic.one_tooth.nobel", request_id="brand", transport=transport) == nobel

@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("option", ["partial", "full"])
def test_removable_exception_is_single_and_authored(http_env, transport, option):
    client, db, use, root = http_env
    wire = Transport(message(None, price("removable_dentures",option_id=option)),message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body = send(client, transport, request_id="price", q="Цена протеза?")
    row = cards(body)[0]["price"]["rows"][0]
    authored = json.loads((root/f"clients/demo/target_response/pricebook/services/removable_dentures.jaw.{option}.json").read_text(encoding="utf-8"))
    assert row["condition_texts"] == ["Имплантация — отдельно."]
    assert row["scope_text"] == "за одну челюсть"
    assert row["amount"] == authored["price"]["amount"]
    assert row["includes"] == authored["package"]["includes"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_single_brand_keeps_frozen_variant_without_unpublished_tabs(http_env, transport):
    client, db, use, _ = http_env
    wire=Transport(message(None,price("classic",brand_id="nobel_biocare",volume={"extent":"one_tooth"})),message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body=send(client,transport,request_id="single",q="Цена Nobel на один зуб?")
    card=cards(body)[0]
    assert card["price"]["rows"][0]["offer_id"] == "classic.one_tooth.nobel"
    assert card["price"]["rows"][0]["variant_label"] == "Nobel Biocare"
    assert not card["choices"]


@pytest.mark.parametrize("brand", ["implantium", "impro", "nobel"])
def test_one_stage_exclusion_is_published_once(brand):
    from pathlib import Path
    from contracts.response_schema import TargetOffer
    from core.response_plan_materialization import _d2_brief_price_conditions
    data=json.loads((Path(__file__).resolve().parents[1]/f"clients/demo/target_response/pricebook/services/one_stage.one_tooth.{brand}.json").read_text(encoding="utf-8"))
    offer=TargetOffer.model_validate(data)
    scope=offer.package.label.split(";",1)[0]
    conditions=_d2_brief_price_conditions(offer,package_label=offer.package.label,already_shown=scope)
    assert conditions == (data["required_conditions_metadata"]["conditions"][0]["display_text"],)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_short_tabs_do_not_change_variant_or_model_catalog(http_env, transport):
    from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
    from core.response_schema_loader import load_response_schema_bundle
    client, db, use, root=http_env
    bundle=load_response_schema_bundle(root/"clients/demo/target_response")
    descriptor=json.loads(ActiveServiceCatalogSnapshot.from_bundle(bundle).canonical_json)
    service=next(s for s in descriptor["services"] if s["service_id"]=="tooth_extraction")
    assert service["options"] == [{"option_id":"default","name":"Обычное удаление зуба"},{"option_id":"complex","name":"Сложное удаление зуба"}]
    wire=Transport(message(None,price("tooth_extraction")),message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    body=send(client,transport,request_id="short",q="Цена удаления?")
    assert [c["label"] for c in cards(body)[0]["choices"]] == ["Обычное","Сложное"]
    changed=click(client,body,"price_select:tooth_extraction.complex",request_id="complex",transport=transport)
    row=cards(changed)[0]["price"]["rows"][0]
    assert row["variant_label"] == "Сложное удаление зуба" and row["min_amount"]==8000
    assert [c["label"] for c in cards(changed)[0]["choices"]] == ["Обычное","Сложное"]
    assert len(wire.calls)==2
