"""Vague doctor follow-up → doctors_lookup with session service (stage 1C)."""

from __future__ import annotations

import uuid

import pytest

from contracts.decision_frame import DecisionFrame
from contracts.dialog_focus import DialogFocusDecision
from core.routing_loader import THRESHOLDS
from doctors_lookup import build_doctors_list_llm_question, doctors_lookup
from source_routing import _vague_doctor_session_hints, route_source
from session import mem_add_user, mem_get, mem_reset, set_last_subject


def _content_frame(*, topic: str = "implantation") -> DecisionFrame:
    return DecisionFrame(
        route_intent="content",
        service_topic=topic,
        service_id=None,
        query_mode="specific",
        confidence={"intent": 0.9, "topic": 0.9, "service": 0.0, "query_mode": 0.9},
        needs_clarification=False,
    )


def test_vague_kto_iz_vrachej_doctors_lookup_generic():
    hit = doctors_lookup("Кто из врачей?", client_id="demo")
    assert hit is not None
    assert hit.get("routing") in ("overview", "cards", "doc")


def test_vague_kto_delает_uses_session_service():
    hit = doctors_lookup(
        "Кто делает?",
        client_id="demo",
        session_service_id="classic",
        session_topic="implantation",
    )
    assert hit is not None
    assert hit.get("matched_service_id") == "classic"
    assert hit.get("routing") in ("cards", "doc", "overview")


def test_route_source_vague_doctor_with_session():
    sid = f"vague-doc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
    )
    sr = route_source(
        "Кто делает?",
        sid=sid,
        client_id="demo",
        decision=_content_frame(),
        app_intent="content",
    )
    assert sr.source == "doctor"
    assert sr.service_id is None
    assert sr.match_method == "doctors_lookup"
    payload = sr.payload.get("doctor") if isinstance(sr.payload, dict) else None
    assert isinstance(payload, dict)
    assert payload.get("matched_service_id") == "classic"


def test_route_source_vague_doctor_uses_dialog_focus_ctx_without_session_subject():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": DialogFocusDecision(
                focus_service_id="classic",
                focus_topic="implantation",
                focus_label="Классическая имплантация",
                focus_turn_age=0,
                attribute="doctor",
                explicit_topic_change=False,
                resolved_service_id="classic",
                source="last_subject",
                used_llm=False,
                confidence=0.8,
                reason="test",
            ).model_dump()
        }
        sr = route_source(
            "Кто делает?",
            sid="doctor-dialog-focus",
            client_id="demo",
            decision=_content_frame(),
            app_intent="content",
        )
    payload = sr.payload.get("doctor") if isinstance(sr.payload, dict) else None
    assert sr.source == "doctor"
    assert isinstance(payload, dict)
    assert payload.get("matched_service_id") == "classic"


def test_doctors_list_prompt_leaves_consult_invite_to_policy():
    prompt = build_doctors_list_llm_question(
        user_question="Кто делает имплантацию?",
        client_id="demo",
    )

    assert "Не добавляй отдельное приглашение на консультацию" in prompt


def test_vague_doctor_session_hints_ignore_stale_subject():
    sid = f"stale-doc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
    )
    for _ in range(int(THRESHOLDS.follow_up.max_subject_turn_age) + 1):
        mem_add_user(sid, "другой вопрос")
    assert int(mem_get(sid).get("subject_turn_age") or 0) > int(
        THRESHOLDS.follow_up.max_subject_turn_age
    )

    svc, topic = _vague_doctor_session_hints(sid)
    assert svc is None
    assert topic is None

    sr = route_source(
        "Кто делает?",
        sid=sid,
        client_id="demo",
        decision=_content_frame(),
        app_intent="content",
    )
    payload = sr.payload.get("doctor") if isinstance(sr.payload, dict) else None
    if isinstance(payload, dict):
        assert payload.get("matched_service_id") != "classic"


@pytest.fixture
def ask_client(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    return app.test_client()


def test_e2e_vague_doctor_after_classic(ask_client):
    sid = f"e2e-vague-doc-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    resp = ask_client.post(
        "/ask",
        json={
            "q": "сколько стоит поставить один имплант?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200

    resp = ask_client.post(
        "/ask",
        json={"q": "Кто делает?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    answer = body.get("answer") or ""
    assert len(answer) > 40
    low = answer.lower()
    assert "врач" in low or "имплант" in low or "волков" in low
    plan = (body.get("meta") or {}).get("answer_plan") or {}
    assert plan.get("service_id") == "classic"
