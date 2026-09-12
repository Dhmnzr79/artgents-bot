"""Active lead path must not enqueue patient name/phone into PostgreSQL."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from lead_service import handle_lead


def test_handle_lead_store_postgres_enqueues_null_name_and_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _capture(row: dict) -> None:
        captured.append(dict(row))

    monkeypatch.setattr("lead_service.leads_enabled", lambda _c: True)
    monkeypatch.setattr("lead_service.leads_mode", lambda _c: "email")
    monkeypatch.setattr(
        "lead_service.load_lead_config",
        lambda _c: {"store_in_postgres": True},
    )
    monkeypatch.setattr("lead_service._resolve_delivery_status", lambda *_a, **_k: "email")
    monkeypatch.setattr("lead_service.is_clinic_open_now", lambda _c: True)
    monkeypatch.setattr("lead_service.build_lead_dialog_excerpt", lambda *_a, **_k: {})
    monkeypatch.setattr("lead_service.format_lead_dialog_excerpt_block", lambda _x: "")
    monkeypatch.setattr("lead_service._emit_lead_event", lambda *_a, **_k: None)
    monkeypatch.setattr("pg_sink.enqueue_lead", _capture)

    payload, status = handle_lead(
        {
            "name": "Иван Иванов",
            "phone": "+79001112233",
            "sid": "sid-lead-1",
        },
        client_id="demo",
    )
    assert status == 200
    assert payload.get("ok") is True
    assert len(captured) == 1
    assert captured[0]["name"] is None
    assert captured[0]["phone"] is None
