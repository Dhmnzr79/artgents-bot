from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest
from pydantic import ValidationError

import core.sales_one_plus_live_backend as live_module
from contracts.one_call_envelope import OneCallEnvelope, OneCallEnvelopeReferences
from contracts.sales_one_plus import SalesOnePlusResult
from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError, dumps_production_envelope
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.sales_one_plus_turn import SalesOnePlusBackendFailure, run_sales_one_plus_candidate_stream
from tests.test_sales_one_plus_turn import (
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_EXACT_CATALOG,
    _EMPTY_REF_CATALOG,
    _PACK_IDENTITY,
    _context,
    _resolution,
    admin_envelope,
    answer_envelope,
)


def _run_stream(*, backend, on_delta: Callable[[str], None]):
    return run_sales_one_plus_candidate_stream(
        user_message="Есть парковка?",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=on_delta,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )


def _parser(on_delta: Callable[[str], None]) -> SalesOnePlusStreamParser:
    return SalesOnePlusStreamParser(
        on_delta,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )


@pytest.mark.parametrize("split_at", range(1, 20))
def test_parser_accepts_json_split_at_every_boundary(split_at: int) -> None:
    payload = answer_envelope("Готовый ответ")
    emitted: list[str] = []
    parser = _parser(emitted.append)
    parser.ingest(payload[:split_at])
    parser.ingest(payload[split_at:])

    envelope = parser.finalize()
    assert envelope.route == "ANSWER"
    assert envelope.patient_text == "Готовый ответ"
    assert emitted == ["Готовый ответ"]


def test_parser_unicode_and_escaped_quotes_in_patient_text() -> None:
    text = 'Ответ с "кавычками", \\ и {фигурными} скобками — да.'
    payload = answer_envelope(text)
    emitted: list[str] = []
    parser = _parser(emitted.append)
    parser.ingest(payload)
    envelope = parser.finalize()
    assert envelope.patient_text == text
    assert emitted == [text]


def test_admin_json_never_emits_patient_delta() -> None:
    emitted: list[str] = []
    parser = _parser(emitted.append)
    parser.ingest(admin_envelope())
    envelope = parser.finalize()
    assert envelope.route == "ADMIN"
    assert emitted == []


@pytest.mark.parametrize(
    "chunks",
    (
        (),
        ("plain prose",),
        ("{",),
        ('{"route":"ANSWER"',),
        ("[]",),
    ),
)
def test_parser_rejects_empty_or_malformed_stream(chunks: tuple[str, ...]) -> None:
    parser = _parser(lambda _delta: None)
    with pytest.raises(OneCallEnvelopeProtocolError):
        for chunk in chunks:
            parser.ingest(chunk)
        parser.finalize()


class _StreamBackend:
    def __init__(self, chunks: Iterable[object], *, fail_after: bool = False) -> None:
        self.chunks = tuple(chunks)
        self.fail_after = fail_after
        self.calls = 0

    def generate_stream(self, _invocation, callback, /) -> None:
        self.calls += 1
        for chunk in self.chunks:
            callback(chunk)
        if self.fail_after:
            raise RuntimeError("provider stream failed")


def test_candidate_emits_patient_text_only_after_finalize() -> None:
    emitted: list[str] = []

    class _ObservedBackend:
        calls = 0
        observed_early = False

        def generate_stream(self, _invocation, callback, /) -> None:
            self.calls += 1
            payload = answer_envelope("Первая часть ответа")
            mid = len(payload) // 2
            callback(payload[:mid])
            self.observed_early = emitted == []
            callback(payload[mid:])

    backend = _ObservedBackend()
    result = _run_stream(backend=backend, on_delta=emitted.append)

    assert backend.calls == 1 and backend.observed_early
    assert result.patient_text == "Первая часть ответа"
    assert emitted == ["Первая часть ответа"]
    assert result.interrupted is False


def test_candidate_spam_makes_zero_calls_and_zero_deltas() -> None:
    backend = _StreamBackend((answer_envelope("wrong"),))
    emitted: list[str] = []
    result = run_sales_one_plus_candidate_stream(
        user_message="!!!!!",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=emitted.append,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )
    assert result.decision == "spam" and emitted == []
    assert backend.calls == 0


