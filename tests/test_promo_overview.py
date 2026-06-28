from __future__ import annotations

from core.promo_overview import (
    active_promo_overview_items,
    build_promo_overview_payload,
    is_direct_promo_question,
)


def test_direct_promo_question_detection():
    assert is_direct_promo_question("Есть акции?")
    assert is_direct_promo_question("Есть скидка на All-on-4?")
    assert not is_direct_promo_question("Сколько стоит All-on-4?")


def test_promo_overview_lists_active_configured_promos():
    payload = build_promo_overview_payload(
        sid="promo-1",
        client_id="demo",
        q="Есть акции?",
    )

    assert payload is not None
    answer = payload["answer"]
    meta = payload["meta"]
    assert "10%" in answer
    assert "free_implant_consult" in meta["marketing_promos_applied"]
    assert "professional_whitening_discount" in meta["marketing_promos_applied"]
    assert meta["intent"] == "promo_overview"
    assert payload["cta"] is None
    assert all((q.get("ref") or "").startswith("price:") for q in payload["quick_replies"])
    refs = [q["ref"] for q in payload["quick_replies"]]
    assert "price:professional_whitening" in refs


def test_discount_question_excludes_free_consult_promo():
    items = active_promo_overview_items(
        client_id="demo",
        q="Есть скидки?",
    )
    ids = [item.fact.id for item in items]

    assert "free_implant_consult" not in ids
    assert "professional_whitening_discount" in ids


def test_service_specific_discount_filters_promos():
    payload = build_promo_overview_payload(
        sid="promo-2",
        client_id="demo",
        q="Есть скидка на All-on-4?",
    )

    assert payload is not None
    applied = payload["meta"]["marketing_promos_applied"]
    assert "all_on_same_day_discount" in applied
    assert "professional_whitening_discount" not in applied
    assert "free_implant_consult" not in applied
