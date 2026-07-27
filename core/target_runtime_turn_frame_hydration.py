"""Hydrate target TurnFrame service continuity from runtime session (S62 correction)."""

from __future__ import annotations

from contracts.turn_frame import FieldMeta, TurnFrame
from core.attribute_followup import (
    detect_vague_attribute_kinds,
    is_vague_attribute_followup_any,
)
from core.target_generic_fullcontext_content import should_skip_session_service_hydration
from core.target_runtime_session import TargetRuntimeSessionState

_SESSION_FOLLOWUP_ASPECTS = frozenset({"price", "payment"})


def _field_meta(*, provenance: str) -> FieldMeta:
    return FieldMeta(confidence=1.0, provenance=provenance, status="valid")


def _is_session_contextual_followup(
    turn_frame: TurnFrame,
    user_message: str,
) -> bool:
    if not is_vague_attribute_followup_any(user_message):
        return False
    kinds = set(detect_vague_attribute_kinds(user_message))
    if "doctor" in kinds or turn_frame.topic == "doctors":
        return True
    if kinds & {"price", "payment"}:
        return True
    aspect = str(turn_frame.primary_aspect or "").strip()
    if aspect in _SESSION_FOLLOWUP_ASPECTS:
        return True
    if any(item in _SESSION_FOLLOWUP_ASPECTS for item in turn_frame.aspects):
        return True
    return False


def hydrate_target_runtime_turn_frame_from_session(
    turn_frame: TurnFrame,
    *,
    user_message: str,
    session_state: TargetRuntimeSessionState,
    allowed_service_ids: frozenset[str],
) -> TurnFrame:
    """Restore service continuity for contextual follow-ups when shadow frame lost it."""

    if turn_frame.service_id is not None:
        return turn_frame
    if should_skip_session_service_hydration(turn_frame, user_message=user_message):
        return turn_frame
    if not _is_session_contextual_followup(turn_frame, user_message):
        return turn_frame

    if not session_state.is_service_focus_fresh():
        return turn_frame
    last_service_id = str(session_state.last_service_id or "").strip()
    if not last_service_id or last_service_id not in allowed_service_ids:
        return turn_frame

    provenance = "target_runtime_session.last_service_id"
    service_meta = _field_meta(provenance=provenance)
    follow_meta = _field_meta(provenance=provenance)
    return turn_frame.model_copy(
        update={
            "service_id": last_service_id,
            "follow_up": True,
            "followup_of": last_service_id,
            "field_meta": turn_frame.field_meta.model_copy(
                update={
                    "service_id": service_meta,
                    "follow_up": follow_meta,
                    "followup_of": follow_meta,
                }
            ),
        }
    )
