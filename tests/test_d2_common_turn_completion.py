"""CP4 offline completion: one D2 owner state, result replay and PII-free effects."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore, D2RequestIdConflict, D2RequestInProgress
from core.one_call_envelope_protocol import production_envelope_template


PACK = Path(__file__).parent / "fixtures" / "d2_a08"
KEY = SessionKey(client_id="clinic_a", sid="cp4-a08")
NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
MESSAGE = "Нет одного зуба, сколько стоит восстановить?"


def raw_a08() -> str:
    return json.dumps(production_envelope_template(
        commercial_intent="price", primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": "s1",
                "context": "general_information", "topic_id": "implantation", "service_id": None,
                "statement_mode": "question", "situation": {
                    "scope_commitment": "reported", "extent": "one_tooth", "tooth_count": 1,
                    "jaw": "unknown", "continuity": "new",
                },
            }],
        },
    ), ensure_ascii=False)


class Provider:
    def __init__(self, raw: str = raw_a08()) -> None:
        self.raw = raw
        self.calls = 0
        self.inputs = []

    def generate(self, request):
        self.calls += 1
        self.inputs.append(request)
        return self.raw


class Dispatcher:
    def __init__(self, status: str = "sent", *, raises: bool = False) -> None:
        self.status = status
        self.raises = raises
        self.calls: list[str] = []

    def dispatch(self, *, effect_id: str):
        self.calls.append(effect_id)
        if self.raises:
            raise OSError("ambiguous transport outcome")
        return self.status


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP4 offline tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def run(store, provider, *, request_id="req-1", message=MESSAGE, dispatcher=None):
    return run_d2_dialogue_turn(
        session_key=KEY,
        user_message=message,
        request_id=request_id,
        provider=provider,
        clients_root=PACK,
        store=store,
        now=NOW,
        lead_effect_id="lead-1" if dispatcher is not None else None,
        lead_effect_dispatcher=dispatcher,
    )


def test_exact_request_replays_durable_result_without_provider_or_effect(tmp_path):
    provider = Provider()
    dispatcher = Dispatcher()
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        first = run(store, provider, dispatcher=dispatcher)
        replay = run(store, provider, dispatcher=dispatcher)
        saved = store.read(KEY)
    assert provider.calls == 1
    assert dispatcher.calls == ["lead-1"]
    assert first.response == replay.response
    assert replay.idempotent_replay is True
    assert replay.committed_revision == 1
    assert replay.lead_effect.status == "sent"
    assert saved.state.revision == 1


def test_same_request_id_with_other_message_is_rejected_before_provider(tmp_path):
    provider = Provider()
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, provider)
        with pytest.raises(D2RequestIdConflict, match="d2_request_id_payload_conflict"):
            run(store, provider, message="А протезирование?")
    assert provider.calls == 1


def test_contact_is_masked_before_provider_and_absent_from_durable_result(tmp_path):
    phone = "+79991234001"
    email = "cp4.private@example.test"
    provider = Provider()
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        run(store, provider, message=f"{MESSAGE} Мой номер {phone}, почта {email}")
        payloads = [row[0] for row in store._connection.execute(
            "SELECT payload FROM d2_turn_request"
        ).fetchall()]
    assert phone not in provider.inputs[0].user_message
    assert email not in provider.inputs[0].user_message
    assert "[телефон скрыт]" in provider.inputs[0].user_message
    assert all(phone not in payload and email not in payload for payload in payloads)


def test_privacy_only_input_never_calls_provider_or_becomes_final_result(tmp_path):
    provider = Provider()
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        with pytest.raises(ValueError, match="d2_provider_input_privacy_only"):
            run(store, provider, message="+79991234001")
        rows = store._connection.execute("SELECT * FROM d2_turn_request").fetchall()
    assert provider.calls == 0
    assert rows == []


def test_ambiguous_effect_is_recorded_once_and_never_retried_by_replay(tmp_path):
    provider = Provider()
    dispatcher = Dispatcher(raises=True)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        first = run(store, provider, dispatcher=dispatcher)
        replay = run(store, provider, dispatcher=dispatcher)
    assert first.lead_effect.status == "unknown"
    assert replay.lead_effect.status == "unknown"
    assert provider.calls == 1
    assert dispatcher.calls == ["lead-1"]


def test_failed_provider_leaves_no_final_result_and_allows_explicit_retry(tmp_path):
    provider = Provider("not json")
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        with pytest.raises(ValueError):
            run(store, provider)
        assert store._connection.execute("SELECT * FROM d2_turn_request").fetchall() == []
        provider.raw = raw_a08()
        completed = run(store, provider)
    assert completed.idempotent_replay is False
    assert provider.calls == 2


def test_second_serial_request_is_rejected_while_first_is_inflight(tmp_path):
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        store.reserve_request(KEY, request_id="req-1", request_fingerprint="a")
        with pytest.raises(D2RequestInProgress, match="d2_session_request_in_progress"):
            store.reserve_request(KEY, request_id="req-2", request_fingerprint="b")
