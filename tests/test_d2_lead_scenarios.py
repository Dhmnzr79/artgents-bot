"""CP5-LEAD: assembled A12 lead/privacy through common D2 route.

Fake raw → production parser → clinic_policy_resolver → existing session lead
owner → D2DialogueStore. Provider/live/network forbidden except one booking
entry call. Decisions: A12, D2-022, D2-031, D2-036. HTTP/SMTP FUTURE.
"""

from __future__ import annotations

import os
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from lead_interrupt import (
    LEAD_CANCEL_REF,
    LEAD_PENDING_ANSWER_REF,
    LEAD_PENDING_CONTINUE_NAME_REF,
)
from session import is_active_lead_flow, mem_get, mem_reset, session_client_scope
from tests.d1r_envelope_fixtures import (
    envelope_adult_booking_only,
    envelope_child_booking_blocked,
)


NOW = datetime(2026, 9, 22, 20, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[1]


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


class CountingDispatcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def dispatch(self, *, effect_id: str):
        self.calls.append(effect_id)
        return "demo_stub"


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    monkeypatch.setattr("session.sqlite_path_for_client", _sqlite_path)
    # Drop cached connections from prior tests.
    import session as session_mod

    with session_mod._lock:
        for conn in list(session_mod._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_mod._conns.clear()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-LEAD")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@contextmanager
def observed_common_route():
    """Forbid legacy ordinary ask/sales path; session lead-owner cleanup allowed."""
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith("core.sales_"), f"legacy sales called: {module}"
        assert module != "core.target_marketing_selector", "legacy marketing selector called"
        assert module != "orchestration.sales_one_plus_ask_turn", "legacy ask turn called"
        assert module != "core.target_composer", "legacy composer called"
        assert module != "core.one_call_runtime", "legacy one_call_runtime called"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _pack_clients(tmp_path: Path) -> Path:
    root = tmp_path / "clients"
    dest = root / "demo"
    if not dest.exists():
        shutil.copytree(REPO / "clients" / "demo", dest)
    return root


def _turn(
    *,
    tmp_path: Path,
    sid: str,
    message: str,
    provider: RawFakeProvider | None = None,
    request_id: str,
    lead_ui_ref: str | None = None,
    situation_action: str | None = None,
    lead_effect_id: str | None = None,
    dispatcher: CountingDispatcher | None = None,
    store: D2DialogueStore | None = None,
):
    clients = _pack_clients(tmp_path)
    dialogue_store = store or D2DialogueStore(tmp_path / "d2.sqlite")
    key = SessionKey(client_id="demo", sid=sid)
    fake = provider or RawFakeProvider("{}")
    return run_d2_dialogue_turn(
        session_key=key,
        user_message=message,
        provider=fake,
        clients_root=clients,
        store=dialogue_store,
        now=NOW,
        request_id=request_id,
        lead_ui_ref=lead_ui_ref,
        situation_action=situation_action,
        lead_effect_id=lead_effect_id,
        lead_effect_dispatcher=dispatcher,
        lead_bridge=True,
    ), fake, dialogue_store, key


def _assert_no_cta(outcome) -> None:
    assert outcome.response.ui_projection.buttons == ()


def test_a12_adult_booking_enters_name_collection(tmp_path):
    sid = "lead-a12-book"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        provider = RawFakeProvider(envelope_adult_booking_only())
        with observed_common_route():
            outcome, fake, _store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите меня",
                provider=provider,
                request_id="req-book-1",
            )
        assert len(fake.inputs) == 1
        assert mem_get(sid).get("lead_intent") == "collecting_name"
        assert is_active_lead_flow(mem_get(sid))
        assert "обращать" in outcome.response.rendered_text.lower()
        assert "записал" not in outcome.response.rendered_text.lower()
        _assert_no_cta(outcome)
        refs = {item.reply_id for item in outcome.response.ui_projection.quick_replies}
        assert LEAD_CANCEL_REF in refs


def test_a12_child_booking_blocked_no_lead(tmp_path):
    sid = "lead-a12-child"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        provider = RawFakeProvider(envelope_child_booking_blocked())
        with observed_common_route():
            outcome, fake, _store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите ребёнка",
                provider=provider,
                request_id="req-child-1",
            )
        assert len(fake.inputs) == 1
        assert mem_get(sid).get("lead_intent") in (None, "", "none")
        assert not is_active_lead_flow(mem_get(sid))
        _assert_no_cta(outcome)
        text = outcome.response.rendered_text.lower()
        assert "дет" in text or "ребен" in text or "ребён" in text


