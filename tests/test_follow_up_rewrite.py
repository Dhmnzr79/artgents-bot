"""Follow-up rewrite unit tests (PRODUCT_WORK_PLAN stage 4a)."""

from __future__ import annotations

import pytest

from contracts.dialog_focus import DialogFocusDecision
from core.follow_up_rewrite import (
    is_explicit_topic_change,
    prepare_follow_up_turn,
    rewrite_follow_up_query,
    resolve_focus_from_turn,
)
from session import mem_get, mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def test_rewrite_warranty_from_focus_label():
    focus = {
        "service_id": "classic",
        "topic": "implantation",
        "label": "классическую имплантацию",
        "last_route": "retrieval_chunk",
    }
    out = rewrite_follow_up_query("а гарантия?", focus)
    assert out == "гарантия на классическую имплантацию"


def test_rewrite_pain_and_payment():
    focus = {
        "service_id": "classic",
        "topic": "implantation",
        "label": "классическую имплантацию",
        "last_route": "retrieval_chunk",
    }
    assert rewrite_follow_up_query("а больно?", focus) == "больно ли классическую имплантацию"
    assert (
        rewrite_follow_up_query("рассрочка?", focus)
        == "оплата и рассрочка классическую имплантацию"
    )


def test_rewrite_included_from_focus_label():
    focus = {
        "service_id": "classic",
        "topic": "implantation",
        "label": "классическую имплантацию",
        "last_route": "retrieval_chunk",
    }
    assert rewrite_follow_up_query("Что входит?", focus) == "что входит в классическую имплантацию"


def test_prepare_follow_up_turn_uses_dialog_focus_ctx_without_session_subject():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": DialogFocusDecision(
                focus_service_id="classic",
                focus_topic="implantation",
                focus_label="Классическая имплантация",
                focus_turn_age=0,
                attribute="included",
                explicit_topic_change=False,
                resolved_service_id="classic",
                source="target_runtime_state",
                used_llm=False,
                confidence=0.8,
                reason="test",
            ).model_dump()
        }
        ctx = prepare_follow_up_turn("Что входит?", {}, client_id="demo")
    assert ctx is not None
    assert ctx.focus["service_id"] == "classic"
    assert ctx.rewritten_query == "что входит в Классическая имплантация"


def test_prepare_follow_up_turn_uses_general_dialog_focus_rewrite():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": DialogFocusDecision(
                focus_service_id="classic",
                focus_topic="implantation",
                focus_label="Классическая имплантация",
                focus_turn_age=0,
                attribute="general",
                explicit_topic_change=False,
                resolved_service_id="classic",
                source="llm_gray",
                used_llm=True,
                confidence=0.86,
                reason="test",
                query_rewrite="подойдет ли классическая имплантация пациенту",
            ).model_dump()
        }
        ctx = prepare_follow_up_turn("А мне подойдет?", {}, client_id="demo")
    assert ctx is not None
    assert ctx.focus["service_id"] == "classic"
    assert ctx.rewritten_query == "подойдет ли классическая имплантация пациенту"


def test_prepare_follow_up_turn_with_session_focus():
    sid = "test-follow-up-focus"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
    )
    st = mem_get(sid)
    ctx = prepare_follow_up_turn("а гарантия?", st, client_id="demo")
    assert ctx is not None
    assert ctx.follow_up_mode is True
    assert "гарантия" in ctx.rewritten_query
    assert ctx.focus["service_id"] == "classic"


def test_prepare_blocks_explicit_topic_change():
    sid = "test-follow-up-topic-change"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
    )
    st = mem_get(sid)
    assert prepare_follow_up_turn("сколько стоят виниры?", st, client_id="demo") is None
    assert is_explicit_topic_change(
        "сколько стоят виниры?",
        {"service_id": "classic"},
        client_id="demo",
    )


def test_resolve_focus_from_turn_doc_id():
    focus = resolve_focus_from_turn(
        client_id="demo",
        doc_id="implantation__service__classic",
        matched_service_id=None,
        route="catalog_md_first",
        meta={"topic": "implantation"},
    )
    assert focus is not None
    assert focus["service_id"] == "classic"
    assert "имплантац" in focus["label"].lower()
