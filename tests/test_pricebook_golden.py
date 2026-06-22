from __future__ import annotations

import pytest

from core.price_answer_assembler import (
    assemble_price_answer,
    followups_to_quick_replies,
    plan_for_service,
)
from core.price_offers import build_price_answer_for_lookup, get_price_offers
from core.pricebook_loader import load_pricebook_service


@pytest.fixture
def demo_client():
    return "demo"


def test_s1_whitening_simple_price(demo_client):
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="professional_whitening",
        q="Сколько стоит отбеливание?",
    )
    assert answer
    assert "18 000" in answer
    assert meta.get("pricebook_applied") is True
    assert "10%" in answer or meta.get("pricebook_promo_applied")


def test_s2_pulpitis_with_followup(demo_client):
    entry = load_pricebook_service(demo_client, "pulpitis")
    assert entry
    answer, meta = assemble_price_answer(
        client_id=demo_client,
        service_id="pulpitis",
        offers=[],
        entry=entry,
    )
    assert answer
    assert "12 000" in answer
    quick = followups_to_quick_replies(entry)
    assert any("входит" in q["label"].lower() for q in quick)


def test_s4_classic_three_brands_and_consult_fact(demo_client):
    offers = get_price_offers(demo_client, "classic", unit="one_tooth")
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="classic",
        q="Сколько стоит классическая имплантация?",
    )
    assert answer
    assert "76 200" in answer
    assert "85 200" in answer
    assert "101 200" in answer
    assert "консульта" in answer.lower()
    assert meta.get("pricebook_applied") is True
    assert meta.get("price_offers_applied") is True


def test_s5_all_on_4_jaw(demo_client):
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="all_on_4",
        q="Сколько стоит All-on-4 на челюсть?",
    )
    assert answer
    assert "318 000" in answer
    assert meta.get("pricebook_applied") is True


def test_all_on_4_compact_first_screen(demo_client):
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="all_on_4",
        q="Сколько стоит All-on-4?",
    )
    assert answer
    assert "318 000" in answer
    assert "368 000" in answer
    assert meta.get("pricebook_scenario") == "complex"
    assert "Актуальные пакеты" not in answer
    assert "Точные цены" not in answer
    assert "**Оплата по этапам**" not in answer
    assert "**Входит" not in answer
    assert "консульта" in answer.lower()


def test_followups_hide_active_aspect(demo_client):
    entry = load_pricebook_service(demo_client, "all_on_4")
    assert entry
    all_refs = [q["ref"] for q in followups_to_quick_replies(entry)]
    stages_refs = [q["ref"] for q in followups_to_quick_replies(entry, active_aspect="stages")]
    assert "price:all_on_4/stages" in all_refs
    assert "price:all_on_4/stages" not in stages_refs
    assert "price:all_on_4/includes" in stages_refs
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="all_on_4",
        q="",
        aspect="stages",
    )
    assert answer
    assert "220 800" in answer
    assert meta.get("pricebook_aspect") == "stages"
    assert "318 000" not in answer


def test_all_on_4_aspect_includes_only(demo_client):
    answer, meta = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="all_on_4",
        q="",
        aspect="includes",
    )
    assert answer
    assert "**Входит" in answer
    assert meta.get("pricebook_aspect") == "includes"
    assert "318 000" not in answer


def test_complex_plan_no_stages_in_first_blocks(demo_client):
    entry = load_pricebook_service(demo_client, "all_on_4")
    assert entry
    plan = plan_for_service(entry)
    assert "stages" not in plan.blocks
    assert "includes" not in plan.blocks


def test_s3_group_overview_from_manifest(demo_client):
    from core.price_group_overview import build_group_overview_answer

    answer, quick, meta = build_group_overview_answer(demo_client, group_id="implantation")
    assert answer
    assert "76 200" in answer
    assert "318 000" in answer
    assert meta.get("pricebook_scenario") == "overview"
    assert len(quick) == 5
    assert quick[0]["label"] == "Классическая"


def test_s3_full_jaw_overview_from_manifest(demo_client):
    from core.price_group_overview import build_group_overview_answer

    answer, quick, meta = build_group_overview_answer(demo_client, group_id="full_jaw")
    assert answer
    assert "318 000" in answer
    assert "398 000" in answer
    assert "76 200" not in answer
    assert meta.get("pricebook_group_id") == "full_jaw"
    assert len(quick) == 2


def test_merge_price_quick_replies_fact_button_not_duplicated(demo_client):
    from core.price_answer_assembler import merge_price_quick_replies
    from core.pricebook_loader import load_pricebook_service

    entry = load_pricebook_service(demo_client, "classic")
    assert entry
    quick = merge_price_quick_replies(entry, demo_client)
    labels = [r["label"] for r in quick]
    refs = [r["ref"] for r in quick]
    assert labels.count("Что будет на консультации") == 1
    assert "clinic__info__consultation.md#korotko" in refs
    assert "price:classic/stages" in refs


def test_merge_price_quick_replies_hides_active_and_used_refs(demo_client):
    from core.price_answer_assembler import hide_navigated_quick_replies, merge_price_quick_replies
    from core.pricebook_loader import load_pricebook_service

    entry = load_pricebook_service(demo_client, "all_on_4")
    assert entry
    quick = merge_price_quick_replies(
        entry,
        demo_client,
        active_aspect="stages",
        active_ref="price:all_on_4/stages",
        exclude_refs={
            "price:all_on_4/stages",
            "clinic__info__consultation.md#korotko",
        },
    )
    refs = [r["ref"] for r in quick]
    assert "price:all_on_4/stages" not in refs
    assert "clinic__info__consultation.md#korotko" not in refs
    assert "price:all_on_4/includes" in refs

    filtered = hide_navigated_quick_replies(
        [{"label": "x", "ref": "doc.md#korotko"}],
        active_ref="doc.md#korotko",
    )
    assert filtered == []


def test_price_answer_hides_used_nav_refs_in_session(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    import uuid

    from app import app

    client = app.test_client()
    sid = f"test-nav-used-{uuid.uuid4().hex[:12]}"
    client.post("/ask", json={"sid": sid, "client_id": "demo", "ref": "price:all_on_4", "q": ""})
    resp = client.post(
        "/ask",
        json={"sid": sid, "client_id": "demo", "ref": "price:all_on_4/stages", "q": ""},
    )
    body = resp.get_json()
    refs = [r.get("ref") for r in body.get("quick_replies") or []]
    assert "price:all_on_4/stages" not in refs

    resp2 = client.post(
        "/ask",
        json={"sid": sid, "client_id": "demo", "ref": "price:all_on_4", "q": ""},
    )
    refs2 = [r.get("ref") for r in resp2.get_json().get("quick_replies") or []]
    assert "price:all_on_4/stages" not in refs2


def test_no_duplicate_llm_boilerplate_on_offers_path(demo_client):
    answer, _ = build_price_answer_for_lookup(
        client_id=demo_client,
        service_id="all_on_4",
        q="price:all_on_4",
    )
    assert answer
    assert "Стоимость восстановления" not in answer
