"""Stage 3A: permanent One Call HTTP cutover; legacy modules remain dormant on disk."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

import app as app_module
import config
from core.provider_call_budget import ProviderCallPolicy, current_provider_call_budget, http_provider_budget_scope
from core.sales_one_plus_turn import SalesOnePlusBackendFailure
from tests.test_sales_one_plus_turn import admin_envelope, answer_envelope


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        text = str(self.output)
        on_raw_delta(text)
        return None


def _install_backend(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _legacy_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    counts = {"pre_resolver": 0, "planner": 0, "target": 0}

    def _pre(*_a, **_k):
        counts["pre_resolver"] += 1
        raise AssertionError("legacy pre_resolver must not run")

    def _planner(**_k):
        counts["planner"] += 1
        raise AssertionError("legacy planner must not run")

    def _target(**_k):
        counts["target"] += 1
        raise AssertionError("legacy target_fullcontext must not run")

    monkeypatch.setattr(app_module, "run_pre_resolver_turn", _pre)
    monkeypatch.setattr(app_module, "run_planner_turn", _planner)
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", _target)
    return counts


def _parse_sse_ui_payload(resp) -> dict:
    buffer = ""
    ui_payload: dict | None = None
    for chunk in resp.response:
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            if "event: ui" not in block:
                continue
            for line in block.splitlines():
                if line.startswith("data: "):
                    ui_payload = json.loads(line[len("data: ") :])
    assert ui_payload is not None
    return ui_payload


def test_ask_default_routes_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-default", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_sales_one_plus_zero_still_routes_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    monkeypatch.setenv("SALES_ONE_PLUS_ON", "0")
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-zero", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_legacy_emergency_env_does_not_route_http_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    monkeypatch.setenv("LEGACY_EMERGENCY_RUNTIME_ON", "1")
    monkeypatch.setattr(config, "LEGACY_EMERGENCY_RUNTIME_ON", True)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-emerg", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1
    assert config.is_one_call_runtime_locked() is True


def test_ask_stream_routes_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-stream", "client_id": "demo"},
    )
    assert resp.status_code == 200
    _parse_sse_ui_payload(resp)
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_one_call_failure_is_fail_closed_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(SalesOnePlusBackendFailure("provider_error"))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-fail", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_one_call_timeout_is_fail_closed_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(TimeoutError("provider timeout"))
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-timeout", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_invalid_envelope_is_fail_closed_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend("{not-json")
    _install_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s3a-invalid", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_admin_semantic_turn_uses_single_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(admin_envelope())
    _install_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={
            "q": "После операции появилось воспаление, подскажите порядок действий",
            "sid": "s3a-admin",
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    assert backend.call_count == 1


def test_deterministic_parking_uses_zero_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("unused"))
    _install_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Есть ли парковка?", "sid": "s3a-parking", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert "парков" in str(resp.get_json().get("answer") or "").lower()
    assert backend.call_count == 0


def test_http_budget_always_one_call_locked() -> None:
    with http_provider_budget_scope(request_id="stage3a", sales_one_plus_on=True):
        budget = current_provider_call_budget()
        assert budget is not None
        assert budget.policy == ProviderCallPolicy.ONE_CALL_LOCKED


def test_startup_diagnostics_always_fullcontext_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _capture(_logger, event, **fields):
        if event == "runtime_provenance_startup":
            captured.append(fields)

    monkeypatch.setattr("core.startup_check.log_json", _capture)
    monkeypatch.setattr("core.startup_check.list_buildable_client_ids", lambda: ["demo"])
    monkeypatch.setattr(
        "core.startup_check.load_target_client_data",
        lambda _cid: SimpleNamespace(bundle=SimpleNamespace(services={"x": 1}, offers={"y": 1})),
    )
    monkeypatch.setattr("core.startup_check.client_md_dir", lambda _cid: "clients/demo/md")
    monkeypatch.setattr("core.startup_check.os.path.isdir", lambda _p: True)
    monkeypatch.setattr("core.startup_check.os.listdir", lambda _p: ["a.md"])
    monkeypatch.setattr("core.startup_check.os.path.isfile", lambda _p: True)

    from core.startup_check import run_startup_check

    run_startup_check(logging.getLogger("test"))
    assert captured
    assert captured[0]["architecture"] == "fullcontext_one_call"
