"""REC-1: real endpoints/parser/store, fake transport, text-free observer."""
import json
from types import SimpleNamespace

import pytest

from contracts.response_plan import SessionKey
from core import d2_diagnostics as diagnostics
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d1r_envelope_fixtures import envelope_clinic_policy_only
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events


SECRET = "PRIVATE_NAME_Секрет +7 999 123 45 67 private-key-XYZ"


@pytest.fixture
def observed(http_env, monkeypatch):
    import core.d2_http_adapter as adapter
    events, calls = [], []
    replies = [envelope_clinic_policy_only("no_pediatric_dentistry")]

    def transport(**kwargs):
        calls.append(kwargs)
        reply = replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])

    monkeypatch.setattr(adapter, "D2HttpProvider", lambda: D2HttpProvider(transport=transport))
    monkeypatch.setattr(diagnostics, "_write", lambda fields: events.append(dict(fields)))
    yield http_env, events, calls, replies
    assert diagnostics._current.get() is None
    assert SECRET not in json.dumps(events, ensure_ascii=False)


def event_rows(events, event):
    return [row for row in events if row["event"] == event]


def test_json_sse_replay_has_same_frozen_result_and_no_second_call(observed):
    (client, db, _, _), events, calls, _ = observed
    first = post(client, sid=SECRET, request_id=SECRET).get_json()
    replay = sse_events(post_sse(client, sid=SECRET, request_id=SECRET))
    assert dict(replay)["ui"] == first
    assert replay[-1] == ("done", {})
    assert len(calls) == 1
    assert len(event_rows(events, "commit_confirmed")) == 1
    assert len(event_rows(events, "replay")) == 1
    assert event_rows(events, "replay")[0]["provider_attempts"] == 0
    assert len({row["attempt_trace_id"] for row in events}) == 2
    timing = event_rows(events, "provider_finished")
    assert len(timing) == 1 and timing[0]["provider_attempts"] == 1
    assert timing[0]["duration_ms"] >= 0
    assert event_rows(events, "stream_done_emitted")[0]["commit_state"] == "confirmed"
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=SECRET))
        assert saved.response.rendered_text == first["answer"]
        assert saved.response.ui_projection.model_dump(mode="json") == first["ui"]


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("reply,stage,reason,status", [
    ("{invalid", "parse", "invalid_envelope", 400),
    (TimeoutError(SECRET), "provider_transport", "provider_timeout", 503),
    (RuntimeError(SECRET), "provider_transport", "unknown", 503),
    ("", "provider_response", "d2_http_response_content_missing", 503),
])
def test_failures_preserve_wire_and_report_safe_step(observed, streaming, reply, stage, reason, status):
    (client, db, _, _), events, calls, replies = observed
    replies[0] = reply
    if streaming:
        response = post_sse(client)
        assert response.status_code == 200
        assert [name for name, _ in sse_events(response)] == ["status", "error"]
    else:
        response = post(client)
        assert response.status_code == status and "answer" not in response.get_json()
    failures = event_rows(events, "failure")
    assert len(failures) == 1
    assert (failures[0]["stage"], failures[0]["reason"]) == (stage, reason)
    assert len(calls) == 1 and len(event_rows(events, "provider_finished")) == 1
    assert not event_rows(events, "commit_confirmed")
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")) is None


@pytest.mark.parametrize("after_commit", [False, True])
def test_store_failure_preserves_commit_knowledge_and_replay(observed, monkeypatch, after_commit):
    (client, db, _, _), events, calls, _ = observed
    real_complete = D2DialogueStore.complete

    def broken_complete(self, *args, **kwargs):
        if after_commit:
            real_complete(self, *args, **kwargs)
        raise RuntimeError(SECRET)

    monkeypatch.setattr(D2DialogueStore, "complete", broken_complete)
    assert post(client).status_code == 503
    assert event_rows(events, "failure")[0]["stage"] == "commit"
    assert bool(event_rows(events, "commit_confirmed")) == after_commit
    assert bool(event_rows(events, "completion_not_found")) != after_commit
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert (saved is not None) == after_commit
    monkeypatch.setattr(D2DialogueStore, "complete", real_complete)
    assert post(client).status_code == 200
    assert len(calls) == (1 if after_commit else 2)


