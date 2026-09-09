"""BOT-COMMERCIAL-CONTRACT-STAGE-B-1-REALIGN-FIX-1 — monetary policy + shown_fact_ids."""

from __future__ import annotations

import inspect
import json
import re
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

import config
import pytest

import app as app_module
import core.one_call_presentation_pass as presentation_pass_module
from core.one_call_envelope_protocol import dumps_production_envelope
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


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

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        on_raw_delta(self.output)
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _Backend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _run_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    backend = _Backend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    response = client.post("/ask", json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    body["_backend_calls"] = backend.call_count
    return body


def _run_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    backend = _Backend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    response = client.post("/ask/stream", json=payload)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "event: status" in text or "event: ui" in text
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    body["_backend_calls"] = backend.call_count
    return body


def _scope_ref(payload: dict, extent_token: str) -> str:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if extent_token in ref:
            return ref
    raise AssertionError(f"scope ref {extent_token} missing")


@pytest.mark.parametrize(
    ("user_message", "stub", "commercial_intent", "direct_fact_ids"),
    [
        (
            "Есть ли у вас рассрочка?",
            "STUB-INSTALLMENT-PROSE-42",
            "payment",
            ["installment_12"],
        ),
        (
            "Какая у вас гарантия?",
            "STUB-WARRANTY-PROSE-42",
            "payment",
            ["implant_warranty"],
        ),
        (
            "Цена фиксируется в договоре?",
            "STUB-CONTRACT-PROSE-42",
            "payment",
            [],
        ),
        (
            "Можно получить налоговый вычет?",
            "STUB-TAX-PROSE-42",
            "payment",
            [],
        ),
        (
            "Что обычно входит в имплантацию?",
            "STUB-PACKAGE-PROSE-42",
            "included",
            [],
        ),
    ],
)
def test_general_model_owned_questions_preserve_stub_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
    user_message: str,
    stub: str,
    commercial_intent: str,
    direct_fact_ids: list[str],
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix-model-owned-{uuid.uuid4().hex[:8]}"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        envelope_json=answer_envelope(
            stub,
            commercial_intent=commercial_intent,
            service_reference_status="none",
            references={"direct_fact_ids": direct_fact_ids},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert stub in answer
    assert "76200" not in _norm_digits(answer)
    assert "318000" not in _norm_digits(answer)
    assert "Хирургический этап" not in answer
    session = read_target_runtime_session(sid)
    assert session.last_selected_offer_id is None
    assert tuple(session.shown_fact_ids or ()) == ()


def test_exact_price_monetary_paragraph_filter(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    captured: dict = {}

    def _capture_meta(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        "core.one_call_presentation_pass.record_monetary_prose_filter_meta",
        _capture_meta,
    )
    prose = (
        "Рассрочка доступна до 12 месяцев.\n\n"
        "Ежемесячный платёж составит 7 500 ₽."
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"fix-exact-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4 на Implantium и можно ли в рассрочку?",
        envelope_json=dumps_production_envelope(
            patient_text=prose,
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
    assert "7500" not in _norm_digits(answer)
    assert captured.get("removed_paragraph_count") == 1


def test_broad_price_hostile_paragraph_removed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    prose = (
        "Стоимость зависит от объёма.\n\n"
        "На консультации врач предложит вариант.\n\n"
        "Цена всего 999 999 ₽ за всё сразу."
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"fix-broad-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит имплантация?",
        envelope_json=answer_envelope(
            prose,
            commercial_intent="price",
            service_reference_status="none",
            scenario="cost",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "76200" in _norm_digits(answer) or "318000" in _norm_digits(answer)
    assert "999999" not in _norm_digits(answer)
    assert "стоимость зависит" not in answer.casefold()


def test_scoped_price_monetary_filter_and_history_label(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix-scoped-{uuid.uuid4().hex[:8]}"
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит имплантация?",
        envelope_json=answer_envelope(
            "Обзор.",
            commercial_intent="price",
            service_reference_status="none",
            scenario="cost",
        ),
    )
    ref = _scope_ref(t1, "full_arch")
    label = next(
        str(item.get("label") or "")
        for item in t1.get("quick_replies") or []
        if str(item.get("ref") or "") == ref
    )
    prose = (
        "Консультация без цен в модели.\n\n"
        "Итого 500 000 ₽ по нашей акции."
    )
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope(
            prose,
            commercial_intent="none",
            service_reference_status="none",
        ),
        ref=ref,
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "500000" not in _norm_digits(answer)
    assert "консультация без цен" not in answer.casefold()
    users = [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]
    assert label in users


def _count_amount(answer: str, amount: int) -> int:
    return _norm_digits(answer).count(str(amount))


def test_payment_stages_mixed_keeps_clean_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    clean = "Оплату можно разбить по этапам лечения без переплаты."
    hostile = "Первый платёж составит 45 200 ₽."
    payload = _run_ask(
        monkeypatch,
        sid=f"fix-stages-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит имплантация на Implantium и сколько платить на каждом этапе?",
        envelope_json=dumps_production_envelope(
            patient_text=f"{clean}\n\n{hostile}",
            commercial_intent="payment_stages",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "")
    assert _count_amount(answer, 45200) == 1
    assert _count_amount(answer, 31000) == 1
    assert "без переплаты" in answer.casefold()
    assert "первый платёж" not in answer.casefold()
    assert "хирургическ" in answer.casefold()


def test_no_public_price_keeps_medical_paragraph(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    prose = (
        "Костная пластика стоит 100 ₽.\n\n"
        "Процедура требуется при недостаточном объёме кости."
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"fix-no-public-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит костная пластика?",
        envelope_json=answer_envelope(
            prose,
            commercial_intent="price",
            service_id="bone_graft",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert answer.strip()
    assert "100" not in _norm_digits(answer)
    assert "недостаточн" in answer.casefold()


def test_ask_stream_parity_mixed_exact_price(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    prose = (
        "Рассрочка до 12 месяцев.\n\n"
        "Платёж 7 500 ₽ в месяц."
    )
    env = dumps_production_envelope(
        patient_text=prose,
        commercial_intent="price",
        scenario="cost",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        price_text=None,
    )
    sid_ask = f"fix-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"fix-parity-stream-{uuid.uuid4().hex[:8]}"
    q = "Сколько стоит All-on-4 на Implantium и можно ли в рассрочку?"
    ask_payload = _run_ask(monkeypatch, sid=sid_ask, user_message=q, envelope_json=env)
    stream_payload = _run_stream(monkeypatch, sid=sid_stream, user_message=q, envelope_json=env)
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert ask_payload.get("answer") == stream_payload.get("answer")
    assert "7500" not in _norm_digits(str(ask_payload.get("answer") or ""))


def test_stream_ui_event_is_final_presentation_not_raw_model(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    raw = "Стоимость 318 000 рублей. Рассрочка 12 месяцев."
    env = dumps_production_envelope(
        patient_text=raw,
        commercial_intent="price",
        scenario="cost",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
        price_text=None,
    )
    sid = f"fix-stream-invariant-{uuid.uuid4().hex[:8]}"
    client = app_module.app.test_client()
    _install_sales_fast(monkeypatch, _Backend(env))
    mem_reset(sid)
    response = client.post(
        "/ask/stream",
        json={
            "q": "Сколько стоит All-on-4 на Implantium?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    text = response.get_data(as_text=True)
    assert raw not in text
    ui = json.loads(re.search(r"event: ui\ndata: (.+?)\n\n", text).group(1))
    answer = str(ui.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert _norm_digits(answer).count("318000") == 1


def test_dormant_commercial_paths_not_in_active_presentation() -> None:
    source = inspect.getsource(presentation_pass_module.build_one_call_presentation_result)
    assert "render_offer_commercial_blocks" not in source
    assert "filter_price_turn_supplemental_prose" not in source
    assert "_apply_price_microfacts" not in source
    assert "strip_code_owned_price_claims_from_prose" not in source
    assert "strip_unauthorized_price_claims_from_prose" not in source
    assert "_rendered_fact_ids_from_text(" not in source
