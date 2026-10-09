"""Stage 1: bounded provider metadata on the real D2 path, fake transport."""
import json
from types import SimpleNamespace

import pytest

from contracts.response_plan import SessionKey
from core import d2_diagnostics as diagnostics
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events


PRIVATE = "FAKE_PRIVATE_SENTINEL"
VALID = json.dumps({"outcome": "dialogue", "blocks": [
    {"kind": "clinic_policy", "request_id": "r1", "policy_ids": ["no_oms"]},
]})


def install_transport(monkeypatch, response):
    calls, events = [], []

    def transport(**kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr("core.d2_http_adapter.D2HttpProvider",
        lambda **kwargs: D2HttpProvider(transport=transport, **kwargs))
    monkeypatch.setattr(diagnostics, "_write", lambda fields: events.append(dict(fields)))
    return calls, events


def response(content=VALID, finish_reason="stop", usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)],
        usage=usage if usage is not None else
            SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150),
    )


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("content,finish_reason,status,reason", [
    (VALID, "stop", 200, None),
    (VALID, "length", 200, None),  # Observation is not a new rejection gate.
    ("{", "length", 400, "invalid_envelope"),
    ("", "content_filter", 503, "d2_http_response_content_missing"),
])
def test_provider_metadata_precedes_validation_and_keeps_wire(http_env, monkeypatch,
        streaming, content, finish_reason, status, reason):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")
    client, db, _, _ = http_env
    calls, events = install_transport(monkeypatch, response(content, finish_reason))
    args = dict(sid="metadata", request_id="same", q="Работаете по ОМС?")
    result = (post_sse if streaming else post)(client, **args)
    wire = dict(sse_events(result)) if streaming else result.get_json()
    assert result.status_code == (200 if streaming else status)
    assert ("ui" in wire if streaming else "answer" in wire) is (status == 200)
    if streaming:
        assert ("done" in wire) is (status == 200)
    finished = [event for event in events if event["event"] == "provider_finished"]
    assert len(finished) == len(calls) == 1
    observed = finished[0]
    assert observed["finish_reason"] == finish_reason
    assert (observed["prompt_tokens"], observed["completion_tokens"], observed["total_tokens"]) == (120, 30, 150)
    assert observed["provider_attempts"] == 1 and observed["duration_ms"] >= 0
    failures = [event for event in events if event["event"] == "failure"]
    if reason:
        assert len(failures) == 1 and failures[0]["reason"] == reason
        assert events.index(observed) < events.index(failures[0])
    else:
        assert not failures
        body = wire["ui"] if streaming else wire
        assert "ОМС" in body["answer"]
        # Replay uses the completion, without another provider call/observation.
        repeated = (post_sse if streaming else post)(client, **args)
        repeated_wire = dict(sse_events(repeated)) if streaming else repeated.get_json()
        assert repeated_wire == wire and len(calls) == 1
        assert len([event for event in events if event["event"] == "provider_finished"]) == 1
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="metadata"))
        assert (saved is not None) is (status == 200)
    assert diagnostics._current.get() is None


@pytest.mark.parametrize("usage,expected", [
    ({"prompt_tokens": 0, "completion_tokens": 5, "total_tokens": 5,
      "private": PRIVATE}, (0, 5, 5)),
    ({"prompt_tokens": PRIVATE, "completion_tokens": -1, "total_tokens": True}, (None, None, None)),
    (SimpleNamespace(prompt_tokens=1.5, completion_tokens="2", total_tokens=None), (None, None, None)),
])
def test_metadata_is_closed_and_never_exports_arbitrary_provider_values(http_env, monkeypatch, usage, expected):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")
    client, _, _, _ = http_env
    calls, events = install_transport(monkeypatch, response(finish_reason=PRIVATE, usage=usage))
    assert post(client).status_code == 200
    finished = next(event for event in events if event["event"] == "provider_finished")
    assert finished["finish_reason"] == "unknown"
    assert tuple(finished[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")) == expected
    assert PRIVATE not in json.dumps(events)
    assert len(calls) == 1


def test_metadata_write_failure_does_not_change_the_answer(http_env, monkeypatch):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")
    client, _, _, _ = http_env
    calls, _ = install_transport(monkeypatch, response())

    def broken(_fields):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(diagnostics, "_write", broken)
    result = post(client)
    assert result.status_code == 200 and "ОМС" in result.get_json()["answer"]
    assert len(calls) == 1 and diagnostics._current.get() is None
