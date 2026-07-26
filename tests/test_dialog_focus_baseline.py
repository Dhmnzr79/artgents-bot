from __future__ import annotations

import uuid

from core.attribute_followup import detect_vague_attribute_kinds
from core.dialog_focus import build_dialog_focus_decision
from core.target_client_data import load_target_client_data, match_service_from_target_catalog
from session import mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def _set_focus(
    sid: str,
    *,
    service_id: str,
    topic: str = "implantation",
) -> None:
    _seed_target_runtime_state(
        sid,
        last_service_id=service_id,
        last_topic=topic,
        service_focus_set_at_turn=0,
    )


def _offer_amount_for_service(client_id: str, service_id: str) -> int:
    bundle = load_target_client_data(client_id).bundle
    for offer in bundle.offers:
        if offer.service_id == service_id and offer.active:
            price = offer.price
            if price.min_amount is not None:
                return int(price.min_amount)
            if price.amount is not None:
                return int(price.amount)
    raise AssertionError(f"no active offer for {service_id}")


def test_baseline_singular_price_followup_uses_last_focus():
    sid = f"df-price-singular-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants")

    focus = build_dialog_focus_decision("А сколько стоит?", sid=sid, client_id="demo")
    assert focus.resolved_service_id == "zygomatic_implants"
    assert focus.attribute == "price"
    assert _offer_amount_for_service("demo", "zygomatic_implants") == 420_000


def test_target_pronoun_plural_price_followup_uses_last_focus():
    sid = f"df-price-pronoun-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants")

    q = "А сколько они стоят?"

    focus = build_dialog_focus_decision(q, sid=sid, client_id="demo")
    assert focus.attribute == "price"
    assert focus.resolved_service_id == "zygomatic_implants"


def test_baseline_explicit_new_service_does_not_use_previous_focus():
    sid = f"df-topic-change-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="classic")

    match = match_service_from_target_catalog(
        "Сколько стоят виниры?",
        client_id="demo",
    )
    assert match.get("matched_service_id") == "veneers"
    assert match.get("matched_service_id") != "classic"


def test_baseline_vague_attribute_kinds_cover_common_followups():
    assert "warranty" in detect_vague_attribute_kinds("А что по гарантиям?")
    assert "duration" in detect_vague_attribute_kinds("Сколько это длится?")
    assert "doctor" in detect_vague_attribute_kinds("Кто делает?")
    assert "included" in detect_vague_attribute_kinds("Что входит?")
