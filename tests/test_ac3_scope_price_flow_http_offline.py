from __future__ import annotations

import uuid

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ui_scope_action import build_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_reset
from tests.test_s61_correction_target_runtime import (
    _fake_backends,
    _fake_target_turn_factory,
    _pre_resolver,
    _seed_followups,
)

UI_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")
PAYMENT_REF = "price:all_on_4/stages"


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_http_ask_and_stream_scope_click_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    for path in ("/ask", "/ask/stream"):
        sid = f"s-parity-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _seed_followups(
            sid,
            TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
        )
        captured: dict[str, object] = {}
        composer, semantic, boundary = _fake_backends()

        def target_turn(**kwargs):
            from flask import request

            captured["ui_scope"] = request.ctx.get("current_ui_scope_action")
            return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

        monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
        monkeypatch.setattr(
            app_module,
            "run_planner_turn",
            lambda **k: PlannerTurnOutcome("content", None),
        )
        client = app_module.app.test_client()
        resp = client.post(
            path,
            json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
        )
        assert resp.status_code == 200
        assert captured.get("ui_scope", {}).get("extent") == "one_tooth"


def test_http_unshown_ui_scope_ref_fail_closed(flask_ctx) -> None:
    sid = f"s-ac3-unshown-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = _pre_resolver({"q": "", "ref": UI_REF, "sid": sid})
    assert isinstance(result, AskOrchestrationResult)
    assert result.service_route == "target_fullcontext_followup_unknown"


def test_http_finance_followup_ref_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s-ac3-pay-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=PAYMENT_REF, label="Оплата по этапам"),
    )
    captured: dict[str, str] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": PAYMENT_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured["q"] == "Оплата по этапам"
