"""Multi-turn e2e: vague attribute follow-up after classic implant context (stage 1B)."""

from __future__ import annotations

import uuid

import pytest

from core.attribute_followup import detect_vague_attribute_kinds
from core.target_runtime_session import read_target_runtime_session
from session import mem_reset


def _classic_context_turn(client, sid: str) -> None:
    resp = client.post(
        "/ask",
        json={
            "q": "сколько стоит поставить один имплант?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert resp.status_code == 200
    runtime = read_target_runtime_session(sid)
    assert runtime.last_service_id == "classic"


@pytest.fixture
def ask_client(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    return app.test_client()


def test_e2e_vague_duration_after_classic(ask_client):
    sid = f"e2e-vague-dur-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    _classic_context_turn(ask_client, sid)

    resp = ask_client.post(
        "/ask",
        json={"q": "А долго?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    meta = body.get("meta") or {}
    plan = meta.get("answer_plan") or {}
    assert plan.get("service_id") == "classic"
    assert "duration" in detect_vague_attribute_kinds("А долго?")
    assert str(meta.get("doc_id") or "").startswith("implantation__service__classic")
    answer = (body.get("answer") or "").lower()
    assert "месяц" in answer or "недел" in answer or "срок" in answer
    assert "all-on-4" not in answer


def test_e2e_vague_pain_after_classic(ask_client):
    sid = f"e2e-vague-pain-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    _classic_context_turn(ask_client, sid)

    resp = ask_client.post(
        "/ask",
        json={"q": "Больно?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    meta = body.get("meta") or {}
    plan = meta.get("answer_plan") or {}
    assert plan.get("service_id") == "classic"
    assert "pain" in detect_vague_attribute_kinds("Больно?")
    answer = (body.get("answer") or "").lower()
    assert "анестез" in answer or "безболезн" in answer or "боль" in answer


def test_e2e_vague_warranty_after_classic(ask_client):
    sid = f"e2e-vague-war-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    _classic_context_turn(ask_client, sid)

    resp = ask_client.post(
        "/ask",
        json={"q": "Гарантия какая?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    meta = body.get("meta") or {}
    plan = meta.get("answer_plan") or {}
    assert plan.get("service_id") == "classic"
    assert "warranty" in detect_vague_attribute_kinds("Гарантия какая?")
    doc_id = str(meta.get("doc_id") or "")
    assert doc_id != "implantation__info__implant_systems"
    answer = (body.get("answer") or "").lower()
    assert "гарант" in answer
