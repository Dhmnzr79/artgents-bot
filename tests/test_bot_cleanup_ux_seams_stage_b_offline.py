"""Offline E2E for BOT-CLEANUP-UX-SEAMS-STAGE-B-1 (price-turn prose ownership)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import config
import pytest

import app as app_module
from core.one_call_price_text import (
    filter_price_turn_supplemental_prose,
    is_pure_price_only_request,
)
from session import bind_session_client, mem_reset
from tests.test_bot_cleanup_price_text_microfacts_offline import (
    _run_turn,
    dumps_production_envelope,
)
from tests.test_sales_one_plus_turn import answer_envelope


@pytest.fixture
def flask_app():
    return app_module.app


def _clear_session_connection_cache() -> None:
    import session as session_module

    with session_module._lock:
        for conn in list(session_module._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_module._conns.clear()


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    import unittest.mock as um

    p1 = um.patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    p2 = um.patch("session.sqlite_path_for_client", _sqlite_path)
    p1.start()
    p2.start()
    bind_session_client("demo")
    try:
        yield
    finally:
        p2.stop()
        p1.stop()
        _clear_session_connection_cache()


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def _install(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _run_ask(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
) -> dict:
    _install(monkeypatch, _CountingBackend(envelope_json))
    mem_reset(sid)
    client = flask_app.test_client()
    resp = client.post(
        "/ask",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, dict)
    return payload


def _norm_digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def test_pure_price_request_detection() -> None:
    assert is_pure_price_only_request("Сколько стоит классическая имплантация?")
    assert not is_pure_price_only_request(
        "Сколько стоит All-on-4 Implantium и как оформляется рассрочка?"
    )
    assert not is_pure_price_only_request(
        "Сколько стоит All-on-4 и какая скидка в день обращения?"
    )


def test_filter_drops_unrequested_prose_on_pure_price() -> None:
    prose = (
        "Стоимость зависит от системы. На консультации врач предложит вариант. "
        "Доступна рассрочка и оплата по этапам."
    )
    assert filter_price_turn_supplemental_prose(
        prose,
        "Сколько стоит классическая имплантация?",
    ) == ""


def test_filter_keeps_requested_installment_prose() -> None:
    installment = (
        "На имплантацию можно оформить рассрочку до 12 месяцев на консультации."
    )
    prose = f"Популярный вариант. {installment}"
    filtered = filter_price_turn_supplemental_prose(
        prose,
        "Сколько стоит All-on-4 Implantium и как оформляется рассрочка?",
    )
    assert installment in filtered
    assert "популярный вариант" not in filtered.casefold()


def test_classic_multi_price_turn_code_owned_without_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    prose = (
        "Стоимость зависит от системы. На консультации врач предложит вариант. "
        "Доступна рассрочка и оплата по этапам."
    )
    payload = _run_ask(
        monkeypatch,
        flask_app,
        sid=f"stage-b-classic-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит классическая имплантация?",
        envelope_json=answer_envelope(
            prose,
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            references={
                "direct_fact_ids": [
                    "payment_stages",
                    "installment_12",
                    "implant_same_day_discount",
                ]
            },
        ),
    )
    answer = str(payload.get("answer") or "")
    norm = _norm_digits(answer)
    assert "76200" in norm or "70200" in norm or "45200" in norm
    assert "консультации врач" not in answer.casefold()
    assert "оплата по этапам" not in answer.casefold()
    assert "стоимость зависит" not in answer.casefold()
    assert "Хирургический этап" not in answer
    assert "Рассрочка до 12 месяцев, оформление на консультации." in answer
    assert "Скидка до 15%" not in answer


def test_mixed_price_installment_keeps_requested_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    installment_explanation = (
        "На имплантацию и протезирование можно оформить рассрочку до 12 месяцев. "
        "Оформление — на консультации после согласования плана лечения."
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"stage-b-mixed-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4 Implantium и как оформляется рассрочка?",
        envelope_json=dumps_production_envelope(
            patient_text=f"All-on-4 — популярный вариант. {installment_explanation}",
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert installment_explanation in answer
    assert answer.count("Рассрочка до 12 месяцев, оформление на консультации.") == 1


def test_payment_stages_explicit_request_still_shows_table(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"stage-b-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _install(
        monkeypatch,
        _CountingBackend(
            answer_envelope(
                "Implantium.",
                commercial_intent="price",
                service_id="classic",
                extent="one_tooth",
                service_reference_status="resolved",
                requested_service_id="classic",
            )
        ),
    )
    client = flask_app.test_client()
    resp1 = client.post(
        "/ask",
        json={
            "q": "Сколько стоит классическая имплантация на Implantium?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp1.status_code == 200
    _install(
        monkeypatch,
        _CountingBackend(
            answer_envelope(
                "Этапы.",
                commercial_intent="payment_stages",
                service_id="classic",
                service_reference_status="resolved",
                requested_service_id="classic",
                references={"direct_fact_ids": []},
            )
        ),
    )
    resp2 = client.post(
        "/ask",
        json={
            "q": "Как платить по этапам?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp2.status_code == 200
    payload = resp2.get_json()
    assert isinstance(payload, dict)
    answer = str(payload.get("answer") or "")
    norm = _norm_digits(answer)
    assert "45200" in norm or "31000" in norm