def test_a12_cancel_exits_without_cta(tmp_path):
    sid = "lead-a12-cancel"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        provider = RawFakeProvider(envelope_adult_booking_only())
        with observed_common_route():
            _, _, store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите меня",
                provider=provider,
                request_id="req-c0",
            )
            outcome, fake, _store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="не надо",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-c1",
                store=store,
            )
        assert fake.inputs == []
        assert mem_get(sid).get("lead_intent") == "none"
        assert not is_active_lead_flow(mem_get(sid))
        _assert_no_cta(outcome)
        assert outcome.response.ui_projection.quick_replies == ()


def test_d2_031_old_consent_does_not_auto_reenter(tmp_path):
    sid = "lead-d2031"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        with observed_common_route():
            _, _, store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите меня",
                provider=RawFakeProvider(envelope_adult_booking_only()),
                request_id="req-31-0",
            )
            _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="отмена",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-31-1",
                lead_ui_ref=LEAD_CANCEL_REF,
                store=store,
            )
            assert mem_get(sid).get("booking_intent_ever") is True
            assert mem_get(sid).get("lead_intent") == "none"
            # Ordinary clinic_policy turn must not reopen lead without fresh booking.
            from tests.d1r_envelope_fixtures import envelope_clinic_policy_only

            outcome, fake, _store, _key = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Вы работаете по ОМС?",
                provider=RawFakeProvider(envelope_clinic_policy_only("no_oms")),
                request_id="req-31-2",
                store=store,
            )
        assert len(fake.inputs) == 1
        assert mem_get(sid).get("lead_intent") == "none"
        assert not is_active_lead_flow(mem_get(sid))
        assert "обращать" not in outcome.response.rendered_text.lower()


def test_d2_022_situation_note_to_name_not_answered(tmp_path):
    sid = "lead-sit"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        with observed_common_route():
            start, fake0, store, _k0 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-sit-0",
                situation_action="start",
            )
            assert fake0.inputs == []
            assert mem_get(sid).get("situation_pending") is True
            assert "ситуац" in start.response.rendered_text.lower()

            note = "Нужна консультация по имплантации одного зуба"
            moved, fake1, _s1, _k1 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message=note,
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-sit-1",
                store=store,
            )
        assert fake1.inputs == []
        assert mem_get(sid).get("situation_pending") is False
        assert mem_get(sid).get("situation_note") == note
        assert mem_get(sid).get("lead_intent") == "collecting_name"
        # Note is clinic comment, not a medical/marketing answer.
        assert "имплант" not in moved.response.rendered_text.lower() or "обращать" in moved.response.rendered_text.lower()
        assert "обращать" in moved.response.rendered_text.lower()


def test_a12_name_phone_submit_one_effect(tmp_path):
    sid = "lead-submit"
    dispatcher = CountingDispatcher()
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        with observed_common_route():
            _, _, store, _k0 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите меня",
                provider=RawFakeProvider(envelope_adult_booking_only()),
                request_id="req-sub-0",
            )
            name_turn, fake_name, _s1, _k1 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Анна",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-sub-1",
                store=store,
            )
            assert fake_name.inputs == []
            assert mem_get(sid).get("lead_intent") == "collecting_phone"
            assert "телефон" in name_turn.response.rendered_text.lower()
            # No name confirmation prompt (A12).
            assert "правильно" not in name_turn.response.rendered_text.lower()

            phone_turn, fake_phone, _s2, _k2 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="+79001234567",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-sub-2",
                lead_effect_id="effect-1",
                dispatcher=dispatcher,
                store=store,
            )
        assert fake_phone.inputs == []
        assert mem_get(sid).get("lead_intent") == "none"
        assert dispatcher.calls == ["effect-1"]
        assert phone_turn.lead_effect.status == "demo_stub"
        assert phone_turn.lead_effect.effect_id == "effect-1"


