"""Resolve EffectiveScope from typed UI action and session patient_facts (AC1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.effective_scope import (
    EffectiveScope,
    EffectiveScopeJaw,
    ScopeAxisProvenance,
)
from contracts.patient_scope_projection import ProjectedPatientScope
from contracts.target_service_applicability import PatientStage, ReportedContext
from contracts.ui_scope_action import ScopeExtent, UiScopeAction
from contracts.ui_stage_action import UiStageAction
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
    jaw: Literal["upper", "lower", "both"] | None = None
    reported_context: ReportedContext | None = None

    def is_fresh(self, *, session_turn_count: int) -> bool:
        age = max(0, int(session_turn_count) - int(self.set_at_turn))
        return age <= int(THRESHOLDS.follow_up.max_service_focus_turn_age)


def strip_reported_context_for_product(scope: EffectiveScope) -> EffectiveScope:
    """Remove diagnostic-only reported_context before AC2/session product boundaries."""

    if scope.reported_context is None and scope.reported_context_axis.source == "unknown":
        return scope
    return scope.model_copy(
        update={
            "reported_context": None,
            "reported_context_axis": ScopeAxisProvenance(
                source="unknown",
                provenance="unknown",
            ),
        }
    )


def resolve_effective_scope(
    *,
    current_ui_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None = None,
    session_facts: SessionPatientFacts | None,
    current_topic: str | None,
    session_turn_count: int,
    projected_turn_scope: ProjectedPatientScope | None = None,
) -> EffectiveScope:
    """Priority: UI actions > A9 projection (when enabled) > fresh session > unknown."""

    from config import A9_PATIENT_SCOPE_AUTHORITY

    if A9_PATIENT_SCOPE_AUTHORITY:
        from core.target_effective_scope_merge import (
            EffectiveScopeMergeInputs,
            merge_effective_scope_axes,
        )

        merged = merge_effective_scope_axes(
            EffectiveScopeMergeInputs(
                current_topic=current_topic,
                session_turn_count=session_turn_count,
                session_facts=session_facts,
                current_ui_scope_action=current_ui_action,
                current_ui_stage_action=current_ui_stage_action,
                projected_turn_scope=projected_turn_scope,
            )
        )
        return strip_reported_context_for_product(merged)

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
    jaw_raw = raw.get("jaw")
    jaw: Literal["upper", "lower", "both"] | None = None
    if isinstance(jaw_raw, str) and jaw_raw.strip() in ("upper", "lower", "both"):
        jaw = jaw_raw.strip()  # type: ignore[assignment]
    reported_raw = raw.get("reported_context")
    reported_context: ReportedContext | None = None
    if reported_raw == "reported_bone_deficit":
        reported_context = "reported_bone_deficit"
    return SessionPatientFacts(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        provenance=provenance,
        ref=ref,
        set_at_turn=set_at_turn,
        stage=stage,
        stage_ref=stage_ref,
        jaw=jaw,
        reported_context=reported_context,
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
    if facts.jaw is not None:
        payload["jaw"] = facts.jaw
    if facts.reported_context is not None:
        payload["reported_context"] = facts.reported_context
    return payload
