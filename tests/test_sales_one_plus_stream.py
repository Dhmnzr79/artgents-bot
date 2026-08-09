from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest
from pydantic import ValidationError

import core.sales_one_plus_live_backend as live_module
from contracts.sales_one_plus import SalesOnePlusResult
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend
from core.sales_one_plus_protocol import SalesOnePlusProtocolError
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.sales_one_plus_turn import run_sales_one_plus_candidate_stream
from tests.test_sales_one_plus_turn import _context, _resolution


def _run_stream(*, backend, on_delta: Callable[[str], None]):
    return run_sales_one_plus_candidate_stream(
        user_message="Есть парковка?",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        on_delta=on_delta,
    )


@pytest.mark.parametrize("split_at", range(len("@ANSWER ") + 1))
def test_parser_accepts_every_answer_marker_split(split_at: int) -> None:
    marker = "@ANSWER "
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(emitted.append)
    parser.ingest(marker[:split_at])
    parser.ingest(marker[split_at:] + "Готовый ")
    parser.ingest("ответ")

    decision, text = parser.finalize()
    assert (decision, text) == ("answer", "Готовый ответ")
    assert text == "".join(emitted)


def test_parser_accepts_inline_answer_marker() -> None:
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(emitted.append)
    parser.ingest("@ANSWER Да, у здания есть парковка")

    decision, text = parser.finalize()
    assert decision == "answer"
    assert text == "Да, у здания есть парковка"
    assert text == "".join(emitted)


def test_parser_accepts_newline_answer_marker() -> None:
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(emitted.append)
    parser.ingest("@ANSWER\nГотовый ответ")

    decision, text = parser.finalize()
    assert (decision, text) == ("answer", "Готовый ответ")


def test_parser_handles_leading_empty_lines_and_normalizes_whitespace_tail() -> None:
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(emitted.append)
    for chunk in ("\n\r\n@AN", "SWER\n \nHello ", "world\n", "again   "):
        parser.ingest(chunk)

    decision, text = parser.finalize()
    assert decision == "answer"
    assert text == "Hello world\nagain"
    assert text == "".join(emitted)


@pytest.mark.parametrize(
    "chunks",
    (
        ("@ADMIN\nsecret", " must not escape"),
        ("@AD", "MIN\r\nsecret"),
        ("\n\n@ADMIN",),
        ("@ADMIN inline ignored",),
    ),
)
def test_admin_marker_and_body_never_emit(chunks: tuple[str, ...]) -> None:
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(emitted.append)
    for chunk in chunks:
        parser.ingest(chunk)

    assert parser.finalize() == ("admin", None)
    assert emitted == []
    assert parser.answer_text == ""


@pytest.mark.parametrize(
    "chunks",
    (
        (),
        ("plain prose",),
        ("@ANSWER",),
        ("@ANSWER\n   ",),
        ("```\n@ANSWER\ntext",),
        ("@ANSWERABLE\nbody",),
        ("@ANSWERABLE inline",),
    ),
)
def test_parser_rejects_empty_or_malformed_stream(chunks: tuple[str, ...]) -> None:
    parser = SalesOnePlusStreamParser(lambda _delta: None)
    with pytest.raises(SalesOnePlusProtocolError):
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


def test_candidate_emits_answer_before_backend_iteration_completes() -> None:
    emitted: list[str] = []

    class _ObservedBackend:
        calls = 0
        observed_early = False

        def generate_stream(self, _invocation, callback, /) -> None:
            self.calls += 1
            callback("@ANSWER\nПервая часть ")
            self.observed_early = emitted == ["Первая часть"]
            callback("ответа")

    backend = _ObservedBackend()
    result = _run_stream(backend=backend, on_delta=emitted.append)

    assert backend.calls == 1 and backend.observed_early
    assert result.patient_text == "".join(emitted) == "Первая часть ответа"
    assert result.interrupted is False


def test_candidate_local_admin_and_spam_make_zero_calls_and_zero_deltas() -> None:
    backend = _StreamBackend(("@ANSWER\nwrong",))
    for message, expected in (("Сильно болит зуб", "admin"), ("!!!!!", "spam")):
        emitted: list[str] = []
        result = run_sales_one_plus_candidate_stream(
            user_message=message,
            cached_full_context=_context(),
            exact_sales_resolution=_resolution(),
            static_admin_handoff_text="Позвоните администратору.",
            backend=backend,
            on_delta=emitted.append,
        )
        assert result.decision == expected and emitted == []
    assert backend.calls == 0


def test_candidate_model_admin_malformed_and_early_failure_use_static_handoff() -> None:
    for backend in (
        _StreamBackend(("@ADMIN\nmodel prose",)),
        _StreamBackend(("not a marker\n",)),
        _StreamBackend((), fail_after=True),
    ):
        emitted: list[str] = []
        result = _run_stream(backend=backend, on_delta=emitted.append)
        assert result.decision == "admin"
        assert result.handoff_text == "Позвоните администратору."
        assert result.patient_text is None and emitted == [] and backend.calls == 1


def test_candidate_late_provider_failure_keeps_exact_emitted_partial_answer() -> None:
    emitted: list[str] = []
    backend = _StreamBackend(("@ANSWER\nЧасть ответа ",), fail_after=True)
    result = _run_stream(backend=backend, on_delta=emitted.append)

    assert result.decision == "answer"
    assert result.patient_text == "".join(emitted) == "Часть ответа"
    assert result.source == "backend" and result.interrupted is True
    assert result.handoff_text is None


def test_consumer_callback_error_propagates_without_becoming_handoff() -> None:
    backend = _StreamBackend(("@ANSWER\ntext",))

    def fail_consumer(_delta: str) -> None:
        raise ValueError("client disconnected")

    with pytest.raises(ValueError, match="client disconnected"):
        _run_stream(backend=backend, on_delta=fail_consumer)
    assert backend.calls == 1


def test_result_contract_marks_only_partial_backend_answers_interrupted() -> None:
    with pytest.raises(ValidationError):
        SalesOnePlusResult(
            decision="answer",
            source="backend",
            reason="late failure",
            patient_text="partial",
            interrupted=False,
        )
    with pytest.raises(ValidationError):
        SalesOnePlusResult(
            decision="admin",
            source="backend",
            reason="early failure",
            handoff_text="admin",
            interrupted=True,
        )


def test_live_adapter_streams_raw_chunks_once_without_json_format(monkeypatch) -> None:
    provider_calls: list[dict[str, object]] = []

    class _Chunk:
        def __init__(self, text: str | None) -> None:
            delta = type("Delta", (), {"content": text})()
            self.choices = [type("Choice", (), {"delta": delta})()]

    def fake_create(**kwargs):
        provider_calls.append(kwargs)
        return iter((_Chunk("@AN"), _Chunk("SWER\nДа"), _Chunk(None)))

    monkeypatch.setattr(live_module, "chat_completions_create", fake_create)
    backend = SalesOnePlusLiveBackend(model="candidate-plus")
    emitted: list[str] = []
    result = _run_stream(backend=backend, on_delta=emitted.append)

    assert result.patient_text == "".join(emitted) == "Да"
    assert len(provider_calls) == 1 and backend.call_count == 1
    request = provider_calls[0]
    assert request["model"] == "candidate-plus" and request["stream"] is True
    assert request["stream_options"] == {"include_usage": True}
    assert "response_format" not in request

    second = _run_stream(backend=backend, on_delta=lambda _delta: None)
    assert second.decision == "admin" and second.interrupted is False
    assert len(provider_calls) == 1
