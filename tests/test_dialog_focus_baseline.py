"""Dialog focus baseline/golden tests.

Stage 0 only: describe the desired multi-turn focus behavior before changing
runtime routing. Known gaps are marked xfail so the suite can stay green while
the target is explicit.
"""

from __future__ import annotations

import uuid

import pytest

from contracts.decision_frame import DecisionFrame
from core.attribute_followup import detect_vague_attribute_kinds
from core.price_followup import (
    is_vague_price_followup,
    price_query_has_explicit_service_object,
)
from core.pricebook_loader import load_pricebook_service
from core.routing_loader import THRESHOLDS
from query_selector import select_price_service_route
from source_routing import route_source
from session import mem_add_user, mem_get, mem_reset, set_last_subject


def _content_frame(*, topic: str = "implantation") -> DecisionFrame:
    return DecisionFrame(
        route_intent="content",
        service_topic=topic,
        service_id=None,
        query_mode="specific",
        confidence={"intent": 0.9, "topic": 0.9, "service": 0.0, "query_mode": 0.9},
        needs_clarification=False,
    )


def _set_focus(
    sid: str,
    *,
    service_id: str,
    topic: str = "implantation",
    label: str | None = None,
) -> None:
    set_last_subject(
        sid,
        service_id=service_id,
        topic=topic,
        label=label or service_id.replace("_", " "),
        last_route="catalog_md_first",
    )


def test_baseline_singular_price_followup_uses_last_focus():
    sid = f"df-price-singular-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants", label="Скуловая имплантация")

    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)

    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "zygomatic_implants"
    pb = load_pricebook_service("demo", "zygomatic_implants")
    assert pb is not None
    assert pb.price is not None
    assert pb.price.value == 420_000


@pytest.mark.xfail(
    reason="Stage 0 baseline: pronoun/plural price follow-up is not unified yet.",
    strict=False,
)
def test_target_pronoun_plural_price_followup_uses_last_focus():
    sid = f"df-price-pronoun-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="zygomatic_implants", label="Скуловая имплантация")

    q = "А сколько они стоят?"

    assert is_vague_price_followup(q)
    assert not price_query_has_explicit_service_object(q)
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
    _set_focus(sid, service_id="classic", label="Классическая имплантация")

    route = select_price_service_route(
        "Сколько стоят виниры?",
        client_id="demo",
        sid=sid,
        intent_override="price_lookup",
    )

    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "veneers"
    assert route.get("matched_service_id") != "classic"


def test_baseline_vague_doctor_followup_uses_last_focus():
    sid = f"df-doctor-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="classic", label="Классическая имплантация")

    sr = route_source(
        "Кто делает?",
        sid=sid,
        client_id="demo",
        decision=_content_frame(),
        app_intent="content",
    )

    payload = sr.payload.get("doctor") if isinstance(sr.payload, dict) else None
    assert sr.source == "doctor"
    assert isinstance(payload, dict)
    assert payload.get("matched_service_id") == "classic"


def test_baseline_vague_attribute_kinds_cover_common_followups():
    assert "warranty" in detect_vague_attribute_kinds("А что по гарантиям?")
    assert "duration" in detect_vague_attribute_kinds("Сколько это длится?")
    assert "doctor" in detect_vague_attribute_kinds("Кто делает?")
    assert "included" in detect_vague_attribute_kinds("Что входит?")


def test_baseline_stale_focus_is_not_used_for_vague_doctor():
    sid = f"df-stale-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, service_id="classic", label="Классическая имплантация")

    for _ in range(int(THRESHOLDS.follow_up.max_subject_turn_age) + 1):
        mem_add_user(sid, "другой вопрос")
    assert int(mem_get(sid).get("subject_turn_age") or 0) > int(
        THRESHOLDS.follow_up.max_subject_turn_age
    )

    sr = route_source(
        "Кто делает?",
        sid=sid,
        client_id="demo",
        decision=_content_frame(),
        app_intent="content",
    )

    payload = sr.payload.get("doctor") if isinstance(sr.payload, dict) else None
    if isinstance(payload, dict):
        assert payload.get("matched_service_id") != "classic"
