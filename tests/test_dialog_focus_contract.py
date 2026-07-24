from __future__ import annotations

import uuid

import pytest

from contracts.dialog_focus import DialogFocusGrayOutput
from core.dialog_focus import build_dialog_focus_decision, dialog_focus_for_turn
from core.routing_loader import THRESHOLDS
from session import mem_add_user, mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def _set_focus(sid: str, service_id: str = "classic") -> None:
    _seed_target_runtime_state(
        sid,
        last_service_id=service_id,
        last_topic="implantation",
        service_focus_set_at_turn=0,
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
    assert focus.source == "target_runtime_state"
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


def test_dialog_focus_gray_llm_adds_general_rewrite(monkeypatch):
    sid = f"df-contract-gray-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "classic")

    def _fake_gray(q, **kwargs):
        assert q == "А мне подойдет?"
        assert kwargs["focus_service_id"] == "classic"
        return DialogFocusGrayOutput(
            kind="follow_up",
            attribute="general",
            query_rewrite="подойдет ли классическая имплантация пациенту",
            confidence=0.86,
        )

    monkeypatch.setattr("core.dialog_focus_llm.classify_dialog_focus_gray_zone", _fake_gray)

    focus = build_dialog_focus_decision("А мне подойдет?", sid=sid, client_id="demo")

    assert focus.attribute == "general"
    assert focus.resolved_service_id == "classic"
    assert focus.query_rewrite == "подойдет ли классическая имплантация пациенту"
    assert focus.used_llm is True
    assert focus.source == "llm_gray"


def test_dialog_focus_gray_llm_skips_bare_ack(monkeypatch):
    sid = f"df-contract-ack-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _set_focus(sid, "classic")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("gray LLM must not run for bare acknowledgement")

    monkeypatch.setattr(
        "core.dialog_focus_llm.classify_dialog_focus_gray_zone",
        _raise_if_called,
    )

    focus = build_dialog_focus_decision("да", sid=sid, client_id="demo")

    assert focus.attribute == "overview"
    assert focus.used_llm is False
    assert focus.query_rewrite is None


def test_dialog_focus_for_turn_prefers_cached_ctx(monkeypatch):
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": {
                "focus_service_id": "classic",
                "focus_topic": "implantation",
                "focus_label": "Классическая имплантация",
                "focus_turn_age": 0,
                "attribute": "general",
                "explicit_topic_change": False,
                "resolved_service_id": "classic",
                "source": "llm_gray",
                "used_llm": True,
                "confidence": 0.86,
                "reason": "test",
                "query_rewrite": "подойдет ли классическая имплантация пациенту",
            }
        }

        def _raise_if_recomputed(*args, **kwargs):
            raise AssertionError("cached dialog focus should be reused")

        monkeypatch.setattr("core.dialog_focus.build_dialog_focus_decision", _raise_if_recomputed)
        focus = dialog_focus_for_turn("А мне подойдет?", sid="sid", client_id="demo")

    assert focus is not None
    assert focus.resolved_service_id == "classic"
    assert focus.query_rewrite == "подойдет ли классическая имплантация пациенту"


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
    for _ in range(int(THRESHOLDS.follow_up.max_service_focus_turn_age) + 1):
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
