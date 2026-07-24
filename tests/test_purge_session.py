"""Tests for manual session purge."""
from __future__ import annotations

from pg_retention import purge_session_observability


def test_purge_session_empty_args() -> None:
    stats = purge_session_observability("", sid="", client_id="demo")
    assert stats["found"] is False
    assert stats["bot_events_deleted"] == 0
