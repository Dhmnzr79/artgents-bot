from __future__ import annotations

import uuid

from core.attribute_followup import detect_vague_attribute_kinds
from core.dialog_focus import build_dialog_focus_decision
from core.pricebook_loader import load_pricebook_service
from query_selector import select_price_service_route
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


def test_baseline_singular_price_followup_uses_last_focus():
    sid = f"df-price-singular-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants")

    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)

    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "zygomatic_implants"
    pb = load_pricebook_service("demo", "zygomatic_implants")
    assert pb is not None
    assert pb.price is not None
    assert pb.price.value == 420_000


def test_target_pronoun_plural_price_followup_uses_last_focus():
    sid = f"df-price-pronoun-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants")

    q = "А сколько они стоят?"

    focus = build_dialog_focus_decision(q, sid=sid, client_id="demo")
    assert focus.attribute == "price"
    assert focus.resolved_service_id == "zygomatic_implants"
    route = select_price_service_route(
        q,
        client_id="demo",
        sid=sid,
        intent_override="price_lookup",
    )
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "zygomatic_implants"


def test_baseline_explicit_new_service_does_not_use_previous_focus():
    sid = f"df-topic-change-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="classic")

    route = select_price_service_route(
        "Сколько стоят виниры?",
        client_id="demo",
        sid=sid,
        intent_override="price_lookup",
    )

    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "veneers"
    assert route.get("matched_service_id") != "classic"


def test_baseline_vague_attribute_kinds_cover_common_followups():
    assert "warranty" in detect_vague_attribute_kinds("А что по гарантиям?")
    assert "duration" in detect_vague_attribute_kinds("Сколько это длится?")
    assert "doctor" in detect_vague_attribute_kinds("Кто делает?")
    assert "included" in detect_vague_attribute_kinds("Что входит?")
