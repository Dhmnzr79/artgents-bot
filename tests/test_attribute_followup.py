"""Unit tests for vague attribute follow-up detection."""

from __future__ import annotations

import uuid

from core.answer_planner import build_answer_plan
from core.attribute_followup import (
    catalog_match_is_authoritative,
    detect_vague_attribute_kinds,
    is_vague_attribute_followup,
    query_has_explicit_service_object,
)
from core.price_followup import is_vague_price_followup
from session import mem_reset, set_last_subject


def test_vague_price_via_attribute_layer():
    assert is_vague_attribute_followup("А что по ценам?", "price")
    assert is_vague_price_followup("А что по ценам?")


def test_vague_duration_pain_warranty():
    assert is_vague_attribute_followup("А долго?", "duration")
    assert is_vague_attribute_followup("Больно?", "pain")
    assert is_vague_attribute_followup("Гарантия какая?", "warranty")
    assert "duration" in detect_vague_attribute_kinds("А долго?")


def test_explicit_service_not_vague():
    assert not is_vague_attribute_followup(
        "Сколько длится классическая имплантация?", "duration"
    )
    assert query_has_explicit_service_object(
        "Сколько длится классическая имплантация?", kind="duration"
    )


def test_weak_catalog_not_authoritative_for_vague_duration():
    m = {
        "matched_service_id": "all_on_4",
        "match_channel": "lemma_weak",
        "is_confident": True,
        "containment_eligible": False,
    }
    assert not catalog_match_is_authoritative(m, "А долго?")


def test_planner_session_first_for_vague_duration():
    sid = f"vague-dur-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
    )
    plan = build_answer_plan(
        q="А долго?",
        sid=sid,
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert plan.service_id == "classic"
    assert "subject_carry" in plan.plan_reason


def test_doctor_detected_as_attribute_kind_not_aspect():
    kinds = detect_vague_attribute_kinds("Кто делает?")
    assert "doctor" in kinds
    assert "duration" not in kinds
