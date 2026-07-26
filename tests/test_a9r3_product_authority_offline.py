"""A9R3 product authority wiring — offline acceptance matrix (no LLM)."""

from __future__ import annotations

import importlib
import json
import uuid
from typing import Any

import pytest
from flask import Flask, request

from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref, is_ui_scope_ref
from core.target_effective_scope import resolve_effective_scope, strip_reported_context_for_product
from core.target_effective_scope_merge import merge_effective_scope_axes, EffectiveScopeMergeInputs
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from core.target_runtime_session import read_target_runtime_session
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.target_strategy_context import strategy_match_from_effective_scope
from core.turn_frame_from_raw import build_turn_frame_from_raw
from session import mem_get, mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _install_turn_frame,
    _pre_resolver,
    _seed_followups,
)
from tests.test_target_boundary_enforced_fullcontext_response import PRICE_TEXT
from tests.test_w1_family_price_overview_offline import _family_overview_frame

_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics", "doctors"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic", "veneers"})


@pytest.fixture(autouse=True)
def _enable_a9_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A9_PATIENT_SCOPE_AUTHORITY", "1")
    import config

    importlib.reload(config)


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def _native_frame(
    patient_scope: dict,
    *,
    topic: str = "implantation",
    service_id: str | None = None,
    aspects: list[str] | None = None,
):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": aspects or ["price"],
            "primary_aspect": "price",
            "service_id": service_id,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": patient_scope,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _run_materialized(
    sid: str,
    frame,
    *,
    user_message: str,
    composer_text: str = PRICE_TEXT,
):
    _install_turn_frame(frame)
    return run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message=user_message,
        composer_backend=RecordingComposerBackend(composer_text),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )


def _quick_refs(outcome) -> list[str]:
    payload = outcome.widget.payload
    quick = payload.get("quick_replies") if isinstance(payload.get("quick_replies"), list) else []
    return [str(item.get("ref") or "") for item in quick if isinstance(item, dict)]


def _scope_nav_refs(refs: list[str]) -> list[str]:
    return [ref for ref in refs if is_ui_scope_ref(ref)]


def _effective_scope_from_ctx() -> dict[str, Any]:
    raw = request.ctx.get("effective_scope")
    assert isinstance(raw, dict)
    return raw


def _bump_session_turn(sid: str) -> None:
    from session import _lock, _persist_unlocked

    with _lock:
        st = mem_get(sid)
        st["session_turn_count"] = int(st.get("session_turn_count") or 0) + 1
        _persist_unlocked(sid, st)


def test_ac3_1_full_arch_scoped_price_without_scope_nav(flask_ctx) -> None:
    sid = f"s-a9r3-1-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _native_frame(
        {"extent": "full_arch", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    outcome = _run_materialized(
        sid,
        frame,
        user_message="Сколько стоит имплантация всей челюсти?",
    )
    assert outcome.widget.kind == "materialized"
    scope = _effective_scope_from_ctx()
    assert scope["extent"] == "full_arch"
    assert scope.get("reported_context") is None
    assert _scope_nav_refs(_quick_refs(outcome)) == []


def test_ac3_2_broad_price_has_three_scope_buttons(flask_ctx) -> None:
    sid = f"s-a9r3-2-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _family_overview_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    outcome = _run_materialized(
        sid,
        frame,
        user_message="Сколько стоит имплантация?",
        composer_text="Краткий обзор цен.",
    )
    assert outcome.widget.kind == "materialized"
    scope = _effective_scope_from_ctx()
    assert scope["extent"] == "unknown"
    assert len(_scope_nav_refs(_quick_refs(outcome))) == 3


def test_ac3_3_all_on_4_does_not_invent_patient_scope(flask_ctx) -> None:
    sid = f"s-a9r3-3-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _native_frame(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        service_id="all_on_4",
    )
    outcome = _run_materialized(sid, frame, user_message="Сколько стоит All-on-4?")
    assert outcome.widget.kind == "materialized"
    scope = _effective_scope_from_ctx()
    assert scope["extent"] == "unknown"
    assert scope.get("stage") is None
    meta = outcome.widget.payload.get("meta") or {}
    assert meta.get("service_route") == "target_fullcontext_materialized"
    assert "w1" not in str(meta.get("service_route", "")).lower()


