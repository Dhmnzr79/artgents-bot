"""Session carry for patient_situation (Slice 3) — fresh scope with age guard."""

from __future__ import annotations

from typing import Any

from contracts.patient_situation import PatientSituationCues, PatientSituationResult
from core.patient_situation import detect_patient_situation
from core.patient_situation_routing import situation_routing_eligible
from core.price_followup import is_vague_price_followup


def _result_from_snapshot(snapshot: dict[str, Any], *, cues: PatientSituationCues) -> PatientSituationResult:
    data = dict(snapshot)
    data["cues"] = cues.model_dump()
    evidence = list(data.get("evidence") or [])
    if "session_carry" not in evidence:
        evidence.append("session_carry")
    data["evidence"] = evidence
    return PatientSituationResult.model_validate(data)


def get_carried_patient_situation(sid: str | None) -> dict[str, Any] | None:
    if not sid:
        return None
    from session import get_last_patient_situation

    return get_last_patient_situation(sid)


def _should_use_session_carry(fresh: PatientSituationResult, q: str) -> bool:
    if not is_vague_price_followup(q):
        return False
    if situation_routing_eligible(fresh) and not fresh.should_clarify:
        return False
    return True


def resolve_patient_situation_for_turn(
    q: str,
    *,
    sid: str | None = None,
) -> tuple[PatientSituationResult, dict[str, Any]]:
    """Detect situation for this turn; optionally carry from session on vague price."""
    fresh = detect_patient_situation(q)
    meta: dict[str, Any] = {
        "patient_situation_carried": False,
        "patient_situation_carry_age": None,
    }
    if not sid or not _should_use_session_carry(fresh, q):
        return fresh, meta

    from session import patient_situation_turn_age

    snap = get_carried_patient_situation(sid)
    if not snap:
        return fresh, meta

    age = patient_situation_turn_age(sid)
    cues = fresh.cues.model_copy()
    if is_vague_price_followup(q):
        cues = cues.model_copy(update={"intent": "price"})
    carried = _result_from_snapshot(snap, cues=cues)
    meta["patient_situation_carried"] = True
    meta["patient_situation_carry_age"] = age
    meta["patient_situation_carried_kind"] = carried.kind
    meta["patient_situation_carried_scope"] = carried.patient_scope
    return carried, meta


def persist_patient_situation_after_turn(
    sid: str | None,
    q: str,
    *,
    carry_meta: dict[str, Any] | None = None,
) -> None:
    """Persist fresh patient situation from q when eligible (not vague carry-only turns)."""
    if not sid:
        return
    carry_meta = carry_meta or {}
    if carry_meta.get("patient_situation_carried"):
        return
    from session import set_last_patient_situation

    fresh = detect_patient_situation(q)
    if situation_routing_eligible(fresh) and not fresh.should_clarify:
        set_last_patient_situation(sid, fresh.model_dump())
