"""Vague doctor follow-up → doctors_lookup with session service (stage 1C)."""

from __future__ import annotations

import uuid

import pytest

from doctors_lookup import build_doctors_list_llm_question, doctors_lookup
from session import mem_reset


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


def test_doctors_list_prompt_leaves_consult_invite_to_policy():
    prompt = build_doctors_list_llm_question(
        user_question="Кто делает имплантацию?",
        client_id="demo",
    )

    assert "Не добавляй отдельное приглашение на консультацию" in prompt


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
