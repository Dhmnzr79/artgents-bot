"""P0A: code-owned promotions and financial amplifiers on demo sales-fast path."""

from __future__ import annotations

from datetime import date

import pytest

from core.one_call_direct_commercial import DIRECT_COMMERCIAL_INELIGIBLE_PHRASE
from core.one_call_envelope_protocol import dumps_production_envelope
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.target_client_data import load_target_client_data
from session import bind_session_client, mem_reset, session_client_scope
import app as app_module
from tests.test_sales_fast_widget_integration import (
    _CountingBackend,
    _install_sales_fast_transport,
    _offline_widget_request_ctx,
    _orchestrate_ask,
    _parse_sse_events,
)
from tests.test_sales_one_plus_turn import admin_envelope, answer_envelope

_DEMO_BUNDLE = load_target_client_data("demo").bundle
_WHITENING_MICRO = str(_DEMO_BUNDLE.facts["professional_whitening_discount"].microfact_text)
_WHITENING_FULL = str(_DEMO_BUNDLE.facts["professional_whitening_discount"].text_fact)
_INSTALLMENT_FULL = str(_DEMO_BUNDLE.facts["installment_12"].text_fact)
_INSTALLMENT_MICRO = str(_DEMO_BUNDLE.facts["installment_12"].microfact_text)
_IMPLANT_DISCOUNT_MICRO = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].microfact_text)
_IMPLANT_DISCOUNT_FULL = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].text_fact)
_FREE_IMPLANT_CONSULT_MICRO = str(_DEMO_BUNDLE.facts["free_implant_consult"].microfact_text)
_FREE_IMPLANT_CONSULT_FULL = str(_DEMO_BUNDLE.facts["free_implant_consult"].text_fact)
_OVERVIEW_IDS = (
    "implant_same_day_discount",
    "professional_whitening_discount",
    "free_implant_consult",
)


class _StaticBackend:
    def __init__(self, output: object) -> None:
        self._output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self._output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        on_raw_delta(str(self._output))
        return None


def _widget_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
):
    backend = _StaticBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    bind_session_client("demo")
    if reset_session:
        mem_reset(sid, client_id="demo")
    with session_client_scope("demo"):
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            request.ctx = _offline_widget_request_ctx()
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
    return outcome, backend


@pytest.fixture
def flask_app():
    return app_module.app


def test_whitening_price_appends_short_promotion_once(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "Профессиональное отбеливание.",
        commercial_intent="price",
        service_id="professional_whitening",
    )
    outcome, backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-whitening-price",
        user_message="Сколько стоит профессиональное отбеливание?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    normalized = answer.replace("\u00a0", "").replace(" ", "")
    assert "18000" in normalized
    assert _WHITENING_MICRO in answer
    assert answer.count(_WHITENING_MICRO) == 1
    assert _WHITENING_FULL not in answer
    assert backend.call_count == 1


