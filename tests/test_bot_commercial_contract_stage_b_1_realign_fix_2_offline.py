"""BOT-COMMERCIAL-CONTRACT-STAGE-B-1-REALIGN-FIX-2 — typed UI pure-price + parity."""

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
from core.one_call_price_text import resolve_pure_code_owned_monetary_request
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]

_HOSTILE_CONSULTATION_PROSE = (
    "На бесплатной консультации врач подберёт план лечения и предложит записаться."
)


def _assert_no_hostile_consultation_prose(answer: str) -> None:
    assert _HOSTILE_CONSULTATION_PROSE.casefold() not in str(answer or "").casefold()


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


def _user_history(sid: str) -> list[str]:
    return [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]


def _snapshot_payload(sid: str, payload: dict) -> dict:
    meta = payload.get("meta") or {}
    session = read_target_runtime_session(sid)
    return {
        "answer": payload.get("answer"),
        "offer": payload.get("offer"),
        "quick_replies": payload.get("quick_replies"),
        "cta": payload.get("cta"),
        "video": payload.get("video"),
        "meta": {
            key: meta.get(key)
            for key in (
                "matched_service_id",
                "service_route",
                "terminal_mode",
                "answer_path",
            )
            if key in meta
        },
        "session": {
            "last_service_id": session.last_service_id,
            "last_selected_offer_id": session.last_selected_offer_id,
            "last_displayed_offer_ids": tuple(session.last_displayed_offer_ids),
        },
        "history": tuple(_user_history(sid)),
    }


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_followups"] = [
            {
                "ref": item.ref,
                "label": item.label,
                **({"client_id": item.client_id} if item.client_id else {}),
            }
            for item in items
        ]
        _persist_unlocked(sid, st)


def _clarify_service_envelope(text: str, *, options: list[str]) -> str:
    return answer_envelope(
        text,
        route="CLARIFY",
        commercial_intent="price",
        promotion_scope="none",
        clarify_axis="service",
        clarify_service_options=options,
        service_reference_status="none",
        requested_service_id=None,
    )


def _neutral_price_answer_envelope(text: str = "Актуальная стоимость.") -> str:
    return answer_envelope(
        text,
        commercial_intent="price",
        service_id=None,
        extent=None,
        service_reference_status="none",
        requested_service_id=None,
    )


def test_resolve_pure_price_from_governed_scope_ref_not_label() -> None:
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    assert resolve_pure_code_owned_monetary_request(
        "Вся челюсть",
        nav_ref=ref,
    )
    assert resolve_pure_code_owned_monetary_request("", nav_ref=ref)
    assert not resolve_pure_code_owned_monetary_request(
        "Вся челюсть",
        nav_ref=None,
    )


def test_scope_click_empty_q_suppresses_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix2-scope-empty-{uuid.uuid4().hex[:8]}"
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
    ref, label = _scope_ref(t1, "full_arch")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope(
            _HOSTILE_CONSULTATION_PROSE,
            commercial_intent="none",
            service_reference_status="none",
        ),
        ref=ref,
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    _assert_no_hostile_consultation_prose(answer)
    assert label in _user_history(sid)


def test_scope_click_with_label_q_suppresses_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix2-scope-label-{uuid.uuid4().hex[:8]}"
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
    ref, label = _scope_ref(t1, "full_arch")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message=label,
        envelope_json=answer_envelope(
            _HOSTILE_CONSULTATION_PROSE,
            commercial_intent="none",
            service_reference_status="none",
        ),
        ref=ref,
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    _assert_no_hostile_consultation_prose(answer)
    assert label in _user_history(sid)


