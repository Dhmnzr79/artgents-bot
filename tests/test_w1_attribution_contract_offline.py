from __future__ import annotations

import json

import pytest
from flask import Flask

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundTerminalResponse,
    TargetTurnFrameTerminalDispatch,
)
from core.target_runtime_widget import materialize_s41_terminal_payload
from orchestration.planner_turn import PlannerTurnOutcome


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.app_context():
        yield app


def test_ask_and_stream_share_plain_attribution_for_terminal(
    monkeypatch: pytest.MonkeyPatch,
    flask_ctx,
) -> None:
    import app as app_module

    terminal = TargetTurnFrameBoundTerminalResponse(
        kind="terminal",
        dispatch=TargetTurnFrameTerminalDispatch(
            kind="terminal",
            terminal_mode="defer",
            spec=TargetResponseSpec(
                response_mode="defer",
                tone_key="commercial_warm",
                allowed_topics=("implantation",),
                required_components=(),
            ),
        ),
    )
    widget = materialize_s41_terminal_payload(
        client_id="demo",
        sid="sid-attrib",
        terminal=terminal,
    )

    def target_turn(**kwargs):
        payload = widget.payload
        return AskOrchestrationResult(
            kind="service_reply",
            q=kwargs["q"],
            sid=kwargs["sid"],
            client_id=kwargs["client_id"],
            service_payload=payload,
            service_route=str((payload.get("meta") or {}).get("service_route", "target")),
        )

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    client = app_module.app.test_client()
    ask = client.post(
        "/ask",
        json={"q": "Сколько стоит имплантация?", "sid": "sid-attrib", "client_id": "demo"},
    )
    assert ask.status_code == 200
    ask_meta = ask.get_json()["meta"]
    assert ask_meta["attribution_kind"] == "plain"
    assert not ask_meta.get("followups")

    stream = client.post(
        "/ask/stream",
        json={"q": "Сколько стоит имплантация?", "sid": "sid-attrib-2", "client_id": "demo"},
    )
    assert stream.status_code == 200
    stream_text = stream.data.decode("utf-8")
    assert "event: ui" in stream_text
    assert '"attribution_kind": "plain"' in stream_text or '"attribution_kind":"plain"' in stream_text


def test_materialized_ask_keeps_content_attribution(
    monkeypatch: pytest.MonkeyPatch,
    flask_ctx,
) -> None:
    import app as app_module
    from core.target_runtime_widget import materialize_verified_widget_payload
    from core.target_response_followup_policy import TargetResponseFollowupSelection
    from core.target_response_verifier import TargetVerifiedComposedResponse
    from tests.test_w1_widget_followup_contract_offline import build_turn_frame_for_widget
    import types

    spec = TargetResponseSpec(
        response_mode="answer",
        service_id="all_on_4",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("price",),
        followup_source="price",
    )
    verified = TargetVerifiedComposedResponse(
        text="Цена All-on-4 от 318 000 рублей.",
        spec=spec,
        selected_followups=TargetResponseFollowupSelection(source="price", content=(), price=()),
        selected_cta_key=None,
    )
    widget = materialize_verified_widget_payload(
        context=types.SimpleNamespace(client_id="demo"),
        sid="sid-mat",
        verified=verified,
        turn_frame=build_turn_frame_for_widget(),
    )

    def target_turn(**kwargs):
        payload = widget.payload
        return AskOrchestrationResult(
            kind="service_reply",
            q=kwargs["q"],
            sid=kwargs["sid"],
            client_id=kwargs["client_id"],
            service_payload=payload,
            service_route=str((payload.get("meta") or {}).get("service_route", "target")),
        )

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": "sid-mat", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["attribution_kind"] == "content"
