"""BOT-CLEANUP-WIDGET-PRICE-FOLLOWUP-FIX-1 — conditions dedupe, stages chain, exact price."""

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
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_service_action import build_ui_service_ref
from core.sales_fast_authoritative_commerce import PAYMENT_STAGES_UNAVAILABLE_TEXT
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_CLASSIC_CONDITION = "КТ при необходимости и временная коронка"
_HOSTILE_STAGE_AMOUNT = "Первый платёж составит 99 999 ₽."


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _count_amount(answer: str, amount: int) -> int:
    return _norm_digits(answer).count(str(amount))


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
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
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
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    return body


def _scope_ref(payload: dict, extent_token: str) -> tuple[str, str]:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if extent_token in ref:
            return ref, str(item.get("label") or "")
    raise AssertionError(f"scope ref {extent_token} missing")


def _followup_ref(payload: dict, token: str) -> tuple[str, str]:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if token in ref:
            return ref, str(item.get("label") or "")
    raise AssertionError(f"followup ref {token} missing")


def _user_history(sid: str) -> list[str]:
    return [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]


def test_one_tooth_scope_mandatory_condition_appears_once(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pf-one-tooth-{uuid.uuid4().hex[:8]}"
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
    ref, _ = _scope_ref(t1, "one_tooth")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=ref,
        envelope_json=answer_envelope(
            "Консультация бесплатно.",
            commercial_intent="none",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "76200" in _norm_digits(answer)
    assert _CLASSIC_CONDITION.casefold() in answer.casefold()
    assert answer.lower().count(_CLASSIC_CONDITION.casefold()) == 1


@pytest.mark.parametrize("user_message", ["", "Оплата по этапам"])
def test_implantation_one_tooth_stages_chain_not_empty(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
    user_message: str,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pf-stages-{uuid.uuid4().hex[:8]}"
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
    scope_ref, _ = _scope_ref(t1, "one_tooth")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=scope_ref,
        envelope_json=answer_envelope(
            "Цена.",
            commercial_intent="price",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    stages_ref, stages_label = _followup_ref(t2, "/stages")
    t3 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message=user_message,
        ref=stages_ref,
        envelope_json=answer_envelope(
            _HOSTILE_STAGE_AMOUNT,
            commercial_intent="payment",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        reset_session=False,
    )
    answer = str(t3.get("answer") or "")
    assert answer.strip()
    assert _count_amount(answer, 45200) == 1
    assert _count_amount(answer, 31000) == 1
    assert _count_amount(answer, 99999) == 0
    assert _count_amount(answer, 85200) == 0
    assert "impro" not in answer.casefold()
    assert "nobel" not in answer.casefold()
    assert stages_label in _user_history(sid)
    assert "продолжить" not in _user_history(sid)


def test_exact_implantium_brand_stages_only_selected_offer(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pf-exact-brand-{uuid.uuid4().hex[:8]}"
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит классическая имплантация на Implantium?",
        envelope_json=answer_envelope(
            "Цена.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
    )
    stages_ref, _ = _followup_ref(t1, "/stages")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=stages_ref,
        envelope_json=answer_envelope(
            _HOSTILE_STAGE_AMOUNT,
            commercial_intent="payment",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert answer.strip()
    assert _count_amount(answer, 45200) == 1
    assert _count_amount(answer, 31000) == 1
    assert "85200" not in _norm_digits(answer)
    session = read_target_runtime_session(sid)
    assert session.last_selected_offer_id == "classic.one_tooth.implantium"


def test_multi_brand_classic_stages_are_labeled(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pf-multi-brand-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Уточните.",
            route="CLARIFY",
            commercial_intent="price",
            clarify_axis="service",
            clarify_service_options=options,
            service_reference_status="none",
        ),
    )
    classic_ref = str(
        next(item["ref"] for item in t1["quick_replies"] if "classic" in str(item.get("ref")))
    )
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=classic_ref,
        envelope_json=answer_envelope(
            "Цены.",
            commercial_intent="price",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        reset_session=False,
    )
    stages_ref, _ = _followup_ref(t2, "/stages")
    t3 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=stages_ref,
        envelope_json=answer_envelope(
            _HOSTILE_STAGE_AMOUNT,
            commercial_intent="payment",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        reset_session=False,
    )
    answer = str(t3.get("answer") or "").casefold()
    assert answer.strip()
    assert _count_amount(answer, 45200) >= 1
    assert _count_amount(answer, 31000) >= 1
    assert "implantium" in answer
    assert "impro" in answer


def test_service_without_stages_returns_safe_nonempty_message(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
    from session import _lock, _persist_unlocked, mem_get as mem_get_locked

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"pf-no-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    forged_ref = "price:tomography/stages"
    with _lock:
        st = mem_get_locked(sid)
        st["target_runtime_followups"] = [
            {"ref": forged_ref, "label": "Оплата по этапам", "client_id": "demo"}
        ]
        _persist_unlocked(sid, st)
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=forged_ref,
        envelope_json=answer_envelope(
            "Этапы.",
            commercial_intent="payment",
            service_id="tomography",
            service_reference_status="resolved",
            requested_service_id="tomography",
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert answer.strip()
    assert PAYMENT_STAGES_UNAVAILABLE_TEXT in answer


def test_zygomatic_exact_price_grammar_and_capitalized_condition(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    ref = build_ui_service_ref(service_id="zygomatic_implants")
    from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
    from session import _lock, _persist_unlocked, mem_get as mem_get_locked

    sid = f"pf-zygo-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    with _lock:
        st = mem_get_locked(sid)
        st["target_runtime_followups"] = [
            {
                "ref": ref,
                "label": "Скуловая имплантация",
                "client_id": "demo",
            }
        ]
        _persist_unlocked(sid, st)
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=ref,
        envelope_json=answer_envelope(
            "Цена.",
            commercial_intent="price",
            service_id="zygomatic_implants",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="zygomatic_implants",
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert "420000" in _norm_digits(answer)
    assert answer.startswith("Скуловая имплантация —")
    assert "Стоимость Скуловая" not in answer
    assert "Постоянный протез" in answer


def test_stages_chain_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env_broad = answer_envelope(
        "Обзор.",
        commercial_intent="price",
        service_reference_status="none",
        scenario="cost",
    )
    env_scope = answer_envelope(
        "Цена.",
        commercial_intent="price",
        service_reference_status="none",
    )
    env_stages = answer_envelope(
        _HOSTILE_STAGE_AMOUNT,
        commercial_intent="payment",
        service_id="classic",
        service_reference_status="resolved",
        requested_service_id="classic",
    )
    sid_ask = f"pf-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"pf-parity-stream-{uuid.uuid4().hex[:8]}"
    t1_ask = _run_ask(monkeypatch, sid=sid_ask, user_message="Сколько стоит имплантация?", envelope_json=env_broad)
    t1_stream = _run_stream(monkeypatch, sid=sid_stream, user_message="Сколько стоит имплантация?", envelope_json=env_broad)
    scope_ref_ask, _ = _scope_ref(t1_ask, "one_tooth")
    scope_ref_stream, _ = _scope_ref(t1_stream, "one_tooth")
    t2_ask = _run_ask(
        monkeypatch,
        sid=sid_ask,
        user_message="",
        ref=scope_ref_ask,
        envelope_json=env_scope,
        reset_session=False,
    )
    t2_stream = _run_stream(
        monkeypatch,
        sid=sid_stream,
        user_message="",
        ref=scope_ref_stream,
        envelope_json=env_scope,
        reset_session=False,
    )
    stages_ref_ask, _ = _followup_ref(t2_ask, "/stages")
    stages_ref_stream, _ = _followup_ref(t2_stream, "/stages")
    ask_payload = _run_ask(
        monkeypatch,
        sid=sid_ask,
        user_message="",
        ref=stages_ref_ask,
        envelope_json=env_stages,
        reset_session=False,
    )
    stream_payload = _run_stream(
        monkeypatch,
        sid=sid_stream,
        user_message="",
        ref=stages_ref_stream,
        envelope_json=env_stages,
        reset_session=False,
    )
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
