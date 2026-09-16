"""D1R HTTP offline tests with fake backend request_understanding JSON."""

from __future__ import annotations

import uuid

import pytest

from core.clinic_policies_loader import policy_answer
from session import mem_get, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only,
    envelope_booking_plus_contact,
    envelope_child_booking_blocked,
    envelope_clinic_policy_only,
    envelope_content_only,
    envelope_no_subjects_contact_address,
    envelope_pediatric_policy_plus_contact,
)
from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask, _post_stream


def _demo_policy_snippet(policy_key: str) -> str:
    text = policy_answer("demo", policy_key) or ""
    assert text.strip()
    return text.split(".")[0].strip().lower()


@pytest.mark.parametrize(
    ("user_message", "policy_key"),
    [
        ("Лечите детей?", "no_pediatric_dentistry"),
        ("Лечите по ОМС?", "no_oms"),
        ("Принимаете ДМС?", "no_dms"),
    ],
)
def test_d1r_policy_http_uses_authored_answer(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    policy_key: str,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet(policy_key)
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=envelope_clinic_policy_only(policy_key),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:40] in answer or snippet in answer


def test_d1r_contact_without_subjects(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-addr-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Нужна справочная информация по локации",
        envelope_json=envelope_no_subjects_contact_address(),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "моск" in answer or "адрес" in answer


def test_d1r_adult_booking_enters_lead_after_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-book-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Хочу записаться",
        envelope_json=envelope_adult_booking_only(),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_name"
    assert (payload.get("meta") or {}).get("lead_step") == "name"


def test_d1r_child_booking_blocked_no_lead_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-child-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_pediatric_dentistry")
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Запишите ребёнка на приём",
        envelope_json=envelope_child_booking_blocked(),
        client_id="demo",
    )
    assert backend.call_count == 1
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") in (None, "", "none")
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:30] in answer or "дет" in answer


def test_d1r_booking_plus_contact_keeps_both_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-mix-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Запись и справка по локации клиники",
        envelope_json=envelope_booking_plus_contact(),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "адрес" in answer or "моск" in answer
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_name"


def test_d1r_policy_plus_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-pol-addr-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_pediatric_dentistry")
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Политика по детям и справка по локации",
        envelope_json=envelope_pediatric_policy_plus_contact("ignore"),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:30] in answer or "дет" in answer
    assert "адрес" in answer or "моск" in answer


def test_d1r_content_plus_policy_block(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-content-{uuid.uuid4().hex}"
    line = "Профессиональная гигиена занимает около часа."
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько длится чистка?",
        envelope_json=envelope_content_only(line),
        client_id="demo",
    )
    assert backend.call_count == 1
    assert line.split()[0].lower() in str(payload.get("answer") or "").lower()


def test_d1r_policy_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-stream-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet("no_oms")
    ask_payload, ask_backend = _post_ask(
        monkeypatch,
        sid=f"{sid}-ask",
        user_message="Лечите по ОМС?",
        envelope_json=envelope_clinic_policy_only("no_oms"),
        client_id="demo",
    )
    stream_payload, stream_backend = _post_stream(
        monkeypatch,
        sid=f"{sid}-stream",
        user_message="Лечите по ОМС?",
        envelope_json=envelope_clinic_policy_only("no_oms"),
        client_id="demo",
    )
    assert ask_backend.call_count == 1 and stream_backend.call_count == 1
    assert snippet[:30] in str(ask_payload.get("answer") or "").lower()
    assert snippet[:30] in str(stream_payload.get("answer") or "").lower()
