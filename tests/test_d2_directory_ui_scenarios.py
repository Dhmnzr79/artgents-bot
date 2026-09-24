"""CP5-DIR B: contacts tenant + CTA free-label gate on common D2 route.

Fake raw → contact/directory builders → D2DialogueStore.
Provider/live/network forbidden. Not full B12 UI matrix.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_contacts_cta import free_consult_fact_active, resolve_d2_lead_cta_button
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.d2_tenant_snapshot import load_d2_tenant_snapshot
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 22, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[1]
DEMO_PHONE = "+7 (495) 128-47-60"
DEMO_ADDRESS = "г. Москва, ул. Тверская, 12"


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


def _contact_raw(*, contact_fields: list[str]) -> str:
    request = {
        "request_id": "r1",
        "kind": "contact",
        "subject_id": None,
        "context": "general_information",
        "topic_id": None,
        "service_id": None,
        "statement_mode": "question",
        "situation": None,
        "contact_fields": contact_fields,
        "content_text": None,
        "content_ref": None,
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


def _content_raw(*, topic_id=None, service_id=None, content_ref=None, content_text=None) -> str:
    if content_text is None:
        # The current D2 contract publishes a live FullContext answer.  This
        # helper tests its CTA/UI projection, so its fake model response must
        # contain the nonempty prose required of a valid content turn.
        content_text = "Расскажу о подходящих вариантах и отвечу на вопросы по материалам клиники."
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
        raise AssertionError("network forbidden in CP5-DIR-B")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


def test_contact_phone_from_tenant_policies(tmp_path: Path) -> None:
    outcome, saved, provider = _run(
        tmp_path,
        message="Какой у вас телефон?",
        raw=_contact_raw(contact_fields=["contact_phone"]),
        key=SessionKey(client_id="demo", sid="dirb-phone"),
        request_id="c1",
    )
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert DEMO_PHONE in text
    assert outcome.response.resolved.route == "ANSWER"
    assert outcome.response.resolved.mode == "standard"
    assert ui.contact is not None
    assert ui.contact.phone == DEMO_PHONE
    assert any(b.action_kind == "contact" for b in ui.buttons)
    assert saved is not None
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1


def test_contact_address_from_tenant_policies(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Где вы находитесь?",
        raw=_contact_raw(contact_fields=["contact_address"]),
        key=SessionKey(client_id="demo", sid="dirb-addr"),
        request_id="c2",
    )
    text = outcome.response.rendered_text
    assert DEMO_ADDRESS in text
    assert DEMO_PHONE not in text
    assert len(provider.inputs) == 1


def test_location_question_includes_address_when_model_selects_phone(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Где вы находитесь?",
        raw=_contact_raw(contact_fields=["contact_phone"]),
        key=SessionKey(client_id="demo", sid="dirb-location-phone"),
        request_id="c2-location",
    )
    assert DEMO_ADDRESS in outcome.response.rendered_text
    assert DEMO_PHONE in outcome.response.rendered_text
    assert len(provider.inputs) == 1


def test_general_contacts_include_address_and_phone(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Как с вами связаться и где вы находитесь?",
        raw=_contact_raw(contact_fields=["contacts"]),
        key=SessionKey(client_id="demo", sid="dirb-contacts"),
        request_id="c-general",
    )
    assert DEMO_ADDRESS in outcome.response.rendered_text
    assert DEMO_PHONE in outcome.response.rendered_text
    assert len(provider.inputs) == 1


def test_doctors_list_attaches_free_cta_when_fact_active(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Кто ставит импланты?",
        raw=_content_raw(topic_id="doctors", service_id="classic"),
        key=SessionKey(client_id="demo", sid="dirb-cta"),
        request_id="c3",
    )
    ui = outcome.response.ui_projection
    cta = next((b for b in ui.buttons if b.action_kind == "cta"), None)
    assert cta is not None
    assert "бесплатн" in cta.label.casefold()
    assert outcome.response.resolved.d2_price_block is None
    assert len(provider.inputs) == 1


def test_free_cta_label_requires_date_window(tmp_path: Path) -> None:
    """After active_until, free wording must not appear (real fact dates, no mock)."""
    root = _clients(tmp_path)
    snapshot = load_d2_tenant_snapshot("demo", clients_root=root)
    assert free_consult_fact_active(snapshot, as_of=date(2026, 12, 31)) is True
    assert free_consult_fact_active(snapshot, as_of=date(2027, 1, 1)) is False
    expired = resolve_d2_lead_cta_button(
        snapshot,
        as_of=date(2027, 1, 1),
        cta_key="doctor",
        prefer_free_consult=True,
    )
    assert expired is not None
    assert "бесплатн" not in expired.label.casefold()
    assert expired.label == "Записаться к врачу"
    active = resolve_d2_lead_cta_button(
        snapshot,
        as_of=date(2026, 9, 22),
        cta_key="doctor",
        prefer_free_consult=True,
    )
    assert active is not None
    assert "бесплатн" in active.label.casefold()


def test_doctors_list_drops_free_cta_after_fact_expires(tmp_path: Path) -> None:
    """Integration: same doctors turn after active_until uses non-free CTA label."""
    root = _clients(tmp_path)
    provider = RawFakeProvider(_content_raw(topic_id="doctors", service_id="classic"))
    key = SessionKey(client_id="demo", sid="dirb-cta-exp")
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=key,
            user_message="Кто ставит импланты?",
            provider=provider,
            clients_root=root,
            store=store,
            now=datetime(2027, 1, 2, 12, tzinfo=timezone.utc),
            request_id="c3b",
        )
    cta = next(
        (b for b in outcome.response.ui_projection.buttons if b.action_kind == "cta"),
        None,
    )
    assert cta is not None
    assert "бесплатн" not in cta.label.casefold()
    assert cta.label == "Записаться к врачу"
    assert len(provider.inputs) == 1


def test_medical_terminal_still_has_no_cta(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Сейчас очень больно после лечения",
        raw=_admin_raw(),
        key=SessionKey(client_id="demo", sid="dirb-term"),
        request_id="c4",
    )
    assert outcome.response.resolved.mode == "medical_terminal"
    assert outcome.response.ui_projection.buttons == ()
    assert outcome.response.ui_projection.contact is None
    assert all(b.action_kind != "cta" for b in outcome.response.ui_projection.buttons)
    assert len(provider.inputs) == 1


def test_protocols_still_have_no_cta(tmp_path: Path) -> None:
    outcome, _, provider = _run(
        tmp_path,
        message="Какие протоколы имплантации есть?",
        raw=_content_raw(topic_id="implantation"),
        key=SessionKey(client_id="demo", sid="dirb-proto"),
        request_id="c5",
    )
    assert all(b.action_kind != "cta" for b in outcome.response.ui_projection.buttons)
    assert len(provider.inputs) == 1
