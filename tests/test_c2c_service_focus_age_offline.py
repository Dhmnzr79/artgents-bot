"""C2c-correction: canonical service focus age from target_runtime_state."""

from __future__ import annotations

import uuid

import pytest
from flask import Flask

from core.routing_loader import THRESHOLDS
from core.target_runtime_session import (
    compute_service_focus_age,
    max_service_focus_turn_age,
    read_age_guarded_service_focus,
    read_target_runtime_session,
)
from core.target_runtime_turn_frame_hydration import hydrate_target_runtime_turn_frame_from_session
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_runtime_session import TargetRuntimeSessionState
from session import mem_add_user, mem_get, mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    _install_turn_frame,
    _run_materialized_turn,
    _seed_target_runtime_state,
    _turn_frame,
)
from tests.test_target_boundary_enforced_fullcontext_response import (
    PERSONAL_MEDICAL_REJECT_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)


def _seed_focus(sid: str, *, service_id: str, set_at_turn: int) -> None:
    _seed_target_runtime_state(
        sid,
        last_service_id=service_id,
        last_topic="implantation",
        service_focus_set_at_turn=set_at_turn,
    )


def test_service_focus_age_zero_after_materialized_service(flask_ctx) -> None:
    sid = f"c2cc-age0-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    mem_add_user(sid, "Сколько стоит All-on-4?")
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    runtime = read_target_runtime_session(sid)
    assert runtime.last_service_id == "all_on_4"
    assert runtime.service_focus_age() == 0


def test_service_focus_age_increments_on_user_turns() -> None:
    sid = f"c2cc-age-inc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_focus(sid, service_id="all_on_4", set_at_turn=1)
    st = mem_get(sid)
    st["session_turn_count"] = 3
    from session import _lock, _persist_unlocked

    with _lock:
        _persist_unlocked(sid, st)
    snap = read_age_guarded_service_focus(mem_get(sid))
    assert snap is not None
    assert snap.service_focus_age == 2


def test_service_focus_fresh_until_limit_four() -> None:
    sid = f"c2cc-limit-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    limit = max_service_focus_turn_age()
    _seed_focus(sid, service_id="all_on_4", set_at_turn=0)
    st = mem_get(sid)
    st["session_turn_count"] = limit
    from session import _lock, _persist_unlocked

    with _lock:
        _persist_unlocked(sid, st)
    assert read_age_guarded_service_focus(mem_get(sid)) is not None
    st["session_turn_count"] = limit + 1
    with _lock:
        _persist_unlocked(sid, st)
    assert read_age_guarded_service_focus(mem_get(sid)) is None


def test_stale_focus_not_used_for_price_route() -> None:
    sid = f"c2cc-stale-price-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_focus(sid, service_id="all_on_4", set_at_turn=0)
    st = mem_get(sid)
    st["session_turn_count"] = int(THRESHOLDS.follow_up.max_service_focus_turn_age) + 1
    from session import _lock, _persist_unlocked

    with _lock:
        _persist_unlocked(sid, st)
    focus = build_dialog_focus_decision("А сколько стоит?", sid=sid, client_id="demo")
    assert focus.resolved_service_id is None


def test_hydration_respects_service_focus_age() -> None:
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        service_focus_set_at_turn=0,
        session_turn_count=int(THRESHOLDS.follow_up.max_service_focus_turn_age) + 1,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        followups=(),
    )
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": "implantation",
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="А сколько стоит?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id is None


def test_new_materialized_service_resets_focus_timestamp(flask_ctx) -> None:
    sid = f"c2cc-reset-ts-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_focus(sid, service_id="classic", set_at_turn=0)
    st = mem_get(sid)
    st["session_turn_count"] = 5
    from session import _lock, _persist_unlocked

    with _lock:
        _persist_unlocked(sid, st)
    mem_add_user(sid, "Сколько стоит All-on-4?")
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    runtime = read_target_runtime_session(sid)
    assert runtime.last_service_id == "all_on_4"
    assert runtime.service_focus_set_at_turn == 6
    assert runtime.service_focus_age() == 0


def test_terminal_error_does_not_rejuvenate_focus_timestamp(flask_ctx) -> None:
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    sid = f"c2cc-err-ts-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _run_materialized_turn(sid)
    before = read_target_runtime_session(sid)
    assert before.service_focus_set_at_turn is not None
    set_at_before = before.service_focus_set_at_turn
    mem_add_user(sid, "follow-up")
    assessment = __import__(
        "core.target_response_verifier",
        fromlist=["TargetSemanticAssessment", "TargetSemanticIssue"],
    )
    _install_turn_frame(_turn_frame(primary_aspect="price", aspects=["price"]))
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(
            assessment=assessment.TargetSemanticAssessment(
                issues=(
                    assessment.TargetSemanticIssue(
                        kind="personal_medical_conclusion",
                        offending_span="x",
                    ),
                ),
            )
        ),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.service_focus_set_at_turn == set_at_before
    assert after.service_focus_age() is not None
    assert after.service_focus_age() > 0


def test_compute_service_focus_age_helper() -> None:
    assert compute_service_focus_age(session_turn_count=7, service_focus_set_at_turn=5) == 2
    assert compute_service_focus_age(session_turn_count=3, service_focus_set_at_turn=None) is None


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        from flask import request

        request.ctx = {}
        yield
