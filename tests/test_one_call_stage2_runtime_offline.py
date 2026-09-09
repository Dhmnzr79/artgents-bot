"""Stage 2: FullContext One Call as the default HTTP runtime (offline)."""

from __future__ import annotations

import json

import pytest

import app as app_module
import config
from core.one_call_client_pack_identity import build_client_pack_identity
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.provider_call_budget import ProviderCallPolicy, current_provider_call_budget, http_provider_budget_scope
from core.sales_one_plus_turn import SalesOnePlusBackendFailure
from tests.test_sales_one_plus_turn import answer_envelope


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0
        self.invocation = None
        self.model = config.SALES_ONE_PLUS_MODEL

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        text = str(self.output)
        on_raw_delta(text)
        return None


def _install_one_call_backend(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(config, "LEGACY_EMERGENCY_RUNTIME_ON", False)
    monkeypatch.delenv("SALES_ONE_PLUS_ON", raising=False)

    def _factory() -> _CountingBackend:
        return backend

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _factory,
    )


def _legacy_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    counts = {"pre_resolver": 0, "planner": 0, "target": 0}

    def _pre_resolver(*_a, **_k):
        counts["pre_resolver"] += 1
        raise AssertionError("legacy pre_resolver must not run")

    def _planner(**_k):
        counts["planner"] += 1
        raise AssertionError("legacy planner must not run")

    def _target(**_k):
        counts["target"] += 1
        raise AssertionError("legacy target_fullcontext must not run")

    monkeypatch.setattr(app_module, "run_pre_resolver_turn", _pre_resolver)
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


@pytest.fixture
def flask_app():
    return app_module.app


def test_ask_default_without_sales_one_plus_env_uses_one_call(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    monkeypatch.delenv("SALES_ONE_PLUS_ON", raising=False)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-default", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_ask_sales_one_plus_zero_does_not_enable_legacy(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    monkeypatch.setenv("SALES_ONE_PLUS_ON", "0")
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-zero", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_ask_stream_without_flag_uses_one_call(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)
    monkeypatch.delenv("SALES_ONE_PLUS_ON", raising=False)

    resp = flask_app.test_client().post(
        "/ask/stream",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-stream", "client_id": "demo"},
    )
    assert resp.status_code == 200
    _parse_sse_ui_payload(resp)
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_model_turn_makes_single_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_one_call_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)

    flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-single", "client_id": "demo"},
    )
    assert backend.call_count == 1


def test_deterministic_parking_route_makes_zero_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("unused"))
    _install_one_call_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Есть ли парковка?", "sid": "s2-parking", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert "парков" in str(resp.get_json().get("answer") or "").lower()
    assert backend.call_count == 0


def test_provider_exception_does_not_invoke_legacy(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(SalesOnePlusBackendFailure("provider_error"))
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-exc", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_provider_timeout_does_not_invoke_legacy(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(TimeoutError("provider timeout"))
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-timeout", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_invalid_envelope_does_not_invoke_legacy(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend("{not-json")
    _install_one_call_backend(monkeypatch, backend)
    legacy = _legacy_spies(monkeypatch)

    resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-invalid", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert legacy == {"pre_resolver": 0, "planner": 0, "target": 0}
    assert backend.call_count == 1


def test_ask_and_stream_share_authoritative_payload(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    envelope = answer_envelope("Стерильность по протоколу клиники.")
    ask_backend = _CountingBackend(envelope)
    stream_backend = _CountingBackend(envelope)
    _install_one_call_backend(monkeypatch, ask_backend)
    _legacy_spies(monkeypatch)

    ask_resp = flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-parity-ask", "client_id": "demo"},
    )
    ask_payload = ask_resp.get_json()

    def _stream_factory() -> _CountingBackend:
        return stream_backend

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _stream_factory,
    )
    stream_resp = flask_app.test_client().post(
        "/ask/stream",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-parity-stream", "client_id": "demo"},
    )
    stream_payload = _parse_sse_ui_payload(stream_resp)

    assert ask_payload["answer"] == stream_payload["answer"]
    assert (ask_payload.get("meta") or {}).get("service_route") == (
        stream_payload.get("meta") or {}
    ).get("service_route")
    assert stream_backend.call_count == 1


def test_provider_invocation_uses_configured_model_id(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    captured: list[dict] = []

    def _capture(**kwargs: object) -> None:
        captured.append(dict(kwargs))
        from core.sales_fast_observability import record_sales_fast_observability

        record_sales_fast_observability(**kwargs)

    _install_one_call_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)
    monkeypatch.setenv("SALES_ONE_PLUS_MODEL", "qwen3.7-plus-stage2-test")
    monkeypatch.setattr(config, "SALES_ONE_PLUS_MODEL", "qwen3.7-plus-stage2-test")
    import core.sales_fast_widget_runtime as runtime_module

    monkeypatch.setattr(runtime_module.config, "SALES_ONE_PLUS_MODEL", "qwen3.7-plus-stage2-test")
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.record_sales_fast_observability",
        _capture,
    )

    flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-model", "client_id": "demo"},
    )
    assert backend.call_count == 1
    obs = next(row for row in captured if row.get("backend_invocations") == 1)
    assert obs.get("model") == "qwen3.7-plus-stage2-test"


