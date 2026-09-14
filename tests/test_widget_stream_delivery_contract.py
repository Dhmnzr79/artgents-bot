"""Widget buffered progressive reveal contract (Phase 2A)."""

from __future__ import annotations

import pytest

import app as app_module
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.widget_stream_delivery import infer_widget_sse_delivery_mode
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_fast_checkpoint_a import (
    _install_sales_fast,
    _parse_sse_events,
    _run_stream_turn,
    _run_turn,
)
from tests.test_sales_one_plus_turn import (
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_REF_CATALOG,
    admin_envelope,
    answer_envelope,
)


@pytest.fixture
def flask_app():
    return app_module.app


def _stream_deltas(events: list[tuple[str, dict]]) -> list[str]:
    return [str(d.get("delta") or "") for name, d in events if name == "text_delta"]


def _event_counts(events: list[tuple[str, dict]], name: str) -> int:
    return sum(1 for ev, _ in events if ev == name)


def test_one_call_parser_never_emits_patient_text_deltas() -> None:
    payload = answer_envelope("Текст до валидации")
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(
        emitted.append,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    mid = len(payload) // 2
    parser.ingest(payload[:mid])
    parser.ingest(payload[mid:])
    parser.finalize()
    assert emitted == []


@pytest.mark.parametrize(
    "payload_factory",
    [
        lambda: admin_envelope(),
        lambda: answer_envelope("Часть", route="CLARIFY"),
        lambda: answer_envelope("Цена", commercial_intent="price", service_id="tomography"),
        lambda: '{"route":"ANSWER","patient_text":"x"',
    ],
)
def test_one_call_unsafe_envelopes_zero_patient_deltas(payload_factory) -> None:
    raw = payload_factory()
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(
        emitted.append,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    parser.ingest(raw)
    try:
        parser.finalize()
    except Exception:
        pass
    assert emitted == []


def test_sales_fast_faq_stream_has_zero_server_deltas(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload = answer_envelope("Гигиена полости рта важна для здоровья зубов.")

    class _ChunkBackend:
        call_count = 0

        def generate_stream(self, _inv, callback, /):
            self.call_count += 1
            callback(payload)

    backend = _ChunkBackend()
    _install_sales_fast(monkeypatch, backend)
    bind_session_client("demo")
    mem_reset("stream-faq-buffered")
    resp = flask_app.test_client().post(
        "/ask/stream",
        json={
            "q": "Расскажите про гигиену полости рта",
            "sid": "stream-faq-buffered",
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp)
    assert _stream_deltas(events) == []
    assert _event_counts(events, "ui") == 1
    assert _event_counts(events, "done") == 1
    assert backend.call_count == 1


def test_price_stream_buffered_zero_deltas(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    _ui, events, _backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="stream-price-buffered",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ стоит 999999 ₽.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    assert _stream_deltas(events) == []
    assert _event_counts(events, "ui") == 1
    assert _event_counts(events, "done") == 1


def test_code_owned_parking_zero_text_delta(flask_app) -> None:
    bind_session_client("demo")
    mem_reset("stream-parking")
    resp = flask_app.test_client().post(
        "/ask/stream",
        json={"q": "Есть парковка?", "sid": "stream-parking", "client_id": "demo"},
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp)
    assert _stream_deltas(events) == []
    assert _event_counts(events, "ui") == 1
    assert _event_counts(events, "done") == 1


def test_stream_session_writes_assistant_once(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "stream-session-once"
    envelope = answer_envelope(
        "Гигиена полости рта важна для здоровья зубов.",
        commercial_intent="none",
        service_id=None,
    )
    _ui, _events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="Расскажите про гигиену полости рта",
        envelope_json=envelope,
    )
    assert backend.call_count == 1
    bind_session_client("demo")
    hist = list(mem_get(sid).get("hist") or [])
    assistant = [row for row in hist if row.get("role") == "assistant"]
    assert len(assistant) == 1


def test_ask_json_parity_with_stream_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "stream-json-parity"
    user_message = "Расскажите про гигиену полости рта"
    envelope = answer_envelope(
        "Гигиена полости рта важна для здоровья зубов.",
        commercial_intent="none",
        service_id=None,
    )
    stream_ui, _events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message=user_message,
        envelope_json=envelope,
        reset_session=True,
    )
    assert backend.call_count == 1
    bind_session_client("demo")
    mem_reset(f"{sid}-json")
    json_payload, json_backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=f"{sid}-json",
        user_message=user_message,
        envelope_json=envelope,
        reset_session=True,
    )
    assert json_backend.call_count == 1
    assert str(stream_ui.get("answer") or "") == str(json_payload.get("answer") or "")


def test_infer_delivery_mode_buffered_and_code_owned() -> None:
    assert (
        infer_widget_sse_delivery_mode(
            text_delta_count=0,
            ui_payload={"meta": {"service_route": "sales_fast_contacts", "provider_calls": 0}},
        )
        == "code_owned"
    )
    assert (
        infer_widget_sse_delivery_mode(
            text_delta_count=0,
            ui_payload={"meta": {"service_route": "sales_fast_materialized", "provider_calls": 1}},
        )
        == "buffered_model"
    )


def test_infer_delivery_mode_real_model_only_when_deltas_present() -> None:
    """Forward-compatible diagnostic; Phase 2A production does not emit text_delta."""
    assert infer_widget_sse_delivery_mode(text_delta_count=2, ui_payload={}) == "real_model"
