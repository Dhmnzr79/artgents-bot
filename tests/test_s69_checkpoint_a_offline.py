"""S69 Checkpoint A offline acceptance: FullContext-only product authority."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ingress_route import IngressRouteResult
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_widget import build_target_runtime_widget_cta
from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged
from evals.v5.s66_default_authority_live_contract import assert_frozen_s63_live_artifacts_unchanged
from orchestration.planner_turn import PlannerTurnOutcome
from orchestration.route_guards import check_rate_limit
from session import mem_get, mem_reset
from tests.test_s61_correction_target_runtime import (
    _fake_backends,
    _fake_target_turn_factory,
    _install_turn_frame,
    _pre_resolver,
    _run_materialized_turn,
    _seed_followups,
    _turn_frame,
)
from tests.test_s65_authority_switch_offline import (
    _ask_context,
    _stub_pre_to_context,
    _stub_resolver,
)
from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP_PATH = _REPO_ROOT / "app.py"
_CONFIG_PATH = _REPO_ROOT / "config.py"


def _install_target_http(monkeypatch: pytest.MonkeyPatch, app_module) -> MagicMock:
    get_chunk = MagicMock(side_effect=AssertionError("get_chunk_by_ref must not run"))
    monkeypatch.setattr("core.md_chunks.get_chunk_by_ref", get_chunk)
    composer, semantic, boundary = _fake_backends()
    target = _fake_target_turn_factory(composer, semantic, boundary)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)
    return get_chunk


def test_config_has_no_target_fullcontext_dev_flag() -> None:
    text = _CONFIG_PATH.read_text(encoding="utf-8")
    assert "TARGET_FULLCONTEXT_DEV" not in text


def test_app_has_no_kill_switch_or_legacy_dispatch() -> None:
    text = _APP_PATH.read_text(encoding="utf-8")
    assert "TARGET_FULLCONTEXT_DEV" not in text
    assert "orchestrate_routing_after_resolver" not in text
    assert 'kind="chunk"' not in text
    assert 'kind="composer"' not in text
    assert "kind='chunk'" not in text
    assert "kind='composer'" not in text


def test_app_has_no_top_level_legacy_imports() -> None:
    tree = ast.parse(_APP_PATH.read_text(encoding="utf-8"))
    forbidden = {"chunk_responder", "orchestration.ask_turn"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden or module.split(".")[0] in forbidden:
                pytest.fail(f"top-level legacy import found: {module}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden:
                    pytest.fail(f"top-level legacy import found: {alias.name}")


def test_http_ask_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s69-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    get_chunk = _install_target_http(monkeypatch, app_module)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["answer_path"] == "target_fullcontext"
    get_chunk.assert_not_called()


def test_http_stream_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s69-stream-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    get_chunk = _install_target_http(monkeypatch, app_module)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert "event: ui" in resp.data.decode("utf-8")
    get_chunk.assert_not_called()


def test_target_error_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s69-err-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

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
    _stub_pre_to_context(monkeypatch, app_module, _ask_context(q="Сколько стоит?", sid=sid))
    _stub_resolver(monkeypatch, app_module)

    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "Сколько стоит?", "sid": sid, "client_id": "demo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["target_error_code"] == "target_runtime_turn_frame_unavailable"
    assert "answer_plan" not in (body.get("meta") or {})


def test_ref_click_no_get_chunk_by_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s69-ref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref="price:all_on_4/stages", label="Этапы оплаты"),
    )
    get_chunk = MagicMock(side_effect=AssertionError("get_chunk_by_ref must not run"))
    monkeypatch.setattr("core.md_chunks.get_chunk_by_ref", get_chunk)
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
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4/stages", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured.get("q") == "Этапы оплаты"
    get_chunk.assert_not_called()


def test_ingress_hard_stop_before_target(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_lead_flow_before_target(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_planner_turn_frame_path_reaches_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s69-planner-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    called: list[str] = []
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        called.append(kwargs["sid"])
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert called == [sid]


def test_pre_resolver_ref_skips_chunk(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    get_chunk = MagicMock(side_effect=AssertionError("legacy chunk ref must not run"))
    monkeypatch.setattr("core.md_chunks.get_chunk_by_ref", get_chunk)
    _pre_resolver(
        {"q": "", "ref": "price:all_on_4/stages", "sid": "sid-pre", "client_id": "demo"},
    )
    get_chunk.assert_not_called()


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_target_session_continuity(flask_ctx) -> None:
    sid = f"s69-session-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _install_turn_frame(_turn_frame())
    outcome = _run_materialized_turn(sid)
    assert outcome.widget.kind == "materialized"
    st = mem_get(sid)
    assert st["target_runtime_state"]["last_service_id"] == "all_on_4"
    assert st["target_runtime_followups"]


def test_target_cta_mapping() -> None:
    cta = build_target_runtime_widget_cta(client_id="demo", selected_cta_key="plan")
    assert cta is not None
    assert cta["action"] == "lead"


def test_frozen_s62_s63_s66_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    _assert_frozen_s66_artifacts_unchanged()


def test_rate_limit_blocks_after_bucket_exhaustion() -> None:
    ip = f"s69-rate-limit-{uuid.uuid4().hex[:8]}"
    from orchestration import route_guards

    with route_guards._IP_RATE_LOCK:
        route_guards._IP_RATE_BUCKETS.clear()
    try:
        for _ in range(40):
            assert check_rate_limit(ip) is True
        assert check_rate_limit(ip) is False
    finally:
        with route_guards._IP_RATE_LOCK:
            route_guards._IP_RATE_BUCKETS.clear()
