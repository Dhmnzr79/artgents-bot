"""Session focus helpers for follow-up (stage 4a)."""

from __future__ import annotations

from session import (
    clear_last_subject,
    get_last_aspect,
    get_last_subject,
    mem_add_user,
    mem_get,
    set_last_aspect,
    set_last_subject,
)


def test_set_and_get_last_subject():
    sid = "test-last-subject"
    clear_last_subject(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
        last_route="retrieval_chunk",
    )
    sub = get_last_subject(sid)
    assert sub is not None
    assert sub["service_id"] == "classic"
    assert sub["label"] == "Классическая имплантация"
    assert int(mem_get(sid).get("subject_turn_age") or 0) == 0


def test_mem_add_user_increments_subject_turn_age():
    sid = "test-subject-turn-age"
    clear_last_subject(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="classic",
        last_route="retrieval_chunk",
    )
    mem_add_user(sid, "а гарантия?")
    assert int(mem_get(sid).get("subject_turn_age") or 0) == 1


def test_clear_last_subject_clears_aspect_too():
    sid = "test-clear-aspect"
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="classic",
        last_route="retrieval_chunk",
    )
    set_last_aspect(sid, "payment")
    clear_last_subject(sid)
    assert get_last_subject(sid) is None
    assert get_last_aspect(sid) is None


def test_clear_last_subject_resets_age():
    sid = "test-clear-subject"
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="classic",
        last_route="retrieval_chunk",
    )
    mem_add_user(sid, "а больно?")
    clear_last_subject(sid)
    st = mem_get(sid)
    assert st.get("last_subject") is None
    assert int(st.get("subject_turn_age") or 0) == 0
