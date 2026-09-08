"""BOT-COMMERCIAL-CONTRACT-STAGE-B-1-REALIGN-1 — narrowed code-owned commerce."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

import config
import pytest

import app as app_module
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_payment_stages_policy import (
    governed_payment_stages_ui_ref,
    payment_stages_materialization_allowed,
)
from core.one_call_price_text import (
    filter_monetary_paragraphs_from_model_prose,
    is_pure_price_only_request,
    paragraph_contains_monetary_expression,
)
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.target_client_data import load_target_client_data
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import restore_session_snapshot
from session import bind_session_client, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
_DEMO_BUNDLE = load_target_client_data("demo").bundle
_LIVE_ARTIFACT = (
    _REPO
    / "evals/v5/artifacts/bot_cleanup_live_1/bot_cleanup_live_1_2026-09-04-live-01"
)


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _semantic(**kwargs):
    from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame

    base = {
        "route": "ANSWER",
        "commercial_intent": "price",
        "promotion_scope": "none",
        "scenario": "cost",
        "service_id": "classic",
        "service_id_provenance": "envelope",
        "extent": None,
        "extent_provenance": "null",
        "jaw": None,
        "jaw_provenance": "null",
        "stage": None,
        "stage_provenance": "null",
        "clarify_axis": None,
        "clarify_service_options": None,
        "service_reference_status": "resolved",
        "requested_service_id": "classic",
        "availability_status": "none",
        "direct_fact_ids": (),
    }
    base.update(kwargs)
    return SalesOnePlusSemanticFrame.model_validate(base)


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    patch_runtime = patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    patch_session = patch("session.sqlite_path_for_client", _sqlite_path)
    patch_runtime.start()
    patch_session.start()
    bind_session_client("demo")
    try:
        yield
    finally:
        patch_session.stop()
        patch_runtime.stop()


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self.output


@pytest.fixture
def flask_app():
    return app_module.app


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
    ref: str | None = None,
) -> tuple[dict, _Backend]:
    backend = _Backend(envelope_json)
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )
    if reset_session:
        mem_reset(sid)
    json_body = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        json_body["ref"] = ref
    with flask_app.test_request_context("/ask", method="POST", json=json_body):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        if ref:
            request.ctx["nav_ref"] = ref
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            backend=backend,
        )
    payload = dict(outcome.widget.payload or {})
    payload["_backend_calls"] = backend.call_count
    return payload, backend


def test_pure_exact_price_suppresses_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"realign-pure-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит классическая имплантация на Implantium?",
        envelope_json=dumps_production_envelope(
            patient_text="Классическая имплантация восстанавливает один зуб.",
            commercial_intent="price",
            scenario="cost",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
            references={"direct_fact_ids": ["installment_12", "payment_stages"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "76200" in _norm_digits(answer)
    assert "восстанавливает один зуб" not in answer.casefold()
    assert "Рассрочка до 12 месяцев, оформление на консультации." in answer
    assert "КТ при необходимости" in answer or "отдельно" in answer.casefold()


def test_price_plus_installment_keeps_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    installment = "Рассрочка оформляется на 12 месяцев без переплаты."
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"realign-install-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4 на Implantium и можно ли в рассрочку?",
        envelope_json=dumps_production_envelope(
            patient_text=installment,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert "12 месяцев" in answer.casefold()


def test_price_plus_package_keeps_model_phrase(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    package_phrase = "В пакет включены импланты, анестезия, временный протез."
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"realign-package-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4 на Implantium и что входит?",
        envelope_json=dumps_production_envelope(
            patient_text=package_phrase,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "").casefold()
    assert "318000" in _norm_digits(str(payload.get("answer") or ""))
    assert "в пакет включены импланты" in answer


def test_price_plus_medical_keeps_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    medical = "Операция проходит под местной анестезией, обычно без боли."
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"realign-med-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит классическая имплантация и как проходит операция?",
        envelope_json=dumps_production_envelope(
            patient_text=medical,
            commercial_intent="price",
            scenario="cost",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "").casefold()
    assert "76200" in _norm_digits(str(payload.get("answer") or ""))
    assert "анестез" in answer


def test_monetary_paragraph_filter() -> None:
    clean = "Рассрочка оформляется на 12 месяцев."
    dirty = "Платёж составит 7 500 ₽ в месяц."
    prose = f"{clean}\n\n{dirty}"
    filtered, removed = filter_monetary_paragraphs_from_model_prose(prose)
    assert removed == 1
    assert clean in filtered
    assert "7 500" not in filtered
    assert not paragraph_contains_monetary_expression("Скидка 15%")
    assert not paragraph_contains_monetary_expression("4 импланта")
    assert not paragraph_contains_monetary_expression("1 год гарантии")


def test_general_installment_model_owned(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, _ = _run_turn(
        monkeypatch,
        flask_app,
        sid=f"realign-general-install-{uuid.uuid4().hex[:8]}",
        user_message="Есть ли у вас рассрочка?",
        envelope_json=answer_envelope(
            "Рассрочка оформляется на 12 месяцев.",
            commercial_intent="payment",
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "").casefold()
    assert "рассроч" in answer
    assert "76200" not in _norm_digits(str(payload.get("answer") or ""))


def test_payment_stages_explicit_without_direct_fact_ids() -> None:
    semantic = _semantic(commercial_intent="payment_stages", direct_fact_ids=())
    assert payment_stages_materialization_allowed(
        semantic=semantic,
        user_message="Сколько платить на каждом этапе для Implantium?",
    )


def test_payment_stages_not_from_generic_payment_question() -> None:
    semantic = _semantic(
        commercial_intent="price",
        direct_fact_ids=("payment_stages",),
    )
    assert not payment_stages_materialization_allowed(
        semantic=semantic,
        user_message="Сколько стоит и как оплачивается?",
    )


def test_governed_ui_stages_ref_allowed() -> None:
    assert governed_payment_stages_ui_ref("price:classic/stages")


def test_is_pure_price_only_request() -> None:
    assert is_pure_price_only_request("Сколько стоит классическая имплантация?")
    assert not is_pure_price_only_request(
        "Сколько стоит All-on-4 и можно ли в рассрочку?"
    )
