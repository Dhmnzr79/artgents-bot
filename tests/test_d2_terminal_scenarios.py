"""CP5-TERM: assembled B03 medical/complaint terminal through common D2 route.

Fake raw → production parser → tenant snapshot → manual_contact stub →
D2DialogueStore. Provider/live/network forbidden. Decisions: D2-023, D2-012,
D2-042 (terminal beats other parts). Lead A12 / spam hard-stop are FUTURE SCOPE.
"""

from __future__ import annotations

import json
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
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 19, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="term-b03")
STUB_CORE = "Такой вопрос лучше решить напрямую с клиникой"
STUB_CALL = "позвоните нам"
STUB_URGENT = "Если ситуация срочная"
PHONE = "+7 (495) 128-47-60"
PAIN_FEAR_LIVE = (
    "Понимаю этот страх — при имплантации работаем с анестезией, "
    "и обычно всё терпимее, чем кажется заранее."
)


def _admin_raw() -> str:
    return json.dumps(
        production_envelope_template(
            route="ADMIN",
            patient_text=None,
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            request_understanding={"subjects": [], "requests": []},
        ),
        ensure_ascii=False,
    )


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


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-TERM")

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
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_",
            "core.target_composer",
            "core.target_runtime_",
            "core.response_plan_composer_executor",
            "core.target_session_selection",
            "core.one_call_runtime",
            "core.one_call_presentation",
            "core.response_plan_session",
            "core.target_offer_projection",
            "core.target_service_selection",
            "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        assert module != "core.target_marketing_selector", "legacy marketing selector called"
        # CP5-LEAD privacy probe: only the exact client-binding read is allowed.
        # mem_get / lead mutations must not appear on ordinary terminal turns.
        if module == "session":
            assert frame.f_code.co_name == "current_session_client_id", (
                f"unexpected session use on terminal route: {frame.f_code.co_name}"
            )
            return
        assert module != "session", "second ordinary memory called"
        assert module != "orchestration.sales_one_plus_ask_turn", "legacy ask turn called"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def _run(tmp_path: Path, raw: str, *, message: str, key: SessionKey = KEY):
    root = _clients(tmp_path)
    provider = RawFakeProvider(raw)
    with observed_common_route() as calls:
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=root,
                store=store,
                now=NOW,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls


@pytest.mark.parametrize(
    "message",
    (
        "Сейчас очень больно после лечения",
        "Идёт кровь из десны",
        "Хочу оставить жалобу на врача",
        "Дайте директора",
    ),
)
def test_b03_problem_cases_share_one_manual_contact_stub(tmp_path: Path, message: str) -> None:
    outcome, saved, provider, calls = _run(
        tmp_path,
        _admin_raw(),
        message=message,
        key=SessionKey(client_id="demo", sid=f"term-{abs(hash(message)) % 10_000}"),
    )

    resolved = outcome.response.resolved
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert resolved.route == "ADMIN"
    assert resolved.mode == "medical_terminal"
    assert resolved.terminal_text is not None
    assert STUB_CORE in text
    assert STUB_CALL in text
    assert STUB_URGENT in text
    assert PHONE in text
    assert resolved.d2_price_block is None
    assert resolved.information_blocks == ()
    assert resolved.promo_blocks == ()
    assert ui.quick_replies == ()
    assert ui.video is None
    assert ui.buttons == ()
    assert ui.contact is None
    assert saved is not None
    assert saved.state.terminal_state == "medical_terminal"
    assert len(provider.inputs) == 1
    assert any(module == "core.d2_dialogue" for module, _ in calls)


def test_future_pain_fear_stays_ordinary_content(tmp_path: Path) -> None:
    """Contrast: future fear is not ADMIN — ordinary pain.md path (A03)."""
    outcome, saved, _, _ = _run(
        tmp_path,
        _fear_raw(),
        message="Боюсь, что будет больно при имплантации",
        key=SessionKey(client_id="demo", sid="term-fear"),
    )

    resolved = outcome.response.resolved
    assert resolved.route == "ANSWER"
    assert PAIN_FEAR_LIVE in outcome.response.rendered_text
    assert STUB_CORE not in outcome.response.rendered_text
    assert saved is not None
    assert saved.state.terminal_state == "none"
