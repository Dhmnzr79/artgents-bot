"""CP5-B12: CTA source/default/free + secondary cap + forbid surfaces.

Assembles existing common-route UI rules into one offline proof set.
Not full widget click-wire. Off-topic refuse / doctors overview = next tails.
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


NOW = datetime(2026, 9, 22, 16, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[1]
PAIN_LIVE = (
    "Понимаю этот страх — при имплантации работаем с анестезией, "
    "и обычно всё терпимее, чем кажется заранее."
)
PAIN_VIDEO = "pain-doctor-explains"
PAIN_FOLLOW = "implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut"
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


def _cta_buttons(ui) -> list:
    return [b for b in ui.buttons if b.action_kind == "cta"]


def _content_pain_raw() -> str:
    return json.dumps({"outcome": "dialogue", "blocks": [{
        "kind": "content", "request_id": "r1", "target": {"type": "service", "id": "classic"},
        "content_text": PAIN_LIVE, "content_ref": "implantation__faq__pain.md",
        "content_realization": "model_prose", "content_section_refs": ["a:korotko"],
        "content_fallback_section_ref": "a:korotko"}]}, ensure_ascii=False)


def _price_raw(topic: str | None, volume: dict[str, object] | None = None, *,
               service_id: str | None = None, subject_id: str | None = "s1") -> str:
    operation = {"kind": "price", "request_id": "r1", "volume": volume}
    if service_id or topic:
        operation["target"] = {"type": "service", "id": service_id} if service_id else {"type": "topic", "id": topic}
    if not service_id and not topic:
        operation["clarification"] = {"missing": "service", "choices": ["classic", "all_on_4"]}
    return json.dumps({"outcome": "dialogue", "blocks": [operation]}, ensure_ascii=False)


def _doctors_raw() -> str:
    return json.dumps({"outcome": "dialogue", "blocks": [{
        "kind": "doctors", "request_id": "r1", "target": {"type": "service", "id": "classic"}}]}, ensure_ascii=False)


def _admin_raw() -> str:
    return json.dumps({"outcome": "admin"})


def _run(
    tmp_path: Path,
    *,
    message: str,
    raw: str,
    key: SessionKey,
    request_id: str,
    now: datetime = NOW,
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
            now=now,
            request_id=request_id,
        )
        saved = store.read(key)
    return outcome, saved, provider, root


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-B12")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


def test_source_cta_from_md_with_secondary_cap(tmp_path: Path) -> None:
    """B12 source: md cta_key=consult → tone label; secondary ≤2 (video counts)."""
    outcome, saved, provider, _ = _run(
        tmp_path,
        message="Я боюсь боли при имплантации",
        raw=_content_pain_raw(),
        key=SessionKey(client_id="demo", sid="b12-source"),
        request_id="b12-1",
    )
    ui = outcome.response.ui_projection
    ctas = _cta_buttons(ui)
    assert len(ctas) == 1
    assert ctas[0].button_id == "consult"
    assert "бесплатн" not in ctas[0].label.casefold()
    assert ui.video is not None and ui.video.video_id == PAIN_VIDEO
    assert len(ui.quick_replies) <= 1
    assert len(ui.quick_replies) + (1 if ui.video else 0) <= 2
    assert [item.reply_id for item in ui.quick_replies] == [PAIN_FOLLOW]
    assert saved is not None
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1


def test_default_price_cta_after_unknown_extent(tmp_path: Path) -> None:
    """B12 default: overview volume QR, then «Не знаю» → one price CTA, no volume QR."""
    key = SessionKey(client_id="demo", sid="b12-default")
    volume = ("one_tooth", "full_arch", "unknown")
    overview, _, _, clients = _run(
        tmp_path,
        message="Сколько стоит имплантация?",
        raw=_price_raw("implantation", None),
        key=key,
        request_id="b12-2a",
    )
    decision = overview.response.resolved.d2_price_scope_decision
    assert decision is not None
    assert decision.reason == "overview"
    assert [item.extent for item in decision.volume_choices] == list(volume)
    assert [item.reply_id for item in overview.response.ui_projection.quick_replies] == [
        f"volume:implantation:{extent}" for extent in volume
    ]
    assert [item.label for item in overview.response.ui_projection.quick_replies] == [
        "Один зуб",
        "Вся челюсть",
        "Пока не знаю",
    ]

    unknown, saved, provider, _ = _run(
        tmp_path,
        message="Не знаю",
        raw=_price_raw(
            "implantation",
            {
                "extent": "unknown",
                "tooth_count": None,
                "jaw": "unknown",
                },
        ),
        key=key,
        request_id="b12-2b",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    after = unknown.response.resolved.d2_price_scope_decision
    assert after is not None
    assert after.reason == "overview"
    assert after.applied_extent is None
    assert after.volume_choices == ()
    ctas = _cta_buttons(unknown.response.ui_projection)
    assert [b.button_id for b in ctas] == ["default_consult"]
    assert ctas[0].label == "Записаться на консультацию"
    assert {q.reply_id for q in unknown.response.ui_projection.quick_replies} == {
        "price_detail:includes", "price_detail:stages",
    }
    assert "бесплатн" not in ctas[0].label.casefold()
    assert saved is not None
    assert len(provider.inputs) == 1


def test_free_cta_on_doctors_only_while_fact_window_open(tmp_path: Path) -> None:
    """B12 free: doctors list uses free book_label inside window; not after."""
    active, _, provider_a, clients = _run(
        tmp_path,
        message="Кто ставит импланты?",
        raw=_doctors_raw(),
        key=SessionKey(client_id="demo", sid="b12-free-ok"),
        request_id="b12-3a",
        now=NOW,
    )
    active_cta = _cta_buttons(active.response.ui_projection)
    assert len(active_cta) == 1
    assert "бесплатн" in active_cta[0].label.casefold()
    assert len(provider_a.inputs) == 1

    expired, _, provider_b, _ = _run(
        tmp_path,
        message="Кто ставит импланты?",
        raw=_doctors_raw(),
        key=SessionKey(client_id="demo", sid="b12-free-exp"),
        request_id="b12-3b",
        now=datetime(2027, 1, 2, 12, tzinfo=timezone.utc),
        clients=clients,
    )
    expired_cta = _cta_buttons(expired.response.ui_projection)
    assert len(expired_cta) == 1
    assert "бесплатн" not in expired_cta[0].label.casefold()
    assert expired_cta[0].label == "Записаться к врачу"
    assert len(provider_b.inputs) == 1


def test_pure_clarify_has_menu_but_no_lead_cta(tmp_path: Path) -> None:
    """B12 forbid: empty-session price ask → CLARIFY + guided QR, zero CTA."""
    outcome, saved, provider, _ = _run(
        tmp_path,
        message="Сколько стоит?",
        raw=_price_raw(None, None, subject_id=None),
        key=SessionKey(client_id="demo", sid="b12-clarify"),
        request_id="b12-4",
    )
    assert outcome.response.resolved.route == "ANSWER"
    assert outcome.response.resolved.d2_price_block is None
    assert outcome.response.ui_projection.quick_replies
    assert _cta_buttons(outcome.response.ui_projection) == []
    assert saved is not None
    assert saved.state.clarify_task.clarification.missing == "service"
    assert saved.state.clarify_task.kind == "price"
    assert saved.state.clarify_task.clarification.choices == ("classic", "all_on_4")
    assert saved.state.terminal_state == "none"
    assert len(provider.inputs) == 1


@pytest.mark.parametrize("tail_kind", ["price", "content", "contacts"])
def test_clarification_cta_preserves_independent_parts(tmp_path: Path, tail_kind: str) -> None:
    raw = json.loads(_price_raw(None, None, subject_id=None))
    tails = {
        "price": {"kind": "price", "request_id": "r2", "target": {"type": "service", "id": "professional_whitening"}},
        "content": {"kind": "content", "request_id": "r2", "target": {"type": "service", "id": "classic"},
                    "content_text": PAIN_LIVE, "content_realization": "model_prose"},
        "contacts": {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_phone"]},
    }
    raw["blocks"].append(tails[tail_kind])
    outcome, saved, _, _ = _run(
        tmp_path, message="Сколько стоит? И расскажите о клинике.",
        raw=json.dumps(raw, ensure_ascii=False),
        key=SessionKey(client_id="demo", sid=f"b12-mixed-{tail_kind}"), request_id="b12-mixed",
    )
    assert saved.state.clarify_task.clarification.missing == "service"
    parts = outcome.response.resolved.d2_request_parts
    if tail_kind == "price":
        assert parts[1].status == "deferred"
        assert _cta_buttons(outcome.response.ui_projection) == []
    else:
        assert parts[1].status == "answered"
        assert _cta_buttons(outcome.response.ui_projection)
    if tail_kind == "content":
        assert PAIN_LIVE in outcome.response.rendered_text
    if tail_kind == "contacts":
        assert any(button.action_kind != "cta" for button in outcome.response.ui_projection.buttons)


def test_medical_terminal_and_spam_have_no_cta(tmp_path: Path) -> None:
    """B12 forbid: medical stub and spam warn never attach lead CTA."""
    medical, _, provider_m, clients = _run(
        tmp_path,
        message="Сейчас очень больно после лечения",
        raw=_admin_raw(),
        key=SessionKey(client_id="demo", sid="b12-med"),
        request_id="b12-5a",
    )
    assert medical.response.resolved.mode == "medical_terminal"
    assert _cta_buttons(medical.response.ui_projection) == []
    assert medical.response.ui_projection.buttons == ()
    assert len(provider_m.inputs) == 1

    spam, saved, provider_s, _ = _run(
        tmp_path,
        message="asdf",
        raw=_content_pain_raw(),
        key=SessionKey(client_id="demo", sid="b12-spam"),
        request_id="b12-5b",
        clients=clients,
    )
    # Garbage short-circuits before provider.
    assert WARN_CORE in spam.response.rendered_text
    assert _cta_buttons(spam.response.ui_projection) == []
    assert saved is not None
    assert saved.state.terminal_state == "spam_warn"
    assert len(provider_s.inputs) == 0
