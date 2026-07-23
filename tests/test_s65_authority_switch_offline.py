"""S65 offline acceptance tests for default FullContext product authority."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ingress_route import IngressRouteResult
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_widget import build_target_runtime_widget_cta
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged
from orchestration.context import AskTurnContext
from orchestration.resolver_turn import ResolverTurnOutcome
from session import mem_get, mem_reset
from tests.test_s61_correction_target_runtime import (
    BackendPayload,
    RecordingBoundaryBackend,
    _fake_backends,
    _fake_target_turn_factory,
    _install_turn_frame,
    _run_materialized_turn,
    _seed_followups,
    _turn_frame,
)
from tests.test_target_boundary_enforced_fullcontext_response import (
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)


def _ask_context(q: str = "test", sid: str = "sid", data: dict | None = None):
    return AskTurnContext(
        q=q,
        sid=sid,
        client_id="demo",
        ref="",
        data=data or {"q": q, "sid": sid, "client_id": "demo"},
        st={},
    )


def _stub_resolver(monkeypatch: pytest.MonkeyPatch, app_module) -> None:
    monkeypatch.setattr(
        app_module,
        "run_resolver_turn",
        lambda **k: ResolverTurnOutcome("content", None, None, False),
    )


def _stub_pre_to_context(monkeypatch: pytest.MonkeyPatch, app_module, ctx: AskTurnContext) -> None:
    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *a, **k: ctx)


# --- A: Default authority ---


def test_app_default_authority_calls_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    target = MagicMock(
        return_value=AskOrchestrationResult(
            kind="service_reply",
            q="q",
            sid="sid",
            client_id="demo",
            service_payload={"answer": "target", "meta": {"answer_path": "target_fullcontext"}},
            service_route="target_fullcontext_materialized",
        )
    )
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    _stub_pre_to_context(monkeypatch, app_module, _ask_context())
    _stub_resolver(monkeypatch, app_module)

    result = app_module._orchestrate_ask_turn({"q": "test", "sid": "sid"})
    target.assert_called_once()
    assert result.service_route == "target_fullcontext_materialized"


def test_http_ask_default_target_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s65-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        _fake_target_turn_factory(composer, semantic, boundary),
    )
    monkeypatch.setattr(app_module, "run_resolver_turn", lambda **k: ResolverTurnOutcome("content", None, None, False))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["answer_path"] == "target_fullcontext"


def test_http_stream_default_target_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s65-stream-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        _fake_target_turn_factory(composer, semantic, boundary),
    )
    monkeypatch.setattr(app_module, "run_resolver_turn", lambda **k: ResolverTurnOutcome("content", None, None, False))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert "event: ui" in resp.data.decode("utf-8")


# --- B: Target failure ---


def test_target_error_does_not_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    def failing_target(**kwargs):
        payload = {
            "answer": "controlled error",
            "meta": {
                "service_route": "target_fullcontext_error",
                "answer_path": "target_fullcontext",
                "target_error_code": "target_runtime_turn_frame_unavailable",
            },
        }
        return AskOrchestrationResult(
            kind="service_reply",
            q=kwargs["q"],
            sid=kwargs["sid"],
            client_id=kwargs["client_id"],
            service_payload=payload,
            service_route="target_fullcontext_error",
        )

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", failing_target)
    _stub_pre_to_context(monkeypatch, app_module, _ask_context())
    _stub_resolver(monkeypatch, app_module)

    result = app_module._orchestrate_ask_turn({"q": "test", "sid": "sid-err"})
    assert result.service_route == "target_fullcontext_error"
    assert result.service_payload["meta"]["target_error_code"] == "target_runtime_turn_frame_unavailable"


def test_target_runtime_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    from core.target_runtime_turn_frame_bridge import TargetRuntimeTurnFrameError

    _stub_pre_to_context(monkeypatch, app_module, _ask_context(q="Сколько стоит?", sid="sid-tf"))
    _stub_resolver(monkeypatch, app_module)

    def _missing_turn_frame():
        raise TargetRuntimeTurnFrameError("target_runtime_turn_frame_unavailable", "not_available")

    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _missing_turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит?", "sid": "sid-tf", "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["service_route"] == "target_fullcontext_error"


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


# --- C: Guards ---


def test_ingress_manual_contact_short_circuits_before_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    target = MagicMock(side_effect=AssertionError("target must not run"))
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    monkeypatch.setattr(
        "orchestration.pre_resolver_turn.classify_ingress",
        lambda **k: IngressRouteResult(
            route="manual_contact",
            confidence=0.95,
            reason="complaint",
            source="llm",
        ),
    )

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Хочу пожаловаться директору", "sid": "sid-ingress", "client_id": "demo"},
    )
    assert resp.status_code == 200
    target.assert_not_called()


def test_lead_flow_short_circuits_before_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    target = MagicMock(side_effect=AssertionError("target must not run"))
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"cta_action": "lead", "q": "", "sid": "sid-lead", "client_id": "demo"},
    )
    assert resp.status_code == 200
    target.assert_not_called()


def test_ref_click_uses_target_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s65-ref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref="price:all_on_4/stages", label="Этапы оплаты"),
    )
    captured: dict[str, str] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(app_module, "run_resolver_turn", lambda **k: ResolverTurnOutcome("content", None, None, False))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4/stages", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured.get("q") == "Этапы оплаты"


# --- D: State and UI ---


def test_target_session_continuity_after_materialized(flask_ctx) -> None:
    sid = f"s65-session-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _install_turn_frame(_turn_frame())
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    st = mem_get(sid)
    assert st["target_runtime_state"]["last_service_id"] == "all_on_4"
    assert st["target_runtime_followups"]


def test_target_cta_mapping_still_works() -> None:
    cta = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="plan")
    assert cta is not None
    assert cta["action"] == "lead"
    assert cta["key"] == "plan"


def test_json_and_stream_share_target_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    calls: list[str] = []
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        calls.append(kwargs["sid"])
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(app_module, "run_resolver_turn", lambda **k: ResolverTurnOutcome("content", None, None, False))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    for endpoint, sid in (("/ask", "sid-json"), ("/ask/stream", "sid-sse")):
        mem_reset(sid)
        resp = client.post(
            endpoint,
            json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
        )
        assert resp.status_code == 200
    assert calls == ["sid-json", "sid-sse"]


# --- E: Frozen artifacts ---


def test_frozen_s62_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
