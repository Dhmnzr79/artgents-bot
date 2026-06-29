from __future__ import annotations

import uuid

from core.dialog_focus import build_dialog_focus_decision
from core.routing_loader import THRESHOLDS
from session import mem_add_user, mem_reset, set_last_subject


def _set_focus(sid: str, service_id: str = "classic") -> None:
    set_last_subject(
        sid,
        service_id=service_id,
        topic="implantation",
        label="Классическая имплантация" if service_id == "classic" else "Скуловая имплантация",
        last_route="catalog_md_first",
    )


def test_dialog_focus_contract_carries_last_subject_for_pronoun_price():
    sid = f"df-contract-price-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "zygomatic_implants")

    focus = build_dialog_focus_decision(
        "А сколько они стоят?",
        sid=sid,
        client_id="demo",
    )

    assert focus.focus_service_id == "zygomatic_implants"
    assert focus.resolved_service_id == "zygomatic_implants"
    assert focus.attribute == "price"
    assert focus.explicit_topic_change is False
    assert focus.source == "last_subject"
    assert focus.used_llm is False


def test_dialog_focus_contract_common_attribute_followups():
    sid = f"df-contract-attrs-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "classic")

    cases = {
        "Кто делает?": "doctor",
        "Гарантия какая?": "warranty",
        "Сколько это длится?": "duration",
        "Что входит?": "included",
        "Больно?": "pain",
    }
    for q, attr in cases.items():
        focus = build_dialog_focus_decision(q, sid=sid, client_id="demo")
        assert focus.resolved_service_id == "classic"
        assert focus.attribute == attr
        assert focus.explicit_topic_change is False


def test_dialog_focus_contract_detects_explicit_topic_change():
    sid = f"df-contract-topic-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "classic")

    focus = build_dialog_focus_decision(
        "Сколько стоят виниры?",
        sid=sid,
        client_id="demo",
    )

    assert focus.focus_service_id == "classic"
    assert focus.resolved_service_id == "veneers"
    assert focus.attribute == "price"
    assert focus.explicit_topic_change is True
    assert focus.source == "explicit_service"


def test_dialog_focus_contract_uses_explicit_service_without_previous_focus():
    sid = f"df-contract-explicit-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    focus = build_dialog_focus_decision(
        "Сколько стоят виниры?",
        sid=sid,
        client_id="demo",
    )

    assert focus.focus_service_id is None
    assert focus.resolved_service_id == "veneers"
    assert focus.attribute == "price"
    assert focus.explicit_topic_change is False
    assert focus.source == "explicit_service"


def test_dialog_focus_contract_ignores_stale_subject():
    sid = f"df-contract-stale-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "classic")
    for _ in range(int(THRESHOLDS.follow_up.max_subject_turn_age) + 1):
        mem_add_user(sid, "другой вопрос")

    focus = build_dialog_focus_decision(
        "Кто делает?",
        sid=sid,
        client_id="demo",
    )

    assert focus.focus_service_id is None
    assert focus.resolved_service_id is None
    assert focus.attribute == "doctor"
    assert focus.source == "none"