def test_ac3_4_implant_placed_prosthetics_scoped_path(flask_ctx) -> None:
    sid = f"s-a9r3-4-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _native_frame(
        {
            "extent": "one_tooth",
            "jaw": "unknown",
            "stage": "implant_placed",
            "modifiers": [],
        },
        topic="prosthetics",
    )
    outcome = _run_materialized(
        sid,
        frame,
        user_message="Имплант уже установлен, сколько коронка?",
        composer_text="Цены на коронки.",
    )
    assert outcome.widget.kind == "materialized"
    scope = _effective_scope_from_ctx()
    assert scope["topic"] == "prosthetics"
    assert scope.get("stage") == "implant_placed"
    assert _scope_nav_refs(_quick_refs(outcome)) == []


def test_ac3_5_correction_replaces_session_full_arch(flask_ctx) -> None:
    sid = f"s-a9r3-5-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = _native_frame(
        {"extent": "full_arch", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    outcome1 = _run_materialized(
        sid,
        turn1,
        user_message="Сколько стоит имплантация всей челюсти?",
    )
    assert outcome1.widget.kind == "materialized"
    after1 = read_target_runtime_session(sid)
    assert after1.patient_facts is not None
    assert after1.patient_facts.extent == "full_arch"

    _bump_session_turn(sid)
    turn2 = _native_frame(
        {"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    outcome2 = _run_materialized(
        sid,
        turn2,
        user_message="Нет, речь об одном зубе",
        composer_text="Краткий обзор цен.",
    )
    assert outcome2.widget.kind == "materialized"
    after2 = read_target_runtime_session(sid)
    assert after2.patient_facts is not None
    assert after2.patient_facts.extent == "one_tooth"


def test_ac3_6_ui_scope_click_beats_planner_extent(flask_ctx) -> None:
    sid = f"s-a9r3-6-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ui_ref = build_ui_scope_ref(topic="implantation", extent="one_tooth")
    from core.target_runtime_followup_nav import TargetRuntimeFollowupItem

    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ui_ref, label="Один зуб"))
    request.ctx["current_ui_scope_action"] = UiScopeAction(
        extent="one_tooth",
        topic="implantation",
        ref=ui_ref,
    ).model_dump()
    frame = _native_frame(
        {"extent": "full_arch", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    outcome = _run_materialized(sid, frame, user_message="Один зуб", composer_text="Краткий обзор цен.")
    assert outcome.widget.kind == "materialized"
    scope = _effective_scope_from_ctx()
    assert scope["extent"] == "one_tooth"
    assert scope["source"] == "ui_action"


def test_ui_scope_full_arch_beats_medical_handoff_and_needs_clarify(flask_ctx) -> None:
    sid = f"s-a9r3-ui-handoff-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ui_ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    request.ctx["current_ui_scope_action"] = UiScopeAction(
        extent="full_arch",
        topic="implantation",
        ref=ui_ref,
    ).model_dump()
    frame = build_turn_frame_from_raw(
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": "implantation",
            "topic_confidence": 0.9,
            "needs_clarify": True,
            "patient_scope": {
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    _install_turn_frame(frame)
    outcome = run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="продолжить",
        composer_backend=RecordingComposerBackend("318 000 ₽ за All-on-4."),
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("medical_handoff", 0.9)),
    )
    assert outcome.widget.kind == "materialized"
    route = str((outcome.widget.payload.get("meta") or {}).get("service_route") or "")
    assert "terminal" not in route


def test_ac3_7_ambiguous_turn_does_not_overwrite_session(flask_ctx) -> None:
    sid = f"s-a9r3-7-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = _native_frame(
        {"extent": "few_teeth", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    _run_materialized(
        sid,
        turn1,
        user_message="Несколько зубов под имплантацию",
        composer_text="Краткий обзор цен.",
    )
    before = read_target_runtime_session(sid)
    assert before.patient_facts is not None
    assert before.patient_facts.extent == "few_teeth"

    _bump_session_turn(sid)
    turn2 = _native_frame(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    _run_materialized(sid, turn2, user_message="ну примерно")
    after = read_target_runtime_session(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "few_teeth"


def test_ac3_8_terminal_turn_does_not_persist_a9_facts(flask_ctx) -> None:
    from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue

    sid = f"s-a9r3-8-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _native_frame(
        {"extent": "full_arch", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    _install_turn_frame(frame)
    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="personal_medical_conclusion", offending_span="x"),),
    )
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит имплантация всей челюсти?",
        composer_backend=RecordingComposerBackend("x"),
        semantic_backend=RecordingSemanticBackend(assessment=assessment),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    after = read_target_runtime_session(sid)
    assert after.patient_facts is None


def test_ac3_9_pre_resolver_and_runtime_ui_scope_parity(flask_ctx) -> None:
    """`/ask` and `/ask/stream` share pre_resolver ingress; parity on EffectiveScope."""
    from orchestration.context import AskTurnContext

    ui_ref = build_ui_scope_ref(topic="implantation", extent="one_tooth")
    from core.target_runtime_followup_nav import TargetRuntimeFollowupItem

    for label in ("ask", "ask_stream"):
        sid = f"s-parity-{label}-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _seed_followups(sid, TargetRuntimeFollowupItem(ref=ui_ref, label="Один зуб"))
        result = _pre_resolver({"q": "", "ref": ui_ref, "sid": sid})
        assert isinstance(result, AskTurnContext)
        frame = _native_frame(
            {
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            }
        )
        outcome = _run_materialized(
            sid,
            frame,
            user_message="Один зуб",
            composer_text="Краткий обзор цен.",
        )
        assert outcome.widget.kind == "materialized"
        scope = _effective_scope_from_ctx()
        assert scope["extent"] == "one_tooth"
        assert scope["source"] == "ui_action"


def test_ac3_10_price_evidence_from_pricebook_not_invented(flask_ctx) -> None:
    sid = f"s-a9r3-10-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _native_frame(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        service_id="all_on_4",
    )
    composer = RecordingComposerBackend(PRICE_TEXT)
    _install_turn_frame(frame)
    run_target_fullcontext_runtime_turn(
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит All-on-4?",
        composer_backend=composer,
        semantic_backend=RecordingSemanticBackend(),
        boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )
    assert composer.invocations
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    offer_blocks = [block for block in evidence if block.get("kind") == "offer"]
    assert offer_blocks
    joined = json.dumps(offer_blocks, ensure_ascii=False)
    assert "all_on_4" in joined


def test_ac3_11_no_legacy_w1_routes(flask_ctx) -> None:
    sid = f"s-a9r3-11-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    frame = _family_overview_frame(
        patient_scope={
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        }
    )
    outcome = _run_materialized(
        sid,
        frame,
        user_message="Сколько стоит имплантация?",
        composer_text="Краткий обзор цен.",
    )
    route = str((outcome.widget.payload.get("meta") or {}).get("service_route") or "")
    assert route.startswith("target_fullcontext")
    assert "w1" not in route.lower()


