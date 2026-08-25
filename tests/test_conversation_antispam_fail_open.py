from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

import app as app_module
import config
from contracts.ingress_route import IngressRouteResult
from orchestration.context import AskTurnContext
from orchestration.pre_resolver_turn import run_pre_resolver_turn
from orchestration.route_guards import is_obvious_noise
from orchestration.sales_one_plus_ask_turn import _post_gate_flows
from session import _fresh_defaults, _lock, _persist_unlocked, mem_add_user, mem_get, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRODUCTION_ROOTS = (
    _REPO_ROOT / "config.py",
    _REPO_ROOT / "session.py",
    _REPO_ROOT / "orchestration",
)

_REMOVED_RUNTIME_SYMBOLS = (
    "ANTI_SPAM_BURST_WINDOW_SEC",
    "ANTI_SPAM_BURST_MESSAGES",
    "ANTI_SPAM_NO_INTENT_TURNS",
    "is_message_burst",
    "should_soft_redirect_no_intent",
    "set_anti_spam_redirect_shown",
    "user_turn_timestamps",
    "anti_spam_redirect_shown",
    "anti_spam_burst_redirect",
    "soft_redirect_payload",
)

_SEVEN_TURN_QUESTIONS = (
    "Какие виды имплантации есть?",
    "Чем отличается All-on-4?",
    "А All-on-6?",
    "Сколько длится лечение?",
    "Какие врачи проводят имплантацию?",
    "Есть ли рассрочка?",
    "Как проходит консультация?",
)


class _CountingBackend:
    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text
        self.call_count = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocation = invocation
        return self.answer_text

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.invocation = invocation
        on_raw_delta(self.answer_text)
        return None


@pytest.fixture(autouse=True)
def _bypass_technical_rate_limit_for_conversation_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")


