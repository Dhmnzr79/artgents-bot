"""Unit tests for deterministic answer slot assembly (stage 2)."""
from __future__ import annotations

import uuid

import pytest

from core.answer_slots import (
    assemble_answer_slots,
    doc_meta_has_consult_value,
    is_commercial_intent,
    is_promo_blocked,
)
from session import get_topic_state, mem_reset, record_answer_slots_shown


@pytest.fixture
def sid():
    s = f"test-slots-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


def test_doc_meta_has_consult_value_doc_and_h3():
    meta = {
        "consult_value": "На консультации врач скажет.",
        "h3_overrides": {"sroki": {"consult_value": "H3 consult"}},
    }
    assert doc_meta_has_consult_value(meta)
    assert doc_meta_has_consult_value({"h3_overrides": {"sroki": {"consult_value": "x"}}}, h3_id="sroki")
    assert not doc_meta_has_consult_value({"clinic_note": "note only"})


def test_consult_value_suppresses_consult_nudge_planning(sid):
    from chunk_responder import _planned_consult_nudge_for_chunk

    meta = {"consult_value": "На консультации врач скажет."}
    kind = _planned_consult_nudge_for_chunk(
        sid=sid,
        route="retrieval_chunk",
        meta=meta,
        chunk={"h3_id": None},
        topic_state={"covered_h3_ids": [], "doc_turn_count": 0},
        client_id="demo",
    )
    assert kind is None


def test_promo_only_on_commercial_intent():
    meta = {
        "doc_id": "implantation__service__classic",
        "promo_note": {"text": "Акция до конца месяца.", "active_until": "2026-12-31"},
        "clinic_note": "Клиника.",
    }
    text, telemetry = assemble_answer_slots(
        meta=meta,
        h3_id=None,
        q="расскажите про имплантацию",
        route="retrieval_chunk",
        topic_state={},
        lead_context=False,
    )
    assert "Акция" not in text
    assert telemetry.suppressed.get("promo_note") == "not_commercial_intent"
    assert is_commercial_intent("есть рассрочка?", "retrieval_chunk")
    assert is_commercial_intent("есть акции на All-on-4?", "retrieval_chunk")


def test_text_marketing_limit_prefers_eligible_promo():
    meta = {
        "doc_id": "implantation__service__all_on_4",
        "clinic_note": "Клиника планирует по КТ.",
        "consult_value": "На консультации врач скажет.",
        "promo_note": {"text": "Акция до конца месяца.", "active_until": "2026-12-31"},
    }
    text, telemetry = assemble_answer_slots(
        meta=meta,
        h3_id=None,
        q="есть акции на All-on-4?",
        route="retrieval_chunk",
        topic_state={},
        lead_context=False,
    )

    assert "Акция" in text
    assert "КТ" not in text
    assert telemetry.appended == ["promo_note"]
    assert telemetry.suppressed.get("clinic_note") == "text_ingredient_limit"
    assert telemetry.suppressed.get("consult_value") == "text_ingredient_limit"


def test_promo_blocked_on_pain_doc():
    meta = {
        "doc_id": "implantation__faq__pain",
        "subtopic": "pain",
        "promo_note": {"text": "Акция.", "active_until": "2026-12-31"},
    }
    assert is_promo_blocked(q="боюсь боли", route="retrieval_chunk", meta=meta, lead_context=False)
    _, telemetry = assemble_answer_slots(
        meta=meta,
        h3_id=None,
        q="есть рассрочка?",
        route="retrieval_chunk",
        topic_state={},
        lead_context=False,
    )
    assert "promo_note" not in telemetry.appended
    assert telemetry.suppressed.get("promo_note") == "blocked_intent_or_topic"


def test_cooldown_per_doc(sid):
    doc_id = "implantation__service__classic"
    meta = {
        "doc_id": doc_id,
        "clinic_note": "Клиника планирует по КТ.",
        "consult_value": "На консультации врач скажет.",
    }
    text1, t1 = assemble_answer_slots(
        meta=meta,
        h3_id=None,
        q="классическая имплантация",
        route="retrieval_chunk",
        topic_state={"doc_turn_count": 0, "slots_last_turn": {}},
        lead_context=False,
    )
    assert "консультац" in text1
    assert t1.appended == ["consult_value"]
    assert t1.suppressed.get("clinic_note") == "text_ingredient_limit"
    record_answer_slots_shown(sid, doc_id, slot_keys=list(t1.appended), turn=1)

    tstate = get_topic_state(sid, doc_id)
    text2, t2 = assemble_answer_slots(
        meta=meta,
        h3_id=None,
        q="ещё вопрос про классику",
        route="retrieval_chunk",
        topic_state=tstate,
        lead_context=False,
    )
    assert "КТ" in text2
    assert t2.appended == ["clinic_note"]
    assert t2.skipped_cooldown == ["consult_value"]