def test_candidate_symptom_reaches_composer_once() -> None:
    backend = _StreamBackend((answer_envelope("Ответ."),))
    emitted: list[str] = []
    result = run_sales_one_plus_candidate_stream(
        user_message="Сильно болит зуб",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=emitted.append,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )
    assert result.decision == "answer"
    assert backend.calls == 1


def test_candidate_model_admin_malformed_and_backend_failure_are_not_admin_handoff() -> None:
    emitted: list[str] = []
    admin_result = _run_stream(backend=_StreamBackend((admin_envelope(),)), on_delta=emitted.append)
    assert admin_result.decision == "admin"
    assert admin_result.handoff_text == "Позвоните администратору."
    assert admin_result.patient_text is None and emitted == []

    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_stream(backend=_StreamBackend(("not json",)), on_delta=emitted.append)

    with pytest.raises(SalesOnePlusBackendFailure, match="backend_failed"):
        _run_stream(backend=_StreamBackend((), fail_after=True), on_delta=emitted.append)


def test_candidate_late_provider_failure_raises_backend_failure() -> None:
    emitted: list[str] = []
    partial = answer_envelope("Часть ответа")[:20]
    backend = _StreamBackend((partial,), fail_after=True)
    with pytest.raises(SalesOnePlusBackendFailure, match="stream_interrupted"):
        _run_stream(backend=backend, on_delta=emitted.append)
    assert emitted == []


def test_consumer_callback_error_propagates_without_becoming_handoff() -> None:
    backend = _StreamBackend((answer_envelope("text"),))

    def fail_consumer(_delta: str) -> None:
        raise ValueError("client disconnected")

    with pytest.raises(ValueError, match="client disconnected"):
        _run_stream(backend=backend, on_delta=fail_consumer)
    assert backend.calls == 1


def test_result_contract_marks_only_partial_backend_answers_interrupted() -> None:
    envelope = OneCallEnvelope(
        route="ANSWER",
        service_id=None,
        extent=None,
        jaw=None,
        stage=None,
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis=None,
        clarify_service_options=None,
        patient_text="partial",
        service_reference_status="none",
        requested_service_id=None,
        references=OneCallEnvelopeReferences(direct_fact_ids=()),
    )
    with pytest.raises(ValidationError):
        SalesOnePlusResult(
            decision="answer",
            source="backend",
            reason="late failure",
            patient_text="partial",
            interrupted=False,
            envelope=envelope,
        )
    with pytest.raises(ValidationError):
        SalesOnePlusResult(
            decision="admin",
            source="backend",
            reason="early failure",
            handoff_text="admin",
            interrupted=True,
        )


def test_live_adapter_streams_raw_chunks_once_with_json_format(monkeypatch) -> None:
    provider_calls: list[dict[str, object]] = []
    payload = answer_envelope("Да")

    class _Chunk:
        def __init__(self, text: str | None) -> None:
            delta = type("Delta", (), {"content": text})()
            self.choices = [type("Choice", (), {"delta": delta})()]

    def fake_create(**kwargs):
        provider_calls.append(kwargs)
        return iter((_Chunk(payload[:2]), _Chunk(payload[2:]), _Chunk(None)))

    monkeypatch.setattr(live_module, "chat_completions_create", fake_create)
    backend = SalesOnePlusLiveBackend(model="candidate-plus")
    emitted: list[str] = []
    result = _run_stream(backend=backend, on_delta=emitted.append)

    assert result.patient_text == "Да"
    assert emitted == ["Да"]
    assert len(provider_calls) == 1 and backend.call_count == 1
    request = provider_calls[0]
    assert request["model"] == "candidate-plus" and request["stream"] is True
    assert request["stream_options"] == {"include_usage": True}
    assert request["response_format"] == {"type": "json_object"}

    spam = run_sales_one_plus_candidate_stream(
        user_message="!!!!!",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=lambda _delta: None,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )
    assert spam.decision == "spam"
    assert len(provider_calls) == 1
