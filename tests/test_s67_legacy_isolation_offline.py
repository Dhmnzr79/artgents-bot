"""S67 offline acceptance: legacy answer path not eagerly loaded; target-only authority."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ingress_route import IngressRouteResult
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_widget import build_target_runtime_widget_cta
from evals.v5.fullcontext_response_eval_contract import sha256_file_hex
from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged
from evals.v5.s66_default_authority_live_contract import assert_frozen_s63_live_artifacts_unchanged
from orchestration.planner_turn import PlannerTurnOutcome
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

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP_PATH = _REPO_ROOT / "app.py"

LEGACY_EAGER_MODULES = (
    "orchestration.ask_turn",
    "chunk_responder",
    "source_routing",
    "orchestration.composer_flow",
)

FROZEN_S66_ARTIFACT_SHA256: dict[str, str] = {
    "s66_default_authority_live_attempt.json": (
        "a0b4ce5af4f3acce0e9e43820a82f52d1aa6200ce808f98a032bb78914364d04"
    ),
    "s66_default_authority_live_audit.log": (
        "078146892a3afe2aaed4dfb95385087b05063500edeec9b4a963089f1f4bed07"
    ),
    "s66_default_authority_live_call_ledger.jsonl": (
        "70617b0787ce4c3a69de0aef3181d6050a1cc1ce3a34a6870ea2c308b5cd4249"
    ),
    "s66_default_authority_live_manifest.json": (
        "1b56d27b2f9eb13f0236a6d149ea8daeddd9a704049534a1cdd589675fe6b7ab"
    ),
    "s66_default_authority_live_manual_review.json": (
        "2b8e1734b7da002b096e62b1c0fad60edbe6802825d7900e2093dd2016b17d69"
    ),
    "s66_default_authority_live_raw.json": (
        "24afce2a33a415a6fe62f778a38abdd6070bbf94afd16814659d457a3bf0d020"
    ),
    "s66_default_authority_live_result.json": (
        "24afce2a33a415a6fe62f778a38abdd6070bbf94afd16814659d457a3bf0d020"
    ),
}

TARGET_RUNTIME_MODULES = (
    "orchestration.target_fullcontext_turn",
    "core.target_runtime_turn",
    "core.target_composer_executor",
    "core.target_medical_boundary",
    "core.target_response_verifier",
)

LEGACY_STACK_PREFIXES = (
    "orchestration.ask_turn",
    "chunk_responder",
    "source_routing",
    "orchestration.composer_flow",
    "core.md_chunks",
)


def _assert_frozen_s66_artifacts_unchanged() -> None:
    artifacts_dir = _REPO_ROOT / "evals" / "v5" / "artifacts"
    for name, expected in FROZEN_S66_ARTIFACT_SHA256.items():
        path = artifacts_dir / name
        assert path.exists(), f"frozen s66 artifact missing: {path}"
        actual = sha256_file_hex(path)
        assert actual == expected, f"s66 artifact sha mismatch path={path} expected={expected} actual={actual}"


def _install_default_target_http(monkeypatch: pytest.MonkeyPatch, app_module) -> tuple:
    get_chunk = MagicMock(side_effect=AssertionError("get_chunk_by_ref must not run"))
    answer_plan = MagicMock(side_effect=AssertionError("answer_plan_from_ctx must not run"))

    monkeypatch.setattr("core.md_chunks.get_chunk_by_ref", get_chunk)
    monkeypatch.setattr("core.answer_planner.answer_plan_from_ctx", answer_plan)

    composer, semantic, boundary = _fake_backends()
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        _fake_target_turn_factory(composer, semantic, boundary),
    )
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)
    return get_chunk, answer_plan


# --- A: Default import isolation ---


def test_default_import_does_not_eagerly_load_legacy_modules() -> None:
    script = textwrap.dedent(
        f"""
        import sys
        repo = {str(_REPO_ROOT)!r}
        if repo not in sys.path:
            sys.path.insert(0, repo)
        legacy = {list(LEGACY_EAGER_MODULES)!r}
        loaded_before = [m for m in legacy if m in sys.modules]
        import app  # noqa: F401
        loaded_after = [m for m in legacy if m in sys.modules]
        assert not loaded_before, loaded_before
        assert not loaded_after, loaded_after
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- B: Default /ask ---


