"""Demo D1R: clinic policy via request_understanding on /ask (offline)."""

from __future__ import annotations

import uuid

import pytest

from core.clinic_policies_loader import clinic_business_policy_keys, policy_answer
from core.one_call_clinic_policy_authority import serialize_clinic_business_policies_block
from tests.d1r_envelope_fixtures import (
    envelope_adult_price_cleaning,
    envelope_clinic_policy_only,
    envelope_content_only,
    envelope_pediatric_policy_plus_contact,
)
from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask, _post_stream, _parse_sse_ui_payload
_HOSTILE_PEDIATRIC = (
    "Да, мы с радостью примем вашего ребёнка и ведём детскую стоматологию. Запишем на приём."
)
_HOSTILE_OMS = "Да, лечим по полису ОМС — приносите полис, всё оформим."


def _demo_policy_snippet(policy_key: str) -> str:
    text = policy_answer("demo", policy_key) or ""
    assert text.strip()
    return text.split(".")[0].strip().lower()


@pytest.mark.parametrize(
    ("user_message", "policy_key"),
    [
        ("Лечите детей?", "no_pediatric_dentistry"),
        ("Вы ведёте детскую стоматологию?", "no_pediatric_dentistry"),
        ("Лечите по ОМС?", "no_oms"),
        ("Принимаете ДМС?", "no_dms"),
    ],
)
def test_demo_policy_questions_use_authored_answer_json(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    policy_key: str,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-json-{uuid.uuid4().hex}"
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
    assert "примем вашего реб" not in answer


def test_hostile_model_cannot_leak_via_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-sse-{uuid.uuid4().hex}"
    ui, backend = _post_stream(
        monkeypatch,
        sid=sid,
        user_message="Лечите детей?",
        envelope_json=envelope_clinic_policy_only("no_pediatric_dentistry"),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(ui.get("answer") or "").lower()
    assert "примем вашего реб" not in answer
    assert _HOSTILE_PEDIATRIC[:20].lower() not in answer


@pytest.mark.parametrize(
    "user_message",
    [
        "Я взрослый, не ребёнок, сколько стоит чистка?",
        "В детстве лечили зуб, сейчас нужна коронка",
    ],
)
def test_adult_context_not_blocked(monkeypatch: pytest.MonkeyPatch, user_message: str) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-adult-{uuid.uuid4().hex}"
    model_line = (
        "Профессиональная чистка для взрослых доступна, стоимость уточним на консультации."
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=envelope_adult_price_cleaning(model_line),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "детскую стоматологию в клинике не вед" not in answer


def test_mixed_contact_and_pediatric_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-mix-{uuid.uuid4().hex}"
    payload, _backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Принимаете детей?",
        envelope_json=envelope_pediatric_policy_plus_contact(_HOSTILE_PEDIATRIC),
        client_id="demo",
    )
    answer = str(payload.get("answer") or "").lower()
    assert "детск" in answer
    assert "тверск" in answer or "москв" in answer or "адрес" in answer


def test_follow_up_adult_booking_not_inherits_pediatric_ban(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-follow-{uuid.uuid4().hex}"
    _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Можно записать ребёнка?",
        envelope_json=envelope_clinic_policy_only("no_pediatric_dentistry"),
        client_id="demo",
    )
    payload, _backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Тогда запишите меня, взрослого",
        envelope_json=envelope_content_only(
            "Хорошо, записываю вас на консультацию для взрослого пациента."
        ),
        client_id="demo",
    )
    answer = str(payload.get("answer") or "").lower()
    assert "детскую стоматологию в клинике не вед" not in answer


def test_nikadent_does_not_inherit_demo_oms_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    assert "no_oms" in clinic_business_policy_keys("demo")
    assert "no_oms" not in clinic_business_policy_keys("nikadent")
    block = serialize_clinic_business_policies_block("nikadent")
    assert block
    assert "no_oms" not in block
    sid = f"d1-tenant-{uuid.uuid4().hex}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Лечите по ОМС?",
        envelope_json=envelope_content_only(_HOSTILE_OMS),
        client_id="nikadent",
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "по полису омс мы не работаем" not in answer


def test_stable_prefix_contains_demo_policies_block() -> None:
    block = serialize_clinic_business_policies_block("demo")
    assert "CLINIC_BUSINESS_POLICIES" in block
    assert "no_pediatric_dentistry" in block


def test_presentation_suppresses_hostile_model_when_policy_applies() -> None:
    from datetime import date

    from tests.test_one_call_stage5_1_promotion import _run_presentation_result

    envelope = envelope_clinic_policy_only("no_pediatric_dentistry")
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=_HOSTILE_PEDIATRIC,
        user_message="Лечите детей?",
        today=date(2026, 8, 1),
    )
    text = result.final_patient_text.lower()
    assert "детск" in text
    assert "примем вашего реб" not in text
