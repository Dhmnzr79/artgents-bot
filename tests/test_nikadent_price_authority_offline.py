"""Nikadent owner-approved prices through current native D2 and real HTTP/SSE.

No live model or SMTP. Legacy sales_fast price assertions are replaced by tests
of the actual route, frozen rows, units, volume controls and authenticated tabs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
from tests.d2_ci_http import http_env, send, click
from tests.test_d2_http_contract import post
from tests.test_d2_native_price_runtime import Transport, message
from tests.test_d2_price_cards import cards

ROOT = Path(__file__).resolve().parents[1]


def request(target, *, topic=False, extent=None, count=None, option=None, **extra):
    args = {"target": {"type": "topic" if topic else "service", "id": target}, **extra}
    if extent:
        args["volume"] = {"extent": extent, "tooth_count": count, "jaw": "unknown"}
    if option:
        args["option_id"] = option
    return args


def native(use, args, *, completion="Состав лечения согласуем после осмотра."):
    wire = Transport(message("Предварительный текст не публикуется.", args), message(completion))
    use(D2HttpProvider(model="offline-price-check", transport=wire))
    return wire


def saved(db):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id="nikadent", sid="nika-prices"))


def rows(body):
    return [row for card in cards(body) for row in card["price"]["rows"]]


def amount(row):
    return row["amount"] if row["mode"] == "fixed" else row["min_amount"]


def frozen_rows(db):
    block = saved(db).response.resolved.d2_price_block
    return [] if block is None else [row.model_dump(mode="json") for row in block.rows]


def price_scope(db):
    return next(part.discussion_scope for part in saved(db).response.resolved.d2_request_parts
                if part.kind == "price" and part.discussion_scope is not None)


@pytest.mark.parametrize("tenant", ["nikadent", "demo"])
def test_md_has_no_commercial_currency_tokens(tenant):
    offenders = []
    for path in (ROOT / "clients" / tenant / "md").glob("*.md"):
        if re.search(r"\d[\d\s]*\s*(?:₽|руб(?:лей)?|р\.)", path.read_text(encoding="utf-8"), re.I):
            offenders.append(path.name)
    assert not offenders


def test_prosthodontic_topics_are_current_d2_sources():
    snapshot = load_d2_tenant_snapshot("nikadent", clients_root=ROOT / "clients")
    for service in ("metal_ceramic_crowns", "zirconia_crowns", "fixed_bridge", "core_inlay",
                    "emax_crowns", "temporary_denture", "denture_reline"):
        assert snapshot.service_topics[service] == "prosthetics"
    assert snapshot.bundle.family_prices.records == []
    assert {d.topic_id for d in build_d2_model_view(snapshot).direction_prices} == {
        "prosthetics", "implantation", "restoration"}


# Expected amounts come from the owner's detailed screenshots, not the source JSON.
EXACT = [
    ("prosthetics_consultation", None, "prosthetics_consultation.default", "fixed", 0, "procedure"),
    ("caries", None, "caries.default", "from", 5250, "tooth"),
    ("tooth_extraction", None, "tooth_extraction.default", "from", 5500, "tooth"),
    ("classic", None, "classic.default", "fixed", 35000, "implant"),
    ("one_stage", None, "one_stage.default", "fixed", 35000, "implant"),
    ("metal_ceramic_crowns", None, "metal_ceramic_crowns.default", "fixed", 22000, "tooth"),
    ("zirconia_crowns", None, "zirconia_crowns.default", "from", 24000, "tooth"),
    ("emax_crowns", None, "emax_crowns.default", "from", 24000, "tooth"),
    ("veneers", None, "veneers.default", "fixed", 30000, "tooth"),
    ("implant_supported_prosthetics", "crown", "implant_supported_prosthetics.crown", "from", 30000, "tooth"),
    ("removable_dentures", "partial", "removable_dentures.jaw.partial", "fixed", 35000, "jaw"),
    ("removable_dentures", "full", "removable_dentures.jaw.full", "fixed", 40000, "jaw"),
    ("removable_dentures", "acry_free", "removable_dentures.jaw.acry_free", "fixed", 55000, "jaw"),
    ("removable_dentures", "nylon", "removable_dentures.jaw.nylon", "fixed", 40000, "unit"),
    ("temporary_denture", None, "temporary_denture.default", "fixed", 12000, "unit"),
    ("clasp_dentures", None, "clasp_dentures.default", "from", 65000, "jaw"),
    ("denture_repair", None, "denture_repair.default", "fixed", 7000, "procedure"),
    ("denture_reline", None, "denture_reline.default", "fixed", 7500, "procedure"),
    ("sinus_lift", None, "sinus_lift.default", "from", 25000, "procedure"),
    ("bone_graft", None, "bone_graft.default", "from", 25000, "procedure"),
    ("core_inlay", None, "core_inlay.default", "from", 7000, "tooth"),
]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service,option,offer,mode,cost,unit", EXACT)
def test_precise_prices_modes_units_and_provider_grounding(http_env, transport, service, option, offer, mode, cost, unit):
    client, db, use, _ = http_env
    wire = native(use, request(service, option=option))
    body = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="exact", q="Цена выбранной услуги?")
    row = rows(body)[0]
    assert (row["offer_id"], row["mode"], amount(row), row["billing_unit"]) == (offer, mode, cost, unit)
    assert "Предварительный текст" not in body["answer"]
    ground = json.loads(wire.calls[1]["messages"][-2]["content"])
    assert ground["price"]["rows"][0]["offer_id"] == offer
    assert wire.calls[1]["tool_choice"] == "none" and len(wire.calls) == 2
    completion = saved(db)
    assert completion.response.resolved.finalized_commercial_ids.price_offer_ids == (offer,)
    assert send(client, transport, client_id="nikadent", sid="nika-prices", request_id="exact", q="Цена выбранной услуги?") == body
    assert len(wire.calls) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("topic,initial", [
    ("prosthetics", ["removable_dentures.jaw.partial", "metal_ceramic_crowns.default", "zirconia_crowns.default"]),
    ("implantation", ["classic.default", "all_on_4.default", "all_on_6.default"]),
    ("restoration", ["classic.default", "removable_dentures.jaw.partial", "zirconia_crowns.default"]),
])
def test_overview_volume_clicks_and_unknown_are_server_owned(http_env, transport, topic, initial):
    client, db, use, _ = http_env
    wire = native(use, request(topic, topic=True))
    body = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="overview", q="Сколько стоит восстановление зубов?")
    assert [r["offer_id"] for r in rows(body)] == initial
    assert [q["reply_id"] for q in body["ui"]["quick_replies"] if q["reply_id"].startswith("volume:")] == [
        f"volume:{topic}:one_tooth", f"volume:{topic}:full_arch", f"volume:{topic}:unknown"]
    assert len(rows(body)) <= 3
    one = click(client, body, f"volume:{topic}:one_tooth", transport=transport,
                request_id="one", client_id="nikadent", sid="nika-prices")
    assert all(r["billing_unit"] in {"tooth", "implant"} for r in rows(one))
    assert all("all_on" not in r["offer_id"] and "removable" not in r["offer_id"] for r in rows(one))
    full = click(client, one, f"volume:{topic}:full_arch", transport=transport,
                 request_id="full", client_id="nikadent", sid="nika-prices")
    ids = [r["offer_id"] for r in frozen_rows(db)]
    if topic == "implantation":
        assert ids == ["all_on_4.default", "all_on_6.default"]
        assert all(r["mode"] == "no_public_price" for r in frozen_rows(db))
        assert cards(full)[0]["price"]["presentation"] == "options"
        assert "после диагностики и согласования плана" in full["answer"]
    else:
        assert ids == ["removable_dentures.jaw.full", "all_on_4.default", "all_on_6.default"]
        assert amount(rows(full)[0]) == 40000 and rows(full)[0]["billing_unit"] == "jaw"
    assert not any(r["offer_id"] in {"classic.default", "implant_supported_prosthetics.crown", "removable_dentures.jaw.partial"} for r in rows(full))
    unknown = click(client, full, f"volume:{topic}:unknown", transport=transport,
                    request_id="unknown", client_id="nikadent", sid="nika-prices")
    # Existing implementation repeats authored overview, omits its question.
    assert [r["offer_id"] for r in rows(unknown)] == initial
    assert "Какой объём" not in unknown["answer"]
    assert len(wire.calls) == 2
    assert price_scope(db).volume.extent == "unknown"


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_three_teeth_free_text_keeps_unit_prices_not_multiplied_totals(http_env, transport):
    client, db, use, _ = http_env
    wire = native(use, request("prosthetics", topic=True, extent="few_teeth", count=3))
    body = send(client, transport, client_id="nikadent", sid="nika-prices", q="А если восстановить три зуба?")
    assert [(r["offer_id"], amount(r)) for r in rows(body)] == [
        ("removable_dentures.jaw.partial", 35000), ("metal_ceramic_crowns.default", 22000), ("zirconia_crowns.default", 24000)]
    assert "за один зуб" in " ".join(t for r in rows(body) if r["billing_unit"] == "tooth" for t in r["condition_texts"])
    assert price_scope(db).volume.tooth_count == 3
    assert not any(amount(r) in {66000, 72000, 105000} for r in rows(body))
    assert len(wire.calls) == 2


@pytest.mark.parametrize("service,extent", [("all_on_4", "full_arch"), ("all_on_6", "full_arch"),
    ("implant_supported_prosthetics", "full_arch"), ("fixed_bridge", "few_teeth"),
    ("pulpitis", None), ("teeth_cleaning", None), ("teeth_treatment", None)])
def test_no_invented_full_package_or_unpublished_prices(http_env, service, extent):
    client, db, use, _ = http_env
    native(use, request(service, extent=extent))
    body = send(client, client_id="nikadent", sid="nika-prices")
    assert all(r["mode"] == "no_public_price" for r in frozen_rows(db))
    assert not re.search(r"\d[\d\s]*₽", body["answer"])
    if service in {"pulpitis", "teeth_cleaning"}:
        assert not cards(body)
        assert not saved(db).response.resolved.finalized_commercial_ids.price_offer_ids
    else:
        assert frozen_rows(db) and all(r["approved_text"] for r in frozen_rows(db))
        assert cards(body)[0]["price"]["presentation"] == "detail"
        assert cards(body)[0]["price"]["rows"] == frozen_rows(db)


@pytest.mark.parametrize("service,option,extent", [
    ("classic", None, "full_arch"), ("caries", None, "full_arch"),
    ("removable_dentures", "partial", "full_arch"), ("removable_dentures", "full", "one_tooth"),
    ("removable_dentures", "acry_free", "few_teeth"), ("removable_dentures", "nylon", "full_arch"),
    ("implant_supported_prosthetics", "crown", "full_arch"), ("temporary_denture", None, "full_arch"),
    ("removable_dentures", "missing", None), ("zirconia_crowns", "full", None),
])
def test_wrong_volume_or_option_does_not_substitute_cheapest_price(http_env, service, option, extent):
    client, _, use, _ = http_env
    native(use, request(service, option=option, extent=extent))
    body = send(client, client_id="nikadent", sid="nika-prices")
    assert not cards(body)
    assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_removable_options_and_authenticated_alternative_keep_scope(http_env, transport):
    client, db, use, _ = http_env
    wire = native(use, request("removable_dentures"))
    body = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="first")
    assert rows(body)[0]["offer_id"] == "removable_dentures.jaw.partial"
    assert amount(rows(body)[0]) == 35000
    assert cards(body)[0]["price"]["presentation"] == "options" and len(rows(body)) == 4
    assert price_scope(db).brand_id is None
    refs = {c["reply_id"] for card in cards(body) for c in card["choices"]}
    assert refs == {"price_select:removable_dentures.jaw."+op for op in ["partial", "full", "acry_free", "nylon"]}
    selected = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="acry", q="",
                    ref="price_select:removable_dentures.jaw.acry_free", ui_revision=body["revision"])
    assert amount(rows(selected)[0]) == 55000 and rows(selected)[0]["billing_unit"] == "jaw"
    assert len(wire.calls) == 2
    assert send(client, transport, client_id="nikadent", sid="nika-prices", request_id="acry", q="",
                ref="price_select:removable_dentures.jaw.acry_free", ui_revision=body["revision"]) == selected
    assert len(wire.calls) == 2
    # Following ordinary turn reads the actual published selected variant.
    wire.replies.append(message("Выбран полный протез Acry Free."))
    send(client, transport, client_id="nikadent", sid="nika-prices", request_id="after", q="А какой материал мы выбрали?")
    assert "removable_dentures.jaw.acry_free" in wire.calls[-1]["messages"][1]["content"]


@pytest.mark.parametrize("ref", ["price_select:classic.one_tooth.implantium", "price_select:removable_dentures.jaw.foreign",
    "price_select:temporary_denture.default", "volume:implantation:full_arch"])
def test_unpublished_foreign_or_wrong_direction_refs_rejected_before_model(http_env, ref):
    client, _, use, _ = http_env
    wire = native(use, request("removable_dentures"))
    first = send(client, client_id="nikadent", sid="nika-prices", request_id="first")
    rejected = post(client, client_id="nikadent", sid="nika-prices", request_id="forged", q="", ref=ref, ui_revision=first["revision"])
    assert rejected.status_code == 400
    assert len(wire.calls) == 2


@pytest.mark.parametrize("service,excluded", [("classic", "Коронка и протезирование"),
    ("one_stage", "Коронка и протезирование"), ("implant_supported_prosthetics", "Установка импланта"),
    ("core_inlay", "Стоимость коронки")])
def test_surgical_and_prosthetic_exclusions_reach_card_grounding_and_history(http_env, service, excluded):
    client, _, use, _ = http_env
    wire = native(use, request(service))
    body = send(client, client_id="nikadent", sid="nika-prices", request_id="first")
    row = rows(body)[0]
    assert any(excluded in x for x in row["excludes"])
    assert excluded in json.dumps(json.loads(wire.calls[1]["messages"][-2]["content"]), ensure_ascii=False)
    if cards(body)[0]["price"]["presentation"] == "options":
        # A list shows prices first; package details enter visible history
        # only after the user opens this exact offer.
        selected = click(client, body, "price_select:"+row["offer_id"],
            client_id="nikadent",sid="nika-prices",request_id="detail")
        assert cards(selected)[0]["price"]["presentation"] == "detail"
        assert len(wire.calls) == 2
    wire.replies.append(message("Это разные этапы лечения."))
    send(client, client_id="nikadent", sid="nika-prices", request_id="follow", q="Это всё лечение целиком?")
    assert excluded in wire.calls[-1]["messages"][1]["content"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("count", [1, 3])
def test_core_inlay_known_volume_retains_unit_price_and_crown_exclusion(http_env, transport, count):
    client, _, use, _ = http_env
    native(use, request("core_inlay", extent="one_tooth" if count == 1 else "few_teeth", count=count))
    body = send(client, transport, client_id="nikadent", sid="nika-prices",
                q=f"Сколько стоит культевая вкладка на {count} зуба?")
    row, = rows(body)
    assert (row["offer_id"], row["min_amount"], row["billing_unit"]) == ("core_inlay.default", 7000, "tooth")
    assert "Стоимость коронки оплачивается отдельно." in row["excludes"]
    assert "21 000" not in body["answer"].replace("\u00a0", " ")


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_consultation_price_preserves_advance_booking_in_grounding_and_receipt(http_env, transport):
    client, db, use, _ = http_env
    wire = native(use, request("prosthetics_consultation"), completion="Консультация бесплатная.")
    body = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="consult")
    row, = rows(body)
    condition = "Обязательна предварительная запись."
    assert row["amount"] == 0 and condition in row["condition_texts"]
    assert condition in json.dumps(json.loads(wire.calls[1]["messages"][-2]["content"]), ensure_ascii=False)
    frozen, = frozen_rows(db)
    assert condition in frozen["condition_texts"]
    assert send(client, transport, client_id="nikadent", sid="nika-prices", request_id="consult") == body
    assert len(wire.calls) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, None])
def test_temporary_denture_known_count_respects_authored_limit(http_env, transport, count):
    client, db, use, _ = http_env
    wire = native(use, request("temporary_denture", extent="one_tooth" if count == 1 else "few_teeth", count=count))
    body = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="temporary")
    if count is None or count <= 3:
        row, = rows(body)
        assert row["offer_id"] == "temporary_denture.default" and row["amount"] == 12000
        assert "1–3" in row["scope_text"]
    else:
        assert not rows(body) and not frozen_rows(db)
        assert "Стоимость этого варианта можно уточнить у администратора" in body["answer"]
        assert "12 000" not in body["answer"].replace("\u00a0", " ")
        assert not body["ui"]["projected_commercial_ids"]["price_offer_ids"]
    assert send(client, transport, client_id="nikadent", sid="nika-prices", request_id="temporary") == body
    assert len(wire.calls) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target,topic", [("prosthetics", True), ("removable_dentures", False)])
def test_count_cap_uses_authored_value_for_other_offers_and_overview_tabs(http_env, transport, target, topic):
    client, _, use, tmp = http_env
    # A different service and cap prove the mechanism does not special-case
    # temporary dentures, the number3, or natural-language price labels.
    path = tmp / "clients/nikadent/target_response/pricebook/services/removable_dentures.jaw.partial.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["max_tooth_count"] = 2
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    wire = native(use, request(target, topic=topic, extent="few_teeth", count=3))
    body = send(client, transport, client_id="nikadent", sid="nika-prices")
    ids = [row["offer_id"] for row in rows(body)]
    assert "removable_dentures.jaw.partial" not in ids
    if topic:
        assert "metal_ceramic_crowns.default" in ids
        assert "zirconia_crowns.default" in ids
    else:
        assert ids == ["removable_dentures.jaw.nylon"]
    assert "price_select:removable_dentures.jaw.partial" not in {
        reply["reply_id"] for reply in body["ui"]["quick_replies"]}
    rejected = post(client, client_id="nikadent", sid="nika-prices", request_id="forged-cap", q="",
                    ref="price_select:removable_dentures.jaw.partial", ui_revision=body["revision"])
    assert rejected.status_code == 400 and len(wire.calls) == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_saved_price_selection_keeps_allowed_count_and_replays_without_model(http_env, transport):
    client, db, use, tmp = http_env
    path = tmp / "clients/nikadent/target_response/pricebook/services/removable_dentures.jaw.partial.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["max_tooth_count"] = 2
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    wire = native(use, request("removable_dentures", extent="few_teeth", count=2))
    first = send(client, transport, client_id="nikadent", sid="nika-prices", request_id="first")
    selected = click(client, first, "price_select:removable_dentures.jaw.partial", transport=transport,
                     client_id="nikadent", sid="nika-prices", request_id="selected")
    row, = rows(selected)
    assert row["offer_id"] == "removable_dentures.jaw.partial" and row["amount"] == 35000
    assert price_scope(db).volume.tooth_count == 2
    assert click(client, first, "price_select:removable_dentures.jaw.partial", transport=transport,
                 client_id="nikadent", sid="nika-prices", request_id="selected") == selected
    assert len(wire.calls) == 2


@pytest.mark.parametrize("service", ["metal_ceramic_crowns", "fixed_bridge", "core_inlay", "all_on_4"])
def test_ordinary_information_does_not_force_a_price_card(http_env, service):
    client, _, use, _ = http_env
    wire = Transport(message("Врач объяснит подходящий вариант лечения."))
    use(D2HttpProvider(transport=wire))
    body = send(client, client_id="nikadent", sid="nika-prices", q="Расскажите об услуге "+service)
    assert not cards(body) and "₽" not in body["answer"] and len(wire.calls) == 1


@pytest.mark.parametrize("extra", [{"amount": 1}, {"currency": "USD"}, {"source_client_id": "demo"}])
def test_model_cannot_override_catalog_money_or_tenant(http_env, extra):
    client, db, use, _ = http_env
    wire = Transport(message(None, request("classic", **extra)))
    use(D2HttpProvider(transport=wire))
    response = post(client, client_id="nikadent", sid="nika-prices")
    assert response.status_code == 400
    assert saved(db) is None and len(wire.calls) == 1


def test_nonexistent_ui_revision_cannot_select_an_otherwise_valid_variant(http_env):
    client, _, use, _ = http_env
    wire = native(use, request("removable_dentures"))
    first = send(client, client_id="nikadent", sid="nika-prices", request_id="first")
    response = post(client, client_id="nikadent", sid="nika-prices", request_id="forged-revision", q="",
        ref="price_select:removable_dentures.jaw.full", ui_revision=first["revision"]+1000)
    assert response.status_code == 400 and len(wire.calls) == 2


def test_price_ref_from_other_tenant_session_has_no_authority(http_env):
    client, _, use, _ = http_env
    wire = native(use, request("removable_dentures"))
    demo = send(client, client_id="demo", sid="same-sid", request_id="first")
    # Same textual SID does not make the Demo publication available to Nika.
    response = post(client, client_id="nikadent", sid="same-sid", request_id="foreign", q="",
        ref="price_select:removable_dentures.jaw.full", ui_revision=demo["revision"])
    assert response.status_code == 400 and len(wire.calls) == 2


@pytest.mark.parametrize("service", ["all_on_4", "all_on_6"])
def test_no_public_price_omits_loose_scope_but_preserves_authored_caveats(http_env, service):
    client, _, use, tmp = http_env
    path = tmp / "clients/nikadent/target_response/pricebook/services" / (service+".default.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    scope = data["package"]["label"]
    caveat = "Подготовка согласуется до лечения."
    mandatory = "Состав плана уточняется после диагностики."
    data["package"]["label"] += "; "+caveat
    data["required_conditions_metadata"] = {"completeness":"complete", "conditions":[
        {"condition_id":"mandatory_exclusion", "display_text":mandatory}]}
    path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    native(use, request(service, extent="full_arch"))
    body = send(client, client_id="nikadent", sid="nika-prices")
    assert scope not in body["answer"]
    assert data["price"]["approved_text"] in body["answer"]
    assert caveat in body["answer"] and mandatory in body["answer"]
    assert cards(body)[0]["price"]["presentation"] == "detail"