def test_service_promotion_whitening_without_model_direct_fact_ids(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "Про акции.",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="professional_whitening",
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-whitening-promo-select",
        user_message="Какая акция на отбеливание?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _WHITENING_FULL in answer
    assert "Про акции." not in answer


def test_general_promotion_overview_from_config(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "Модельный обзор.",
        commercial_intent="promotion",
        promotion_scope="general",
        service_id=None,
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-general-promo",
        user_message="Какие сейчас есть акции?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    for fact_id in _OVERVIEW_IDS:
        assert str(_DEMO_BUNDLE.facts[fact_id].text_fact) in answer
    assert answer.index(str(_DEMO_BUNDLE.facts[_OVERVIEW_IDS[0]].text_fact)) < answer.index(
        str(_DEMO_BUNDLE.facts[_OVERVIEW_IDS[1]].text_fact)
    )
    assert "Модельный обзор." not in answer


def test_wrong_service_direct_fact_id_ignored_on_service_promotion(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = dumps_production_envelope(
        patient_text="Про отбеливание.",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="professional_whitening",
        references={"direct_fact_ids": ["implant_same_day_discount"]},
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-wrong-direct-id",
        user_message="Какая акция на отбеливание?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _WHITENING_FULL in answer
    assert str(_DEMO_BUNDLE.facts["implant_same_day_discount"].text_fact) not in answer


def test_all_on_4_price_installment_once_with_promos(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "All-on-4 на нижнюю челюсть.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
    )
    outcome, backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-all-on-4-price",
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    normalized = answer.replace("\u00a0", "").replace(" ", "")
    assert "368000" in normalized
    assert "Также мы предлагаем:" in answer
    assert answer.count(_IMPLANT_DISCOUNT_MICRO) == 1
    assert answer.count(_FREE_IMPLANT_CONSULT_MICRO) == 1
    assert answer.count(_INSTALLMENT_MICRO) == 1
    assert _IMPLANT_DISCOUNT_FULL not in answer
    assert _FREE_IMPLANT_CONSULT_FULL not in answer
    assert _INSTALLMENT_FULL not in answer
    assert backend.call_count == 1


def test_direct_installment_all_on_4_service_context(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = dumps_production_envelope(
        patient_text="Про рассрочку.",
        commercial_intent="payment",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        references={"direct_fact_ids": ["installment_12"]},
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-installment-direct",
        user_message="Есть ли рассрочка на All-on-4?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _INSTALLMENT_FULL in answer
    assert answer.count(_INSTALLMENT_FULL) == 1


def test_expired_whitening_promo_not_auto_on_price(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.runtime_today",
        lambda: date(2026, 12, 1),
    )
    envelope = answer_envelope(
        "Отбеливание.",
        commercial_intent="price",
        service_id="professional_whitening",
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-whitening-expired",
        user_message="Сколько стоит отбеливание?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _WHITENING_MICRO not in answer


def test_expired_direct_promotion_request_is_controlled(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    from core.one_call_presentation_pass import _fail_closed_text

    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.runtime_today",
        lambda: date(2026, 12, 1),
    )
    envelope = answer_envelope(
        "Про отбеливание.",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="professional_whitening",
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-expired-direct",
        user_message="Есть скидка на отбеливание?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _WHITENING_FULL not in answer
    assert answer.strip() == _fail_closed_text("promotion_no_eligible_facts")


def test_whitening_promo_not_on_classic_price(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "Классическая имплантация.",
        commercial_intent="price",
        service_id="classic",
        extent="one_tooth",
    )
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-classic-price",
        user_message="Сколько стоит имплант?",
        envelope_json=envelope,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert _WHITENING_MICRO not in answer


def test_admin_turn_has_no_automatic_financial_block(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    outcome, _backend = _widget_turn(
        monkeypatch,
        flask_app,
        sid="p0a-admin",
        user_message="Хочу поговорить с администратором",
        envelope_json=admin_envelope(),
    )
    answer = str(outcome.widget.payload.get("answer") or "").casefold()
    assert _WHITENING_MICRO.casefold() not in answer
    assert _INSTALLMENT_MICRO.casefold() not in answer


def test_multi_turn_session_cadence_and_direct_repeat(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    sid = "p0a-multi-turn"
    bind_session_client("demo")
    mem_reset(sid, client_id="demo")
    price_envelope = answer_envelope(
        "All-on-4.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
    )
    outcome1, backend1 = _widget_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        envelope_json=price_envelope,
        reset_session=False,
    )
    answer1 = str(outcome1.widget.payload.get("answer") or "")
    assert _IMPLANT_DISCOUNT_MICRO in answer1
    outcome2, backend2 = _widget_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        envelope_json=price_envelope,
        reset_session=False,
    )
    answer2 = str(outcome2.widget.payload.get("answer") or "")
    assert _INSTALLMENT_MICRO in answer2
    assert answer2.count(_INSTALLMENT_MICRO) == 1
    promo_envelope = answer_envelope(
        "Про скидку.",
        commercial_intent="promotion",
        promotion_scope="service",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
    )
    outcome3, _backend3 = _widget_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Какая скидка на All-on-4 в день обращения?",
        envelope_json=promo_envelope,
        reset_session=False,
    )
    answer3 = str(outcome3.widget.payload.get("answer") or "")
    discount_full = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].text_fact)
    assert discount_full in answer3
    assert backend1.call_count == 1
    assert backend2.call_count == 1


def test_inactive_promo_automatic_price_path_not_rendered(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    from dataclasses import replace

    from core.target_runtime_client_context import load_target_runtime_client_context

    from core.target_client_data import clear_target_client_data_cache
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()
    data = load_target_client_data("demo")
    inactive_discount = data.bundle.facts["implant_same_day_discount"].model_copy(
        update={"active": False}
    )
    bundle = data.bundle.model_copy(
        deep=True,
        update={
            "facts": {
                **data.bundle.facts,
                "implant_same_day_discount": inactive_discount,
            }
        },
    )
    ctx = replace(load_target_runtime_client_context("demo"), bundle=bundle)
    monkeypatch.setattr(
        "core.target_runtime_client_context.load_target_runtime_client_context",
        lambda _client_id: ctx,
    )
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.load_target_runtime_client_context",
        lambda _client_id: ctx,
    )
    try:
        outcome, _backend = _widget_turn(
            monkeypatch,
            flask_app,
            sid="p0a-inactive-auto-promo",
            user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
            envelope_json=answer_envelope(
                "All-on-4 на нижнюю челюсть — 368 000 ₽.",
                commercial_intent="price",
                service_id="all_on_4",
                extent="full_arch",
                jaw="lower",
            ),
        )
        answer = str(outcome.widget.payload.get("answer") or "")
        assert _IMPLANT_DISCOUNT_MICRO not in answer
        assert str(inactive_discount.text_fact) not in answer
    finally:
        from core.target_runtime_client_context import clear_target_runtime_client_context_cache

        clear_target_runtime_client_context_cache()


def test_inactive_promo_direct_fact_not_rendered(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    from dataclasses import replace

    from core.target_runtime_client_context import load_target_runtime_client_context

    from core.target_client_data import clear_target_client_data_cache
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()
    data = load_target_client_data("demo")
    inactive_discount = data.bundle.facts["implant_same_day_discount"].model_copy(
        update={"active": False}
    )
    bundle = data.bundle.model_copy(
        deep=True,
        update={
            "facts": {
                **data.bundle.facts,
                "implant_same_day_discount": inactive_discount,
            }
        },
    )
    ctx = replace(load_target_runtime_client_context("demo"), bundle=bundle)
    monkeypatch.setattr(
        "core.target_runtime_client_context.load_target_runtime_client_context",
        lambda _client_id: ctx,
    )
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.load_target_runtime_client_context",
        lambda _client_id: ctx,
    )
    try:
        outcome, _backend = _widget_turn(
            monkeypatch,
            flask_app,
            sid="p0a-inactive-direct-promo",
            user_message="Какая скидка на All-on-4?",
            envelope_json=answer_envelope(
                "Про скидку.",
                service_id="all_on_4",
                extent="full_arch",
                jaw="lower",
                references={"direct_fact_ids": ["implant_same_day_discount"]},
            ),
        )
        answer = str(outcome.widget.payload.get("answer") or "")
        assert str(inactive_discount.text_fact) not in answer
        assert _IMPLANT_DISCOUNT_MICRO not in answer
    finally:
        from core.target_runtime_client_context import clear_target_runtime_client_context_cache

        clear_target_runtime_client_context_cache()


def test_ask_and_stream_answer_parity(
    monkeypatch: pytest.MonkeyPatch, flask_app
) -> None:
    envelope = answer_envelope(
        "Отбеливание.",
        commercial_intent="price",
        service_id="professional_whitening",
    )
    backend = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, backend)
    ask_payload = _orchestrate_ask(
        monkeypatch,
        backend=backend,
        q="Сколько стоит профессиональное отбеливание?",
        sid="p0a-parity-ask",
    )
    stream_backend = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, stream_backend)
    bind_session_client("demo")
    mem_reset("p0a-parity-stream", client_id="demo")
    client = flask_app.test_client()
    with session_client_scope("demo"):
        resp = client.post(
            "/ask/stream",
            json={
                "q": "Сколько стоит профессиональное отбеливание?",
                "sid": "p0a-parity-stream",
                "client_id": "demo",
            },
        )
    assert resp.status_code == 200
    ui_events = [data for name, data in _parse_sse_events(resp) if name == "ui"]
    assert ui_events
    stream_answer = str(ui_events[-1].get("answer") or "")
    assert ask_payload["answer"] == stream_answer
    assert backend.call_count == 1
    assert stream_backend.call_count == 1
