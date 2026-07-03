"""Per-turn booking_intent cache (Level 1)."""

from __future__ import annotations

import re

import pytest

from policy import booking_intent


@pytest.fixture()
def flask_app():
    from app import app

    return app


def test_booking_intent_cached_per_request(flask_app, monkeypatch):
    calls: list[str] = []

    def _fake_llm(msg, *, client_id, sid):
        calls.append(msg)
        return True

    monkeypatch.setattr("policy.classify_booking_wants_appointment", _fake_llm)
    monkeypatch.setattr("policy.BOOKING_INTENT_RE", re.compile(r"$^"))

    from logging_setup import make_request_context

    with flask_app.test_request_context():
        from flask import request

        request.ctx = make_request_context()
        q = "хотел бы узнать про запись на приём к врачу"
        assert booking_intent(q, sid="s1", client_id="demo") is True
        assert booking_intent(q, sid="s1", client_id="demo") is True
        assert len(calls) == 1
