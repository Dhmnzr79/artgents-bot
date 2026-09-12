"""PostgreSQL enqueue contract — tenant-owned rows require explicit client_id."""

from __future__ import annotations

import queue

import pytest

import pg_sink


@pytest.fixture
def pg_queue(monkeypatch: pytest.MonkeyPatch):
    q: queue.Queue = queue.Queue()
    monkeypatch.setattr(pg_sink, "_SINK_DISABLED", False)
    monkeypatch.setattr(pg_sink, "_Q", q)
    monkeypatch.setattr(pg_sink, "_log", lambda *_a, **_k: None)
    return q


@pytest.mark.parametrize(
    "client_id",
    [None, "", "  ", " demo", "demo "],
)
def test_enqueue_bot_event_rejects_missing_or_untrimmed_client_id(
    pg_queue: queue.Queue,
    client_id,
) -> None:
    pg_sink.enqueue_bot_event(
        {
            "event_type": "turn_complete",
            "client_id": client_id,
            "details": {},
        }
    )
    assert pg_queue.empty()


def test_enqueue_bot_event_preserves_explicit_tenant(pg_queue: queue.Queue) -> None:
    pg_sink.enqueue_bot_event(
        {
            "event_type": "turn_complete",
            "client_id": "nikadent",
            "details": {"ok": True},
        }
    )
    kind, payload, retries = pg_queue.get_nowait()
    assert kind == "bot_event"
    assert retries == 0
    assert payload["client_id"] == "nikadent"


@pytest.mark.parametrize(
    "enqueue_fn,kind",
    [
        (pg_sink.enqueue_lead, "lead"),
        (pg_sink.enqueue_v5_turn_trace, "v5_turn_trace"),
        (pg_sink.enqueue_v5_verifier_shadow, "v5_verifier_shadow"),
    ],
)
def test_tenant_owned_enqueue_kinds_require_client_id(
    pg_queue: queue.Queue,
    enqueue_fn,
    kind: str,
) -> None:
    enqueue_fn({"client_id": None, "turn_id": "t-1"})
    assert pg_queue.empty()
    enqueue_fn({"client_id": "demo", "turn_id": "t-2", "event_type": "x"})
    item_kind, payload, _ = pg_queue.get_nowait()
    assert item_kind == kind
    assert payload["client_id"] == "demo"


def test_tenant_client_id_for_pg_write_contract() -> None:
    assert pg_sink.tenant_client_id_for_pg_write({"client_id": "nikadent"}) == "nikadent"
    assert pg_sink.tenant_client_id_for_pg_write({"client_id": None}) is None
    assert pg_sink.tenant_client_id_for_pg_write({"client_id": " demo"}) is None


def test_enqueue_rejects_without_mutating_caller_payload(pg_queue: queue.Queue) -> None:
    original = {"event_type": "turn_complete", "client_id": None, "details": {"a": 1}}
    snapshot = dict(original)
    pg_sink.enqueue_bot_event(original)
    assert original == snapshot
    assert pg_queue.empty()


def test_enqueue_valid_tenant_does_not_mutate_caller_payload(pg_queue: queue.Queue) -> None:
    original = {"event_type": "turn_complete", "client_id": "demo", "details": {"a": 1}}
    snapshot = dict(original)
    pg_sink.enqueue_bot_event(original)
    assert original == snapshot
    _, payload, _ = pg_queue.get_nowait()
    assert payload["client_id"] == "demo"


def test_emit_bot_event_skips_pg_without_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    from logging_setup import emit_bot_event, get_logger

    enqueued: list[dict] = []

    def _capture(row: dict) -> None:
        enqueued.append(dict(row))

    monkeypatch.setattr(pg_sink, "enqueue_bot_event", _capture)
    monkeypatch.setattr(
        "core.client_config_loader.postgres_events_enabled",
        lambda _cid: True,
    )
    logger = get_logger("test_pg_contract")
    emit_bot_event(logger, "test_event", status="ok", details={"x": 1})
    assert enqueued == []
