"""Patient situation session carry (Slice 3)."""

from __future__ import annotations

import uuid

import pytest

from core.patient_situation import detect_patient_situation, record_patient_situation_ctx
from core.patient_situation_session import (
    get_carried_patient_situation,
    persist_patient_situation_after_turn,
    resolve_patient_situation_for_turn,
)
from core.routing_loader import THRESHOLDS
from query_selector import _patient_situation_for_turn, select_price_service_route
from session import (
    clear_focus_context,
    clear_last_patient_situation,
    get_last_patient_situation,
    mem_add_user,
    mem_get,
    mem_reset,
    patient_situation_turn_age,
    set_last_patient_situation,
)


def test_persist_eligible_situation():
    sid = f"ps-sess-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    q = "У меня нет одного зуба, что лучше?"
    persist_patient_situation_after_turn(sid, q)
    snap = get_last_patient_situation(sid)
    assert snap is not None
    assert snap["kind"] == "one_tooth_missing"
    assert snap["patient_scope"] == "one_tooth"
    assert patient_situation_turn_age(sid) == 0


def test_mem_add_user_increments_patient_situation_turn_age():
    sid = f"ps-age-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = detect_patient_situation("нет одного зуба")
    set_last_patient_situation(sid, result.model_dump())
    mem_add_user(sid, "а сколько стоит?")
    assert patient_situation_turn_age(sid) == 1


def test_age_guard_blocks_stale_carry():
    sid = f"ps-stale-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = detect_patient_situation("нет одного зуба")
    set_last_patient_situation(sid, result.model_dump())
    st = mem_get(sid)
    st["patient_situation_turn_age"] = int(THRESHOLDS.patient_situation.max_turn_age) + 1
    from session import _persist_unlocked, _lock

    with _lock:
        _persist_unlocked(sid, st)
    assert get_carried_patient_situation(sid) is None
    situation, meta = resolve_patient_situation_for_turn("А сколько стоит?", sid=sid)
    assert meta["patient_situation_carried"] is False
    assert situation.kind == "unknown"


def test_vague_price_carries_one_tooth_without_last_subject():
    sid = f"ps-incident-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = "У меня нет одного зуба, что лучше?"
    persist_patient_situation_after_turn(sid, turn1)
    mem_add_user(sid, turn1)
    situation, meta = resolve_patient_situation_for_turn("А сколько стоит?", sid=sid)
    assert meta["patient_situation_carried"] is True
    assert situation.kind == "one_tooth_missing"
    assert situation.patient_scope == "one_tooth"
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "classic"
    assert route.get("matched_service_id") != "all_on_4"


def test_explicit_new_situation_replaces_carry():
    sid = f"ps-replace-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    persist_patient_situation_after_turn(sid, "нет одного зуба")
    mem_add_user(sid, "нет одного зуба")
    persist_patient_situation_after_turn(sid, "сколько стоит all on 4 на всю челюсть?")
    snap = get_last_patient_situation(sid)
    assert snap is not None
    assert snap["kind"] == "full_arch_missing"


def test_clear_last_patient_situation():
    sid = f"ps-clear-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    persist_patient_situation_after_turn(sid, "нет одного зуба")
    clear_last_patient_situation(sid)
    assert get_last_patient_situation(sid) is None


def test_clear_focus_context_clears_patient_situation_carry():
    sid = f"ps-focus-clear-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    persist_patient_situation_after_turn(sid, "нет одного зуба")
    mem_add_user(sid, "нет одного зуба")
    clear_focus_context(sid)
    assert get_last_patient_situation(sid) is None
    assert patient_situation_turn_age(sid) == 0
    situation, meta = resolve_patient_situation_for_turn("А сколько стоит?", sid=sid)
    assert meta["patient_situation_carried"] is False
    route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
    assert route.get("mode") == "clarify"
    assert route.get("fallback_reason") == "price_clarify_no_context"


def test_flask_ctx_carry_wires_vague_price_route():
    """request.ctx path: carry_meta in ctx → select_price sees vague_carry (not getattr bug)."""
    app = pytest.importorskip("flask").Flask(__name__)
    sid = f"ps-ctx-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = "У меня нет одного зуба, что лучше?"
    persist_patient_situation_after_turn(sid, turn1)
    mem_add_user(sid, turn1)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        situation, carry_meta = resolve_patient_situation_for_turn("А сколько стоит?", sid=sid)
        record_patient_situation_ctx(situation, carry_meta=carry_meta)
        assert request.ctx.get("patient_situation_carried") is True

        _, vague_carry = _patient_situation_for_turn("А сколько стоит?", sid=sid)
        assert vague_carry is True

        route = select_price_service_route("А сколько стоит?", client_id="demo", sid=sid)
        assert route.get("mode") == "matched"
        assert route.get("matched_service_id") == "classic"
        assert route.get("matched_service_id") != "all_on_4"
