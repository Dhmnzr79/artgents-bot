"""Session carry for patient_situation (Slice 3) — fresh scope with age guard."""

from __future__ import annotations

from typing import Any

from contracts.patient_situation import PatientSituationCues, PatientSituationKind, PatientSituationResult
from core.patient_situation import detect_patient_situation
from core.patient_situation_routing import situation_routing_eligible
from core.price_followup import is_vague_price_followup


_PLANNER_SCOPE_BY_KIND: dict[PatientSituationKind, str] = {
    "one_tooth_missing": "one_tooth",
    "few_teeth_missing": "few_teeth",
    "full_arch_missing": "full_jaw",
    "upper_jaw_missing_or_complex": "upper_jaw",
    "existing_implant_prosthetic_stage": "prosthetic_stage",
    "extraction_then_implant": "one_tooth",
    "bone_deficit_or_grafting": "adjunct",
    "urgent_problem": "urgent",
    "generic_implant_interest": "generic",
    "unknown": "unknown",
}

_PLANNER_EXTENT_BY_SCOPE = {
    "one_tooth": "one_tooth",
    "few_teeth": "few_teeth",
    "full_jaw": "full_arch",
    "upper_jaw": "full_arch",
}


def _result_from_turn_plan(kind: PatientSituationKind, *, q: str) -> PatientSituationResult:
    scope = _PLANNER_SCOPE_BY_KIND.get(kind, "unknown")
    problem = "unknown"
    if kind in {
        "one_tooth_missing",
        "few_teeth_missing",
        "full_arch_missing",
        "upper_jaw_missing_or_complex",
        "extraction_then_implant",
    }:
        problem = "missing_teeth"
    elif kind == "bone_deficit_or_grafting":
        problem = "bone_deficit"
    elif kind == "existing_implant_prosthetic_stage":
        problem = "existing_implant"
    elif kind == "urgent_problem":
        problem = "urgent"
    elif kind == "generic_implant_interest":
        problem = "generic_implant_interest"
    modifiers: list[str] = []
    if kind == "bone_deficit_or_grafting":
        modifiers.append("bone_deficit")
    if kind == "extraction_then_implant":
        modifiers.append("extracted")
    if kind == "existing_implant_prosthetic_stage":
        modifiers.append("existing_implant")
    if kind == "urgent_problem":
        modifiers.append("urgent")
    jaw = "upper" if kind == "upper_jaw_missing_or_complex" else "unknown"
    extent = _PLANNER_EXTENT_BY_SCOPE.get(scope, "unknown")
    intent = "price" if is_vague_price_followup(q) else "unknown"
    return PatientSituationResult(
        kind=kind,
        confidence=0.9 if kind != "unknown" else 0.0,
        source="llm_fallback",
        evidence=["turn_planner"],
        patient_scope=scope,  # type: ignore[arg-type]
        problem=problem,
        extent=extent,
        jaw=jaw,
        modifiers=modifiers,
        next_best_action="none",
        should_clarify=False,
        cues=PatientSituationCues(intent=intent),  # type: ignore[arg-type]
    )


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
    client_id: str | None = None,
) -> tuple[PatientSituationResult, dict[str, Any]]:
    """Detect situation for this turn; optionally carry from session on vague price."""
    try:
        from core.turn_planner_llm import turn_plan_from_ctx

        plan = turn_plan_from_ctx()
        if plan is not None and plan.patient_situation:
            return _result_from_turn_plan(plan.patient_situation, q=q), {
                "patient_situation_carried": False,
                "patient_situation_carry_age": None,
                "patient_situation_source": "turn_planner",
            }
    except Exception:
        pass
    fresh = detect_patient_situation(q, client_id=client_id, sid=sid)
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
    client_id: str | None = None,
    fresh_result: PatientSituationResult | None = None,
    carry_meta: dict[str, Any] | None = None,
) -> None:
    """Persist fresh patient situation from q when eligible (not vague carry-only turns)."""
    if not sid:
        return
    carry_meta = carry_meta or {}
    if carry_meta.get("patient_situation_carried"):
        return
    from session import set_last_patient_situation

    fresh = fresh_result or detect_patient_situation(q, client_id=client_id, sid=sid)
    if situation_routing_eligible(fresh) and not fresh.should_clarify:
        set_last_patient_situation(sid, fresh.model_dump())
