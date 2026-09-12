"""BOT-CLEANUP-WIDGET-COMMERCIAL-ALIGNMENT-1 — CTA ingress, scope preservation, contract."""

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
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_service_action import build_ui_service_ref
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)
from core.sales_one_plus_protocol import SALES_ONE_PLUS_SYSTEM_POLICY
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
_INSTALLMENT_STUB = "Рассрочка доступна до 12 месяцев без переплаты."


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
    envelope_json: str | None = None,
    ref: str | None = None,
    extra: dict | None = None,
    reset_session: bool = True,
    backend: _Backend | None = None,
) -> dict:
    be = backend or _Backend(envelope_json or answer_envelope("ok"))
    _install_sales_fast(monkeypatch, be)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    if extra:
        payload.update(extra)
    response = client.post("/ask", json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    body["_backend_calls"] = be.call_count
    return body


def _run_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
    extra: dict | None = None,
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
    if extra:
        payload.update(extra)
    response = client.post("/ask/stream", json=payload)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    body["_backend_calls"] = backend.call_count
    return body


def _scope_ref(payload: dict, extent_token: str) -> tuple[str, str]:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if extent_token in ref:
            return ref, str(item.get("label") or "")
    raise AssertionError(f"scope ref {extent_token} missing")


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


def _user_history(sid: str) -> list[str]:
    return [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]


def test_cta_lead_flow_starts_before_empty_question_guard(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    sid = f"align-cta-{uuid.uuid4().hex[:8]}"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        extra={"cta_action": "lead"},
        envelope_json=answer_envelope("ignored"),
    )
    assert payload["_backend_calls"] == 0
    assert (payload.get("meta") or {}).get("lead_flow") is True
    assert (payload.get("meta") or {}).get("lead_step") == "name"
    assert mem_get(sid).get("lead_intent") == "collecting_name"


def test_empty_q_without_managed_action_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    sid = f"align-empty-{uuid.uuid4().hex[:8]}"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope("ignored"),
    )
    assert payload["_backend_calls"] == 0
    assert (payload.get("meta") or {}).get("error") == "empty_question"


def test_forged_scope_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    sid = f"align-forged-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=ref,
        envelope_json=answer_envelope("ignored"),
    )
    assert payload["_backend_calls"] == 0
    assert (payload.get("meta") or {}).get("service_route") == "sales_fast_followup_unknown"


