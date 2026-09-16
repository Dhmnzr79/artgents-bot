"""Demo D1: clinic business policy authority on /ask and /ask/stream (offline)."""

from __future__ import annotations

import json
import re
import uuid

import pytest

import app as app_module
import config
from core.clinic_policies_loader import clinic_business_policy_keys, policy_answer
from core.one_call_clinic_policy_authority import (
    assess_applicable_clinic_policies,
    serialize_clinic_business_policies_block,
)
from session import mem_get, mem_reset
from tests.test_one_call_tenant_isolation_offline import (
    _enable_demo_nikadent,
    _parse_sse_ui_payload,
    _post_ask,
    _post_stream,
)
from tests.test_sales_one_plus_turn import answer_envelope

_HOSTILE_PEDIATRIC = (
    "Да, мы с радостью примем вашего ребёнка и ведём детскую стоматологию. Запишем на приём."
)
_HOSTILE_OMS = "Да, лечим по полису ОМС — приносите полис, всё оформим."
_HOSTILE_DMS = "Работаем напрямую по ДМС, ваш страховой полис подойдёт."


def _demo_policy_snippet(policy_key: str) -> str:
    text = policy_answer("demo", policy_key) or ""
    assert text.strip()
    return text.split(".")[0].strip().lower()


@pytest.mark.parametrize(
    ("user_message", "policy_key", "hostile"),
    [
        ("Лечите детей?", "no_pediatric_dentistry", _HOSTILE_PEDIATRIC),
        ("Можно записать ребёнка 8 лет?", "no_pediatric_dentistry", _HOSTILE_PEDIATRIC),
        ("Лечите по ОМС?", "no_oms", _HOSTILE_OMS),
        ("Принимаете ДМС?", "no_dms", _HOSTILE_DMS),
    ],
)
def test_demo_policy_questions_use_authored_answer_json(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    policy_key: str,
    hostile: str,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-json-{uuid.uuid4().hex}"
    snippet = _demo_policy_snippet(policy_key)
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=answer_envelope(hostile),
        client_id="demo",
    )
    assert backend.call_count in (0, 1)
    answer = str(payload.get("answer") or "").lower()
    assert snippet[:40] in answer or snippet in answer
    assert "прием вашего реб" not in answer or policy_key != "no_pediatric_dentistry"
    if policy_key == "no_pediatric_dentistry":
        assert "детск" in answer
        assert "примем вашего реб" not in answer
    if policy_key == "no_oms":
        assert "омс" in answer
        assert "лечим по полису омс" not in answer
    if policy_key == "no_dms":
        assert "дмс" in answer
        assert "работаем напрямую по дмс" not in answer


@pytest.mark.parametrize(
    "hostile",
    [_HOSTILE_PEDIATRIC, _HOSTILE_OMS, _HOSTILE_DMS],
)
def test_hostile_model_cannot_leak_via_sse(
    monkeypatch: pytest.MonkeyPatch,
    hostile: str,
) -> None:
    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _install_sales_fast_transport,
    )

    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-sse-{uuid.uuid4().hex}"
    user_message = {
        _HOSTILE_PEDIATRIC: "Можно записать ребёнка?",
        _HOSTILE_OMS: "Работаете по ОМС?",
        _HOSTILE_DMS: "Принимаете ДМС?",
    }[hostile]
    backend = _CountingBackend(answer_envelope(hostile))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count in (0, 1)
    raw = resp.get_data(as_text=True)
    assert hostile[:30].lower() not in raw.lower()
    ui = _parse_sse_ui_payload(resp)
    answer = str(ui.get("answer") or "").lower()
    assert "примем вашего реб" not in answer
    assert "лечим по полису омс" not in answer
    assert "работаем напрямую по дмс" not in answer
    assert raw.count("text_delta") == 0 or "text_delta" not in raw


@pytest.mark.parametrize(
    "user_message",
    [
        "Я взрослый, не ребёнок, сколько стоит чистка?",
        "В детстве лечили зуб, сейчас нужна коронка",
    ],
)
def test_adult_context_not_blocked(monkeypatch: pytest.MonkeyPatch, user_message: str) -> None:
    _enable_demo_nikadent(monkeypatch)
    keys = assess_applicable_clinic_policies(user_message=user_message, client_id="demo")
    assert keys == ()
    sid = f"d1-adult-{uuid.uuid4().hex}"
    payload, _backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=answer_envelope(
            "Профессиональная чистка для взрослых доступна, стоимость уточним на консультации."
        ),
        client_id="demo",
    )
    answer = str(payload.get("answer") or "").lower()
    assert "детскую стоматологию в клинике не вед" not in answer


def test_mixed_contact_and_pediatric_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"d1-mix-{uuid.uuid4().hex}"
    payload, _backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Принимаете детей и где находитесь?",
        envelope_json=answer_envelope(_HOSTILE_PEDIATRIC),
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
        envelope_json=answer_envelope(_HOSTILE_PEDIATRIC),
        client_id="demo",
    )
    payload, _backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Тогда запишите меня, взрослого",
        envelope_json=answer_envelope("Хорошо, записываю вас на консультацию для взрослого пациента."),
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
        envelope_json=answer_envelope(_HOSTILE_OMS),
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

    hostile = _HOSTILE_PEDIATRIC
    envelope = answer_envelope(hostile)
    result = _run_presentation_result(
        envelope_json=envelope,
        patient_text=hostile,
        user_message="Лечите детей?",
        today=date(2026, 8, 1),
    )
    text = result.final_patient_text.lower()
    assert "детск" in text
    assert "примем вашего реб" not in text
