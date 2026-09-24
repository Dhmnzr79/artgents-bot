"""CP5-C2a/C2b: continuation — overview/volume, A07, TTL, A10, B11 person-change."""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
VOLUME = ("one_tooth", "few_teeth", "full_arch", "unknown")
CLASSIC_THREE = (
    "classic.one_tooth.impro",
    "classic.one_tooth.implantium",
    "classic.one_tooth.nobel",
)
WHITENING_OFFER = "professional_whitening.default"
CLARIFY_TEXT = "Могу подсказать по услугам, ценам, врачам или записи. Что вас интересует?"


def _situation(
    *,
    commitment: str = "reported",
    extent: str = "one_tooth",
    tooth_count: int | None = 1,
    continuity: str = "new",
) -> dict[str, object]:
    return {
        "scope_commitment": commitment,
        "extent": extent,
        "tooth_count": tooth_count,
        "jaw": "unknown",
        "continuity": continuity,
    }


def _raw(
    topic: str | None,
    situation: dict[str, object] | None = None,
    *,
    service_id: str | None = None,
    subject_id: str | None = "s1",
    relation: str = "self",
) -> str:
    subjects: list[dict[str, object]] = []
    if subject_id is not None:
        subjects.append(
            {"subject_id": subject_id, "relation": relation, "age_group": "unknown"}
        )
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": subjects,
                "requests": [
                    {
                        "request_id": "r1",
                        "kind": "price",
                        "subject_id": subject_id,
                        "context": "general_information",
                        "topic_id": topic,
                        "service_id": service_id,
                        "statement_mode": "question",
                        "situation": situation,
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
        raise AssertionError("network forbidden in CP5-C2 continuation")

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
        if module == "session":
            assert frame.f_code.co_name == "current_session_client_id", (
                f"unexpected session use on ordinary D2 route: {frame.f_code.co_name}"
            )
            return

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


def _run(
    tmp_path: Path,
    raw: str,
    *,
    key: SessionKey,
    message: str,
    now: datetime = NOW,
    clients: Path | None = None,
    store_path: Path | None = None,
):
    clients = clients if clients is not None else _clients(tmp_path)
    provider = RawFakeProvider(raw)
    db = store_path or (tmp_path / "dialogue.sqlite")
    with observed_common_route() as calls:
        with D2DialogueStore(db) as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=clients,
                store=store,
                now=now,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls, clients


def _offer_ids(outcome) -> tuple[str, ...]:
    block = outcome.response.resolved.d2_price_block
    assert block is not None
    return tuple(row.offer_id for row in block.rows)


def test_a01_overview_volume_hypothesis_does_not_overwrite_correction_does(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2a-a01")
    overview, saved, _, calls, clients = _run(
        tmp_path,
        _raw("implantation"),
        key=key,
        message="Сколько стоит имплантация?",
    )
    decision = overview.response.resolved.d2_price_scope_decision
    assert decision is not None
    assert decision.reason == "overview"
    assert decision.applied_extent is None
    assert [item.extent for item in decision.volume_choices] == list(VOLUME)
    assert [item.reply_id for item in overview.response.ui_projection.quick_replies] == [
        f"volume:implantation:{extent}" for extent in VOLUME
    ]
    assert [item.label for item in overview.response.ui_projection.quick_replies] == [
        "Один зуб", "Несколько зубов", "Вся челюсть", "Не знаю",
    ]
    assert _offer_ids(overview) == CLASSIC_THREE
    assert decision.introduction_text == (
        "Понимаю, хочется сначала сориентироваться по стоимости имплантации. "
        "Вот опубликованные примеры цен."
    )
    assert overview.response.rendered_text.startswith(decision.introduction_text)
    assert "восстановления одного зуба" not in overview.response.rendered_text
    assert "Подскажите" in overview.response.rendered_text
    assert saved.state.situation_state is None
    assert overview.response.resolved.terminal_text is None

    one, saved, _, _, _ = _run(
        tmp_path,
        _raw("implantation", _situation()),
        key=key,
        message="Один зуб",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    assert one.response.resolved.d2_price_scope_decision.applied_extent == "one_tooth"
    assert _offer_ids(one) == CLASSIC_THREE
    assert one.response.ui_projection.quick_replies == ()
    assert saved.state.situation_state is not None
    assert saved.state.situation_state.extent == "one_tooth"
    owner = saved.state.situation_state.situation_owner_id

    hypo, saved, _, _, _ = _run(
        tmp_path,
        _raw(
            "implantation",
            _situation(commitment="hypothetical", extent="few_teeth", tooth_count=3, continuity="same"),
        ),
        key=key,
        message="А если три?",
        now=NOW.replace(minute=2),
        clients=clients,
    )
    assert hypo.response.resolved.d2_price_scope_decision.applied_extent == "few_teeth"
    assert "pterygoid_implants.default" in _offer_ids(hypo)
    assert saved.state.situation_state is not None
    assert saved.state.situation_state.extent == "one_tooth"
    assert saved.state.situation_state.situation_owner_id == owner

    corr, saved, _, _, _ = _run(
        tmp_path,
        _raw(
            "implantation",
            _situation(commitment="correction", extent="few_teeth", tooth_count=3, continuity="same"),
        ),
        key=key,
        message="Нет, всё-таки три",
        now=NOW.replace(minute=3),
        clients=clients,
    )
    assert corr.response.resolved.d2_price_scope_decision.applied_extent == "few_teeth"
    assert saved.state.situation_state is not None
    assert saved.state.situation_state.extent == "few_teeth"
    assert saved.state.situation_state.tooth_count == 3
    assert saved.state.situation_state.situation_owner_id == owner
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


def test_a07_unknown_keeps_overview_without_repeating_volume_or_starting_lead(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2a-a07")
    first, _, _, _, clients = _run(
        tmp_path,
        _raw("prosthetics"),
        key=key,
        message="Сколько стоит протезирование?",
    )
    assert [item.extent for item in first.response.resolved.d2_price_scope_decision.volume_choices] == list(VOLUME)
    assert first.response.resolved.terminal_text is None

    second, saved, _, _, _ = _run(
        tmp_path,
        _raw(
            "prosthetics",
            _situation(commitment="unknown", extent="unknown", tooth_count=None, continuity="same"),
        ),
        key=key,
        message="Не знаю",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    decision = second.response.resolved.d2_price_scope_decision
    assert decision is not None
    assert decision.reason == "overview"
    assert decision.applied_extent is None
    assert decision.volume_choices == ()
    assert decision.unknown_extent_text is None
    assert second.response.ui_projection.quick_replies == ()
    assert [b.button_id for b in second.response.ui_projection.buttons] == ["price"]
    assert second.response.ui_projection.buttons[0].action_kind == "cta"
    assert second.response.resolved.terminal_text is None
    assert saved.state.terminal_state == "none"
    assert saved.state.situation_state is None
    assert "Подскажите" not in second.response.rendered_text
    assert "ориентир" in second.response.rendered_text.lower()
    assert second.response.resolved.d2_price_block is not None
    assert second.response.resolved.d2_price_block.rows


def test_ttl_expiry_drops_carried_situation_on_ambiguous_followup(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2a-ttl")
    first, saved, _, _, clients = _run(
        tmp_path,
        _raw("implantation", _situation()),
        key=key,
        message="Нет одного зуба, сколько стоит?",
    )
    assert saved.state.situation_state is not None
    assert _offer_ids(first) == CLASSIC_THREE

    second, saved, provider, _, _ = _run(
        tmp_path,
        _raw("implantation", _situation(commitment="unknown", extent="unknown", tooth_count=None, continuity="same")),
        key=key,
        message="А сколько стоит?",
        now=NOW + timedelta(minutes=30),
        clients=clients,
    )
    assert provider.inputs[0].context.freshness == "expired"
    assert second.focus.carried_situation is None
    assert second.response.resolved.d2_price_scope_decision.applied_extent is None
    assert second.response.resolved.d2_price_scope_decision.reason == "overview"
    assert saved.state.situation_state is None


def test_a10_empty_session_price_ask_clarifies_without_inventing_price(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2b-a10-empty")
    outcome, saved, _, _, _ = _run(
        tmp_path,
        _raw(None, subject_id=None),
        key=key,
        message="Сколько стоит?",
    )
    assert outcome.focus.action == "clarify_focus"
    assert outcome.response.resolved.route == "CLARIFY"
    assert outcome.response.resolved.d2_price_block is None
    assert outcome.response.resolved.session_delta.clarify_pending is True
    assert saved.state.clarify_pending is True
    assert saved.state.terminal_state == "clarify"
    assert saved.state.situation_state is None
    assert CLARIFY_TEXT in outcome.response.rendered_text
    assert outcome.response.ui_projection.quick_replies


def test_a10_switch_to_whitening_does_not_carry_implant_prices(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2b-a10-switch")
    first, saved, _, _, clients = _run(
        tmp_path,
        _raw("implantation", _situation()),
        key=key,
        message="Нет одного зуба, сколько стоит?",
    )
    assert _offer_ids(first) == CLASSIC_THREE

    second, saved, _, _, _ = _run(
        tmp_path,
        _raw(
            "whitening",
            service_id="professional_whitening",
            subject_id=None,
        ),
        key=key,
        message="А отбеливание сколько?",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    assert second.focus.action == "resolve_topic"
    assert second.focus.carried_situation is None
    assert second.focus.cross_topic_carry is None
    assert _offer_ids(second) == (WHITENING_OFFER,)
    assert all(row.offer_id != CLASSIC_THREE[0] for row in second.response.resolved.d2_price_block.rows)
    assert second.response.resolved.d2_price_scope_decision is None
    assert saved.state.situation_state is None
    assert saved.state.active_topic is not None
    assert saved.state.active_topic.topic_id == "whitening"


def test_b11_other_person_does_not_inherit_prior_situation(tmp_path: Path) -> None:
    key = SessionKey(client_id="demo", sid="c2b-b11-person")
    first, saved, _, _, clients = _run(
        tmp_path,
        _raw("implantation", _situation()),
        key=key,
        message="Нет одного зуба, сколько стоит?",
    )
    owner = saved.state.situation_state.situation_owner_id
    assert _offer_ids(first) == CLASSIC_THREE

    second, saved, _, _, _ = _run(
        tmp_path,
        _raw(
            "implantation",
            _situation(commitment="reported", extent="one_tooth", tooth_count=1, continuity="same"),
            subject_id="s2",
            relation="other",
        ),
        key=key,
        message="А жене тоже один зуб, сколько?",
        now=NOW.replace(minute=1),
        clients=clients,
    )
    assert second.focus.carried_situation is None
    assert second.focus.cross_topic_carry is None
    assert second.response.resolved.d2_price_scope_decision.applied_extent == "one_tooth"
    assert _offer_ids(second) == CLASSIC_THREE
    assert saved.state.situation_state is not None
    assert saved.state.situation_state.extent == "one_tooth"
    assert saved.state.situation_state.situation_owner_id != owner
