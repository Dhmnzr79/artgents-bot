"""C2c: session continuity via target_runtime_state only (no last_subject product path)."""

from __future__ import annotations

import uuid

import pytest
from flask import Flask

from core.target_runtime_session import (
    focus_dict_from_session_state,
    read_target_runtime_session,
)
from core.target_runtime_turn_frame_hydration import (
    hydrate_target_runtime_turn_frame_from_session,
)
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.target_runtime_session import TargetRuntimeSessionState
from session import mem_get, mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    _install_turn_frame,
    _run_materialized_turn,
    _seed_followups,
    _seed_target_runtime_state,
    _turn_frame,
)
from tests.test_target_boundary_enforced_fullcontext_response import (
    PERSONAL_MEDICAL_REJECT_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)

def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4", "classic"}),
    )


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        from flask import request

        request.ctx = {}
        yield


def test_hydrate_all_on_4_price_doctors_payment_followups() -> None:
    session = TargetRuntimeSessionState(
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="overview",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    allowed = frozenset({"all_on_4"})

    price_frame = _frame(aspects=["price"], primary_aspect="price", topic="implantation")
    hydrated_price = hydrate_target_runtime_turn_frame_from_session(
        price_frame,
        user_message="А сколько стоит?",
        session_state=session,
        allowed_service_ids=allowed,
    )
    assert hydrated_price.service_id == "all_on_4"

    doctors_frame = _frame(topic="doctors", aspects=["doctor"], primary_aspect="doctor")
    hydrated_doctors = hydrate_target_runtime_turn_frame_from_session(
        doctors_frame,
        user_message="А кто делает?",
        session_state=session,
        allowed_service_ids=allowed,
    )
    assert hydrated_doctors.service_id == "all_on_4"

    payment_frame = _frame(aspects=["payment"], primary_aspect="payment", topic="implantation")
    hydrated_payment = hydrate_target_runtime_turn_frame_from_session(
        payment_frame,
        user_message="А как оплатить?",
        session_state=session,
        allowed_service_ids=allowed,
    )
    assert hydrated_payment.service_id == "all_on_4"


def test_fresh_clinic_wide_doctors_question_does_not_invent_service_id() -> None:
    session = TargetRuntimeSessionState(
        last_service_id=None,
        last_topic=None,
        last_primary_aspect=None,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    doctors_frame = _frame(topic="doctors", aspects=["doctor"], primary_aspect="doctor")
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        doctors_frame,
        user_message="Кто из врачей?",
        session_state=session,
        allowed_service_ids=frozenset({"all_on_4", "classic"}),
    )
    assert hydrated.service_id is None


def test_focus_dict_requires_service_focus_timestamp() -> None:
    sid = f"c2c-focus-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_state"] = {
            "last_service_id": "all_on_4",
            "last_topic": "implantation",
        }
        _persist_unlocked(sid, st)
    assert focus_dict_from_session_state(mem_get(sid)) is None
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    focus = focus_dict_from_session_state(mem_get(sid))
    assert focus is not None
    assert focus["service_id"] == "all_on_4"


def test_materialized_turn_updates_target_runtime_focus(flask_ctx) -> None:
    sid = f"c2c-mat-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    after = read_target_runtime_session(sid)
    assert after.last_service_id == "all_on_4"
    assert after.last_topic == "implantation"


def test_terminal_error_does_not_wipe_service_focus(flask_ctx) -> None:
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    sid = f"c2c-err-focus-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _run_materialized_turn(sid)
    before = read_target_runtime_session(sid)
    assert before.last_service_id == "all_on_4"

    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    _install_turn_frame(_turn_frame(primary_aspect="price", aspects=["price"]))
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="test",
        composer_backend=RecordingComposerBackend(PERSONAL_MEDICAL_REJECT_TEXT),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.last_service_id == before.last_service_id
    assert after.last_topic == before.last_topic


def test_mem_reset_clears_target_runtime_state_and_followups() -> None:
    sid = f"c2c-reset-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_target_runtime_state(sid, last_service_id="all_on_4", last_topic="implantation")
    from core.target_runtime_followup_nav import TargetRuntimeFollowupItem

    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref="implantation__service__all_on_4.md#x", label="x"),
    )
    mem_reset(sid)
    st = mem_get(sid)
    assert st.get("target_runtime_state") is None
    assert st.get("target_runtime_followups") is None
    session = read_target_runtime_session(sid)
    assert session.last_service_id is None
    assert not session.followups


def test_new_sid_does_not_inherit_prior_service_focus() -> None:
    sid1 = f"c2c-sid1-{uuid.uuid4().hex[:8]}"
    sid2 = f"c2c-sid2-{uuid.uuid4().hex[:8]}"
    mem_reset(sid1)
    mem_reset(sid2)
    _seed_target_runtime_state(sid1, last_service_id="all_on_4", last_topic="implantation")
    assert read_target_runtime_session(sid2).last_service_id is None
    assert focus_dict_from_session_state(mem_get(sid2)) is None


def test_price_followup_uses_target_runtime_state() -> None:
    from core.dialog_focus import build_dialog_focus_decision

    sid = f"c2c-price-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_target_runtime_state(sid, last_service_id="all_on_4", last_topic="implantation")
    focus = build_dialog_focus_decision("А сколько стоит?", sid=sid, client_id="demo")
    assert focus.resolved_service_id == "all_on_4"