@pytest.mark.parametrize("site", ["materialize", "payload", "transport"])
def test_boundary_fault_does_not_leak_exception_or_lose_saved_result(observed, monkeypatch, site):
    from tests.test_d2_widget_replay import _mixed_widget_raw
    import app
    import core.d2_dialogue as dialogue
    import core.d2_http_adapter as adapter
    (client, db, _, _), events, calls, replies = observed
    replies[0] = _mixed_widget_raw()

    def broken(*args, **kwargs):
        raise RuntimeError(SECRET)

    target, name = {
        "materialize": (dialogue, "resolve_d2_envelope_response"),
        "payload": (adapter, "_response_payload"),
        "transport": (app, "_sse_typing_line"),
    }[site]
    monkeypatch.setattr(target, name, broken)
    response = post_sse(client)
    assert [kind for kind, _ in sse_events(response)] == ["status", "error"]
    assert event_rows(events, "failure")[0]["stage"] == site
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        assert (saved is not None) == (site != "materialize")


@pytest.mark.parametrize("broken_name", ["_write", "monotonic", "uuid4"])
def test_observer_fault_cannot_change_success_or_original_failure(observed, monkeypatch, broken_name):
    (client, _, _, _), _, calls, replies = observed
    def broken(*args, **kwargs):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(diagnostics, broken_name, broken)
    good = post(client).get_json()
    assert "answer" in good
    assert post(client).get_json() == good
    assert len(calls) == 1
    replies[0] = "{invalid"
    response = post(client, sid="bad", request_id="bad")
    assert response.status_code == 400
    assert response.get_json() == {"error": "d2_invalid_turn"}
    error = RuntimeError(SECRET)
    def original_error():
        raise error
    with pytest.raises(RuntimeError) as caught:
        diagnostics.call_provider(original_error)
    assert caught.value is error


def test_stream_close_before_first_next_is_recorded_without_starting_turn(observed):
    import app
    (_, _, _, _), events, calls, _ = observed
    with app.app.test_request_context("/ask/stream", method="POST", json={
        "client_id": "demo", "sid": "not-started", "request_id": "not-started", "q": "Вопрос",
    }):
        response = app.ask_stream()
    assert diagnostics._current.get() is None
    response.close()
    response.close()
    assert not calls
    assert len(event_rows(events, "stream_disconnected")) == 1
    assert not event_rows(events, "stage_started")


def test_interleaved_streams_reset_context_and_close_after_done(observed):
    import app
    (_, _, _, _), events, calls, _ = observed
    responses = []
    for index, tenant in enumerate(("demo", "nikadent")):
        with app.app.test_request_context("/ask/stream", method="POST", json={
            "client_id": tenant, "sid": f"interleaved-{index}", "request_id": "same", "q": "Вопрос",
        }):
            responses.append(app.ask_stream())
    streams = [iter(response.response) for response in responses]
    for iterator in streams:
        assert "event: status" in next(iterator)
        assert diagnostics._current.get() is None
    # First stream commits then disconnects before UI; second finishes.
    assert "event: typing" in next(streams[0])
    assert diagnostics._current.get() is None
    responses[0].close()
    assert "event: typing" in next(streams[1])
    assert "event: ui" in next(streams[1])
    assert "event: done" in next(streams[1])
    responses[1].close()
    assert diagnostics._current.get() is None
    assert len(calls) == 2
    disconnected = event_rows(events, "stream_disconnected")
    finished = event_rows(events, "stream_closed_after_done")
    assert len(disconnected) == len(finished) == 1
    assert disconnected[0]["commit_state"] == finished[0]["commit_state"] == "confirmed"
    assert disconnected[0]["attempt_trace_id"] != finished[0]["attempt_trace_id"]
    for trace in {row["attempt_trace_id"] for row in events}:
        assert len(event_rows([row for row in events if row["attempt_trace_id"] == trace], "provider_finished")) == 1


def test_prompt_failure_means_zero_transport_attempts(observed, monkeypatch):
    import core.d2_live_provider as provider
    (client, _, _, _), events, calls, _ = observed
    def broken(*args, **kwargs):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(provider, "build_d2_d1r_messages", broken)
    assert post(client).status_code == 503
    assert not calls and not event_rows(events, "provider_finished")
    failed = event_rows(events, "failure")[0]
    assert failed["stage"] == "prompt" and failed["provider_attempts"] == 0


def test_real_logger_does_not_inject_request_context(http_env, caplog):
    import app
    with app.app.test_request_context("/ask"):
        app.request.ctx = {"request_id": SECRET, "sid": SECRET, "client_id": SECRET}
        attempt = diagnostics._begin()
        with diagnostics._Bound(attempt):
            diagnostics.failure(RuntimeError(SECRET))
    records = [r.extra_data for r in caplog.records if r.getMessage() == "d2_diagnostic"]
    assert records
    assert SECRET not in json.dumps(records, ensure_ascii=False)
    assert all("request_id" not in row and "sid" not in row and "client_id" not in row for row in records)


