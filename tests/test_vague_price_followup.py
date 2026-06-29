"""Vague price follow-up routing: session before weak catalog price-token matches."""
from __future__ import annotations

import uuid

import pytest

from core.price_followup import (
    is_vague_price_followup,
    price_query_has_explicit_service_object,
)
from core.pricebook_loader import load_pricebook_service
from core.service_followup import is_short_attribute_followup
from query_selector import match_service_from_catalog, select_price_service_route
from session import get_last_subject, mem_add_user, mem_reset, set_last_catalog_service, set_last_subject


def test_vague_price_not_short_attribute_followup():
    assert not is_short_attribute_followup("А что по ценам?")
    assert not is_short_attribute_followup("А сколько стоит?")


def test_vague_price_phrases_detected():
    assert is_vague_price_followup("А что по ценам?")
    assert is_vague_price_followup("А сколько стоит?")
    assert not price_query_has_explicit_service_object("А что по ценам?")
    assert not price_query_has_explicit_service_object("А сколько стоит?")


def test_explicit_service_price_not_vague():
    assert not is_vague_price_followup("Сколько стоит обеливание?")
    assert price_query_has_explicit_service_object("Сколько стоит обеливание?")


def test_bare_vague_price_clarifies_not_all_on_4():
    sid = f"vague-bare-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    route = select_price_service_route("А что по ценам?", client_id="demo", sid=sid)
    assert route.get("mode") == "clarify"
    assert route.get("fallback_reason") == "price_clarify_no_context"


def test_one_tooth_patient_situation_vague_price_without_last_subject():
    """Инцидент: content one-tooth → vague price без last_subject (Slice 3)."""
    from core.patient_situation_session import persist_patient_situation_after_turn

    sid = f"vague-ps-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = "У меня нет одного зуба, что лучше?"
    persist_patient_situation_after_turn(sid, turn1)
    mem_add_user(sid, turn1)
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "classic"
    assert route.get("matched_service_id") != "all_on_4"


def test_price_only_lemma_weak_not_confident():
    m = match_service_from_catalog("А сколько стоит?", client_id="demo")
    assert m.get("match_channel") == "lemma_weak"
    assert m.get("is_confident") is False


def test_one_tooth_context_vague_price_uses_session():
    sid = f"vague-classic-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация одного зуба",
    )
    route = select_price_service_route("А что по ценам?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "classic"
    assert route.get("matched_service_id") != "all_on_4"


def test_zygomatic_context_vague_price_uses_session():
    sid = f"vague-zygo-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="zygomatic_implants",
        topic="implantation",
        label="Зигоматические импланты",
    )
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "zygomatic_implants"
    pb = load_pricebook_service("demo", "zygomatic_implants")
    assert pb is not None
    assert pb.price is not None
    assert pb.price.value == 420_000


def test_zygomatic_pricebook_has_demo_price():
    pb = load_pricebook_service("demo", "zygomatic_implants")
    assert pb is not None
    assert pb.price is not None
    assert pb.price.price_type == "from"
    assert pb.price.value == 420_000


def test_all_on_4_context_vague_price_stays_all_on_4():
    sid = f"vague-a4-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="all_on_4",
        topic="implantation",
        label="All-on-4",
    )
    set_last_catalog_service(sid, "all_on_4")
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "all_on_4"


def test_e2e_multi_turn_vague_price_after_zygomatic_content(monkeypatch):
    """Инцидент: classic → jaw overview → zygomatic content → vague price (не All-on-4)."""
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"e2e-vague-mt-{uuid.uuid4().hex[:12]}"
    turns_before_price = [
        "сколько стоит поставить один имплант?",
        "Сколько стоит имплантация всей челюсти?",
        "расскажите про скуловую имплантацию",
    ]
    for i, q in enumerate(turns_before_price):
        resp = client.post("/ask", json={"q": q, "sid": sid, "client_id": "demo"})
        assert resp.status_code == 200
        if i == 2:
            meta3 = (resp.get_json() or {}).get("meta") or {}
            assert meta3.get("doc_id") == "implantation__service__zygomatic_implants"

    sub = get_last_subject(sid)
    assert sub is not None
    assert sub.get("service_id") == "zygomatic_implants"
    assert sub.get("last_route") == "catalog_md_first"

    resp = client.post(
        "/ask",
        json={"q": "А сколько они стоят?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    meta = body.get("meta") or {}
    assert meta.get("matched_service_id") == "zygomatic_implants"
    answer = body.get("answer") or ""
    assert "420 000" in answer or "420000" in answer.replace(" ", "")
    assert "318 000" not in answer
    assert "all-on-4" not in answer.lower()
