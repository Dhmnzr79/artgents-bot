"""Offline tests for BOT-CLEANUP-MANUAL-WIDGET-FINDINGS-1."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import config
import pytest

import app as app_module
from contracts.ui_scope_action import build_ui_scope_ref
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend
from core.sales_one_plus_provider_diagnostics import (
    categorize_provider_exception,
    log_sales_one_plus_provider_error,
)
from core.sales_one_plus_turn import SalesOnePlusBackendFailure
from session import bind_session_client, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

@pytest.fixture
def flask_app():
    return app_module.app


def _minimal_invocation():
    from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
    from contracts.sales_one_plus import SalesOnePlusInvocation
    from core.one_call_client_pack_identity import build_client_pack_identity

    auth = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    return SalesOnePlusInvocation(
        system_prompt="system policy",
        user_prompt="user prompt",
        model_corpus_text="corpus text",
        user_message="Сколько стоит?",
        exact_sales_resolution=ExactSalesResolution(
            service_id=None,
            aspect=None,
            extent=None,
            jaw=None,
            stage=None,
            service_id_authority=auth,
            aspect_authority=auth,
            extent_authority=auth,
            jaw_authority=auth,
            stage_authority=auth,
        ),
        current_strict_facts=(),
        sales_context={},
        pack_identity=build_client_pack_identity("demo"),
        local_prefix_cache_hit=False,
        prefix_build_ms=None,
    )


def _clear_session_connection_cache() -> None:
    import session as session_module

    with session_module._lock:
        for conn in list(session_module._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_module._conns.clear()


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    monkeypatch.setattr("session.sqlite_path_for_client", _sqlite_path)
    bind_session_client("demo")
    yield
    _clear_session_connection_cache()


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _run_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    backend: _CountingBackend,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
) -> dict:
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    response = client.post(
        "/ask",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    return body


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


def _broad_implant_clarify_envelope() -> str:
    return answer_envelope(
        "Уточните, пожалуйста, какой вариант восстановления вас интересует.",
        route="CLARIFY",
        commercial_intent="price",
        promotion_scope="none",
        clarify_axis="service",
        clarify_service_options=["classic", "all_on_4", "all_on_6"],
        service_reference_status="none",
        requested_service_id=None,
    )


def test_broad_price_overview_on_model_clarify(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(_broad_implant_clarify_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-clarify-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=backend.output,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    assert "76200" in answer
    assert "318000" in answer
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") in quick_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") in quick_refs
    assert (payload.get("meta") or {}).get("terminal_mode") != "clarify"


def test_broad_price_overview_on_model_answer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "Стоимость зависит от объёма работы.",
            commercial_intent="price",
            service_id=None,
            extent=None,
            scenario="cost",
            service_reference_status="none",
        )
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-answer-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=backend.output,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    assert "76200" in answer
    assert "318000" in answer


def test_explicit_all_on_4_not_broad_overview(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "All-on-4.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        )
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-a4-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Сколько стоит All-on-4?",
        envelope_json=backend.output,
    )
    quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") not in quick_refs
    assert "318000" not in _norm_digits(str(payload.get("answer") or "")) or (
        payload.get("meta") or {}
    ).get("matched_service_id") == "all_on_4"


def test_classic_price_turn_without_payment_stages_table(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "Классическая имплантация восстанавливает один зуб.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
                    )
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-classic-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Сколько стоит классическая имплантация?",
        envelope_json=backend.output,
    )
    answer = str(payload.get("answer") or "")
    norm = _norm_digits(answer)
    assert "45200" in norm or "70200" in norm or "76200" in norm
    assert "31000" not in norm
    assert "45200" not in answer.lower() or "этап" not in answer.lower()
    assert "консультации врач" not in answer.casefold()
    assert "оплата по этапам" not in answer.casefold()


def test_payment_stages_on_explicit_payment_question(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"mwf-stages-{uuid.uuid4().hex[:8]}"
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(
            answer_envelope(
                "Implantium.",
                commercial_intent="price",
                service_id="classic",
                extent="one_tooth",
                service_reference_status="resolved",
                requested_service_id="classic",
            )
        ),
        user_message="Сколько стоит классическая имплантация на Implantium?",
        envelope_json=answer_envelope(
            "Implantium.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(
            answer_envelope(
                "Этапы.",
                commercial_intent="payment_stages",
                service_id="classic",
                service_reference_status="resolved",
                requested_service_id="classic",
                            )
        ),
        user_message="Сколько платить на каждом этапе для Implantium?",
        envelope_json=answer_envelope(
            "Этапы.",
            commercial_intent="payment_stages",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
                    ),
        reset_session=False,
    )
    norm = _norm_digits(str(payload.get("answer") or ""))
    assert "45200" in norm or "31000" in norm


def test_installment_question_without_payment_stages_table(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "Рассрочка оформляется на 12 месяцев.",
            commercial_intent="payment",
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-install-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Есть рассрочка?",
        envelope_json=backend.output,
    )
    answer = str(payload.get("answer") or "").lower()
    assert "рассроч" in answer
    assert "хирургическ" not in answer


def test_combined_price_and_stages_question(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    backend = _CountingBackend(
        answer_envelope(
            "Цена и этапы.",
            commercial_intent="payment_stages",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
                    )
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"mwf-combo-{uuid.uuid4().hex[:8]}",
        backend=backend,
        user_message="Сколько стоит и сколько платить на каждом этапе?",
        envelope_json=backend.output,
    )
    norm = _norm_digits(str(payload.get("answer") or ""))
    assert "45200" in norm or "76200" in norm
    assert "31000" in norm or "45200" in norm


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TimeoutError("read timed out"), "timeout"),
        (Exception("429 Too Many Requests"), "rate_limit"),
        (type("Provider5xx", (), {"status_code": 500})(), "provider_5xx"),
        (ConnectionError("connection refused"), "connection"),
    ],
)
def test_provider_error_categories(exc: Exception, expected: str) -> None:
    assert categorize_provider_exception(exc) == expected


def test_provider_error_diagnostics_safe_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []

    def _capture(_logger, event: str, **fields):
        events.append({"event": event, **fields})

    monkeypatch.setattr(
        "core.sales_one_plus_provider_diagnostics.log_json",
        _capture,
    )
    secret = "sk-secret-api-key-value"
    log_sales_one_plus_provider_error(
        exc=TimeoutError(f"timeout after system prompt {secret}"),
        requested_model="qwen3.7-plus-2026-05-26",
        configured_timeout_sec=40.0,
        elapsed_ms=21906,
        stream=False,
        received_first_stream_chunk=False,
    )
    assert events
    payload = events[0]
    assert payload["event"] == "sales_one_plus_provider_error"
    assert payload["category"] == "timeout"
    assert payload["configured_timeout_sec"] == 40.0
    assert payload["elapsed_ms"] == 21906
    assert secret not in str(payload)


def test_sales_fast_backend_uses_dedicated_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_create(**kwargs):
        captured.update(kwargs)
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content='{"route":"ANSWER","patient_text":"ok"}'))]
        response.model = "qwen3.7-plus-2026-05-26"
        response.usage = None
        return response

    monkeypatch.setattr("core.sales_one_plus_live_backend.chat_completions_create", _fake_create)
    monkeypatch.setattr(config, "SALES_ONE_PLUS_TIMEOUT_SEC", 40.0)
    backend = SalesOnePlusLiveBackend(model="qwen3.7-plus-2026-05-26")
    backend.generate(_minimal_invocation())
    assert captured.get("timeout") == 40.0


def test_sales_fast_backend_logs_on_stream_failure_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict] = []

    def _capture(_logger, event: str, **fields):
        events.append(fields)

    def _boom(**_kwargs):
        raise ConnectionError("stream reset")

    monkeypatch.setattr("core.sales_one_plus_live_backend.chat_completions_create", _boom)
    monkeypatch.setattr("core.sales_one_plus_provider_diagnostics.log_json", _capture)
    backend = SalesOnePlusLiveBackend(model="qwen3.7-plus-2026-05-26")
    with pytest.raises(ConnectionError):
        backend.generate_stream(_minimal_invocation(), lambda _delta: None)
    assert events
    assert events[0]["category"] == "connection"
    assert events[0]["received_first_stream_chunk"] is False


def test_sales_fast_backend_logs_stream_interrupted_after_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict] = []

    def _capture(_logger, event: str, **fields):
        events.append(fields)

    class _Stream:
        def __iter__(self):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content='{"route"'))])
            raise RuntimeError("stream interrupted")

    monkeypatch.setattr(
        "core.sales_one_plus_live_backend.chat_completions_create",
        lambda **_kwargs: _Stream(),
    )
    monkeypatch.setattr("core.sales_one_plus_provider_diagnostics.log_json", _capture)
    backend = SalesOnePlusLiveBackend(model="qwen3.7-plus-2026-05-26")
    with pytest.raises(RuntimeError):
        backend.generate_stream(_minimal_invocation(), lambda _delta: None)
    assert events
    assert events[0]["category"] == "stream_interrupted"
    assert events[0]["received_first_stream_chunk"] is True
