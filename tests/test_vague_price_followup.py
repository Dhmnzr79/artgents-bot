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
from session import mem_add_user, mem_reset, set_last_catalog_service
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


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
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
    )
    route = select_price_service_route("А что по ценам?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "classic"
    assert route.get("matched_service_id") != "all_on_4"


def test_zygomatic_context_vague_price_uses_session():
    sid = f"vague-zygo-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="zygomatic_implants",
        last_topic="implantation",
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
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
    )
    set_last_catalog_service(sid, "all_on_4")
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "all_on_4"


def test_vague_price_after_zygomatic_target_runtime_state():
    """После zygomatic в target_runtime_state vague price не уходит в All-on-4 (offline)."""
    sid = f"vague-zygo-mt-{uuid.uuid4().hex[:12]}"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="zygomatic_implants",
        last_topic="implantation",
    )
    route = select_price_service_route("А сколько они стоят?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "zygomatic_implants"
    assert route.get("matched_service_id") != "all_on_4"
