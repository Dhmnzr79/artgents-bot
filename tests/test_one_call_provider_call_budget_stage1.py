"""Stage 1: HTTP-scoped provider call budget and ONE_CALL wiring bans."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import app as app_module
import config
import ingress_gate
import llm as llm_module
from core.provider_call_budget import (
    ProviderCallBudgetExceeded,
    ProviderCallLegacyBlocked,
    ProviderCallPolicy,
    http_provider_budget_scope,
    reserve_provider_call,
)
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.sales_one_plus import SalesOnePlusInvocation
from core import turn_timing
from core.sales_fast_observability import record_sales_fast_observability
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend


class _FakeCompletion:
    def __init__(self) -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content='{"route":"normal"}'))]
        self.usage = None


def test_flag_off_legacy_accounting_allows_multiple_calls() -> None:
    calls: list[str] = []

    def _fake_create(**kwargs):
        calls.append(str(kwargs.get("provider_call_source")))
        return _FakeCompletion()

    with http_provider_budget_scope(request_id="req-off", sales_one_plus_on=False):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(llm_module.chat_client.chat.completions, "create", _fake_create)
            llm_module.chat_completions_create(
                model="m",
                messages=[],
                provider_call_source="planner",
            )
            llm_module.chat_completions_create(
                model="m",
                messages=[],
                provider_call_source="composer",
            )
    assert len(calls) == 2


def test_one_call_locked_blocks_legacy_before_transport() -> None:
    with http_provider_budget_scope(request_id="req-on", sales_one_plus_on=True):
        with pytest.raises(ProviderCallLegacyBlocked):
            reserve_provider_call(model="m", source="ingress")
        with pytest.raises(ProviderCallLegacyBlocked):
            reserve_provider_call(model="m", source="planner")
        with pytest.raises(ProviderCallLegacyBlocked):
            reserve_provider_call(model="m", source="verifier")


def test_one_call_locked_allows_single_sales_fast_call() -> None:
    with http_provider_budget_scope(request_id="req-sf", sales_one_plus_on=True):
        idx = reserve_provider_call(model="qwen", source="sales_fast")
        assert idx == 1
        with pytest.raises(ProviderCallBudgetExceeded):
            reserve_provider_call(model="qwen", source="sales_fast")


def test_second_call_blocked_at_public_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_module.chat_client.chat.completions,
        "create",
        lambda **_kwargs: _FakeCompletion(),
    )
    with http_provider_budget_scope(request_id="req-wrap", sales_one_plus_on=True):
        llm_module.chat_completions_create(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            provider_call_source="sales_fast",
        )
        with pytest.raises(ProviderCallBudgetExceeded):
            llm_module.chat_completions_create(
                model="m",
                messages=[{"role": "user", "content": "again"}],
                provider_call_source="sales_fast",
            )


def test_transport_failure_does_not_allow_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"n": 0}

    def _fail(**_kwargs):
        attempts["n"] += 1
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _fail)
    with http_provider_budget_scope(request_id="req-fail", sales_one_plus_on=True):
        with pytest.raises(TimeoutError):
            llm_module.chat_completions_create(
                model="m",
                messages=[],
                provider_call_source="sales_fast",
            )
        with pytest.raises(ProviderCallBudgetExceeded):
            llm_module.chat_completions_create(
                model="m",
                messages=[],
                provider_call_source="sales_fast",
            )
    assert attempts["n"] == 1


def test_parallel_requests_have_independent_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_module.chat_client.chat.completions,
        "create",
        lambda **_kwargs: _FakeCompletion(),
    )

    def _one_call(request_id: str) -> int:
        with http_provider_budget_scope(request_id=request_id, sales_one_plus_on=True):
            llm_module.chat_completions_create(
                model="m",
                messages=[],
                provider_call_source="sales_fast",
            )
            from core.provider_call_budget import current_provider_call_budget

            budget = current_provider_call_budget()
            assert budget is not None
            return budget.call_count

    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(_one_call, ("a", "b")))
    assert counts == [1, 1]


def test_ingress_llm_blocked_under_one_call_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _fake_create(**_kwargs):
        calls["n"] += 1
        return _FakeCompletion()

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _fake_create)
    with http_provider_budget_scope(request_id="req-ing", sales_one_plus_on=True):
        result = ingress_gate.classify_ingress(
            "сколько стоит имплантация",
            client_id="demo",
            sid="s1",
        )
    assert calls["n"] == 0
    assert result.route == "normal"
    assert result.source == "fallback"


def test_speculative_planner_not_submitted_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    from core.planner_compute_executor import try_submit_planner_speculation

    handle = try_submit_planner_speculation(
        client_id="demo",
        sid="s2",
        q="сколько стоит",
        history="",
        request_id="r1",
    )
    assert handle is None


def test_flag_off_preserves_planner_target_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", False)
    pre = SimpleNamespace(
        q="ordinary",
        sid="s-off",
        client_id="demo",
        st={},
        data={},
        planner_speculation=None,
    )
    order: list[str] = []

    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *_a, **_k: pre)
    monkeypatch.setattr(app_module, "try_run_typed_ui_planner_turn", lambda **_k: None)
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **_k: order.append("planner"))
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        lambda **kwargs: order.append("target") or type(
            "AskOrchestrationResult",
            (),
            {"kind": "service_reply", "q": pre.q, "sid": pre.sid, "client_id": pre.client_id},
        )(),
    )
    monkeypatch.setattr(
        "orchestration.sales_one_plus_ask_turn.orchestrate_sales_one_plus_ask_turn",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("sales_one_plus must not run when flag OFF")),
    )

    with app_module.app.test_request_context(
        "/ask",
        method="POST",
        json={"q": pre.q, "sid": pre.sid, "client_id": pre.client_id},
    ):
        app_module.request.ctx = app_module.make_request_context()
        app_module._orchestrate_ask_turn(
            {"q": pre.q, "sid": pre.sid, "client_id": pre.client_id}
        )
    assert order == ["planner", "target"]


def test_flag_on_free_text_routes_sales_fast_without_legacy_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    provider_calls: list[str] = []

    def _fake_create(**kwargs):
        provider_calls.append(str(kwargs.get("provider_call_source")))
        return _FakeCompletion()

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _fake_create)
    monkeypatch.setattr(
        app_module,
        "run_pre_resolver_turn",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pre_resolver must not run")),
    )
    monkeypatch.setattr(
        ingress_gate,
        "classify_ingress",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("ingress must not run")),
    )

    def _planner(**_k):
        raise AssertionError("planner must not run when flag ON")

    monkeypatch.setattr(app_module, "run_planner_turn", _planner)
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        lambda **_k: (_ for _ in ()).throw(AssertionError("legacy target must not run")),
    )

    backend = type(
        "B",
        (),
        {
            "call_count": 0,
            "generate": lambda self, _inv: "@ANSWER\nok",
            "generate_stream": lambda self, _inv, on_delta: on_delta("@ANSWER\nok"),
        },
    )()
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )

    with app_module.app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "боюсь боли при имплантации", "sid": "s-on", "client_id": "demo"},
    ):
        app_module.request.ctx = app_module.make_request_context()
        out = app_module._orchestrate_ask_turn(
            {"q": "боюсь боли при имплантации", "sid": "s-on", "client_id": "demo"}
        )
    assert out.kind == "service_reply"
    assert provider_calls == []


def test_production_orchestrate_wraps_http_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    seen: dict[str, object] = {}

    def _inner(data):
        from core.provider_call_budget import current_provider_call_budget

        budget = current_provider_call_budget()
        seen["policy"] = budget.policy if budget else None
        seen["request_id"] = budget.request_id if budget else None
        return type(
            "AskOrchestrationResult",
            (),
            {"kind": "service_reply", "q": data.get("q"), "sid": "s", "client_id": "demo"},
        )()

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn_inner", _inner)
    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()))

    with app_module.app.test_request_context("/ask", method="POST", json={"q": "x"}):
        app_module.request.ctx = app_module.make_request_context()
        app_module._orchestrate_ask_turn({"q": "x", "sid": "s", "client_id": "demo"})
    assert seen["policy"] == ProviderCallPolicy.ONE_CALL_LOCKED
    assert seen["request_id"]


def test_observability_logs_exclude_patient_payload(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        llm_module.chat_client.chat.completions,
        "create",
        lambda **_kwargs: _FakeCompletion(),
    )
    patient = "у меня кровь и сильная боль"
    with http_provider_budget_scope(request_id="req-log", sales_one_plus_on=True):
        llm_module.chat_completions_create(
            model="m",
            messages=[{"role": "user", "content": patient}],
            provider_call_source="sales_fast",
        )
    blob = "\n".join(caplog.messages)
    assert "provider_call_reserved" in blob or "provider_call_finished" in blob
    assert patient not in blob
    for line in caplog.messages:
        if not line.strip().startswith("{"):
            continue
        payload = json.loads(line)
        joined = json.dumps(payload, ensure_ascii=False)
        assert patient not in joined
        assert "prompt" not in joined.lower()
        assert "corpus" not in joined.lower()


def _minimal_invocation() -> SalesOnePlusInvocation:
    authority = ExactSalesFieldAuthority(authority="exact_turn", provenance="stage1_test")
    resolution = ExactSalesResolution(
        service_id="implant",
        aspect=None,
        extent=None,
        jaw=None,
        stage=None,
        service_id_authority=authority,
        aspect_authority=authority,
        extent_authority=authority,
        jaw_authority=authority,
        stage_authority=authority,
    )
    return SalesOnePlusInvocation(
        system_prompt="system policy",
        user_prompt="user prompt body",
        model_corpus_text="corpus text",
        user_message="сколько стоит имплант",
        exact_sales_resolution=resolution,
        current_strict_facts=(),
        sales_context={},
    )


def _finished_events(caplog: pytest.LogCaptureFixture) -> list[dict]:
    events: list[dict] = []
    for record in caplog.records:
        if record.getMessage() != "provider_call_finished":
            continue
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            events.append({"msg": record.getMessage(), **extra})
    return events


def test_provider_call_finished_event_includes_source_and_model_on_success(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        llm_module.chat_client.chat.completions,
        "create",
        lambda **_kwargs: _FakeCompletion(),
    )
    with http_provider_budget_scope(request_id="req-finish-ok", sales_one_plus_on=True):
        llm_module.chat_completions_create(
            model="qwen-test",
            messages=[{"role": "user", "content": "hi"}],
            provider_call_source="sales_fast",
        )
    events = _finished_events(caplog)
    assert len(events) == 1
    finished = events[0]
    assert finished["request_id"] == "req-finish-ok"
    assert finished["call_index"] == 1
    assert finished["call_source"] == "sales_fast"
    assert finished["model"] == "qwen-test"
    assert finished["outcome"] == "ok"
    assert isinstance(finished.get("duration_ms"), int)


def test_provider_call_finished_event_includes_source_and_model_on_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO)

    def _fail(**_kwargs):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(llm_module.chat_client.chat.completions, "create", _fail)
    with http_provider_budget_scope(request_id="req-finish-err", sales_one_plus_on=True):
        with pytest.raises(TimeoutError):
            llm_module.chat_completions_create(
                model="qwen-test",
                messages=[],
                provider_call_source="sales_fast",
            )
    events = _finished_events(caplog)
    assert len(events) == 1
    finished = events[0]
    assert finished["request_id"] == "req-finish-err"
    assert finished["call_index"] == 1
    assert finished["call_source"] == "sales_fast"
    assert finished["model"] == "qwen-test"
    assert finished["outcome"] == "error"
    assert isinstance(finished.get("duration_ms"), int)


def test_live_backend_uses_budget_not_local_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    transport_calls = {"n": 0}

    def _transport_create(**_kwargs):
        transport_calls["n"] += 1
        return _FakeCompletion()

    monkeypatch.setattr(
        llm_module.chat_client.chat.completions,
        "create",
        _transport_create,
    )
    backend = SalesOnePlusLiveBackend(model="qwen-test")
    invocation = _minimal_invocation()
    with http_provider_budget_scope(request_id="req-backend", sales_one_plus_on=True):
        from core.provider_call_budget import current_provider_call_budget

        backend.generate(invocation)
        assert transport_calls["n"] == 1
        budget = current_provider_call_budget()
        assert budget is not None
        assert budget.call_count == 1

        with app_module.app.test_request_context("/ask", method="POST", json={"q": "x"}):
            app_module.request.ctx = {}
            record_sales_fast_observability(
                architecture="new",
                route="model",
                provider_calls=999,
                model=None,
            )
            obs = turn_timing.summary_for_turn_complete().get("sales_fast_observability") or {}
        assert obs.get("provider_calls") == 1

        with pytest.raises(ProviderCallBudgetExceeded):
            llm_module.chat_completions_create(
                model="qwen-test",
                messages=[{"role": "user", "content": "x"}],
                provider_call_source="sales_fast",
            )
        assert transport_calls["n"] == 1
