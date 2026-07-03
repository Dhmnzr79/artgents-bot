"""Unit tests for structured price offers (stage 3)."""
from __future__ import annotations

from core.price_offers import (
    build_price_answer_for_lookup,
    build_price_append_for_lookup,
    build_unit_clarify_answer,
    detect_brand_in_query,
    get_price_offers,
    is_crown_inclusion_content_query,
    is_full_jaw_implant_price_query,
    is_generic_implant_price_query,
    is_one_stage_price_query,
    is_upper_jaw_restoration_price_query,
    render_price_offers_append,
    resolve_implant_group_overview,
    should_offer_unit_clarify,
)


def test_get_price_offers_sinus_lift_from_pricebook():
    offers = get_price_offers("demo", "sinus_lift", unit="one_site")
    assert len(offers) == 2
    assert min(o.total for o in offers) == 42000
    assert max(o.total for o in offers) == 68000


def test_build_price_lookup_sinus_lift_uses_pricebook():
    text, meta = build_price_answer_for_lookup(
        client_id="demo",
        service_id="sinus_lift",
        q="сколько стоит синус-лифтинг",
    )
    assert text
    assert "42 000" in text
    assert "По брендам" not in text
    assert "Варианты" in text
    assert meta.get("pricebook_applied") is True


def test_get_price_offers_three_brands_one_tooth():
    offers = get_price_offers("demo", "classic", unit="one_tooth")
    assert len(offers) == 3
    brands = {o.brand for o in offers}
    assert brands == {"Implantium", "Impro", "Nobel Biocare"}
    assert any(o.recommended for o in offers)


def test_brand_filter_nobel():
    offers = get_price_offers("demo", "classic", unit="one_tooth", brand="Nobel Biocare")
    assert len(offers) == 1
    assert offers[0].total == 101200


def test_detect_brand_in_query():
    assert detect_brand_in_query("сколько стоит Nobel под ключ", client_id="demo") == "Nobel Biocare"
    assert detect_brand_in_query("имплант Impro цена", client_id="demo") == "Impro"


def test_detect_brand_without_aliases_file():
    assert detect_brand_in_query("сколько стоит Nobel под ключ", client_id="cesi") is None


def test_render_append_single_brand_includes_excludes():
    offers = get_price_offers("demo", "classic", unit="one_tooth", brand="Nobel Biocare")
    text = render_price_offers_append(offers)
    assert text
    assert "Входит:" in text
    assert "Не входит:" in text
    assert "коронка на импланте" in text


def test_get_price_offers_all_on_6():
    offers = get_price_offers("demo", "all_on_6", unit="jaw")
    assert len(offers) == 3
    assert min(o.total for o in offers) == 398000


def test_get_price_offers_one_stage():
    offers = get_price_offers("demo", "one_stage", unit="one_tooth")
    assert len(offers) == 3
    assert any(o.total == 96500 for o in offers)


def test_group_overview_four_protocol_buttons():
    from core.price_group_overview import group_overview_quick_replies

    replies = group_overview_quick_replies("demo")
    assert len(replies) == 5
    labels = [r["label"] for r in replies]
    refs = [r["ref"] for r in replies]
    assert "Классическая" in labels
    assert "All-on-4" in labels
    assert "price:classic" in refs
    assert "price:all_on_4" in refs


def test_render_append_contains_amounts_and_stages():
    offers = get_price_offers("demo", "all_on_4", unit="jaw")
    text = render_price_offers_append(offers)
    assert text
    assert "318 000" in text
    assert "220 800" in text
    assert "Nobel Biocare" in text
    assert "Входит" in text


def test_build_append_for_classic():
    text, meta = build_price_append_for_lookup(
        client_id="demo",
        service_id="classic",
        q="сколько стоит один имплант под ключ",
    )
    assert text
    assert "76 200" in text
    assert "54 200" in text
    assert meta.get("price_offers_applied") is True


def test_generic_implant_triggers_unit_clarify():
    q = "Сколько стоит имплантация?"
    assert is_generic_implant_price_query(q)
    assert should_offer_unit_clarify(q, {"matched_service_id": None, "is_confident": False})


def test_explicit_all_on_skips_clarify():
    q = "Сколько стоит all-on-4?"
    assert not is_generic_implant_price_query(q)
    assert not should_offer_unit_clarify(q, {})


def test_unit_clarify_answer_has_protocol_lines():
    answer = build_unit_clarify_answer("demo")
    assert answer
    assert "76 200" in answer
    assert "318 000" in answer
    assert "398 000" in answer
    assert "протокол" in answer.lower()
    assert "По протоколам" in answer


def test_generic_implant_typo_triggers_overview():
    q = "Сколько стоит импланатция?"
    assert is_generic_implant_price_query(q)
    assert should_offer_unit_clarify(q, {"matched_service_id": "classic", "is_confident": True})


def test_full_jaw_implant_price_query():
    q = "Сколько стоит имплантация на челюсть?"
    assert is_full_jaw_implant_price_query(q)
    assert resolve_implant_group_overview(q) == "full_jaw"
    assert not is_generic_implant_price_query(q)


def test_all_on_4_only_not_full_jaw_overview():
    q = "Сколько стоит All-on-4 на челюсть?"
    assert not is_full_jaw_implant_price_query(q)
    assert not is_upper_jaw_restoration_price_query(q)
    assert resolve_implant_group_overview(q) is None


def test_upper_jaw_price_routes_to_upper_jaw_group():
    for question in (
        "сколько стоит вся верхняя челюсть",
        "имплантация верхней челюсти цена",
        "сколько стоит восстановить верхнюю челюсть",
        "сколько стоит если нет зубов на верхней челюсти",
    ):
        assert is_upper_jaw_restoration_price_query(question)
        assert resolve_implant_group_overview(question) == "upper_jaw"
        assert not is_full_jaw_implant_price_query(question)


def test_full_arch_turnkey_price_query():
    q = "Сколько стоит вставить все зубы под ключ?"
    assert is_full_jaw_implant_price_query(q)
    assert resolve_implant_group_overview(q) == "full_jaw"


def test_one_stage_price_not_group_overview():
    q = "Удалить зуб и сразу поставить имплант — сколько стоит?"
    assert is_one_stage_price_query(q)
    assert resolve_implant_group_overview(q) is None


def test_crown_inclusion_is_content_not_price_lookup():
    from query_selector import price_rules_hint, select_price_service_route

    q = "Коронка отдельно оплачивается?"
    assert is_crown_inclusion_content_query(q)
    assert price_rules_hint(q) is None
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    assert route.get("mode") == "other"


def test_price_offer_meta_in_ask_response_meta(monkeypatch):
    """price_ref path must expose price_offers telemetry in response meta (not only answer text)."""
    import uuid

    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-price-offer-meta-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={
            "q": "Сколько стоит один имплант под ключ с коронкой?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body, dict)
    meta = body.get("meta") or {}
    assert meta.get("duplicate_short_circuit") is not True
    assert meta.get("price_offers_applied") is True
    ids = meta.get("price_offer_ids") or []
    assert "classic.one_tooth.implantium" in ids
    assert "classic.one_tooth.impro" in ids
    assert meta.get("price_offer_unit") == "one_tooth"