def test_lead_bridge_false_does_not_enter_or_consume_name(tmp_path):
    """Booking entry needs lead_bridge; active lead still blocks provider without it."""
    sid = "lead-gate"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        clients = _pack_clients(tmp_path)
        store = D2DialogueStore(tmp_path / "d2.sqlite")
        key = SessionKey(client_id="demo", sid=sid)
        # Without lead_bridge, booking envelope must not mutate lead state.
        with pytest.raises(ValueError, match="d2_experiment_single_price_required"):
            run_d2_dialogue_turn(
                session_key=key,
                user_message="Запишите меня",
                provider=RawFakeProvider(envelope_adult_booking_only()),
                clients_root=clients,
                store=store,
                now=NOW,
                request_id="req-gate-0",
                lead_bridge=False,
            )
        assert mem_get(sid).get("lead_intent") in (None, "", "none")

        # Enter with bridge, then send name with lead_bridge=False — must not hit provider.
        _turn(
            tmp_path=tmp_path,
            sid=sid,
            message="Запишите меня",
            provider=RawFakeProvider(envelope_adult_booking_only()),
            request_id="req-gate-1",
            store=store,
        )
        assert mem_get(sid).get("lead_intent") == "collecting_name"
        probe = RawFakeProvider("MUST_NOT_CALL")
        outcome = run_d2_dialogue_turn(
            session_key=key,
            user_message="Анна",
            provider=probe,
            clients_root=clients,
            store=store,
            now=NOW,
            request_id="req-gate-2",
            lead_bridge=False,
        )
        assert probe.inputs == []
        assert mem_get(sid).get("lead_intent") == "collecting_phone"
        assert "телефон" in outcome.response.rendered_text.lower()


def test_mismatched_session_client_fails_closed(tmp_path):
    """Bound pack must equal session_key.client_id; no cross-tenant lead mem."""
    sid = "lead-tenant"
    with session_client_scope("nikadent"):
        mem_reset(sid, client_id="nikadent")
        clients = _pack_clients(tmp_path)
        store = D2DialogueStore(tmp_path / "d2.sqlite")
        key = SessionKey(client_id="demo", sid=sid)
        with pytest.raises(ValueError, match="d2_lead_session_client_mismatch"):
            run_d2_dialogue_turn(
                session_key=key,
                user_message="Запишите меня",
                provider=RawFakeProvider(envelope_adult_booking_only()),
                clients_root=clients,
                store=store,
                now=NOW,
                request_id="req-tenant-0",
                lead_bridge=True,
            )
        assert mem_get(sid).get("lead_intent") in (None, "", "none")


def test_pending_interrupt_zero_provider_on_name_slot(tmp_path):
    sid = "lead-pending"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        with observed_common_route():
            _, _, store, _k0 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="Запишите меня",
                provider=RawFakeProvider(envelope_adult_booking_only()),
                request_id="req-p0",
            )
            pending, fake, _s, _k = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="А сколько стоит All-on-4?",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-p1",
                store=store,
            )
            assert fake.inputs == []
            refs = {item.reply_id for item in pending.response.ui_projection.quick_replies}
            assert LEAD_PENDING_ANSWER_REF in refs
            assert LEAD_PENDING_CONTINUE_NAME_REF in refs
            assert mem_get(sid).get("lead_intent") == "collecting_name"

            continued, fake2, _s2, _k2 = _turn(
                tmp_path=tmp_path,
                sid=sid,
                message="",
                provider=RawFakeProvider("MUST_NOT_CALL"),
                request_id="req-p2",
                lead_ui_ref=LEAD_PENDING_CONTINUE_NAME_REF,
                store=store,
            )
        assert fake2.inputs == []
        assert mem_get(sid).get("lead_intent") == "collecting_name"
        assert "обращать" in continued.response.rendered_text.lower()
