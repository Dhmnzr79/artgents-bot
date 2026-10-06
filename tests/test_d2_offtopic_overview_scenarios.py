"""CP5-OTOV: off-topic refuse + doctors overview content on common D2 route.

Off-topic: typed kind=other empty → ui.yaml offtopic; not spam.
Doctors overview: content_ref=doctors__doctor__overview.md via content lookup.
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
import yaml

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.d2_directory import classify_d2_directory_request
from core.d2_offtopic import is_d2_offtopic_envelope
from core.one_call_envelope_protocol import production_envelope_template
from types import SimpleNamespace


NOW = datetime(2026, 9, 22, 17, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[1]
OFFTOPIC_CORE = "вопросам клиники"
OFFTOPIC_TENANT_MARK = "DEMO-OFFTOPIC-TENANT-MARK-42"
OVERVIEW_SNIPPET = "команда ведущих специалистов"
OVERVIEW_LIVE = (
    "В клинике работает команда ведущих специалистов — "
    "от терапии до имплантации и протезирования."
)
WARN_CORE = "понятный вопрос по стоматологии"


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


def _offtopic_raw() -> str:
    request = {
        "request_id": "r1",
        "kind": "other",
        "subject_id": None,
        "context": "general_information",
        "topic_id": None,
        "service_id": None,
        "statement_mode": "question",
        "situation": None,
        "content_text": None,
        "content_ref": None,
        "content_realization": "authored",
        "content_section_refs": [],
        "content_fallback_section_ref": None,
        "policy_ids": [],
        "contact_fields": [],
    }
    return json.dumps(
        production_envelope_template(
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={"subjects": [], "requests": [request]},
        ),
        ensure_ascii=False,
    )


def _overview_raw() -> str:
    request = {
        "request_id": "r1",
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "topic_id": "doctors",
        "service_id": None,
        "statement_mode": "question",
        "situation": None,
        "content_text": OVERVIEW_LIVE,
        "content_ref": "doctors__doctor__overview.md",
        "content_realization": "model_prose",
        "content_section_refs": ["a:korotko"],
        "content_fallback_section_ref": "a:korotko",
    }
    return json.dumps(
        production_envelope_template(
            commercial_intent="none",
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={"subjects": [], "requests": [request]},
        ),
        ensure_ascii=False,
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


def _run(
    tmp_path: Path,
    *,
    message: str,
    raw: str,
    key: SessionKey,
    request_id: str,
    clients: Path | None = None,
):
    root = clients or _clients(tmp_path)
    provider = RawFakeProvider(raw)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=key,
            user_message=message,
            provider=provider,
            clients_root=root,
            store=store,
            now=NOW,
            request_id=request_id,
        )
        saved = store.read(key)
    return outcome, saved, provider


def _patch_offtopic_answer(clients: Path, answer: str) -> None:
    path = clients / "demo" / "ui.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    fallback = payload.setdefault("fallback_menu", {})
    assert isinstance(fallback, dict)
    offtopic = fallback.setdefault("offtopic", {})
    assert isinstance(offtopic, dict)
    offtopic["answer"] = answer
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-OTOV")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


def test_offtopic_classifier_accepts_empty_other() -> None:
    part = SimpleNamespace(
        kind="other",
        service_id=None,
        topic_id=None,
        content_ref=None,
        content_text=None,
        policy_ids=(),
        contact_fields=(),
        content_section_refs=(),
        content_fallback_section_ref=None,
    )
    understanding = SimpleNamespace(requests=(part,))
    envelope = SimpleNamespace(
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        request_understanding=understanding,
    )
    assert is_d2_offtopic_envelope(envelope) is True
    dental = SimpleNamespace(
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        request_understanding=SimpleNamespace(
            requests=(
                SimpleNamespace(
                    kind="content",
                    service_id=None,
                    topic_id="doctors",
                    content_ref="doctors__doctor__overview.md",
                    content_text="x",
                    policy_ids=(),
                    contact_fields=(),
                    content_section_refs=("a:korotko",),
                    content_fallback_section_ref="a:korotko",
                ),
            )
        ),
    )
    assert is_d2_offtopic_envelope(dental) is False


def test_offtopic_polite_refuse_from_ui_yaml(tmp_path: Path) -> None:
    """Tenant ui.yaml offtopic must win over code default (unique marker)."""
    clients = _clients(tmp_path)
    tenant_answer = (
        f"Только стоматология и запись. {OFFTOPIC_TENANT_MARK} "
        "Другие темы не обсуждаю."
    )
    _patch_offtopic_answer(clients, tenant_answer)
    outcome, saved, provider = _run(
        tmp_path,
        message="Какой курс доллара сегодня?",
        raw=_offtopic_raw(),
        key=SessionKey(client_id="demo", sid="otov-off"),
        request_id="o1",
        clients=clients,
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert OFFTOPIC_TENANT_MARK in text
    assert "Другие темы не обсуждаю" in text
    # Code default must not be the sole source: unique tenant mark proves ui.yaml.
    assert "подскажу по вашему вопросу в этом контексте" not in text
    assert outcome.response.resolved.route == "ANSWER"
    assert outcome.response.resolved.mode == "standard"
    assert ui.buttons == ()
    assert ui.contact is None
    assert outcome.response.resolved.d2_price_block is None
    assert saved is not None
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1


def test_garbage_still_spam_not_offtopic(tmp_path: Path) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message="asdf",
        raw=_offtopic_raw(),
        key=SessionKey(client_id="demo", sid="otov-spam"),
        request_id="o2",
    )
    assert WARN_CORE in outcome.response.rendered_text
    assert outcome.response.resolved.mode == "spam_warn"
    assert OFFTOPIC_CORE not in outcome.response.rendered_text
    assert saved.state.terminal_state == "spam_warn"
    assert len(provider.inputs) == 0


def test_medical_terminal_not_offtopic(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Сейчас очень больно после лечения",
        raw=_admin_raw(),
        key=SessionKey(client_id="demo", sid="otov-med"),
        request_id="o3",
    )
    assert outcome.response.resolved.mode == "medical_terminal"
    assert OFFTOPIC_CORE not in outcome.response.rendered_text
    assert len(provider.inputs) == 1


def test_doctors_overview_is_content_not_directory_card(tmp_path: Path) -> None:
    part = SimpleNamespace(
        kind="content",
        topic_id="doctors",
        service_id=None,
        content_ref="doctors__doctor__overview.md",
    )
    assert (
        classify_d2_directory_request(part=part, envelope_commercial_intent="none")
        is None
    )

    outcome, saved, provider = _run(
        tmp_path,
        message="Расскажите про ваших врачей",
        raw=_overview_raw(),
        key=SessionKey(client_id="demo", sid="otov-docs"),
        request_id="o4",
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert OVERVIEW_LIVE in text or OVERVIEW_SNIPPET in text
    assert "лучш" not in text.lower()
    assert "Орлов" not in text
    assert outcome.response.resolved.route == "ANSWER"
    assert outcome.response.resolved.d2_price_block is None
    assert outcome.response.resolved.ui_plan.source_content_ref == (
        "doctors__doctor__overview.md"
    )
    assert [b.button_id for b in ui.buttons if b.action_kind == "cta"] == ["booking"]
    assert saved is not None
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1
