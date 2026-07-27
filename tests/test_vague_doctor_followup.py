"""Vague doctor follow-up → doctors_lookup with session service (stage 1C)."""

from __future__ import annotations

import uuid

from doctors_lookup import build_doctors_list_llm_question, doctors_lookup
from session import mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state
from core.target_runtime_session import TargetRuntimeSessionState
from core.target_runtime_turn_frame_hydration import hydrate_target_runtime_turn_frame_from_session
from core.turn_frame_from_raw import build_turn_frame_from_raw


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


def test_vague_doctor_followup_hydrates_from_target_runtime_state():
    sid = f"vague-doc-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
    )
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["doctor"],
            "primary_aspect": "doctor",
            "service_id": None,
            "topic": "doctors",
            "topic_confidence": 0.95,
        },
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"classic", "all_on_4"}),
    )
    session = TargetRuntimeSessionState(
        last_service_id="classic",
        last_topic="implantation",
        last_primary_aspect="price",
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        service_focus_set_at_turn=0,
        session_turn_count=0,
        followups=(),
    )
    hydrated = hydrate_target_runtime_turn_frame_from_session(
        frame,
        user_message="Кто делает?",
        session_state=session,
        allowed_service_ids=frozenset({"classic", "all_on_4"}),
    )
    assert hydrated.service_id == "classic"
    assert hydrated.followup_of == "classic"