def test_default_ask_target_only_no_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s67-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    get_chunk, answer_plan = _install_default_target_http(
        monkeypatch, app_module
    )

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["answer_path"] == "target_fullcontext"
    get_chunk.assert_not_called()
    answer_plan.assert_not_called()


# --- C: Default /ask/stream ---


def test_default_stream_target_only_no_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s67-stream-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    get_chunk, answer_plan = _install_default_target_http(
        monkeypatch, app_module
    )

    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "event: ui" in text
    get_chunk.assert_not_called()
    answer_plan.assert_not_called()


# --- D: Target error ---


def test_target_error_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s67-err-{uuid.uuid4().hex[:8]}"
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
    _stub_pre_to_context(monkeypatch, app_module, _ask_context(sid=sid))
    _stub_resolver(monkeypatch, app_module)

    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "Сколько стоит?", "sid": sid, "client_id": "demo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta"]["target_error_code"] == "target_runtime_turn_frame_unavailable"
    assert "answer_plan" not in (body.get("meta") or {})


# --- E: Target ref-click ---


def test_target_ref_click_no_get_chunk_by_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s67-ref-{uuid.uuid4().hex[:8]}"
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
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": "price:all_on_4/stages", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured.get("q") == "Этапы оплаты"
    get_chunk.assert_not_called()


# --- F: Shared guards ---


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

    sid = f"s67-planner-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    called: list[str] = []
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        called.append(kwargs["sid"])
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr("core.target_runtime_turn.load_runtime_turn_frame", _turn_frame)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert called == [sid]


# --- G: Session/UI ---


def test_target_session_continuity(flask_ctx) -> None:
    sid = f"s67-session-{uuid.uuid4().hex[:8]}"
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


def test_target_service_reply_skips_legacy_answer_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    answer_plan = MagicMock(side_effect=AssertionError("answer_plan must not run"))
    monkeypatch.setattr("core.answer_planner.answer_plan_from_ctx", answer_plan)
    payload = {
        "answer": "target answer",
        "meta": {"answer_path": "target_fullcontext", "client_id": "demo"},
    }
    with app_module.app.test_request_context():
        request.ctx = {}
        out = app_module._service_reply(
            payload,
            "sid-svc",
            "q",
            route="target_fullcontext_materialized",
        )
    body = out.get_json()
    assert body["answer"] == "target answer"
    assert "answer_plan" not in (body.get("meta") or {})
    answer_plan.assert_not_called()


# --- H: Frozen protection ---


def test_frozen_s62_s63_s66_artifacts_unchanged() -> None:
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    _assert_frozen_s66_artifacts_unchanged()


# --- I: Import firewall ---


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


def test_app_has_no_kill_switch_symbol() -> None:
    text = _APP_PATH.read_text(encoding="utf-8")
    assert "TARGET_FULLCONTEXT_DEV" not in text
    assert "orchestrate_routing_after_resolver" not in text


def test_target_modules_do_not_import_legacy_stack() -> None:
    for module_name in TARGET_RUNTIME_MODULES:
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, module_name
        module = importlib.import_module(module_name)
        source_path = getattr(module, "__file__", None)
        assert source_path, module_name
        text = Path(source_path).read_text(encoding="utf-8")
        for legacy in LEGACY_STACK_PREFIXES:
            assert legacy not in text, f"{module_name} references {legacy}"


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_target_ref_pre_resolver_skips_chunk(monkeypatch: pytest.MonkeyPatch, flask_ctx) -> None:
    get_chunk = MagicMock(side_effect=AssertionError("legacy chunk ref must not run"))
    monkeypatch.setattr("core.md_chunks.get_chunk_by_ref", get_chunk)
    _pre_resolver(
        {"q": "", "ref": "price:all_on_4/stages", "sid": "sid-pre", "client_id": "demo"},
    )
    get_chunk.assert_not_called()
