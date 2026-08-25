"""Stage 2: ingress reorder, gate-first, typed UI candidate path."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app as app_module
import config
import ingress_gate
import llm as llm_module
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.ui_scope_action import build_ui_scope_ref
from core import turn_timing
from core.provider_call_budget import http_provider_budget_scope
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from orchestration.sales_one_plus_ask_turn import GOVERNED_TYPED_UI_GATE
from session import mem_reset
from tests.test_s61_correction_target_runtime import _seed_followups
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import answer_envelope


class _FakeCompletion:
    def __init__(self) -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content='{"route":"normal"}'))]
        self.usage = None


def _enable_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)


def _spy_legacy_wiring(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    spies = {
        "pre_resolver": MagicMock(side_effect=AssertionError("run_pre_resolver_turn must not run on flag ON")),
        "ingress": MagicMock(side_effect=AssertionError("classify_ingress must not run on flag ON")),
        "planner": MagicMock(side_effect=AssertionError("planner must not run on flag ON")),
        "target": MagicMock(side_effect=AssertionError("legacy target must not run on flag ON")),
    }
    monkeypatch.setattr(app_module, "run_pre_resolver_turn", spies["pre_resolver"])
    monkeypatch.setattr(ingress_gate, "classify_ingress", spies["ingress"])
    monkeypatch.setattr(app_module, "run_planner_turn", spies["planner"])
    monkeypatch.setattr(app_module, "orchestrate_target_fullcontext_turn", spies["target"])
    return spies


def test_on_http_free_text_never_calls_pre_resolver_or_classify_ingress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_flag_on(monkeypatch)
    spies = _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("ответ по базе"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-http-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "боюсь боли при имплантации", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    spies["pre_resolver"].assert_not_called()
    spies["ingress"].assert_not_called()
    spies["planner"].assert_not_called()
    spies["target"].assert_not_called()
    assert backend.call_count == 1


def test_on_http_gate_before_corpus_resolver_and_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_flag_on(monkeypatch)
    order: list[str] = []
    backend = _CountingBackend(answer_envelope("Есть парковка у здания."))

    def _gate(text: str):
        order.append("gate")
        from core.local_problem_gate import decide_local_problem_gate

        return decide_local_problem_gate(text)

    def _load_context(client_id: str):
        order.append("corpus")
        from core.target_runtime_client_context import load_target_runtime_client_context

        return load_target_runtime_client_context(client_id)

    from core.sales_fast_widget_runtime import _resolve_sales_context

    def _resolve(**kwargs):
        order.append("resolver")
        return _resolve_sales_context(**kwargs)

    factory_invoked = {"value": False}

    def _factory() -> _CountingBackend:
        factory_invoked["value"] = True
        return backend

    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.decide_local_problem_gate", _gate)
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.load_target_runtime_client_context",
        _load_context,
    )
    monkeypatch.setattr("core.sales_fast_widget_runtime._resolve_sales_context", _resolve)
    _install_sales_fast_transport(monkeypatch, backend, factory=_factory)
    sid = f"s-order-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert order[:2] == ["gate", "corpus"]
    assert "resolver" in order
    assert factory_invoked["value"] is True
    assert backend.call_count == 1


def test_on_http_ingress_non_normal_cannot_short_circuit_before_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy ingress manual_contact must not run on flag ON even if invoked directly."""

    _enable_flag_on(monkeypatch)
    spies = _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend("@ADMIN\nignored")
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-symptom-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={
            "q": "После операции появилось воспаление, подскажите порядок действий",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    spies["ingress"].assert_not_called()
    assert backend.call_count == 0
    payload = resp.get_json()
    assert payload["meta"]["service_route"] == "sales_fast_admin"


@pytest.mark.parametrize("case_id", ("a02",))
def test_on_http_admin_matrix_zero_transport(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from tests.one_call_stage2_fixture import case_by_id, load_stage2_cases

    fixture = Path(__file__).resolve().parent / "fixtures" / "one_call_stage2_cases.json"
    cases = load_stage2_cases(fixture)
    case = next(c for c in cases if c.case_id == case_id)
    _enable_flag_on(monkeypatch)
    spies = _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend("@ADMIN\nignored")
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"admin-{case_id}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": case.user_message, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    spies["ingress"].assert_not_called()
    spies["pre_resolver"].assert_not_called()
    assert backend.call_count == 0


@pytest.mark.parametrize("case_id", ("a01", "a03"))
def test_on_http_general_medical_faq_pass_with_one_call(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from tests.one_call_stage2_fixture import load_stage2_cases

    fixture = Path(__file__).resolve().parent / "fixtures" / "one_call_stage2_cases.json"
    cases = load_stage2_cases(fixture)
    case = next(c for c in cases if c.case_id == case_id)
    _enable_flag_on(monkeypatch)
    _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("Ответ по материалам клиники о безопасности имплантации."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"faq-{case_id}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": case.user_message, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    payload = resp.get_json()
    assert str(payload.get("answer") or "").strip()
    assert payload["meta"]["service_route"] != "sales_fast_admin"


@pytest.mark.parametrize("case_id", ("f01", "f02", "f03"))
def test_on_http_sales_fears_pass_with_one_call(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from tests.one_call_stage2_fixture import case_by_id, load_stage2_cases

    fixture = Path(__file__).resolve().parent / "fixtures" / "one_call_stage2_cases.json"
    cases = load_stage2_cases(fixture)
    case = next(c for c in cases if c.case_id == case_id)
    _enable_flag_on(monkeypatch)
    _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("ответ по базе клиники"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"fear-{case_id}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": case.user_message, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1


def test_on_http_contacts_after_gate_zero_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_flag_on(monkeypatch)
    _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("ignored"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-contacts-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "телефон клиники", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 0
    assert resp.get_json()["meta"]["service_route"] == "sales_fast_contacts"


def test_on_http_booking_after_gate_zero_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_flag_on(monkeypatch)
    _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("ignored"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-booking-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "Хочу записаться на консультацию", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 0
    payload = resp.get_json()
    assert payload["meta"].get("lead_flow") is True


def test_on_typed_ui_candidate_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_flag_on(monkeypatch)
    spies = _spy_legacy_wiring(monkeypatch)
    backend = _CountingBackend(answer_envelope("Цена на всю челюсть."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-typed-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    mem_reset(sid)
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Вся челюсть"))

    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": "", "ref": ref, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    spies["pre_resolver"].assert_not_called()
    spies["ingress"].assert_not_called()
    spies["target"].assert_not_called()


def test_typed_ui_passes_governed_gate_result_without_re_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    gate_calls: list[str] = []

    def _gate(text: str):
        gate_calls.append(text)
        from core.local_problem_gate import decide_local_problem_gate

        return decide_local_problem_gate(text)

    def _orchestrate_sales_fast(**kwargs):
        captured["local_gate_result"] = kwargs.get("local_gate_result")
        return SimpleNamespace(
            kind="service_reply",
            q=kwargs.get("q"),
            sid=kwargs.get("sid"),
            client_id=kwargs.get("client_id"),
            service_payload={"answer": "ok", "meta": {"service_route": "sales_fast"}},
            service_route="sales_fast",
        )

    monkeypatch.setattr("core.local_problem_gate.decide_local_problem_gate", _gate)
    monkeypatch.setattr(
        "orchestration.sales_one_plus_ask_turn.orchestrate_sales_fast_widget_turn",
        _orchestrate_sales_fast,
    )
    _enable_flag_on(monkeypatch)
    sid = f"s-gate-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    mem_reset(sid)
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Вся челюсть"))

    with app_module.app.test_request_context():
        from flask import request

        request.ctx = {}
        from orchestration.sales_one_plus_ask_turn import orchestrate_sales_one_plus_ask_turn

        orchestrate_sales_one_plus_ask_turn(
            {"q": "", "ref": ref, "sid": sid, "client_id": "demo"},
            resolve_client_id=lambda *_a, **_k: "demo",
            bind_chat_ctx=lambda *_a, **_k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda *_a, **_k: {},
            service_payload=lambda answer, _sid, _cid, **_: {"answer": answer, "meta": {}},
            get_last_content_ui_payload=lambda *_a, **_k: None,
            enqueue_resolver_trace=lambda **_k: None,
        )

    assert gate_calls == []
    result = captured.get("local_gate_result")
    assert isinstance(result, LocalProblemGateResult)
    assert result == GOVERNED_TYPED_UI_GATE


def test_invalid_typed_ref_fail_safe_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_flag_on(monkeypatch)
    spies = _spy_legacy_wiring(monkeypatch)
    sid = f"s-bad-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

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
    spies["target"].assert_not_called()
    assert resp.get_json()["meta"]["service_route"] == "sales_fast_followup_unknown"


def test_off_path_preserves_legacy_order_without_boundary_speculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        lambda **_k: order.append("target") or SimpleNamespace(
            kind="service_reply", q=pre.q, sid=pre.sid, client_id=pre.client_id
        ),
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


def test_parallel_requests_independent_stage1_budget(monkeypatch: pytest.MonkeyPatch) -> None:
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
        counts = list(pool.map(_one_call, ("stage2-a", "stage2-b")))
    assert counts == [1, 1]


def test_observability_excludes_patient_text_and_corpus(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO)
    _enable_flag_on(monkeypatch)
    patient = "у меня кровь и сильная боль после имплантации"
    backend = _CountingBackend(answer_envelope("ответ"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-obs-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    client = app_module.app.test_client()
    client.post(
        "/ask",
        json={"q": patient, "sid": sid, "client_id": "demo"},
    )
    obs = turn_timing.summary_for_turn_complete().get("sales_fast_observability") or {}
    blob = json.dumps(obs, ensure_ascii=False)
    assert patient not in blob
    assert "prompt" not in blob.lower()
    assert "corpus" not in blob.lower()
    for line in caplog.messages:
        if not line.strip().startswith("{"):
            continue
        payload = json.loads(line)
        joined = json.dumps(payload, ensure_ascii=False)
        assert patient not in joined


@pytest.fixture
def flask_app():
    return app_module.app
