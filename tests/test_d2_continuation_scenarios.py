"""CP5-C2a: direction overview, volume choice, hypothesis/correction, A07, TTL."""

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


def _raw(topic: str, situation: dict[str, object] | None = None) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [
                    {"subject_id": "s1", "relation": "self", "age_group": "unknown"}
                ],
                "requests": [
                    {
                        "request_id": "r1",
                        "kind": "price",
                        "subject_id": "s1",
                        "context": "general_information",
                        "topic_id": topic,
                        "service_id": None,
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
        raise AssertionError("network forbidden in CP5-C2a")

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
        assert module != "session", "second ordinary memory called"

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
    assert "Понимаю" in overview.response.rendered_text
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
