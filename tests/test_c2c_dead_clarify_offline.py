"""C2c-dead-clarify: no persistent pending_clarify session state; target clarify/defer preserved."""

from __future__ import annotations

import importlib
import uuid

import config
import session
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response
from core.turn_frame_from_raw import build_turn_frame_from_raw
from session import _fresh_defaults, mem_get, mem_reset, record_last_bot_payload


def _envelope(**overrides: object) -> TargetTurnFramePolicyEnvelope:
    payload: dict[str, object] = {
        "boundary_decision": "none",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation", "doctors"),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": ("free_implant_consult",),
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
        "min_topic_confidence": 0.5,
        "min_service_confidence": 0.0,
        "min_intent_confidence": 0.0,
    }
    payload.update(overrides)
    return TargetTurnFramePolicyEnvelope.model_validate(payload)


def test_fresh_session_has_no_pending_clarify_key() -> None:
    defaults = _fresh_defaults()
    assert "pending_clarify" not in defaults


def test_pending_clarify_session_api_removed() -> None:
    for name in (
        "get_pending_clarify",
        "set_pending_clarify",
        "clear_pending_clarify",
        "increment_pending_clarify_reask",
        "pending_clarify_age",
    ):
        assert not hasattr(session, name), name


def test_clarify_state_on_flag_removed_from_config() -> None:
    assert not hasattr(config, "CLARIFY_STATE_ON")


def test_record_last_bot_payload_does_not_persist_pending_clarify() -> None:
    sid = f"dead-clarify-{uuid.uuid4().hex}"
    mem_reset(sid)
    record_last_bot_payload(
        sid,
        {
            "answer": "Обычная коронка или на имплант?",
            "meta": {
                "clarify": {
                    "question": "Обычная коронка или на имплант?",
                    "option_service_ids": ["crown_metal", "crown_zirconia"],
                    "reask_count": 0,
                }
            },
        },
    )
    st = mem_get(sid)
    assert "pending_clarify" not in st


def test_deserialize_strips_legacy_pending_clarify() -> None:
    sid = f"dead-clarify-load-{uuid.uuid4().hex}"
    mem_reset(sid)
    st = mem_get(sid)
    st["pending_clarify"] = {
        "question": "legacy",
        "option_service_ids": ["a", "b"],
        "asked_at_turn": 1,
    }
    session._persist_unlocked(sid, st)

    reloaded = mem_get(sid)
    assert "pending_clarify" not in reloaded


def test_target_terminal_clarify_still_dispatched() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": "all_on_4",
            "topic": "implantation",
            "topic_confidence": 0.9,
            "needs_clarify": True,
        },
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    result = dispatch_target_turn_frame_response(frame, _envelope())
    assert result.kind == "terminal"
    assert result.terminal_mode == "clarify"
    assert result.spec.response_mode == "clarify"


def test_target_terminal_defer_still_dispatched() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    result = dispatch_target_turn_frame_response(frame, _envelope())
    assert result.kind == "terminal"
    assert result.terminal_mode == "defer"
    assert result.spec.response_mode == "defer"


def test_config_module_reloads_without_clarify_state_on() -> None:
    importlib.reload(config)
    assert not hasattr(config, "CLARIFY_STATE_ON")
