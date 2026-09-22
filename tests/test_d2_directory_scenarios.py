"""CP5-DIR A: doctors / protocols directory on common D2 route.

Fake raw → directory builders → D2DialogueStore.
Provider/live/network forbidden on directory turns. Contacts/CTA FUTURE (slice B).
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
from core.d2_directory import classify_d2_directory_request
from core.one_call_envelope_protocol import production_envelope_template
from types import SimpleNamespace


NOW = datetime(2026, 9, 22, 22, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[1]
ORLOV = "Орлов Никита Владимирович"
VOLKOV = "Волков Александр Сергеевич"
KUZNETSOV = "Кузнецов Дмитрий Андреевич"


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


def _content_raw(*, topic_id=None, service_id=None, content_ref=None, content_text=None) -> str:
    if content_ref is not None and content_text is None:
        content_text = "Карточка врача."
    request = {
        "request_id": "r1",
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "topic_id": topic_id,
        "service_id": service_id,
        "statement_mode": "question",
        "situation": None,
        "content_text": content_text,
        "content_ref": content_ref,
        "content_realization": "authored",
        "content_section_refs": [],
        "content_fallback_section_ref": None,
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


def _run(tmp_path: Path, *, message: str, raw: str, key: SessionKey, request_id: str):
    root = _clients(tmp_path)
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


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-DIR")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


def test_doctors_for_implantation_service_from_catalog(tmp_path: Path) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message="Кто ставит импланты?",
        raw=_content_raw(topic_id="doctors", service_id="classic"),
        key=SessionKey(client_id="demo", sid="dir-docs"),
        request_id="d1",
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert outcome.response.resolved.route == "ANSWER"
    assert ORLOV in text
    assert VOLKOV in text
    assert KUZNETSOV in text
    assert "лучш" not in text.lower()
    assert outcome.response.resolved.d2_price_block is None
    assert ui.buttons == ()
    assert ui.contact is None
    assert saved is not None
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1


def test_doctor_profile_card_without_ranking(tmp_path: Path) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message="Расскажите про Орлова",
        raw=_content_raw(content_ref="doctors__doctor__orlov.md", topic_id="doctors"),
        key=SessionKey(client_id="demo", sid="dir-orlov"),
        request_id="d2",
    )
    text = outcome.response.rendered_text
    assert ORLOV in text
    assert "имплантолог" in text.lower()
    assert "16" in text
    assert VOLKOV not in text
    assert outcome.response.ui_projection.quick_replies == ()
    assert outcome.response.resolved.d2_price_block is None
    assert saved is not None
    assert len(provider.inputs) == 1


def test_protocols_list_excludes_supporting_and_has_no_price(tmp_path: Path) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message="Какие протоколы имплантации есть?",
        raw=_content_raw(topic_id="implantation"),
        key=SessionKey(client_id="demo", sid="dir-proto"),
        request_id="d3",
    )
    text = outcome.response.rendered_text.lower()
    ui = outcome.response.ui_projection
    block = outcome.response.resolved.service_options_block
    assert block is not None
    option_ids = {item.service_id for item in block.options}
    assert "tomography" not in option_ids
    assert "sinus_lift" not in option_ids
    assert "bone_graft" not in option_ids
    assert any(sid in option_ids for sid in ("classic", "one_stage", "all_on_4", "all_on_6"))
    assert "томограф" not in text
    assert "компьютерн" not in text
    assert "синус" not in text
    assert "костн" not in text
    assert all(
        not any(bad in qr.label.lower() for bad in ("кт", "синус", "костн"))
        for qr in ui.quick_replies
    )
    assert outcome.response.resolved.d2_price_block is None
    assert len(block.options) <= 3
    assert len(ui.quick_replies) <= 2
    assert ui.buttons == ()
    assert saved is not None
    assert len(provider.inputs) == 1


def test_medical_terminal_still_beats_directory_shape(tmp_path: Path) -> None:
    """Contrast: pain/complaint ADMIN path unchanged (B03)."""
    outcome, _, provider = _run(
        tmp_path,
        message="Сейчас очень больно после лечения",
        raw=_admin_raw(),
        key=SessionKey(client_id="demo", sid="dir-term"),
        request_id="d4",
    )
    assert outcome.response.resolved.mode == "medical_terminal"
    assert outcome.response.ui_projection.buttons == ()
    assert "Орлов" not in outcome.response.rendered_text
    assert len(provider.inputs) == 1


def test_protocols_classifier_only_allowlisted_topics() -> None:
    """Boundary: bare clinic/other topic is not protocols (external Checker P1)."""
    implantation = SimpleNamespace(
        kind="content",
        topic_id="implantation",
        service_id=None,
        content_ref=None,
    )
    clinic = SimpleNamespace(
        kind="content",
        topic_id="clinic",
        service_id=None,
        content_ref=None,
    )
    assert (
        classify_d2_directory_request(
            part=implantation, envelope_commercial_intent="none"
        )
        == "protocols"
    )
    assert (
        classify_d2_directory_request(part=clinic, envelope_commercial_intent="none")
        is None
    )


def test_clinic_topic_not_hijacked_as_protocols(tmp_path: Path) -> None:
    """Integration: clinic-shaped content does not return the protocols gap stub."""
    with pytest.raises(ValueError, match="d2_experiment_"):
        _run(
            tmp_path,
            message="Расскажите про клинику",
            raw=_content_raw(topic_id="clinic"),
            key=SessionKey(client_id="demo", sid="dir-clinic"),
            request_id="d5",
        )
