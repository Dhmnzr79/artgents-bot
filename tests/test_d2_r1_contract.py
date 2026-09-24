"""R1 contract slices through the production parser, D2 gate and store."""

from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


class RawProvider:
    def __init__(self, payload: dict) -> None:
        self.raw = json.dumps(payload, ensure_ascii=False)
        self.calls = 0

    def generate(self, _request) -> str:
        self.calls += 1
        return self.raw


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_LOG_DIR", str(tmp_path))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("R1 offline test attempted a network call")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def _run(tmp_path: Path, payload: dict, *, sid: str):
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    provider = RawProvider(payload)
    key = SessionKey(client_id="demo", sid=sid)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        turn = run_d2_dialogue_turn(
            session_key=key,
            user_message="Нейтральный тестовый вопрос",
            provider=provider,
            clients_root=root,
            store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        saved = store.read(key)
    return turn, saved, provider


def _other(*, content_text: str | None) -> dict:
    return production_envelope_template(
        commercial_intent="none",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "other", "subject_id": None,
                "context": "general_information", "content_text": content_text,
            }],
        },
    )


def test_other_with_prose_gets_authored_help_not_price_gate(tmp_path: Path) -> None:
    turn, saved, provider = _run(tmp_path, _other(content_text="Здравствуйте!"), sid="r1-other")
    assert turn.response.resolved.route == "ANSWER"
    assert turn.response.rendered_text.strip()
    assert saved is not None and saved.state.revision == 1
    assert provider.calls == 1


def test_typed_clarify_commits_question_and_service_choices(tmp_path: Path) -> None:
    payload = production_envelope_template(
        route="CLARIFY",
        patient_text="Какой вид имплантации вас интересует?",
        clarify_axis="service",
        clarify_service_options=["all_on_4", "all_on_6"],
        commercial_intent="none",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "content", "subject_id": None,
                "context": "general_information", "content_text": None,
            }],
        },
    )
    turn, saved, provider = _run(tmp_path, payload, sid="r1-clarify")
    assert turn.response.resolved.route == "CLARIFY"
    assert "Какую услугу" in turn.response.rendered_text
    assert {item.reply_id for item in turn.response.ui_projection.quick_replies} == {
        "service:all_on_4", "service:all_on_6",
    }
    assert saved is not None and saved.state.revision == 1
    assert saved.state.shown_options_snapshot is not None
    assert saved.state.shown_options_snapshot.topic_id == "implantation"
    assert saved.state.shown_options_snapshot.service_ids == ("all_on_4", "all_on_6")
    assert provider.calls == 1