def test_reported_context_stripped_before_ac2() -> None:
    frame = _native_frame(
        {
            "extent": "one_tooth",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": ["reported_bone_deficit"],
        }
    )
    projected = project_patient_scope_from_turn_frame(frame)
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic="implantation",
            session_turn_count=1,
            session_facts=None,
            projected_turn_scope=projected,
        )
    )
    assert merged.reported_context == "reported_bone_deficit"
    product_scope = strip_reported_context_for_product(merged)
    match = strategy_match_from_effective_scope(product_scope, service_family="implantology")
    assert product_scope.reported_context is None
    assert match.reported_context is None


def test_partial_invalid_extent_preserves_usable_jaw() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_scope": {
                "extent": 42,
                "jaw": "upper",
                "stage": "unknown",
                "modifiers": [],
            },
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    projected = project_patient_scope_from_turn_frame(frame)
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=None,
        current_topic="implantation",
        session_turn_count=1,
        projected_turn_scope=projected,
    )
    assert scope.extent == "unknown"
    assert scope.jaw == "upper"
    assert scope.jaw_axis.source == "a9_turn"


def test_jaw_both_accepted_without_special_exception() -> None:
    frame = _native_frame({"extent": "unknown", "jaw": "both", "stage": "unknown", "modifiers": []})
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=None,
        current_topic="implantation",
        session_turn_count=1,
        projected_turn_scope=project_patient_scope_from_turn_frame(frame),
    )
    assert scope.jaw == "both"
    assert scope.jaw_axis.source == "a9_turn"