def _install_candidate_transport(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _post_ask(client, *, sid: str, q: str) -> dict:
    resp = client.post(
        "/ask",
        json={"q": q, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def _assert_normal_answer_payload(payload: dict) -> None:
    answer = str(payload.get("answer") or "").strip()
    meta = payload.get("meta") or {}
    assert answer
    assert meta.get("service_route") != "sales_fast_admin"
    assert meta.get("anti_spam_soft_redirect") is not True
    assert meta.get("service_route") != "booking_flow"
    assert meta.get("error") != "technical_error"


def test_removed_runtime_symbols_absent_from_production_modules() -> None:
    hits: list[str] = []
    for root in _PRODUCTION_ROOTS:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for symbol in _REMOVED_RUNTIME_SYMBOLS:
                if symbol in text:
                    hits.append(f"{path.relative_to(_REPO_ROOT)}:{symbol}")
    assert hits == []


def test_new_session_has_no_conversation_antispam_state_fields() -> None:
    sid = f"g2-fresh-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    st = mem_get(sid)
    assert "user_turn_timestamps" not in st
    assert "anti_spam_redirect_shown" not in st


def test_mem_add_user_does_not_write_turn_timestamps() -> None:
    sid = f"g2-add-user-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    mem_add_user(sid, "Какие виды имплантации есть?")
    st = mem_get(sid)
    assert "user_turn_timestamps" not in st
    assert int(st.get("session_turn_count") or 0) == 1


def test_legacy_session_payload_with_old_antispam_fields_does_not_redirect() -> None:
    sid = f"g2-legacy-{uuid.uuid4().hex[:8]}"
    now = time.time()
    with _lock:
        st = _fresh_defaults()
        st["user_turn_timestamps"] = [now] * 10
        st["anti_spam_redirect_shown"] = False
        st["session_turn_count"] = 25
        _persist_unlocked(sid, st)

    loaded = mem_get(sid)
    assert loaded.get("user_turn_timestamps")
    assert int(loaded.get("session_turn_count") or 0) == 25

    outcome = _post_gate_flows(
        data={"q": "Какие виды имплантации есть?", "sid": sid, "client_id": "demo"},
        q="Какие виды имплантации есть?",
        sid=sid,
        client_id="demo",
        client_txt=lambda *_a, **_k: {},
        service_payload=lambda answer, _sid, _cid, **_: {"answer": answer, "meta": {}},
        get_last_content_ui_payload=lambda *_a, **_k: None,
    )
    assert outcome is None


def test_pre_resolver_legacy_path_ignores_old_burst_and_no_intent_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"g2-pre-{uuid.uuid4().hex[:8]}"
    now = time.time()
    with _lock:
        st = _fresh_defaults()
        st["user_turn_timestamps"] = [now] * 10
        st["anti_spam_redirect_shown"] = False
        st["session_turn_count"] = 25
        _persist_unlocked(sid, st)

    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", False)
    monkeypatch.setattr(
        "orchestration.pre_resolver_turn.classify_ingress",
        lambda *_a, **_k: IngressRouteResult(
            route="normal",
            confidence=0.9,
            reason="offline_fake",
            policy_key=None,
            requested_service=None,
            source="rule",
            is_urgent=False,
        ),
    )
    monkeypatch.setattr("orchestration.pre_resolver_turn.handle_flows", lambda *_a, **_k: None)

    with app_module.app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "Какие виды имплантации есть?", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {}
        outcome = run_pre_resolver_turn(
            {"q": "Какие виды имплантации есть?", "sid": sid, "client_id": "demo"},
            resolve_client_id=lambda *_a, **_k: "demo",
            bind_chat_ctx=lambda *_a, **_k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda *_a, **_k: {},
            service_payload=lambda **_k: {},
            get_last_content_ui_payload=lambda *_a, **_k: None,
        )

    assert isinstance(outcome, AskTurnContext)
    assert outcome.q == "Какие виды имплантации есть?"


def test_candidate_legacy_session_fields_do_not_block_ask_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(
        answer_envelope("Ответ по материалам клиники о безопасности имплантации.")
    )
    _install_candidate_transport(monkeypatch, backend)
    sid = f"g2-candidate-legacy-{uuid.uuid4().hex[:8]}"
    now = time.time()
    with _lock:
        st = _fresh_defaults()
        st["user_turn_timestamps"] = [now] * 10
        st["anti_spam_redirect_shown"] = False
        st["session_turn_count"] = 25
        _persist_unlocked(sid, st)

    client = app_module.app.test_client()
    payload = _post_ask(client, sid=sid, q="Какие виды имплантации есть?")
    _assert_normal_answer_payload(payload)
    assert backend.call_count == 1


def test_candidate_seven_fast_normal_messages_each_reach_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(
        answer_envelope("Ответ по материалам клиники о безопасности имплантации.")
    )
    _install_candidate_transport(monkeypatch, backend)
    sid = f"g2-seven-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    client = app_module.app.test_client()

    for question in _SEVEN_TURN_QUESTIONS:
        payload = _post_ask(client, sid=sid, q=question)
        _assert_normal_answer_payload(payload)

    assert backend.call_count == len(_SEVEN_TURN_QUESTIONS)


def test_candidate_twenty_one_normal_turns_without_booking_intent_reach_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(
        answer_envelope("Ответ по материалам клиники о безопасности имплантации.")
    )
    _install_candidate_transport(monkeypatch, backend)
    sid = f"g2-twentyone-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    client = app_module.app.test_client()

    questions = [
        (
            f"Уточнение {turn}: какие этапы имплантации проходят в клинике "
            f"для пациента с разным клиническим случаем номер {turn}?"
        )
        for turn in range(1, 22)
    ]
    for question in questions:
        payload = _post_ask(client, sid=sid, q=question)
        _assert_normal_answer_payload(payload)

    assert backend.call_count == 21


def test_obvious_noise_still_blocks_repeated_chars() -> None:
    assert is_obvious_noise("!!!!!")
    assert not is_obvious_noise("Какие виды имплантации есть?")
