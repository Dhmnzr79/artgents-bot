"""Clean One Call safety/content contract (offline HTTP/SSE)."""

from __future__ import annotations

import json
import re
import uuid

import pytest

import app as app_module
from core.sales_fast_presentation import (
    AUTOMATIC_AMPLIFIER_LIST_HEADER,
    static_sales_fast_admin_handoff,
)
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import admin_envelope, answer_envelope

_SAFE_MEDICAL_FAQ_TEXT = (
    "Антибиотики применяются только по назначению врача. "
    "Схему лечения определяет врач после осмотра."
)
_CURRENT_MEDICAL_QUESTION = (
    "У меня сильная боль и опухоль после имплантации, что делать?"
)
_FALSE_CONTENT_MARKER = "DEMO_FAKE_CLINIC_MARKER_XYZ"
_FALSE_KT_PRICE = "5000"
_UNAUTHORIZED_CTA_LABEL = "Записаться по секретной ссылке FAKE_CTA"
_PII_NAME = "Ivan Petrov"
_PII_PHONE = "+79001234567"


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _post_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    client_id: str = "demo",
) -> tuple[dict, _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    )
    assert resp.status_code == 200
    return resp.get_json(), backend


def test_typed_admin_route_uses_static_handoff_for_current_medical_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-admin-{uuid.uuid4().hex[:8]}",
        user_message=_CURRENT_MEDICAL_QUESTION,
        envelope_json=admin_envelope(),
    )
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert payload.get("answer") == static_sales_fast_admin_handoff(client_id="demo")
    answer = str(payload.get("answer") or "").lower()
    assert "администратор" in answer
    assert payload.get("offer") is None
    assert payload.get("promo") is None
    assert payload.get("cta") is None
    for reply in payload.get("quick_replies") or []:
        assert str(reply).strip()


def test_safe_medical_faq_answer_stays_materialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-faq-{uuid.uuid4().hex[:8]}",
        user_message="Можно ли принимать антибиотики без назначения?",
        envelope_json=answer_envelope(_SAFE_MEDICAL_FAQ_TEXT, route="ANSWER"),
    )
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_materialized"
    answer = str(payload.get("answer") or "")
    assert _SAFE_MEDICAL_FAQ_TEXT in answer or "антибиотики" in answer.lower()
    assert "у вас однозначно" not in answer.lower()
    assert "500 мг" not in answer
    assert payload.get("cta") is None or payload.get("cta") == {}


def test_braces_not_offered_removes_false_model_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-braces-{uuid.uuid4().hex[:8]}",
        user_message="Вы ставите брекеты?",
        envelope_json=answer_envelope(
            "Да, мы устанавливаем брекеты любой сложности.",
            service_reference_status="resolved",
            requested_service_id="braces",
            service_id=None,
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "не устанавливаем" in answer
    assert "да, мы устанавливаем брекеты" not in answer
    assert "элайнер" in answer


def test_aligners_available_service_is_not_marked_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-aligners-{uuid.uuid4().hex[:8]}",
        user_message="Расскажите про элайнеры",
        envelope_json=answer_envelope(
            "Элайнеры — прозрачные капы для выравнивания зубов.",
            service_reference_status="resolved",
            requested_service_id="aligners",
            service_id="aligners",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "не устанавливаем" not in answer
    assert "не оказывается" not in answer
    assert "элайнер" in answer


def test_existing_tomography_scan_does_not_add_ungrounded_new_kt_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-tomo-{uuid.uuid4().hex[:8]}",
        user_message="У меня уже есть свежее КT, можно прийти с ним?",
        envelope_json=answer_envelope(
            f"Нужно сделать новое КT за {_FALSE_KT_PRICE} рублей.",
            service_reference_status="resolved",
            requested_service_id="tomography",
            service_id="tomography",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert _FALSE_KT_PRICE not in digits
    assert answer.strip()
    assert "5000" not in digits


def test_unverified_model_cta_is_not_projected_into_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-cta-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            f"Лечение кариеса. {_UNAUTHORIZED_CTA_LABEL}",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert _UNAUTHORIZED_CTA_LABEL.lower() not in answer
    assert "fake_cta" not in answer
    for reply in payload.get("quick_replies") or []:
        assert "fake_cta" not in str(reply).lower()


def test_stream_status_and_diagnostics_do_not_leak_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            captured.append(fields)

    backend = _CountingBackend(
        answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        )
    )
    _install_sales_fast_transport(monkeypatch, backend)
    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    user_message = f"Сколько стоит All-on-4 на Implantium? {_PII_NAME} {_PII_PHONE}"
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": user_message, "sid": f"s-safe-pii-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    body = resp.get_data(as_text=True)
    assert backend.call_count == 1
    assert _PII_NAME not in body
    assert _norm_digits(_PII_PHONE) not in _norm_digits(body)
    assert user_message not in body
    for event_line in body.splitlines():
        if event_line.startswith("data:"):
            assert _PII_NAME not in event_line
            assert _norm_digits(_PII_PHONE) not in _norm_digits(event_line)
    assert captured
    diag_blob = json.dumps(captured[-1], ensure_ascii=False)
    assert _PII_NAME not in diag_blob
    assert _norm_digits(_PII_PHONE) not in _norm_digits(diag_blob)
    assert user_message not in diag_blob


def test_price_only_turn_does_not_activate_legacy_marketing_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-price-only-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Лечение кариеса.",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert "6500" in _norm_digits(answer)
    assert AUTOMATIC_AMPLIFIER_LIST_HEADER not in answer
    assert payload.get("marketing") is None
    assert _FALSE_CONTENT_MARKER not in answer


def test_generic_content_authority_strips_false_clinic_marker_on_code_owned_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-marker-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            f"All-on-4 стоит 1 рубль. {_FALSE_CONTENT_MARKER}",
            service_id="all_on_4",
            commercial_intent="price",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert _FALSE_CONTENT_MARKER not in answer
    assert "318000" in _norm_digits(answer)
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


def test_marketing_contact_activation_requires_typed_basis_not_plain_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-marketing-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "Запишитесь сейчас и получите подарок.",
            service_id="all_on_4",
            commercial_intent="price",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert payload.get("marketing") is None
    assert "подарок" not in answer
    assert AUTOMATIC_AMPLIFIER_LIST_HEADER not in answer


def test_typed_admin_route_uses_code_owned_handoff_without_commerce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-safe-admin-{uuid.uuid4().hex[:8]}",
        user_message="После операции воспаление, что делать?",
        envelope_json=admin_envelope(),
    )
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert payload.get("answer") == static_sales_fast_admin_handoff(client_id="demo")
    assert payload.get("offer") is None
