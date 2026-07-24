"""Focus context: clear_focus_context + session aspect helpers."""

from __future__ import annotations

from session import clear_focus_context, get_last_aspect, mem_reset, set_last_aspect
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def test_clear_focus_context_clears_target_service_focus_and_aspect():
    sid = "test-clear-focus"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    set_last_aspect(sid, "payment")
    clear_focus_context(sid)
    from core.target_runtime_session import read_age_guarded_service_focus
    from session import mem_get

    assert read_age_guarded_service_focus(mem_get(sid)) is None
    assert get_last_aspect(sid) is None
