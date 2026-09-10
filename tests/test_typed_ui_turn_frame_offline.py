"""Offline tests for governed typed UI TurnFrame builder and planner bypass."""

from __future__ import annotations

import json
import re
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
from tests.session_binding_test_support import read_target_runtime_session_for
from core.target_typed_ui_turn_frame import (
    build_typed_ui_turn_frame,
    build_typed_ui_turn_frame_from_scope_action,
    build_typed_ui_turn_frame_from_stage_action,
)
from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn
from session import mem_reset
from tests.target_runtime_test_support import _seed_followups

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

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-typed-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_SCOPE_REF, label="Вся челюсть"),
    )
    backend = _CountingBackend(answer_envelope("Цена на всю челюсть."))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        endpoint,
        json={"q": "", "ref": UI_SCOPE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    if endpoint == "/ask/stream":
        text = resp.get_data(as_text=True)
        assert "event: done" in text
        match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
        assert match is not None
        payload = json.loads(match.group(1))
    else:
        payload = resp.get_json()
    assert backend.call_count == 1
    assert payload.get("answer")
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "full_arch"
    assert after.patient_facts.ref == UI_SCOPE_REF


@pytest.mark.parametrize("endpoint", ["/ask", "/ask/stream"])
def test_ui_stage_click_skips_planner(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-typed-stage-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_STAGE_REF, label="Имплант установлен"),
    )
    backend = _CountingBackend(answer_envelope("На консультации подберём вариант протезирования."))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        endpoint,
        json={"q": "", "ref": UI_STAGE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    if endpoint == "/ask/stream":
        assert "event: done" in resp.get_data(as_text=True)
    assert backend.call_count == 1
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.stage == "implant_placed"
    assert after.patient_facts.topic == "prosthetics"
    assert after.patient_facts.ref == UI_STAGE_REF


def test_free_text_uses_one_call_without_legacy_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-free-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("Имплантация стоит от 45 200 рублей за один зуб."))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит имплантация?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    payload = resp.get_json()
    assert payload.get("answer")


def test_invalid_ui_scope_ref_still_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-bad-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("ignored"))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={
            "q": "",
            "ref": "target:ui_scope/implantation/not_an_extent",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    assert backend.call_count == 0
    payload = resp.get_json()
    assert payload["meta"]["service_route"] == "sales_fast_followup_unknown"
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is None