def test_startup_snapshot_has_only_scoped_code_hash(monkeypatch):
    events = []
    monkeypatch.setattr(diagnostics, "_write", events.append)
    diagnostics.startup()
    assert len(events) == 1
    assert set(events[0]) == {"event", "commit", "source_scope", "source_files_sha256"}
    assert events[0]["commit"] == "unknown"
    assert len(events[0]["source_files_sha256"]) == 64


def test_existing_content_gate_is_diagnosed_not_repaired(observed):
    from tests.test_d2_ui_b12_scenarios import _content_pain_raw
    (client, _, _, _), events, _, replies = observed
    payload = json.loads(_content_pain_raw())
    payload["request_understanding"]["requests"][0]["content_text"] = "Стоимость от 5 000 рублей."
    # This case has no authored recovery; the original helper has one and
    # legitimately returns a recovered answer instead of reaching the gate.
    payload["request_understanding"]["requests"][0]["content_fallback_section_ref"] = None
    replies[0] = json.dumps(payload, ensure_ascii=False)
    response = post(client)
    assert response.status_code == 400
    assert response.get_json() == {"error": "d2_invalid_turn"}
    failed = event_rows(events, "failure")[0]
    assert failed["stage"] == "gate"
    assert failed["reason"] == "d2_experiment_content_not_resolved"


@pytest.mark.parametrize("path", ["/ask", "/ask/stream"])
def test_early_rejection_finishes_trace_without_provider(observed, path):
    (client, _, _, _), events, calls, _ = observed
    response = client.post(path, json=[])
    assert response.status_code == 400 and response.get_json() == {"error": "invalid_request"}
    assert not calls
    assert len(event_rows(events, "http_rejected")) == 1
    assert event_rows(events, "http_rejected")[0]["commit_state"] == "unknown"


def test_close_exception_identity_is_preserved_even_when_sink_fails(monkeypatch):
    error = RuntimeError(SECRET)
    class BrokenIterator:
        def close(self):
            raise error
    def broken(*args, **kwargs):
        raise ValueError("sink failure")
    monkeypatch.setattr(diagnostics, "_write", broken)
    stream = diagnostics._Stream(BrokenIterator(), diagnostics._begin())
    with pytest.raises(RuntimeError) as caught:
        stream.close()
    assert caught.value is error
    stream.close()
    assert diagnostics._current.get() is None


@pytest.mark.parametrize("path", [
    "http_success", "http_error", "stream_exhausted", "stream_error",
    "close_success", "close_error",
])
def test_late_clock_failure_preserves_result_exception_and_context(monkeypatch, path):
    events, attempts, clock_calls = [], [], []
    monkeypatch.setattr(diagnostics, "_write", events.append)
    result = object()
    original_error = RuntimeError(SECRET)

    def broken_clock():
        clock_calls.append(True)
        raise ValueError("diagnostic clock failure")

    def arm_clock_failure():
        attempt = diagnostics._current.get()
        # _begin has succeeded with working clocks. Only finalization fails.
        assert attempt is not None and not attempt.finished
        assert event_rows(events, "attempt_started")
        attempts.append(attempt)
        monkeypatch.setattr(diagnostics, "monotonic", broken_clock)

    if path.startswith("http_"):
        @diagnostics.http_attempt
        def endpoint():
            arm_clock_failure()
            if path == "http_error":
                raise original_error
            return result

        if path == "http_error":
            with pytest.raises(RuntimeError) as caught:
                endpoint()
            assert caught.value is original_error
        else:
            assert endpoint() is result
    else:
        def source():
            arm_clock_failure()
            if path == "stream_error":
                raise original_error
            if path == "stream_exhausted":
                return result
            try:
                yield result
            finally:
                if path == "close_error":
                    raise original_error

        @diagnostics.http_attempt
        def endpoint():
            return diagnostics.stream(source())

        stream = endpoint()
        assert diagnostics._current.get() is None
        if path == "stream_error":
            with pytest.raises(RuntimeError) as caught:
                next(stream)
            assert caught.value is original_error
        elif path == "stream_exhausted":
            with pytest.raises(StopIteration) as caught:
                next(stream)
            assert caught.value.value is result
        else:
            assert next(stream) is result
            assert diagnostics._current.get() is None
            if path == "close_error":
                with pytest.raises(RuntimeError) as caught:
                    stream.close()
                assert caught.value is original_error
            else:
                stream.close()
        stream.close()
        stream.close()

    assert len(attempts) == 1 and attempts[0].finished
    assert len(clock_calls) == 1  # The late failure was actually exercised.
    assert diagnostics._current.get() is None
    assert SECRET not in json.dumps(events, ensure_ascii=False)
