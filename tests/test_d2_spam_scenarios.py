"""CP5-SPAM: D2-040 / D2-071 consecutive garbage on common D2 route.

Fake raw → spam gate / ordinary resolver → D2DialogueStore.
Provider/live/network forbidden on garbage turns. Off-topic polite refuse FUTURE.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from session import is_active_lead_flow, mem_get, mem_reset, session_client_scope
from tests.d1r_envelope_fixtures import envelope_adult_booking_only


NOW = datetime(2026, 9, 22, 21, tzinfo=timezone.utc)
WARN_CORE = "понятный вопрос по стоматологии"
CLOSED_CORE = "Диалог завершён"
PAIN_FEAR_LIVE = (
    "Понимаю этот страх — при имплантации работаем с анестезией, "
    "и обычно всё терпимее, чем кажется заранее."
)
REPO = Path(__file__).resolve().parents[1]


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(REPO / "clients" / "demo", clients / "demo")
    return clients


def _fear_raw() -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={
                "subjects": [],
                "requests": [
                    {
                        "request_id": "r1",
                        "kind": "content",
                        "subject_id": None,
                        "context": "general_information",
                        "topic_id": "implantation",
                        "service_id": "classic",
                        "statement_mode": "question",
                        "situation": None,
                        "content_text": PAIN_FEAR_LIVE,
                        "content_ref": "implantation__faq__pain.md",
                        "content_realization": "model_prose",
                        "content_section_refs": ["a:korotko"],
                        "content_fallback_section_ref": "a:korotko",
                    }
                ],
            },
        ),
        ensure_ascii=False,
    )


def _run(
    tmp_path: Path,
    *,
    message: str,
    raw: str = "",
    key: SessionKey | None = None,
    request_id: str | None = None,
    lead_bridge: bool = False,
):
    sid_key = key or SessionKey(client_id="demo", sid="spam-a")
    root = _clients(tmp_path)
    provider = RawFakeProvider(raw or _fear_raw())
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=sid_key,
            user_message=message,
            provider=provider,
            clients_root=root,
            store=store,
            now=NOW,
            request_id=request_id,
            lead_bridge=lead_bridge,
        )
        saved = store.read(sid_key)
    return outcome, saved, provider


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
    import session as session_mod

    with session_mod._lock:
        for conn in list(session_mod._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_mod._conns.clear()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-SPAM")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@pytest.mark.parametrize(
    "message",
    ("", "!!!!", "asdf", "https://example.com/x"),
)
def test_first_garbage_warns_without_provider_or_ui(tmp_path: Path, message: str) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message=message,
        key=SessionKey(client_id="demo", sid=f"warn-{abs(hash(message)) % 10_000}"),
        request_id=f"warn-{abs(hash(message)) % 10_000}",
    )
    resolved = outcome.response.resolved
    ui = outcome.response.ui_projection
    assert resolved.route == "ADMIN"
    assert resolved.mode == "spam_warn"
    assert WARN_CORE in outcome.response.rendered_text
    assert resolved.d2_price_block is None
    assert resolved.information_blocks == ()
    assert resolved.promo_blocks == ()
    assert ui.quick_replies == ()
    assert ui.buttons == ()
    assert ui.contact is None
    assert ui.video is None
    assert saved is not None
    assert saved.state.terminal_state == "spam_warn"
    assert provider.inputs == []


def test_second_garbage_closes_and_third_stays_closed(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="spam-close")
    first, saved1, p1 = _run(tmp_path, message="!!!!", key=key, request_id="c1")
    assert first.response.resolved.mode == "spam_warn"
    assert saved1 is not None and saved1.state.terminal_state == "spam_warn"
    assert p1.inputs == []

    second, saved2, p2 = _run(tmp_path, message="asdf", key=key, request_id="c2")
    assert second.response.resolved.mode == "spam_closed"
    assert CLOSED_CORE in second.response.rendered_text
    assert second.response.ui_projection.buttons == ()
    assert saved2 is not None and saved2.state.terminal_state == "spam_closed"
    assert p2.inputs == []

    third, saved3, p3 = _run(
        tmp_path,
        message="Сколько стоит имплант?",
        key=key,
        request_id="c3",
    )
    assert third.response.resolved.mode == "spam_closed"
    assert CLOSED_CORE in third.response.rendered_text
    assert saved3 is not None and saved3.state.terminal_state == "spam_closed"
    assert p3.inputs == []


def test_dental_after_warn_resets_and_answers(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="spam-reset")
    warn, saved1, p1 = _run(tmp_path, message="!!!!", key=key, request_id="r1")
    assert warn.response.resolved.mode == "spam_warn"
    assert saved1 is not None and saved1.state.terminal_state == "spam_warn"
    assert p1.inputs == []

    answer, saved2, p2 = _run(
        tmp_path,
        message="Боюсь, что будет больно при имплантации",
        key=key,
        request_id="r2",
        raw=_fear_raw(),
    )
    assert answer.response.resolved.route == "ANSWER"
    assert PAIN_FEAR_LIVE in answer.response.rendered_text
    assert WARN_CORE not in answer.response.rendered_text
    assert saved2 is not None and saved2.state.terminal_state == "none"
    assert len(p2.inputs) == 1


def test_active_lead_not_stolen_by_garbage(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="spam-lead")
    with session_client_scope("demo"):
        mem_reset(key.sid, client_id="demo")
        booking, _, provider = _run(
            tmp_path,
            message="Хочу записаться",
            key=key,
            request_id="l1",
            raw=envelope_adult_booking_only(),
            lead_bridge=True,
        )
        assert booking.response.resolved.route == "ANSWER"
        assert is_active_lead_flow(mem_get(key.sid))
        assert len(provider.inputs) == 1

        garbage, saved, p2 = _run(
            tmp_path,
            message="!!!!",
            key=key,
            request_id="l2",
            lead_bridge=True,
        )
        # Active lead pre-provider owns the turn; spam warn must not replace it.
        assert garbage.response.resolved.mode != "spam_warn"
        assert garbage.response.resolved.mode != "spam_closed"
        assert is_active_lead_flow(mem_get(key.sid))
        assert saved is not None
        assert saved.state.terminal_state != "spam_warn"
        assert p2.inputs == []
