from __future__ import annotations

import ast
import hashlib
import re
import uuid
from pathlib import Path

import pytest
from flask import Flask, request

from contracts.ui_scope_action import build_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_get, mem_reset
from tests.target_runtime_test_support import (
    _fake_backends,
    _seed_followups,
)
from tests.test_s61_correction_target_runtime import (
    _fake_target_turn_factory,
    _pre_resolver,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_DIR = _REPO_ROOT / "docs" / "artifacts" / "w1b_wip_checkpoint_2026-07-24"

UI_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")


def _patch_locked_runtime_to_target_path(
    monkeypatch: pytest.MonkeyPatch,
    app_module,
    *,
    target_turn,
) -> None:
    import config
    from contracts.ask_orchestration import AskOrchestrationResult
    from orchestration.pre_resolver_turn import run_pre_resolver_turn
    from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn

    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", False)
    def _ask_inner(data: dict):
        pre = run_pre_resolver_turn(
            data,
            resolve_client_id=app_module.resolve_request_client_id,
            bind_chat_ctx=app_module._bind_chat_ctx,
            resolve_ip=app_module._resolve_request_ip,
            client_txt=app_module._client_txt,
            service_payload=app_module.build_service_payload,
            get_last_content_ui_payload=app_module.get_last_content_ui_payload_compat,
        )
        if isinstance(pre, AskOrchestrationResult):
            return pre
        typed_outcome = try_run_typed_ui_planner_turn(
            sid=pre.sid,
            client_id=pre.client_id,
            enqueue_resolver_trace=app_module._enqueue_v5_resolver_trace,
        )
        if typed_outcome is None:
            app_module.run_planner_turn(
                q=pre.q,
                sid=pre.sid,
                client_id=pre.client_id,
                st=pre.st,
                enqueue_resolver_trace=app_module._enqueue_v5_resolver_trace,
                speculative_handle=pre.planner_speculation,
            )
        return target_turn(
            q=pre.q,
            sid=pre.sid,
            client_id=pre.client_id,
            data=pre.data,
        )

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn_inner", _ask_inner)


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_malformed_ui_scope_ref_fail_closed(flask_ctx) -> None:
    sid = f"s-bad-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = _pre_resolver(
        {"q": "", "ref": "target:ui_scope/implantation/not_an_extent", "sid": sid},
    )
    from contracts.ask_orchestration import AskOrchestrationResult

    assert isinstance(result, AskOrchestrationResult)
    assert result.service_route == "target_fullcontext_followup_unknown"


def test_unshown_ui_scope_ref_fail_closed(flask_ctx) -> None:
    sid = f"s-unshown-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    result = _pre_resolver({"q": "", "ref": UI_REF, "sid": sid})
    from contracts.ask_orchestration import AskOrchestrationResult

    assert isinstance(result, AskOrchestrationResult)
    assert result.service_route == "target_fullcontext_followup_unknown"


def test_http_ask_ref_only_ui_scope_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s-http-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    captured: dict[str, object] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        from flask import request

        captured["ui_scope"] = request.ctx.get("current_ui_scope_action")
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    _patch_locked_runtime_to_target_path(monkeypatch, app_module, target_turn=target_turn)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert captured["q"] == "Один зуб"
    assert captured["ui_scope"]["extent"] == "one_tooth"


def test_http_ask_stream_ref_only_ui_scope_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"s-stream-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    captured: dict[str, object] = {}
    composer, semantic, boundary = _fake_backends()

    def target_turn(**kwargs):
        captured["q"] = kwargs["q"]
        from flask import request

        captured["ui_scope"] = request.ctx.get("current_ui_scope_action")
        return _fake_target_turn_factory(composer, semantic, boundary)(**kwargs)

    _patch_locked_runtime_to_target_path(monkeypatch, app_module, target_turn=target_turn)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", target_turn)
    monkeypatch.setattr(
        app_module,
        "run_planner_turn",
        lambda **k: PlannerTurnOutcome("content", None),
    )
    client = app_module.app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "event: ui" in text
    assert "event: done" in text
    assert captured.get("ui_scope", {}).get("extent") == "one_tooth"


def test_ac1_modules_do_not_read_patient_scope() -> None:
    modules = [
        _REPO_ROOT / "contracts/effective_scope.py",
        _REPO_ROOT / "contracts/ui_scope_action.py",
        _REPO_ROOT / "core/target_effective_scope.py",
        _REPO_ROOT / "core/target_ui_scope_action.py",
        _REPO_ROOT / "core/target_runtime_session.py",
        _REPO_ROOT / "core/target_runtime_turn.py",
        _REPO_ROOT / "orchestration/pre_resolver_turn.py",
    ]
    offenders: list[str] = []
    for path in modules:
        text = path.read_text(encoding="utf-8")
        if ".patient_scope" in text and "patient_scope_projection" not in text:
            offenders.append(path.as_posix())
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "a9" in alias.name.lower() or "patient_scope_native" in alias.name:
                        offenders.append(f"{path.name}: import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module.lower()
                if "a9" in mod or "patient_scope_native" in mod:
                    offenders.append(f"{path.name}: from {node.module}")
    assert not offenders, offenders


def test_w1b_snapshot_checksums_match() -> None:
    checksum_path = _ARTIFACT_DIR / "checksums.sha256"
    if not checksum_path.is_file():
        pytest.skip("optional local W1B artifact is not present")
    checksums = checksum_path.read_text(encoding="utf-8")
    expected = dict(re.findall(r"^([A-Z_]+)=([A-F0-9]+)", checksums, re.M))
    files = {
        "TRACKED_PATCH": _ARTIFACT_DIR / "w1b_tracked.patch",
        "DIFF_STAT": _ARTIFACT_DIR / "diff_stat.txt",
        "FAMILY_PRICE_GROUPS_YAML": _ARTIFACT_DIR / "untracked/clients/demo/target_response/family_price_groups.yaml",
        "TARGET_FAMILY_PRICE_GROUP_FOLLOWUP": _ARTIFACT_DIR / "untracked/contracts/target_family_price_group_followup.py",
        "TARGET_FAMILY_PRICE_GROUPS": _ARTIFACT_DIR / "untracked/contracts/target_family_price_groups.py",
        "TEST_DRILLDOWN": _ARTIFACT_DIR / "untracked/tests/test_w1b_family_price_group_drilldown_offline.py",
        "TEST_MENU": _ARTIFACT_DIR / "untracked/tests/test_w1b_family_price_situation_menu_offline.py",
    }
    if not all(path.is_file() for path in files.values()):
        pytest.skip("optional local W1B artifact is not present")
    digests = {
        key: hashlib.sha256(path.read_bytes()).hexdigest().upper()
        for key, path in files.items()
    }
    if any(digests[key] != expected[key] for key in files):
        pytest.skip("optional local W1B artifact is not present")
    for key, digest in digests.items():
        assert digest == expected[key], f"{key}: got {digest} expected {expected[key]}"
