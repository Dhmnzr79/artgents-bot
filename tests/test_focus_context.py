"""Focus context: clear_focus_context + price-turn last_subject (4a/4b)."""

from __future__ import annotations

from core.follow_up_rewrite import persist_focus_from_service_turn
from session import (
    clear_focus_context,
    get_last_aspect,
    get_last_subject,
    mem_reset,
    set_last_aspect,
    set_last_subject,
)


def test_clear_focus_context_clears_subject_and_aspect():
    sid = "test-clear-focus"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
    )
    set_last_aspect(sid, "payment")
    clear_focus_context(sid)
    assert get_last_subject(sid) is None
    assert get_last_aspect(sid) is None


def test_persist_focus_from_service_turn_sets_last_subject():
    sid = "test-price-focus"
    mem_reset(sid)
    persist_focus_from_service_turn(
        sid,
        client_id="demo",
        matched_service_id="all_on_4",
        route="price_lookup",
        answer="All-on-4 от 350000 ₽",
        topic="implantation",
    )
    sub = get_last_subject(sid)
    assert sub is not None
    assert sub["service_id"] == "all_on_4"
    assert sub["topic"] == "implantation"
    assert "all-on" in sub["label"].lower() or "all_on" in sub["label"].lower()