def test_runtime_provenance_is_safe_and_complete(monkeypatch: pytest.MonkeyPatch, flask_app) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            captured.append(fields)

    _install_one_call_backend(monkeypatch, backend)
    _legacy_spies(monkeypatch)
    monkeypatch.setattr(app_module, "log_json_no_context", _capture)

    question = "Как обеспечивается стерильность?"
    flask_app.test_client().post(
        "/ask",
        json={"q": question, "sid": "s2-prov", "client_id": "demo"},
    )
    assert captured
    diag = captured[-1]
    sales_fast = diag.get("sales_fast") or {}
    demo_hash = build_client_pack_identity("demo").client_pack_hash
    assert sales_fast.get("architecture") == "fullcontext_one_call"
    assert sales_fast.get("model") == config.SALES_ONE_PLUS_MODEL
    assert sales_fast.get("prompt_contract") == ONE_CALL_PROMPT_CONTRACT_VERSION
    assert diag.get("client_id") == "demo"
    assert sales_fast.get("client_pack_hash") == demo_hash
    blob = json.dumps(diag, ensure_ascii=False)
    assert question not in blob
    assert "Стерильность" not in blob
    assert "sk-" not in blob


def test_demo_and_nikadent_provenance_do_not_mix(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    demo_backend = _CountingBackend(answer_envelope("Ответ demo."))
    nika_backend = _CountingBackend(answer_envelope("Ответ nikadent."))
    _install_one_call_backend(monkeypatch, demo_backend)
    _legacy_spies(monkeypatch)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))

    demo_hash = build_client_pack_identity("demo").client_pack_hash
    nika_hash = build_client_pack_identity("nikadent").client_pack_hash
    assert demo_hash != nika_hash

    captured: list[dict] = []

    def _capture_obs(**kwargs: object) -> None:
        captured.append(dict(kwargs))
        from core.sales_fast_observability import record_sales_fast_observability

        record_sales_fast_observability(**kwargs)

    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.record_sales_fast_observability",
        _capture_obs,
    )

    flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-demo", "client_id": "demo"},
    )
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: nika_backend,
    )
    flask_app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": "s2-nika", "client_id": "nikadent"},
    )

    demo_obs = next(row for row in captured if row.get("client_id") == "demo")
    nika_obs = next(row for row in captured if row.get("client_id") == "nikadent")
    assert demo_obs.get("client_pack_hash") == demo_hash
    assert nika_obs.get("client_pack_hash") == nika_hash
    assert demo_obs.get("model") == nika_obs.get("model") == config.SALES_ONE_PLUS_MODEL


def test_one_call_locked_budget_without_legacy_emergency_flag() -> None:
    with http_provider_budget_scope(request_id="stage2-default", sales_one_plus_on=True):
        budget = current_provider_call_budget()
        assert budget is not None
        assert budget.policy == ProviderCallPolicy.ONE_CALL_LOCKED
