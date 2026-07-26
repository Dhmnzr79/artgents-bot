"""Offline tests for governed typed UI TurnFrame builder and planner bypass."""

from __future__ import annotations

import uuid

import pytest
from flask import Flask, request

from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref
from contracts.ui_stage_action import UiStageAction, build_ui_stage_ref
from core.runtime_turn_frame import (
    get_runtime_turn_frame_status,
    load_runtime_turn_frame_snapshot,
    publish_typed_ui_turn_frame,
)
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_typed_ui_turn_frame import (
    build_typed_ui_turn_frame,
    build_typed_ui_turn_frame_from_scope_action,
    build_typed_ui_turn_frame_from_stage_action,
)
from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn
from session import mem_reset
from tests.test_s61_correction_target_runtime import (
    _fake_backends,
    _fake_target_turn_factory,
    _pre_resolver,
    _seed_followups,
)

UI_SCOPE_REF = build_ui_scope_ref(topic="implantation", extent="full_arch")
UI_STAGE_REF = build_ui_stage_ref(topic="prosthetics", stage="implant_placed")


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_builder_sets_commercial_axes_from_scope_action() -> None:
    action = UiScopeAction(
        extent="full_arch",
        topic="implantation",
        ref=UI_SCOPE_REF,
    )
    frame = build_typed_ui_turn_frame_from_scope_action(action)
    assert frame.intent == "price_lookup"
    assert frame.topic == "implantation"
    assert frame.aspects == ["price"]
    assert frame.primary_aspect == "price"
    assert frame.service_id is None
    assert frame.needs_clarification is False
    assert frame.patient_scope.extent == "unknown"
    assert frame.field_meta.topic.provenance.endswith(UI_SCOPE_REF)
    assert frame.field_meta.topic.status == "valid"


def test_builder_sets_commercial_axes_from_stage_action() -> None:
    action = UiStageAction(
        stage="implant_placed",
        topic="prosthetics",
        ref=UI_STAGE_REF,
    )
    frame = build_typed_ui_turn_frame_from_stage_action(action)
    assert frame.topic == "prosthetics"
    assert frame.needs_clarification is False
    assert frame.field_meta.intent.provenance.endswith(UI_STAGE_REF)


def test_publish_typed_ui_turn_frame_sets_observability(flask_ctx) -> None:
    frame = build_typed_ui_turn_frame(topic="prosthetics", provenance_ref=UI_STAGE_REF)
    published = publish_typed_ui_turn_frame(frame)
    assert published is frame
    assert get_runtime_turn_frame_status() == "ok"
    assert request.ctx["typed_ui_turn_frame_used"] is True
    assert request.ctx["turn_planner_used"] is False
    snapshot = load_runtime_turn_frame_snapshot()
    assert snapshot is not None
    assert snapshot["topic"] == "prosthetics"


def test_try_run_typed_ui_planner_turn_returns_none_without_ui_action(flask_ctx) -> None:
    outcome = try_run_typed_ui_planner_turn(
        sid="s-none",
        client_id="demo",
        enqueue_resolver_trace=lambda **_: None,
    )
    assert outcome is None


def test_try_run_typed_ui_planner_turn_publishes_scope_action(flask_ctx) -> None:
    request.ctx["current_ui_scope_action"] = UiScopeAction(
        extent="full_arch",
        topic="implantation",
        ref=UI_SCOPE_REF,
    ).model_dump()
    outcome = try_run_typed_ui_planner_turn(
        sid="s-scope",
        client_id="demo",
        enqueue_resolver_trace=lambda **_: None,
    )
    assert outcome is not None
    assert outcome.intent == "price_lookup"
    assert outcome.scope_topic_candidate == "implantation"
    assert request.ctx["typed_ui_turn_frame_used"] is True


@pytest.mark.parametrize("endpoint", ["/ask", "/ask/stream"])
def test_ui_scope_click_skips_planner_and_materializes(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    import app as app_module

    sid = f"s-typed-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_SCOPE_REF, label="Вся челюсть"),
    )
    planner_calls: list[str] = []

    def boom_plan(*args: object, **kwargs: object) -> object:
        planner_calls.append(str(kwargs.get("q") or args[0] if args else ""))
        raise AssertionError("planner must not run for governed UI scope click")

    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", _fake_target_turn_factory(composer, semantic, boundary))
    monkeypatch.setattr(app_module, "run_planner_turn", boom_plan)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn_attempt", boom_plan)

    client = app_module.app.test_client()
    resp = client.post(
        endpoint,
        json={"q": "", "ref": UI_SCOPE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert planner_calls == []
    if endpoint == "/ask/stream":
        assert "event: done" in resp.data.decode("utf-8")


@pytest.mark.parametrize("endpoint", ["/ask", "/ask/stream"])
def test_ui_stage_click_skips_planner(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    import app as app_module

    sid = f"s-typed-stage-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_STAGE_REF, label="Имплант установлен"),
    )
    planner_calls: list[str] = []

    def boom_plan(**kwargs: object) -> object:
        planner_calls.append("called")
        raise AssertionError("planner must not run for governed UI stage click")

    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", _fake_target_turn_factory(composer, semantic, boundary))
    monkeypatch.setattr(app_module, "run_planner_turn", boom_plan)

    client = app_module.app.test_client()
    resp = client.post(
        endpoint,
        json={"q": "", "ref": UI_STAGE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert planner_calls == []


def test_free_text_still_calls_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    from orchestration.planner_turn import PlannerTurnOutcome

    sid = f"s-free-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    planner_calls: list[str] = []

    def fake_plan(**kwargs: object) -> PlannerTurnOutcome:
        planner_calls.append(str(kwargs.get("q")))
        return PlannerTurnOutcome("content", None)

    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", _fake_target_turn_factory(composer, semantic, boundary))
    monkeypatch.setattr(app_module, "run_planner_turn", fake_plan)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит имплантация?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert planner_calls == ["Сколько стоит имплантация?"]


def test_invalid_ui_scope_ref_still_fail_closed(flask_ctx) -> None:
    sid = f"s-bad-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = _pre_resolver(
        {"q": "", "ref": "target:ui_scope/implantation/not_an_extent", "sid": sid},
    )
    from contracts.ask_orchestration import AskOrchestrationResult

    assert isinstance(result, AskOrchestrationResult)
    assert result.service_route == "target_fullcontext_followup_unknown"
