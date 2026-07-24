"""Resolve EffectiveScope from typed UI action and session patient_facts (AC1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.effective_scope import EffectiveScope
from contracts.ui_scope_action import ScopeExtent, UiScopeAction
from contracts.ui_stage_action import UiStageAction
from contracts.target_service_applicability import PatientStage
from core.routing_loader import THRESHOLDS


@dataclass(frozen=True, slots=True)
class SessionPatientFacts:
    extent: ScopeExtent
    topic: str
    provenance: str
    ref: str
    set_at_turn: int
    stage: PatientStage | None = None
    stage_ref: str | None = None

    def is_fresh(self, *, session_turn_count: int) -> bool:
        age = max(0, int(session_turn_count) - int(self.set_at_turn))
        return age <= int(THRESHOLDS.follow_up.max_service_focus_turn_age)


def resolve_effective_scope(
    *,
    current_ui_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None = None,
    session_facts: SessionPatientFacts | None,
    current_topic: str | None,
    session_turn_count: int,
) -> EffectiveScope:
    """Priority: explicit UiScopeAction > explicit UiStageAction > fresh session > unknown."""

    if current_ui_action is not None:
        stage = current_ui_stage_action.stage if current_ui_stage_action else None
        if stage is None and session_facts is not None:
            topic_eff = str(current_topic or "").strip().lower() or None
            if topic_eff and session_facts.topic == topic_eff and session_facts.is_fresh(
                session_turn_count=session_turn_count
            ):
                stage = session_facts.stage
        return EffectiveScope(
            extent=current_ui_action.extent,
            stage=stage,
            topic=current_ui_action.topic,
            source="ui_action",
            provenance=current_ui_action.ref,
        )

    if current_ui_stage_action is not None:
        extent: ScopeExtent | Literal["unknown"] = "unknown"
        stage = current_ui_stage_action.stage
        topic = current_ui_stage_action.topic
        if session_facts is not None:
            topic_eff = str(current_topic or "").strip().lower() or None
            if topic_eff and session_facts.topic == topic_eff and session_facts.is_fresh(
                session_turn_count=session_turn_count
            ):
                extent = session_facts.extent
        return EffectiveScope(
            extent=extent,
            stage=stage,
            topic=topic,
            source="ui_stage_action",
            provenance=current_ui_stage_action.ref,
        )

    if session_facts is None:
        return EffectiveScope()

    topic_eff = str(current_topic or "").strip().lower() or None
    if topic_eff and session_facts.topic != topic_eff:
        return EffectiveScope()

    if not session_facts.is_fresh(session_turn_count=session_turn_count):
        return EffectiveScope()

    return EffectiveScope(
        extent=session_facts.extent,
        stage=session_facts.stage,
        topic=session_facts.topic,
        source="session",
        provenance=session_facts.ref,
    )


def session_patient_facts_from_ui_action(
    action: UiScopeAction,
    *,
    set_at_turn: int,
    stage: PatientStage | None = None,
    stage_ref: str | None = None,
) -> SessionPatientFacts:
    return SessionPatientFacts(
        extent=action.extent,
        topic=action.topic,
        provenance=action.provenance,
        ref=action.ref,
        set_at_turn=int(set_at_turn),
        stage=stage,
        stage_ref=stage_ref,
    )


def session_patient_facts_from_ui_stage_action(
    action: UiStageAction,
    *,
    set_at_turn: int,
    prior: SessionPatientFacts | None,
) -> SessionPatientFacts:
    extent = prior.extent if prior is not None else "one_tooth"  # type: ignore[assignment]
    scope_ref = prior.ref if prior is not None else action.ref
    return SessionPatientFacts(
        extent=extent,
        topic=action.topic,
        provenance=action.provenance,
        ref=scope_ref,
        set_at_turn=int(set_at_turn),
        stage=action.stage,
        stage_ref=action.ref,
    )


def read_session_patient_facts(raw: object) -> SessionPatientFacts | None:
    if not isinstance(raw, dict):
        return None
    extent = str(raw.get("extent") or "").strip()
    topic = str(raw.get("topic") or "").strip().lower()
    ref = str(raw.get("ref") or "").strip()
    provenance = str(raw.get("provenance") or "").strip() or "ui_scope_ref"
    if extent not in ("one_tooth", "few_teeth", "full_arch") or not topic or not ref:
        return None
    try:
        set_at_turn = int(raw.get("set_at_turn"))
    except (TypeError, ValueError):
        return None
    stage_raw = raw.get("stage")
    stage: PatientStage | None = None
    if isinstance(stage_raw, str) and stage_raw.strip():
        stage = stage_raw.strip()  # type: ignore[assignment]
    stage_ref = str(raw.get("stage_ref") or "").strip() or None
    return SessionPatientFacts(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        provenance=provenance,
        ref=ref,
        set_at_turn=set_at_turn,
        stage=stage,
        stage_ref=stage_ref,
    )


def patient_facts_payload(facts: SessionPatientFacts) -> dict[str, str | int | None]:
    payload: dict[str, str | int | None] = {
        "extent": facts.extent,
        "topic": facts.topic,
        "provenance": facts.provenance,
        "ref": facts.ref,
        "set_at_turn": facts.set_at_turn,
    }
    if facts.stage is not None:
        payload["stage"] = facts.stage
    if facts.stage_ref is not None:
        payload["stage_ref"] = facts.stage_ref
    return payload
