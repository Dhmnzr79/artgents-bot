from __future__ import annotations

import uuid

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref
from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import (
    read_target_runtime_session,
    sync_session_patient_facts_topic,
    write_session_patient_facts_from_ui_action,
)
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from orchestration.context import AskTurnContext
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from session import mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _install_turn_frame,
    _pre_resolver,
    _seed_followups,
    _seed_target_runtime_state,
    _turn_frame,
)


UI_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")
UI_REF_FEW = build_ui_scope_ref(topic="implantation", extent="few_teeth")


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def _ui_action(ref: str = UI_REF, *, extent: str = "one_tooth") -> UiScopeAction:
    return UiScopeAction(
        extent=extent,  # type: ignore[arg-type]
        topic="implantation",
        ref=ref,
    )


def test_explicit_ui_scope_action_replaces_prior_session_extent() -> None:
    sid = f"s-replace-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(sid, _ui_action(extent="full_arch", ref=build_ui_scope_ref(topic="implantation", extent="full_arch")))
    before = read_target_runtime_session(sid)
    assert before.patient_facts is not None
    assert before.patient_facts.extent == "full_arch"

    write_session_patient_facts_from_ui_action(sid, _ui_action(extent="few_teeth", ref=UI_REF_FEW))
    after = read_target_runtime_session(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "few_teeth"
    assert after.patient_facts.ref == UI_REF_FEW


def test_topic_change_clears_carried_extent_via_sync() -> None:
    sid = f"s-topic-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(sid, _ui_action())
    from core.target_runtime_session import sync_session_patient_facts_topic

    sync_session_patient_facts_topic(sid, current_topic="prosthetics")
    after = read_target_runtime_session(sid)
    assert after.patient_facts is None


def test_sid_isolation_for_patient_facts() -> None:
    sid_a = f"s-a-{uuid.uuid4().hex[:8]}"
    sid_b = f"s-b-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_a)
    mem_reset(sid_b)
    write_session_patient_facts_from_ui_action(sid_a, _ui_action())
    b_state = read_target_runtime_session(sid_b)
    assert b_state.patient_facts is None


def test_reset_clears_patient_facts() -> None:
    sid = f"s-reset-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(sid, _ui_action())
    mem_reset(sid)
    after = read_target_runtime_session(sid)
    assert after.patient_facts is None


def test_pre_resolver_ui_scope_click_persists_session_facts(flask_ctx) -> None:
    sid = f"s-click-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    result = _pre_resolver({"q": "", "ref": UI_REF, "sid": sid})
    assert isinstance(result, AskTurnContext)  # type: ignore[name-defined]
    after = read_target_runtime_session(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "one_tooth"


def test_a9_session_facts_persist_after_materialized_turn(flask_ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import config

    importlib.reload(config)

    sid = f"s-a9-persist-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    from core.turn_frame_from_raw import build_turn_frame_from_raw
    from tests.test_s61_correction_target_runtime import _install_turn_frame

    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_scope": {
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    _install_turn_frame(frame)
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит имплантация всей челюсти?",
        composer_backend=RecordingComposerBackend(
            "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть."
        ),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "full_arch"
    assert after.patient_facts.reported_context is None


def test_terminal_error_does_not_mutate_patient_facts(flask_ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"s-term-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(sid, _ui_action())
    before = read_target_runtime_session(sid)

    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    _install_turn_frame(_turn_frame())
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="test",
        composer_backend=RecordingComposerBackend("x"),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.patient_facts == before.patient_facts


def test_service_focus_hydration_unchanged_with_patient_facts() -> None:
    sid = f"s-focus-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(sid, _ui_action())
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
        last_primary_aspect="price",
    )
    frame = _turn_frame(service_id=None)
    from core.target_runtime_turn_frame_hydration import hydrate_target_runtime_turn_frame_from_session

    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="а по цене?",
        session_state=read_target_runtime_session(sid),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    assert hydrated.service_id == "all_on_4"
