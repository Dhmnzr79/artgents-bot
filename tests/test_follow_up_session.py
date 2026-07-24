"""Session service focus age (target_runtime_state)."""

from __future__ import annotations

from core.target_runtime_session import read_age_guarded_service_focus
from session import mem_add_user, mem_get, mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def test_seed_service_focus_starts_at_age_zero():
    sid = "t-focus-age-zero"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    snap = read_age_guarded_service_focus(mem_get(sid))
    assert snap is not None
    assert snap.service_id == "classic"
    assert snap.service_focus_age == 0


def test_mem_add_user_increments_service_focus_age():
    sid = "t-focus-age-inc"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    mem_add_user(sid, "а гарантия?")
    snap = read_age_guarded_service_focus(mem_get(sid))
    assert snap is not None
    assert snap.service_focus_age == 1


def test_clear_focus_context_clears_target_service_focus():
    sid = "t-focus-clear"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    from session import clear_focus_context

    clear_focus_context(sid)
    assert read_age_guarded_service_focus(mem_get(sid)) is None
