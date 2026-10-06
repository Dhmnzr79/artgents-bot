"""Configured method overview, not catalogue fallback or medical assignment."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation


METHODS = {
    None: ("classic", "all_on_4", "all_on_6"),
    "one_tooth": ("classic", "one_stage"),
    "full_arch": ("all_on_4", "all_on_6"),
}


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("brand", [None, "implantium", "impro", "nobel_biocare"])
@pytest.mark.parametrize("extent", [None, "one_tooth", "full_arch", "few_teeth"])
def test_direction_uses_only_configured_methods_and_preserves_units(http_env, transport, brand, extent):
    client, db, use, _ = http_env
    kwargs = {"brand_id": brand}
    if extent:
        kwargs["volume"] = dict(extent=extent, jaw="unknown",
            tooth_count=1 if extent == "one_tooth" else None)
    fake = use(FakeProvider(raw(price(**kwargs))))
    send = post if transport == "json" else post_sse
    args = dict(sid="sim4", request_id="price", q="Сколько стоит имплантация?")
    first = send(client, **args)
    assert first.status_code == 200
    body = _body(first, transport)
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="sim4"))
        resolved = saved.response.resolved
        if extent == "few_teeth" and brand not in {None, "implantium"}:
            assert resolved.d2_price_block is None
            assert resolved.d2_request_parts[0].status == "unavailable"
            assert "птериго" not in body["answer"].lower()
        else:
            rows = resolved.d2_price_block.rows
            expected_methods = ("classic",) if extent == "few_teeth" else METHODS[extent]
            assert tuple(r.service_id for r in rows) == expected_methods
            selected_brand = brand or "implantium"
            if selected_brand == "nobel_biocare":
                selected_brand = "nobel"
            assert tuple(r.offer_id for r in rows) == tuple(
                f"{m}.{'one_tooth' if m in {'classic', 'one_stage'} else 'jaw'}.{selected_brand}"
                for m in expected_methods)
            assert "КТ" in body["answer"]
            if extent not in {"one_tooth", "few_teeth"}:
                assert "челюсть" in body["answer"]
            if extent != "full_arch":
                assert "одного зуба" in body["answer"]
            if extent == "few_teeth":
                assert "стоимость за один зуб" in body["answer"]
        assert "situation_state" not in store.read(SessionKey(client_id="demo", sid="sim4")).state.model_dump()
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_click_changes_method_overview_without_model_and_followup_keeps_extent(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation("Боль обсуждается с врачом."))))
    send = post if transport == "json" else post_sse
    assert send(client, request_id="fear", q="Я боюсь боли").status_code == 200
    fake.raw = raw(price())
    first = _body(send(client, request_id="overview", q="Сколько стоит имплантация?"), transport)
    calls = len(fake.inputs)
    clicked = _body(send(client, request_id="click", q="", ref="volume:implantation:one_tooth",
        ui_revision=first["revision"]), transport)
    assert len(fake.inputs) == calls
    assert "All-on-4" not in clicked["answer"] and "All-on-6" not in clicked["answer"]
    assert "76 200" in clicked["answer"].replace("\u00a0", " ")
    assert "86 500" in clicked["answer"].replace("\u00a0", " ")
    fake.raw = raw(explanation("Сроки зависят от плана лечения."))
    assert send(client, request_id="next", q="А сколько времени займёт?").status_code == 200
    assert fake.inputs[-1].context.ordinary.discussion_scope.volume.extent == "one_tooth"


@pytest.mark.parametrize("service,expected_count", [("classic", 3), ("all_on_4", 3),
    ("all_on_6", 3), ("zygomatic_implants", 1), ("pterygoid_implants", 1)])
def test_exact_service_is_not_limited_to_overview_pool(http_env, service, expected_count):
    client, db, use, _ = http_env
    use(FakeProvider(raw(price(service, "service"))))
    response = post(client, request_id="exact", q="Сколько стоит названная услуга?")
    assert response.status_code == 200
    with D2DialogueStore(db) as store:
        rows = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block.rows
        assert len(rows) == expected_count
        assert all(r.service_id == service for r in rows)


def test_fourth_catalog_offer_is_visible_only_for_exact_service(http_env):
    client, db, use, tmp = http_env
    folder = tmp / "clients/demo/target_response/pricebook/services"
    extra = json.loads((folder / "classic.one_tooth.implantium.json").read_text(encoding="utf-8"))
    extra["offer_id"] = "classic.one_tooth.extra"
    (folder / "classic.one_tooth.extra.json").write_text(json.dumps(extra), encoding="utf-8")
    fake = use(FakeProvider(raw(price("classic", "service"))))
    assert post(client, request_id="exact", q="Цена классической имплантации?").status_code == 200
    with D2DialogueStore(db) as store:
        rows = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block.rows
        assert len(rows) == 4
        assert "classic.one_tooth.extra" in {r.offer_id for r in rows}
    fake.raw = raw(price(volume=dict(extent="one_tooth", tooth_count=1, jaw="unknown")))
    assert post(client, request_id="overview", q="А имплантация одного зуба вообще?").status_code == 200
    with D2DialogueStore(db) as store:
        rows = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block.rows
        assert tuple(r.service_id for r in rows) == ("classic", "one_stage")
        assert "classic.one_tooth.extra" not in {r.offer_id for r in rows}


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("content_first", [False, True])
def test_financial_prose_risk_does_not_rewrite_price_or_cut_explanation(http_env, transport, content_first):
    client, db, use, _ = http_env
    prose = "Лечение проходит по плану врача. Переплаты не будет. Ошибочный ориентир — 1 ₽."
    blocks = [explanation(prose), price("classic", "service")]
    if not content_first:
        blocks.reverse()
    for i, block in enumerate(blocks, 1):
        block["request_id"] = f"r{i}"
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    args = dict(request_id="mixed", q="Как проходит имплантация и сколько стоит?")
    response = send(client, **args)
    assert response.status_code == 200
    body = _body(response, transport)
    assert prose in body["answer"]
    with D2DialogueStore(db) as store:
        rows = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")).response.resolved.d2_price_block.rows
        assert {r.offer_id for r in rows} == {
            "classic.one_tooth.implantium", "classic.one_tooth.impro", "classic.one_tooth.nobel"}
    for amount in ("76 200", "85 200", "101 200"):
        assert amount in body["answer"].replace("\u00a0", " ")
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1
