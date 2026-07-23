"""Minimal session bridge for target FullContext runtime (S61)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.turn_frame import TurnFrame
from core.target_response_verifier import TargetVerifiedComposedResponse
from session import mem_get

_TARGET_SESSION_KEY = "target_runtime_state"


@dataclass(frozen=True, slots=True)
class TargetRuntimeSessionState:
    last_service_id: str | None
    last_topic: str | None
    last_primary_aspect: str | None
    shown_fact_ids: tuple[str, ...]
    shown_amplifier_refs: tuple[str, ...]
    shown_consultation_value_refs: tuple[str, ...]


def _empty_state() -> TargetRuntimeSessionState:
    return TargetRuntimeSessionState(
        last_service_id=None,
        last_topic=None,
        last_primary_aspect=None,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
    )


def read_target_runtime_session(sid: str) -> TargetRuntimeSessionState:
    st = mem_get(sid)
    raw = st.get(_TARGET_SESSION_KEY)
    if not isinstance(raw, dict):
        return _empty_state()
    return TargetRuntimeSessionState(
        last_service_id=str(raw.get("last_service_id") or "").strip() or None,
        last_topic=str(raw.get("last_topic") or "").strip() or None,
        last_primary_aspect=str(raw.get("last_primary_aspect") or "").strip() or None,
        shown_fact_ids=tuple(str(x).strip() for x in raw.get("shown_fact_ids") or [] if str(x).strip()),
        shown_amplifier_refs=tuple(
            str(x).strip() for x in raw.get("shown_amplifier_refs") or [] if str(x).strip()
        ),
        shown_consultation_value_refs=tuple(
            str(x).strip()
            for x in raw.get("shown_consultation_value_refs") or []
            if str(x).strip()
        ),
    )


def write_target_runtime_session_after_materialized(
    sid: str,
    *,
    turn_frame: TurnFrame,
    verified: TargetVerifiedComposedResponse,
    shown_fact_ids: tuple[str, ...],
    shown_amplifier_refs: tuple[str, ...],
    shown_consultation_value_refs: tuple[str, ...],
) -> None:
    """Persist target continuity only after a successful materialized response."""

    from session import _lock, _persist_unlocked, mem_get, set_last_subject

    _ = verified
    with _lock:
        st = mem_get(sid)
        st[_TARGET_SESSION_KEY] = {
            "last_service_id": turn_frame.service_id,
            "last_topic": turn_frame.topic,
            "last_primary_aspect": turn_frame.primary_aspect,
            "shown_fact_ids": list(shown_fact_ids),
            "shown_amplifier_refs": list(shown_amplifier_refs),
            "shown_consultation_value_refs": list(shown_consultation_value_refs),
        }
        _persist_unlocked(sid, st)

    if turn_frame.service_id:
        set_last_subject(
            sid,
            service_id=turn_frame.service_id,
            topic=str(turn_frame.topic or "unknown"),
            label=turn_frame.service_id,
            last_route=str(turn_frame.intent or "content"),
        )
