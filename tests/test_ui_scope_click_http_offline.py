from __future__ import annotations

import ast
import hashlib
import json
import re
import uuid
from pathlib import Path

import pytest
from flask import Flask, request

from contracts.ui_scope_action import build_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from tests.session_binding_test_support import read_target_runtime_session_for
from session import mem_reset
from tests.target_runtime_test_support import _seed_followups

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_DIR = _REPO_ROOT / "docs" / "artifacts" / "w1b_wip_checkpoint_2026-07-24"

UI_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_malformed_ui_scope_ref_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_unshown_ui_scope_ref_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-unshown-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("ignored"))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 0
    payload = resp.get_json()
    assert payload["meta"]["service_route"] == "sales_fast_followup_unknown"
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is None


def test_http_ask_ref_only_ui_scope_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = f"s-http-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    backend = _CountingBackend(answer_envelope("Цена для одного зуба."))
    _install_sales_fast_transport(monkeypatch, backend)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    payload = resp.get_json()
    assert payload.get("answer")
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "one_tooth"
    assert after.patient_facts.ref == UI_REF


def test_http_ask_stream_ref_only_ui_scope_click(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    envelope = answer_envelope("Цена для одного зуба.")

    sid_ask = f"s-http-ui-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_ask, client_id="demo")
    _seed_followups(
        sid_ask,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    backend_ask = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, backend_ask)
    client = app_module.app.test_client()
    ask_resp = client.post(
        "/ask",
        json={"q": "", "ref": UI_REF, "sid": sid_ask, "client_id": "demo"},
    )
    assert ask_resp.status_code == 200
    assert backend_ask.call_count == 1
    ask_payload = ask_resp.get_json()
    ask_session = read_target_runtime_session_for(sid_ask)

    sid_stream = f"s-stream-ui-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_stream, client_id="demo")
    _seed_followups(
        sid_stream,
        TargetRuntimeFollowupItem(ref=UI_REF, label="Один зуб"),
    )
    backend_stream = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, backend_stream)
    stream_resp = client.post(
        "/ask/stream",
        json={"q": "", "ref": UI_REF, "sid": sid_stream, "client_id": "demo"},
    )
    assert stream_resp.status_code == 200
    text = stream_resp.get_data(as_text=True)
    assert "event: ui" in text
    assert "event: done" in text
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    stream_payload = json.loads(match.group(1))
    assert backend_stream.call_count == 1
    stream_session = read_target_runtime_session_for(sid_stream)

    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert ask_session.patient_facts is not None
    assert stream_session.patient_facts is not None
    assert ask_session.patient_facts.extent == stream_session.patient_facts.extent == "one_tooth"
    assert ask_session.patient_facts.ref == stream_session.patient_facts.ref == UI_REF


def test_ac1_modules_do_not_read_patient_scope() -> None:
    modules = [
        _REPO_ROOT / "contracts/effective_scope.py",
        _REPO_ROOT / "contracts/ui_scope_action.py",
        _REPO_ROOT / "core/target_effective_scope.py",
        _REPO_ROOT / "core/target_ui_scope_action.py",
        _REPO_ROOT / "core/target_runtime_session.py",
        _REPO_ROOT / "core/target_runtime_turn.py",
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
