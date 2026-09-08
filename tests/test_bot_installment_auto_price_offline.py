"""Offline tests for automatic installment_12 on code-owned price turns."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path

import config
import pytest

import app as app_module
from core.one_call_installment_auto_policy import (
    INSTALLMENT_12_FACT_ID,
    INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT,
    all_displayed_offers_support_installment_12,
    installment_microfact_text,
    installment_positive_context_text,
    resolve_installment_excluded_scope_text,
    resolve_shared_installment_suffix_for_price_turn,
)
from core.target_client_data import load_target_client_data
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import bind_session_client, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_DEMO_BUNDLE = load_target_client_data("demo").bundle
_INSTALLMENT_MICROFACT = installment_microfact_text(_DEMO_BUNDLE)
_INSTALLMENT_POSITIVE = installment_positive_context_text(_DEMO_BUNDLE)
_EXCLUDED_SCOPE_TEXT = resolve_installment_excluded_scope_text(_DEMO_BUNDLE, "caries")


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
def isolated_demo_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    monkeypatch.setattr("session.sqlite_path_for_client", _sqlite_path)
    bind_session_client("demo")
    yield
    _clear_session_connection_cache()


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        on_raw_delta(str(self.output))
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _Backend) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
) -> dict:
    backend = _Backend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        from core.sales_fast_widget_runtime import run_sales_fast_widget_turn

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            backend=backend,
        )
    payload = dict(outcome.widget.payload or {})
    payload["_backend_calls"] = backend.call_count
    return payload


@pytest.fixture
def flask_app():
    return app_module.app


def _offer(offer_id: str):
    return next(item for item in _DEMO_BUNDLE.offers if item.offer_id == offer_id)


def test_policy_shared_suffix_only_when_all_offers_eligible() -> None:
    implantium = _offer("all_on_4.jaw.implantium")
    impro = _offer("all_on_4.jaw.impro")
    today = date(2026, 8, 10)
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, impro),
        today=today,
    ) == _INSTALLMENT_MICROFACT
    impro_without = impro.model_copy(
        update={
            "fact_refs": tuple(
                ref for ref in impro.fact_refs if ref != INSTALLMENT_12_FACT_ID
            )
        }
    )
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, impro_without),
        today=today,
    ) is None
    assert not all_displayed_offers_support_installment_12(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, impro_without),
        today=today,
    )


def test_eligible_all_on_4_price_auto_appends_installment(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-price-a4",
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert _INSTALLMENT_MICROFACT in answer
    assert answer.count(_INSTALLMENT_MICROFACT) == 1
    assert INSTALLMENT_12_FACT_ID in read_target_runtime_session("inst-price-a4").shown_fact_ids


def test_ineligible_caries_price_has_no_installment_suffix(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-price-caries",
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Лечение кариеса.",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "6500" in _norm_digits(answer)
    assert _INSTALLMENT_MICROFACT not in answer
    assert INSTALLMENT_12_FACT_ID not in read_target_runtime_session("inst-price-caries").shown_fact_ids


def test_follow_up_after_eligible_price_confirms_installment(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "inst-follow-eligible"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А рассрочка есть?",
        envelope_json=answer_envelope(
            "Да, рассрочка доступна.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert _INSTALLMENT_POSITIVE in answer
    assert "Да, рассрочка доступна." not in answer
    assert "318000" not in _norm_digits(answer)


def test_follow_up_after_ineligible_price_uses_excluded_scope_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "inst-follow-ineligible"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Лечение кариеса.",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А рассрочка есть?",
        envelope_json=answer_envelope(
            "Да, рассрочка доступна.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert _EXCLUDED_SCOPE_TEXT in answer
    assert "Да, рассрочка доступна." not in answer
    assert _INSTALLMENT_MICROFACT not in answer


def test_follow_up_after_whitening_uses_neutral_unavailable_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "inst-follow-whitening"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит отбеливание?",
        envelope_json=answer_envelope(
            "Отбеливание зубов.",
            commercial_intent="price",
            service_id="professional_whitening",
            service_reference_status="resolved",
            requested_service_id="professional_whitening",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А рассрочка есть?",
        envelope_json=answer_envelope(
            "Да, рассрочка доступна.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT in answer
    assert "Да, рассрочка доступна." not in answer
    assert _INSTALLMENT_MICROFACT not in answer


def test_direct_all_on_4_installment_question_without_prior_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-direct-a4",
        user_message="Есть рассрочка на All-on-4?",
        envelope_json=answer_envelope(
            "Да, на All-on-4 доступна рассрочка.",
            commercial_intent="payment",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert _INSTALLMENT_POSITIVE in answer
    assert "Да, на All-on-4 доступна рассрочка." not in answer
    assert "318000" not in _norm_digits(answer)
    assert "368000" not in _norm_digits(answer)


def test_direct_whitening_installment_question_uses_neutral_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-direct-whitening",
        user_message="Есть рассрочка на отбеливание?",
        envelope_json=answer_envelope(
            "Да, рассрочка на отбеливание доступна.",
            commercial_intent="payment",
            service_id="professional_whitening",
            service_reference_status="resolved",
            requested_service_id="professional_whitening",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT in answer
    assert "Да, рассрочка на отбеливание доступна." not in answer
    assert "18000" not in _norm_digits(answer)
    assert _INSTALLMENT_POSITIVE not in answer


def test_general_installment_question_does_not_materialize_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-general",
        user_message="У вас есть рассрочка?",
        envelope_json=answer_envelope(
            "В клинике доступна рассрочка на имплантацию и протезирование.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" not in _norm_digits(answer)
    assert "76200" not in _norm_digits(answer)
    assert "В клинике доступна рассрочка" in answer
    assert _INSTALLMENT_MICROFACT not in answer
    assert INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT not in answer


def test_mixed_multi_offer_has_no_shared_installment_suffix() -> None:
    implantium = _offer("all_on_4.jaw.implantium")
    nobel = _offer("all_on_4.jaw.nobel")
    impro_without = _offer("all_on_4.jaw.impro").model_copy(
        update={
            "fact_refs": tuple(
                ref
                for ref in _offer("all_on_4.jaw.impro").fact_refs
                if ref != INSTALLMENT_12_FACT_ID
            )
        }
    )
    today = date(2026, 8, 10)
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, nobel),
        today=today,
    ) == _INSTALLMENT_MICROFACT
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, impro_without, nobel),
        today=today,
    ) is None


def test_eligible_price_appends_installment_block_once(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="inst-once",
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium — популярный вариант.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert answer.count(_INSTALLMENT_MICROFACT) == 1


def test_installment_price_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = answer_envelope(
        "All-on-4 на Implantium.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
    )
    sid_ask = f"inst-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"inst-stream-{uuid.uuid4().hex[:8]}"

    def _ask(sid: str) -> dict:
        _install_sales_fast(monkeypatch, _Backend(env))
        mem_reset(sid)
        return app_module.app.test_client().post(
            "/ask",
            json={
                "q": "Сколько стоит All-on-4 на Implantium?",
                "sid": sid,
                "client_id": "demo",
            },
        ).get_json()

    def _stream(sid: str) -> dict:
        _install_sales_fast(monkeypatch, _Backend(env))
        mem_reset(sid)
        text = app_module.app.test_client().post(
            "/ask/stream",
            json={
                "q": "Сколько стоит All-on-4 на Implantium?",
                "sid": sid,
                "client_id": "demo",
            },
        ).get_data(as_text=True)
        match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
        assert match is not None
        return json.loads(match.group(1))

    ask_payload = _ask(sid_ask)
    stream_payload = _stream(sid_stream)
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert _INSTALLMENT_MICROFACT in str(ask_payload.get("answer") or "")
