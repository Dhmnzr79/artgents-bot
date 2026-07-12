from __future__ import annotations

import json

import pytest

from contracts.turn_plan import TurnPlan
from core.emotion_policy import (
    build_theme_reassurance_instruction,
    is_emotion_reassurance_eligible,
)
from core.medzone_personal import is_medzone_personal
from core.turn_planner_llm import publish_turn_plan


def test_is_medzone_personal_t7():
    assert is_medzone_personal("У меня пародонтоз, можно ли мне имплант?") is True


def test_fear_pain_not_medzone_personal():
    assert is_medzone_personal("Боюсь, что имплантация будет больно") is False


def test_emotion_reassurance_blocked_for_medzone_personal():
    assert (
        is_emotion_reassurance_eligible(
            q="У меня пародонтоз, можно ли мне имплант?",
            emotion="fear",
        )
        is False
    )


def test_emotion_reassurance_eligible_for_fear():
    assert (
        is_emotion_reassurance_eligible(
            q="Боюсь, что врачи неопытные",
            emotion="fear",
        )
        is True
    )


def test_doctors_theme_instruction_excludes_pain_bleed():
    text = build_theme_reassurance_instruction(
        topic="doctors",
        aspects=["overview"],
        emotion="fear",
        first_touch=True,
    )
    assert "врач" in text.lower() or "опыт" in text.lower()
    assert "Не упоминай боль" in text


def test_fullctx_composer_emotion_fear_doctors_theme_hint(monkeypatch):
    from core.knowledge_base import assemble_client_knowledge_base
    from llm import generate_answer_from_packet_fullctx
    from session import mem_reset

    monkeypatch.setattr("llm.COMPOSER_ON", True)
    monkeypatch.setattr("llm.FULLCTX_ON", True)
    monkeypatch.setattr(
        "core.answer_planner.answer_plan_from_ctx",
        lambda: __import__(
            "contracts.answer_plan", fromlist=["AnswerPlan"]
        ).AnswerPlan(
            aspects=["overview"],
            primary_aspect="overview",
            topic="doctors",
        ),
    )

    app = pytest.importorskip("flask").Flask(__name__)
    sid = "p1-empathy-doctors"
    mem_reset(sid)
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]

        class _Msg:
            content = json.dumps({"answer": "ok"})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("llm.chat_completions_create", _fake_create)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["overview"],
                service_id=None,
                followup_of=None,
                needs_clarify=False,
                emotion="fear",
            )
        )
        answer, meta = generate_answer_from_packet_fullctx(
            "Боюсь, что врачи неопытные",
            assemble_client_knowledge_base("demo"),
            ["overview"],
            [],
            {"client_id": "demo"},
            sid,
        )

    user = captured["messages"][1]["content"]
    assert answer == "ok"
    assert meta.get("empathy_used") is True
    assert "Не упоминай боль" in user
    assert "первое касание" in user.lower()


def test_fullctx_composer_medzone_personal_no_empathy(monkeypatch):
    from core.knowledge_base import assemble_client_knowledge_base
    from llm import generate_answer_from_packet_fullctx
    from session import mem_reset

    monkeypatch.setattr("llm.COMPOSER_ON", True)
    monkeypatch.setattr("llm.FULLCTX_ON", True)
    monkeypatch.setattr(
        "core.answer_planner.answer_plan_from_ctx",
        lambda: __import__(
            "contracts.answer_plan", fromlist=["AnswerPlan"]
        ).AnswerPlan(
            aspects=["overview"],
            primary_aspect="overview",
            topic="implantation",
        ),
    )

    app = pytest.importorskip("flask").Flask(__name__)
    sid = "p1-medzone-no-empathy"
    mem_reset(sid)
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]

        class _Msg:
            content = json.dumps({"answer": "ok"})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("llm.chat_completions_create", _fake_create)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["overview"],
                service_id=None,
                followup_of=None,
                needs_clarify=False,
                emotion="fear",
            )
        )
        answer, meta = generate_answer_from_packet_fullctx(
            "У меня пародонтоз, можно ли мне имплант?",
            assemble_client_knowledge_base("demo"),
            ["overview"],
            [],
            {"client_id": "demo"},
            sid,
        )

    user = captured["messages"][1]["content"]
    assert answer == "ok"
    assert meta.get("empathy_used") is False
    assert "первое касание" not in user.lower()
