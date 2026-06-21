"""Follow-up rewrite unit tests (PRODUCT_WORK_PLAN stage 4a)."""

from __future__ import annotations

from core.follow_up_rewrite import (
    is_explicit_topic_change,
    prepare_follow_up_turn,
    rewrite_follow_up_query,
    resolve_focus_from_turn,
)
from session import clear_last_subject, mem_get, set_last_subject


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


def test_prepare_follow_up_turn_with_session_focus():
    sid = "test-follow-up-focus"
    clear_last_subject(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="классическую имплантацию",
        last_route="retrieval_chunk",
    )
    st = mem_get(sid)
    ctx = prepare_follow_up_turn("а гарантия?", st, client_id="demo")
    assert ctx is not None
    assert ctx.follow_up_mode is True
    assert "гарантия" in ctx.rewritten_query
    assert ctx.focus["service_id"] == "classic"


def test_prepare_blocks_explicit_topic_change():
    sid = "test-follow-up-topic-change"
    clear_last_subject(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="классическую имплантацию",
        last_route="retrieval_chunk",
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