@pytest.mark.parametrize("next_topic", ["implantation", "prosthetics"])
def test_service_clarify_replaces_stale_topic_before_next_explicit_price(
    tmp_path: Path,
    next_topic: str,
) -> None:
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    key = SessionKey(client_id="demo", sid=f"r1-topic-conflict-{next_topic}")

    def price(topic_id: str, *, reported_situation: bool = False) -> dict:
        return production_envelope_template(
            commercial_intent="price", primary_price_request_id="r1",
            request_understanding={
                "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
                "requests": [{
                    "request_id": "r1", "kind": "price", "subject_id": "s1",
                    "context": "general_information", "topic_id": topic_id,
                    "service_id": None,
                    "situation": (
                        {
                            "scope_commitment": "reported", "extent": "one_tooth",
                            "tooth_count": 1, "jaw": "unknown", "continuity": "new",
                        } if reported_situation else None
                    ),
                }],
            },
        )

    clarify = production_envelope_template(
        route="CLARIFY", patient_text="Маркер модели не публикуется",
        clarify_axis="service", clarify_service_options=["all_on_4", "all_on_6"],
        commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_text": None,
        }]},
    )
    with D2DialogueStore(tmp_path / f"{next_topic}.sqlite") as store:
        run_d2_dialogue_turn(
            session_key=key, user_message="Сколько стоит протезирование?",
            provider=RawProvider(price("prosthetics", reported_situation=True)), clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        clarification = run_d2_dialogue_turn(
            session_key=key, user_message="А какие варианты?", provider=RawProvider(clarify),
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        after_clarify = store.read(key)
        next_turn = run_d2_dialogue_turn(
            session_key=key, user_message="Сколько стоит?", provider=RawProvider(price(next_topic)),
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        saved = store.read(key)
    assert clarification.response.resolved.route == "CLARIFY"
    assert after_clarify is not None
    assert after_clarify.state.active_topic is not None
    assert after_clarify.state.active_topic.topic_id == "implantation"
    assert after_clarify.state.active_service is None
    assert after_clarify.state.situation_state is None
    assert next_turn.response.rendered_text.strip()
    assert saved is not None and saved.state.revision == 3
    assert saved.state.active_topic is not None
    assert saved.state.active_topic.topic_id == next_topic


def test_service_click_clears_prior_situation_after_mixed_topic_clarify(tmp_path: Path) -> None:
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    key = SessionKey(client_id="demo", sid="r1-mixed-topic-click")

    def price(topic_id: str, *, situation: dict | None = None) -> dict:
        return production_envelope_template(
            commercial_intent="price", primary_price_request_id="r1",
            request_understanding={
                "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
                "requests": [{
                    "request_id": "r1", "kind": "price", "subject_id": "s1",
                    "context": "general_information", "topic_id": topic_id,
                    "service_id": None, "situation": situation,
                }],
            },
        )

    reported = {
        "scope_commitment": "reported", "extent": "one_tooth", "tooth_count": 1,
        "jaw": "unknown", "continuity": "new",
    }
    mixed = RawProvider(production_envelope_template(
        route="CLARIFY", patient_text="Не публиковать",
        clarify_axis="service",
        clarify_service_options=["all_on_4", "implant_supported_prosthetics"],
        commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_text": None,
        }]},
    ))
    after_click = RawProvider(production_envelope_template(
        route="CLARIFY", patient_text="Не публиковать",
        clarify_axis="extent", commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_text": None,
        }]},
    ))
    with D2DialogueStore(tmp_path / "mixed.sqlite") as store:
        run_d2_dialogue_turn(
            session_key=key, user_message="Протезирование", provider=RawProvider(price("prosthetics", situation=reported)),
            clients_root=root, store=store, now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        clarification = run_d2_dialogue_turn(
            session_key=key, user_message="Что выбрать?", provider=mixed,
            clients_root=root, store=store, now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        clicked = run_d2_dialogue_turn(
            session_key=key, user_message="", lead_ui_ref="service:all_on_4",
            ui_revision=clarification.committed_revision, provider=after_click,
            clients_root=root, store=store, now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        after = store.read(key)
        final = run_d2_dialogue_turn(
            session_key=key, user_message="Цена имплантации", provider=RawProvider(price("implantation")),
            clients_root=root, store=store, now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
    assert clicked.response.resolved.route == "CLARIFY"
    assert after is not None and after.state.situation_state is None
    assert after.state.active_topic is not None and after.state.active_topic.topic_id == "implantation"
    assert final.response.rendered_text.strip()


def test_clarify_service_click_uses_authorized_ref_and_retained_topic(tmp_path: Path) -> None:
    root = tmp_path / "clients"
    shutil.copytree(Path("clients/demo"), root / "demo")
    key = SessionKey(client_id="demo", sid="r1-service-click")
    first = RawProvider(production_envelope_template(
        route="CLARIFY", patient_text="Непроверенный текст модели",
        clarify_axis="service", clarify_service_options=["all_on_4", "all_on_6"],
        commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_text": None,
        }]},
    ))
    second = RawProvider(production_envelope_template(
        route="CLARIFY", patient_text="Цена составляет произвольную сумму",
        clarify_axis="extent", commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "service_id": None,
            "topic_id": None, "content_text": None,
        }]},
    ))
    third = RawProvider(production_envelope_template(
        commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "service_id": "all_on_4",
            "topic_id": None, "content_ref": "implantation__service__all_on_4.md",
            "content_text": "Смысловой текст не является источником.",
        }]},
    ))
    wrong_service = RawProvider(production_envelope_template(
        commercial_intent="none",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "service_id": "all_on_6",
            "topic_id": None, "content_ref": "implantation__service__all_on_4.md",
            "content_text": "Смысловой текст не является источником.",
        }]},
    ))
    fourth = RawProvider(production_envelope_template(
        commercial_intent="price", primary_price_request_id="r1",
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": "s1",
                "context": "general_information", "service_id": None,
                "topic_id": "prosthetics", "situation": None,
            }],
        },
    ))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        clarify = run_d2_dialogue_turn(
            session_key=key, user_message="Какой вариант?", provider=first,
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        assert "Непроверенный текст" not in clarify.response.rendered_text
        with pytest.raises(ValueError, match="d2_ui_service_selection_mismatch"):
            run_d2_dialogue_turn(
                session_key=key, user_message="", lead_ui_ref="service:all_on_4",
                ui_revision=clarify.committed_revision, provider=wrong_service,
                clients_root=root, store=store,
                now=datetime(2026, 9, 23, tzinfo=timezone.utc),
            )
        assert store.read(key).state.revision == 1
        click = run_d2_dialogue_turn(
            session_key=key, user_message="", lead_ui_ref="service:all_on_4",
            ui_revision=clarify.committed_revision, provider=second,
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        after_click = store.read(key)
        answer = run_d2_dialogue_turn(
            session_key=key, user_message="Вся челюсть", provider=third,
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        switched = run_d2_dialogue_turn(
            session_key=key, user_message="Сколько стоит протезирование?", provider=fourth,
            clients_root=root, store=store,
            now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )
        saved = store.read(key)
    assert click.response.resolved.route == "CLARIFY"
    assert "произвольную сумму" not in click.response.rendered_text
    assert after_click is not None and after_click.state.active_service is not None
    assert after_click.state.active_service.service_id == "all_on_4"
    assert answer.response.resolved.route == "ANSWER"
    assert answer.response.rendered_text.strip()
    assert switched.response.rendered_text.strip()
    assert saved is not None and saved.state.revision == 4
    assert saved.state.active_topic is not None and saved.state.active_topic.topic_id == "prosthetics"
    assert saved.state.active_service is None
    assert first.calls == second.calls == third.calls == fourth.calls == wrong_service.calls == 1
