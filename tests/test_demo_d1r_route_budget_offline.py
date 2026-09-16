"""D1R route budget: one fake model call per substantive free-text turn."""

from __future__ import annotations

import uuid

import pytest

from session import mem_get, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only,
    envelope_clinic_policy_only,
    envelope_content_only,
)
from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask


def test_free_text_booking_uses_one_model_call_before_lead_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-budget-book-{uuid.uuid4().hex[:8]}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Хочу записаться на консультацию",
        envelope_json=envelope_adult_booking_only(),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_name"
    meta = payload.get("meta") or {}
    assert meta.get("lead_flow") is True


def test_policy_question_single_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-budget-pol-{uuid.uuid4().hex[:8]}"
    _, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Лечите по ОМС?",
        envelope_json=envelope_clinic_policy_only("no_oms"),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") in (None, "", "none")


def test_content_only_single_model_call_no_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-budget-content-{uuid.uuid4().hex[:8]}"
    _, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Расскажите про имплантацию",
        envelope_json=envelope_content_only("Краткий ответ про имплантацию."),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") in (None, "", "none")
