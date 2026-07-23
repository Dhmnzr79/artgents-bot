"""Focus context: clear_focus_context + session subject/aspect helpers."""

from __future__ import annotations

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