def test_full_arch_scope_click_code_owned_prices(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"align-full-arch-{uuid.uuid4().hex[:8]}"
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
        ref=ref,
        envelope_json=answer_envelope(
            _HOSTILE_CONSULTATION_PROSE,
            commercial_intent="none",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    digits = _norm_digits(answer)
    assert "318000" in digits
    assert "398000" in digits
    assert "420000" not in digits
    _assert_no_hostile_consultation_prose(answer)
    assert label in _user_history(sid)


def test_one_tooth_scope_click_classic_price(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"align-one-tooth-{uuid.uuid4().hex[:8]}"
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
    ref, label = _scope_ref(t1, "one_tooth")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        user_message=label,
        ref=ref,
        envelope_json=answer_envelope(
            _HOSTILE_CONSULTATION_PROSE,
            commercial_intent="none",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    answer = str(t2.get("answer") or "")
    assert "76200" in _norm_digits(answer)
    _assert_no_hostile_consultation_prose(answer)


def test_zygomatic_direct_price_and_structured_exclusions(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"align-zygo-{uuid.uuid4().hex[:8]}"
    ref = build_ui_service_ref(service_id="zygomatic_implants")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=ref, label="Скуловая имплантация", client_id="demo"),
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=ref,
        envelope_json=answer_envelope(
            _HOSTILE_CONSULTATION_PROSE,
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
    assert "хирургический этап" in answer.casefold()
    assert "постоянный протез" in answer.casefold()
    assert "кт" in answer.casefold()
    assert "седация" in answer.casefold() or "наркоз" in answer.casefold()
    assert "импланты по плану" not in answer.casefold()


def test_pure_zygomatic_price_without_auto_commercial_facts(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"align-zygo-pure-{uuid.uuid4().hex[:8]}"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит скуловая имплантация?",
        envelope_json=answer_envelope(
            "Краткий ответ.",
            commercial_intent="price",
            service_id="zygomatic_implants",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="zygomatic_implants",
        ),
    )
    answer = str(payload.get("answer") or "").casefold()
    assert "420000" in _norm_digits(answer)
    assert "акци" not in answer
    assert "гарант" not in answer
    assert "бесплатн" not in answer
    session = read_target_runtime_session(sid)
    assert "implant_same_day_discount" not in (session.shown_fact_ids or ())


def test_zygomatic_mixed_price_and_installment(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"align-zygo-mixed-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит скуловая имплантация и есть ли рассрочка?",
        envelope_json=answer_envelope(
            _INSTALLMENT_STUB,
            commercial_intent="price",
            service_id="zygomatic_implants",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="zygomatic_implants",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "420000" in _norm_digits(answer)
    assert "без переплаты" in answer.casefold()


def test_direct_warranty_question_preserves_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    stub = "STUB-WARRANTY-ALIGN-42"
    payload = _run_ask(
        monkeypatch,
        sid=f"align-warranty-{uuid.uuid4().hex[:8]}",
        user_message="Какая гарантия на импланты?",
        envelope_json=answer_envelope(
            stub,
            commercial_intent="payment",
            service_reference_status="none",
            references={"direct_fact_ids": ["implant_warranty"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert stub in answer
    assert "76200" not in _norm_digits(answer)


def test_direct_promotion_question_preserves_model_prose(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    stub = "STUB-PROMO-ALIGN-42"
    payload = _run_ask(
        monkeypatch,
        sid=f"align-promo-{uuid.uuid4().hex[:8]}",
        user_message="Какие акции на имплантацию?",
        envelope_json=answer_envelope(
            stub,
            commercial_intent="promotion",
            promotion_scope="general",
            service_reference_status="none",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert stub in answer
    assert "318000" not in _norm_digits(answer)


def test_generic_payment_question_without_auto_stages_table(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    payload = _run_ask(
        monkeypatch,
        sid=f"align-pay-generic-{uuid.uuid4().hex[:8]}",
        user_message="Как можно оплатить?",
        envelope_json=answer_envelope(
            "Оплата наличными, картой и поэтапно по плану лечения.",
            commercial_intent="payment",
            service_reference_status="none",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "45200" not in _norm_digits(answer)
    assert "31000" not in _norm_digits(answer)


def test_stable_system_prompt_has_no_microfact_renderer_contradiction() -> None:
    combined = "\n".join(
        (
            SALES_ONE_PLUS_SYSTEM_POLICY,
            ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
        )
    ).casefold()
    assert "up to two assigned short microfacts" not in combined
    assert "do not expect deterministic code to append canonical fact texts" in combined
    assert "mandatory price conditions" in combined
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 13


def test_dormant_commercial_renderer_not_in_active_presentation() -> None:
    source = inspect.getsource(presentation_pass_module.build_one_call_presentation_result)
    assert "render_offer_commercial_blocks" not in source
    assert "_rendered_fact_ids_from_text(" not in source


@pytest.mark.parametrize(
    ("runner", "extra"),
    [
        ("ask", {}),
        ("stream", {}),
        ("ask", {"cta_action": "lead", "q": ""}),
        ("stream", {"cta_action": "lead", "q": ""}),
    ],
)
def test_ask_stream_payload_parity_subset(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
    runner: str,
    extra: dict,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    if extra.get("cta_action") == "lead":
        env = answer_envelope("ignored")
        q = ""
        sid_ask = f"align-parity-cta-ask-{uuid.uuid4().hex[:8]}"
        sid_stream = f"align-parity-cta-stream-{uuid.uuid4().hex[:8]}"
        ask_payload = _run_ask(
            monkeypatch,
            sid=sid_ask,
            user_message=q,
            envelope_json=env,
            extra=extra,
        )
        stream_payload = _run_stream(
            monkeypatch,
            sid=sid_stream,
            user_message=q,
            envelope_json=env,
            extra=extra,
        )
        assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
        assert (ask_payload.get("meta") or {}).get("lead_flow") is True
        return

    env = answer_envelope(
        "Обзор.",
        commercial_intent="price",
        service_reference_status="none",
        scenario="cost",
    )
    q = "Сколько стоит имплантация?"
    sid_ask = f"align-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"align-parity-stream-{uuid.uuid4().hex[:8]}"
    ask_payload = _run_ask(monkeypatch, sid=sid_ask, user_message=q, envelope_json=env)
    stream_payload = _run_stream(monkeypatch, sid=sid_stream, user_message=q, envelope_json=env)
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
