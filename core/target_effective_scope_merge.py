"""Per-axis EffectiveScope merge (A9R1, offline/unwired).

Pure merge API for A9R3 wiring. Does not read TurnFrame.patient_scope from runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.effective_scope import (
    EffectiveScope,
    EffectiveScopeJaw,
    EffectiveScopeSource,
    ScopeAxisProvenance,
    ScopeAxisSource,
)
from contracts.patient_scope_projection import ProjectedPatientScope
from contracts.target_service_applicability import PatientStage, ReportedContext
from contracts.ui_scope_action import ScopeExtent, UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core.target_effective_scope import SessionPatientFacts


@dataclass(frozen=True, slots=True)
class EffectiveScopeMergeInputs:
    current_topic: str | None
    session_turn_count: int
    session_facts: SessionPatientFacts | None
    current_ui_scope_action: UiScopeAction | None = None
    current_ui_stage_action: UiStageAction | None = None
    projected_turn_scope: ProjectedPatientScope | None = None


def _topic_eff(topic: str | None) -> str | None:
    value = str(topic or "").strip().lower()
    return value or None


def _session_usable(
    session_facts: SessionPatientFacts | None,
    *,
    current_topic: str | None,
    session_turn_count: int,
) -> bool:
    if session_facts is None:
        return False
    topic_eff = _topic_eff(current_topic)
    if topic_eff is None or session_facts.topic != topic_eff:
        return False
    return session_facts.is_fresh(session_turn_count=session_turn_count)


def _axis_attr(
    source: ScopeAxisSource,
    provenance: str,
) -> ScopeAxisProvenance:
    return ScopeAxisProvenance(source=source, provenance=provenance)


def _merge_extent(
    inputs: EffectiveScopeMergeInputs,
    *,
    session_ok: bool,
) -> tuple[ScopeExtent | Literal["unknown"], ScopeAxisProvenance]:
    if inputs.current_ui_scope_action is not None:
        action = inputs.current_ui_scope_action
        return action.extent, _axis_attr("ui_action", action.ref)
    projected = inputs.projected_turn_scope
    if projected is not None and projected.extent.usable and projected.extent.value:
        return projected.extent.value, _axis_attr(  # type: ignore[return-value]
            "a9_turn",
            projected.extent.provenance,
        )
    if session_ok and inputs.session_facts is not None:
        return inputs.session_facts.extent, _axis_attr(
            "session",
            inputs.session_facts.ref,
        )
    return "unknown", _axis_attr("unknown", "unknown")


def _merge_jaw(
    inputs: EffectiveScopeMergeInputs,
    *,
    session_ok: bool,
) -> tuple[EffectiveScopeJaw, ScopeAxisProvenance]:
    projected = inputs.projected_turn_scope
    if projected is not None and projected.jaw.usable and projected.jaw.value:
        return projected.jaw.value, _axis_attr(  # type: ignore[return-value]
            "a9_turn",
            projected.jaw.provenance,
        )
    if session_ok and inputs.session_facts is not None and inputs.session_facts.jaw:
        return inputs.session_facts.jaw, _axis_attr(  # type: ignore[return-value]
            "session",
            inputs.session_facts.ref,
        )
    return "unknown", _axis_attr("unknown", "unknown")


def _merge_stage(
    inputs: EffectiveScopeMergeInputs,
    *,
    session_ok: bool,
) -> tuple[PatientStage | None, ScopeAxisProvenance]:
    if inputs.current_ui_stage_action is not None:
        action = inputs.current_ui_stage_action
        return action.stage, _axis_attr("ui_stage_action", action.ref)
    if inputs.current_ui_scope_action is not None and session_ok:
        session = inputs.session_facts
        if session is not None and session.stage is not None:
            return session.stage, _axis_attr("session", session.ref)
    projected = inputs.projected_turn_scope
    if projected is not None and projected.stage.usable and projected.stage.value:
        return projected.stage.value, _axis_attr(  # type: ignore[return-value]
            "a9_turn",
            projected.stage.provenance,
        )
    if session_ok and inputs.session_facts is not None and inputs.session_facts.stage:
        return inputs.session_facts.stage, _axis_attr(
            "session",
            inputs.session_facts.ref,
        )
    return None, _axis_attr("unknown", "unknown")


def _merge_reported_context(
    inputs: EffectiveScopeMergeInputs,
    *,
    session_ok: bool,
) -> tuple[ReportedContext | None, ScopeAxisProvenance]:
    projected = inputs.projected_turn_scope
    if (
        projected is not None
        and projected.reported_context.usable
        and projected.reported_context.value
    ):
        return projected.reported_context.value, _axis_attr(  # type: ignore[return-value]
            "a9_turn",
            projected.reported_context.provenance,
        )
    if session_ok and inputs.session_facts is not None:
        ctx = inputs.session_facts.reported_context
        if ctx is not None:
            return ctx, _axis_attr("session", inputs.session_facts.ref)
    return None, _axis_attr("unknown", "unknown")


def _aggregate_source(
    extent_axis: ScopeAxisProvenance,
    stage_axis: ScopeAxisProvenance,
    jaw_axis: ScopeAxisProvenance,
    reported_axis: ScopeAxisProvenance,
) -> tuple[EffectiveScopeSource, str]:
    for axis in (extent_axis, stage_axis, jaw_axis, reported_axis):
        if axis.source == "ui_action":
            return "ui_action", axis.provenance
    for axis in (extent_axis, stage_axis, jaw_axis, reported_axis):
        if axis.source == "ui_stage_action":
            return "ui_stage_action", axis.provenance
    for axis in (extent_axis, stage_axis, jaw_axis, reported_axis):
        if axis.source == "a9_turn":
            return "a9_turn", axis.provenance
    for axis in (extent_axis, stage_axis, jaw_axis, reported_axis):
        if axis.source == "session":
            return "session", axis.provenance
    return "unknown", "unknown"


def merge_effective_scope_axes(inputs: EffectiveScopeMergeInputs) -> EffectiveScope:
    """Merge UI actions, projected A9 axes, and session facts per axis."""

    session_ok = _session_usable(
        inputs.session_facts,
        current_topic=inputs.current_topic,
        session_turn_count=inputs.session_turn_count,
    )
    extent, extent_axis = _merge_extent(inputs, session_ok=session_ok)
    jaw, jaw_axis = _merge_jaw(inputs, session_ok=session_ok)
    stage, stage_axis = _merge_stage(inputs, session_ok=session_ok)
    reported_context, reported_axis = _merge_reported_context(
        inputs,
        session_ok=session_ok,
    )
    topic: str | None = None
    if inputs.current_ui_scope_action is not None:
        topic = inputs.current_ui_scope_action.topic
    elif inputs.current_ui_stage_action is not None:
        topic = inputs.current_ui_stage_action.topic
    elif session_ok and inputs.session_facts is not None:
        topic = inputs.session_facts.topic
    else:
        topic = _topic_eff(inputs.current_topic)

    source, provenance = _aggregate_source(
        extent_axis,
        stage_axis,
        jaw_axis,
        reported_axis,
    )
    return EffectiveScope(
        extent=extent,
        jaw=jaw,
        stage=stage,
        reported_context=reported_context,
        topic=topic,
        source=source,
        provenance=provenance,
        extent_axis=extent_axis,
        jaw_axis=jaw_axis,
        stage_axis=stage_axis,
        reported_context_axis=reported_axis,
    )


@dataclass(frozen=True, slots=True)
class SimulatedSessionPatientFacts:
    """Offline preview of session facts after a turn; not a product writer."""

    facts: SessionPatientFacts | None
    wrote: bool


def simulate_session_patient_facts_after_turn(
    *,
    merged: EffectiveScope,
    prior: SessionPatientFacts | None,
    current_topic: str | None,
    session_turn_count: int,
    scope_ref: str = "a9_turn:patient_scope",
) -> SimulatedSessionPatientFacts:
    """Simulate session write from merged scope when A9 contributed usable axes."""

    topic_eff = _topic_eff(current_topic)
    if topic_eff is None:
        return SimulatedSessionPatientFacts(facts=prior, wrote=False)

    usable_axes = (
        merged.extent_axis.source == "a9_turn"
        or merged.jaw_axis.source == "a9_turn"
        or merged.stage_axis.source == "a9_turn"
        or merged.reported_context_axis.source == "a9_turn"
    )
    if not usable_axes:
        return SimulatedSessionPatientFacts(facts=prior, wrote=False)

    extent: ScopeExtent | None = None
    if merged.extent != "unknown":
        extent = merged.extent  # type: ignore[assignment]
    elif prior is not None and prior.topic == topic_eff:
        extent = prior.extent

    if extent is None:
        return SimulatedSessionPatientFacts(facts=prior, wrote=False)

    jaw = merged.jaw if merged.jaw_axis.source == "a9_turn" else (
        prior.jaw if prior is not None and prior.topic == topic_eff else None
    )
    stage = merged.stage if merged.stage_axis.source == "a9_turn" else (
        prior.stage if prior is not None and prior.topic == topic_eff else None
    )
    reported_context = (
        merged.reported_context
        if merged.reported_context_axis.source == "a9_turn"
        else (
            prior.reported_context
            if prior is not None and prior.topic == topic_eff
            else None
        )
    )
    facts = SessionPatientFacts(
        extent=extent,
        topic=topic_eff,
        provenance=merged.provenance if merged.source == "a9_turn" else scope_ref,
        ref=scope_ref,
        set_at_turn=session_turn_count,
        stage=stage,
        stage_ref=prior.stage_ref if prior is not None else None,
        jaw=jaw if jaw not in (None, "unknown") else None,
        reported_context=reported_context,
    )
    return SimulatedSessionPatientFacts(facts=facts, wrote=True)