def test_pending_price_service_click_is_pure_price(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix2-pending-svc-{uuid.uuid4().hex[:8]}"
    clarify_backend = _Backend(_clarify_service_envelope("Уточните.", options=["classic", "all_on_4"]))
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    ref = str(next(item["ref"] for item in t1["quick_replies"] if "classic" in str(item.get("ref"))))
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=_neutral_price_answer_envelope(_HOSTILE_CONSULTATION_PROSE),
        ref=ref,
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "76200" in _norm_digits(answer)
    _assert_no_hostile_consultation_prose(answer)
    session = read_target_runtime_session(sid)
    assert session.last_service_id == "classic"


def test_informational_service_click_not_pure_price(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix2-info-svc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ref = build_ui_service_ref(service_id="classic")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(
            ref=ref,
            label="Классическая имплантация",
            client_id="demo",
        ),
    )
    stub = "STUB-INFO-SERVICE-PROSE-99"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope(
            stub,
            commercial_intent="included",
            service_reference_status="none",
        ),
        ref=ref,
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert stub in answer


def test_governed_stages_click_suppresses_model_prose_once(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"fix2-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    stages_ref = "price:classic/stages"
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=stages_ref, label="Оплата по этапам", client_id="demo"),
    )
    _run_ask(
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
        reset_session=False,
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope(
            f"{_HOSTILE_CONSULTATION_PROSE}\n\nПервый платёж составит 45 200 ₽.",
            commercial_intent="payment",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        ref=stages_ref,
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    assert _count_amount(answer, 45200) == 1
    assert _count_amount(answer, 31000) == 1
    _assert_no_hostile_consultation_prose(answer)
    assert "хирургическ" in answer.casefold()


def test_mixed_price_installment_keeps_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    stub = "Рассрочка доступна до 12 месяцев без переплаты."
    payload = _run_ask(
        monkeypatch,
        sid=f"fix2-mixed-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4 на Implantium и можно ли в рассрочку?",
        envelope_json=answer_envelope(
            stub,
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert "без переплаты" in answer.casefold()


def test_broad_price_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = answer_envelope(
        "Обзор.",
        commercial_intent="price",
        service_reference_status="none",
        scenario="cost",
    )
    q = "Сколько стоит имплантация?"
    sid_ask = f"fix2-broad-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"fix2-broad-stream-{uuid.uuid4().hex[:8]}"
    ask_payload = _run_ask(monkeypatch, sid=sid_ask, user_message=q, envelope_json=env)
    stream_payload = _run_stream(monkeypatch, sid=sid_stream, user_message=q, envelope_json=env)
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert _snapshot_payload(sid_ask, ask_payload) == _snapshot_payload(
        sid_stream, stream_payload
    )


def test_scoped_price_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid_ask = f"fix2-scoped-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"fix2-scoped-stream-{uuid.uuid4().hex[:8]}"
    t1_ask = _run_ask(
        monkeypatch,
        sid=sid_ask,
        user_message="Сколько стоит имплантация?",
        envelope_json=answer_envelope(
            "Обзор.",
            commercial_intent="price",
            service_reference_status="none",
            scenario="cost",
        ),
    )
    ref, _ = _scope_ref(t1_ask, "full_arch")
    env = answer_envelope(
        _HOSTILE_CONSULTATION_PROSE,
        commercial_intent="none",
        service_reference_status="none",
    )
    ask_payload = _run_ask(
        monkeypatch,
        sid=sid_ask,
        user_message="",
        envelope_json=env,
        ref=ref,
        reset_session=False,
    )
    t1_stream = _run_ask(
        monkeypatch,
        sid=sid_stream,
        user_message="Сколько стоит имплантация?",
        envelope_json=answer_envelope(
            "Обзор.",
            commercial_intent="price",
            service_reference_status="none",
            scenario="cost",
        ),
    )
    ref_stream, _ = _scope_ref(t1_stream, "full_arch")
    assert ref_stream == ref
    stream_payload = _run_stream(
        monkeypatch,
        sid=sid_stream,
        user_message="",
        envelope_json=env,
        ref=ref_stream,
        reset_session=False,
    )
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    _assert_no_hostile_consultation_prose(str(ask_payload.get("answer") or ""))
    _assert_no_hostile_consultation_prose(str(stream_payload.get("answer") or ""))


def test_stages_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    stages_ref = "price:classic/stages"
    env_price = answer_envelope(
        "Цена.",
        commercial_intent="price",
        service_id="classic",
        extent="one_tooth",
        service_reference_status="resolved",
        requested_service_id="classic",
    )
    env_stages = answer_envelope(
        _HOSTILE_CONSULTATION_PROSE,
        commercial_intent="payment",
        service_id="classic",
        service_reference_status="resolved",
        requested_service_id="classic",
    )
    sid_ask = f"fix2-stages-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"fix2-stages-stream-{uuid.uuid4().hex[:8]}"
    for sid in (sid_ask, sid_stream):
        mem_reset(sid)
        _seed_followups(
            sid,
            TargetRuntimeFollowupItem(ref=stages_ref, label="Этапы оплаты", client_id="demo"),
        )
        _run_ask(
            monkeypatch,
            sid=sid,
            user_message="Сколько стоит классическая имплантация на Implantium?",
            envelope_json=env_price,
            reset_session=False,
        )
    ask_payload = _run_ask(
        monkeypatch,
        sid=sid_ask,
        user_message="",
        envelope_json=env_stages,
        ref=stages_ref,
        reset_session=False,
    )
    stream_payload = _run_stream(
        monkeypatch,
        sid=sid_stream,
        user_message="",
        envelope_json=env_stages,
        ref=stages_ref,
        reset_session=False,
    )
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert _count_amount(str(ask_payload.get("answer") or ""), 45200) == 1
    assert _count_amount(str(stream_payload.get("answer") or ""), 45200) == 1


def test_no_public_and_clarify_not_empty(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    no_public = _run_ask(
        monkeypatch,
        sid=f"fix2-no-public-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит костная пластика?",
        envelope_json=answer_envelope(
            "Костная пластика стоит 100 ₽.\n\nПроцедура требуется при недостаточном объёме кости.",
            commercial_intent="price",
            service_id="bone_graft",
        ),
    )
    assert str(no_public.get("answer") or "").strip()
    clarify = _run_ask(
        monkeypatch,
        sid=f"fix2-clarify-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит?",
        envelope_json=_clarify_service_envelope("Уточните вариант.", options=["classic"]),
    )
    assert str(clarify.get("answer") or "").strip()
