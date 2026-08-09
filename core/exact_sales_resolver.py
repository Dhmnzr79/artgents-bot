"""Pure merger for exact, already-authoritative sales inputs (offline only)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.answer_plan import AspectKind
from contracts.exact_sales_resolution import (
    ExactSalesAuthority,
    ExactSalesConflict,
    ExactSalesFieldAuthority,
    ExactSalesResolution,
)
from contracts.patient_scope_projection import ProjectedPatientScope
from contracts.response_schema import TargetService
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core.target_effective_scope import SessionPatientFacts
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
)
from core.target_service_resolver import resolve_target_service_term


class ExactSalesResolutionConflictError(ValueError):
    """Typed error when governed current-turn facts cannot form one context."""

    def __init__(self, code: str, *, scope_topic: str, stage_topic: str) -> None:
        self.code = code
        self.scope_topic = scope_topic
        self.stage_topic = stage_topic
        super().__init__(f"{code}: {scope_topic!r} != {stage_topic!r}")


class ExactSalesResolverInputError(ValueError):
    """Typed error for malformed resolver control inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


@dataclass(frozen=True, slots=True)
class ExactSalesResolverInputs:
    """Only typed UI, exact-turn and session data may enter the merger."""

    services: dict[str, TargetService]
    current_topic: str | None
    session_turn_count: int
    current_ui_scope_action: UiScopeAction | None = None
    current_ui_stage_action: UiStageAction | None = None
    exact_service_term: str | None = None
    exact_aspect: AspectKind | None = None
    projected_turn_scope: ProjectedPatientScope | None = None
    session_facts: SessionPatientFacts | None = None


def _authority_from_scope_source(source: str) -> ExactSalesAuthority:
    if source in ("ui_action", "ui_stage_action"):
        return "governed_ui"
    if source == "a9_turn":
        return "exact_turn"
    if source == "session":
        return "valid_session"
    return "unknown"


def _field_authority(source: str, provenance: str) -> ExactSalesFieldAuthority:
    return ExactSalesFieldAuthority(
        authority=_authority_from_scope_source(source),
        provenance=provenance,
    )


def _topic_eff(topic: str) -> str:
    return topic.strip().lower()


def _validate_control_inputs(inputs: ExactSalesResolverInputs) -> None:
    if type(inputs.session_turn_count) is not int or inputs.session_turn_count < 0:
        raise ExactSalesResolverInputError(
            "exact_sales_resolution_session_turn_count_invalid",
            inputs.session_turn_count,
        )
    if inputs.current_topic is not None and (
        not isinstance(inputs.current_topic, str) or not inputs.current_topic.strip()
    ):
        raise ExactSalesResolverInputError(
            "exact_sales_resolution_current_topic_invalid",
            inputs.current_topic,
        )


def _validate_governed_ui_topics(inputs: ExactSalesResolverInputs) -> None:
    scope = inputs.current_ui_scope_action
    stage = inputs.current_ui_stage_action
    if scope is None or stage is None:
        return
    if _topic_eff(scope.topic) == _topic_eff(stage.topic):
        return
    raise ExactSalesResolutionConflictError(
        "exact_sales_resolution_ui_topic_conflict",
        scope_topic=scope.topic,
        stage_topic=stage.topic,
    )


def _effective_topic(inputs: ExactSalesResolverInputs) -> str | None:
    """Governed UI has priority over an older/current generic topic label."""

    if inputs.current_ui_scope_action is not None:
        return inputs.current_ui_scope_action.topic
    if inputs.current_ui_stage_action is not None:
        return inputs.current_ui_stage_action.topic
    return inputs.current_topic


def _usable_session(
    inputs: ExactSalesResolverInputs,
    *,
    effective_topic: str | None,
) -> SessionPatientFacts | None:
    session = inputs.session_facts
    if session is None or effective_topic is None:
        return None
    if session.topic != _topic_eff(effective_topic):
        return None
    if not session.is_fresh(session_turn_count=inputs.session_turn_count):
        return None
    return session


def _axis_conflict(
    *,
    field: str,
    selected_value: str | None,
    selected: ExactSalesFieldAuthority,
    candidate_value: str | None,
    candidate: ExactSalesFieldAuthority,
) -> ExactSalesConflict | None:
    if candidate.authority == "unknown" or candidate_value is None:
        return None
    if selected.authority == "unknown" or selected_value is None:
        return None
    if selected_value == candidate_value:
        return None
    if selected.authority == candidate.authority:
        return None
    return ExactSalesConflict(
        field=field,  # type: ignore[arg-type]
        selected_value=selected_value,
        selected_authority=selected.authority,
        rejected_value=candidate_value,
        rejected_authority=candidate.authority,
    )


def _projected_axis(
    scope: ProjectedPatientScope | None,
    axis: str,
) -> tuple[str | None, ExactSalesFieldAuthority]:
    if scope is None:
        return None, _field_authority("unknown", "unknown")
    value = getattr(scope, axis)
    if not value.usable or value.value is None or value.value == "unknown":
        return None, _field_authority("unknown", "unknown")
    return value.value, _field_authority("a9_turn", value.provenance)


def _session_axis(
    session: SessionPatientFacts | None,
    axis: str,
) -> tuple[str | None, ExactSalesFieldAuthority]:
    if session is None:
        return None, _field_authority("unknown", "unknown")
    value = getattr(session, axis)
    if value is None:
        return None, _field_authority("unknown", "unknown")
    return value, _field_authority("session", session.ref)


def _collect_lower_priority_conflicts(
    *,
    field: str,
    selected_value: str | None,
    selected: ExactSalesFieldAuthority,
    candidates: tuple[tuple[str | None, ExactSalesFieldAuthority], ...],
) -> tuple[ExactSalesConflict, ...]:
    return tuple(
        conflict
        for candidate_value, candidate_authority in candidates
        if (
            conflict := _axis_conflict(
                field=field,
                selected_value=selected_value,
                selected=selected,
                candidate_value=candidate_value,
                candidate=candidate_authority,
            )
        )
        is not None
    )


def resolve_exact_sales_inputs(inputs: ExactSalesResolverInputs) -> ExactSalesResolution:
    """Merge governed UI > exact turn > fresh session without semantic inference.

    The only service lookup delegates to ``resolve_target_service_term`` and
    therefore requires an already-extracted whole service term.  Its typed
    ambiguity error intentionally propagates to the caller.
    """

    _validate_control_inputs(inputs)
    _validate_governed_ui_topics(inputs)
    effective_topic = _effective_topic(inputs)
    session = _usable_session(inputs, effective_topic=effective_topic)
    scope = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic=effective_topic,
            session_turn_count=inputs.session_turn_count,
            session_facts=session,
            current_ui_scope_action=inputs.current_ui_scope_action,
            current_ui_stage_action=inputs.current_ui_stage_action,
            projected_turn_scope=inputs.projected_turn_scope,
        )
    )

    service_id: str | None = None
    if inputs.exact_service_term is not None:
        resolution = resolve_target_service_term(inputs.services, inputs.exact_service_term)
        if resolution is not None:
            service_id = resolution.service_id

    service_authority = ExactSalesFieldAuthority(
        authority="exact_turn" if service_id is not None else "unknown",
        provenance="exact_service_term" if service_id is not None else "unknown",
    )
    aspect_authority = ExactSalesFieldAuthority(
        authority="exact_turn" if inputs.exact_aspect is not None else "unknown",
        provenance="exact_aspect" if inputs.exact_aspect is not None else "unknown",
    )
    extent_authority = _field_authority(
        scope.extent_axis.source,
        scope.extent_axis.provenance,
    )
    jaw_authority = _field_authority(scope.jaw_axis.source, scope.jaw_axis.provenance)
    stage_authority = _field_authority(
        scope.stage_axis.source,
        scope.stage_axis.provenance,
    )

    projected_extent, projected_extent_authority = _projected_axis(
        inputs.projected_turn_scope, "extent"
    )
    projected_jaw, projected_jaw_authority = _projected_axis(
        inputs.projected_turn_scope, "jaw"
    )
    projected_stage, projected_stage_authority = _projected_axis(
        inputs.projected_turn_scope, "stage"
    )
    session_extent, session_extent_authority = _session_axis(session, "extent")
    session_jaw, session_jaw_authority = _session_axis(session, "jaw")
    session_stage, session_stage_authority = _session_axis(session, "stage")

    # A scope click governs only extent; it must not make an older session stage
    # outrank a current exact stage fact.
    if inputs.current_ui_stage_action is not None:
        stage = inputs.current_ui_stage_action.stage
        stage_authority = _field_authority(
            "ui_stage_action", inputs.current_ui_stage_action.ref
        )
    elif projected_stage is not None:
        stage = projected_stage
        stage_authority = projected_stage_authority
    else:
        stage = session_stage
        stage_authority = session_stage_authority

    conflicts = (
        _collect_lower_priority_conflicts(
            field="extent",
            selected_value=None if scope.extent == "unknown" else scope.extent,
            selected=extent_authority,
            candidates=(
                (projected_extent, projected_extent_authority),
                (session_extent, session_extent_authority),
            ),
        )
        + _collect_lower_priority_conflicts(
            field="jaw",
            selected_value=None if scope.jaw == "unknown" else scope.jaw,
            selected=jaw_authority,
            candidates=(
                (projected_jaw, projected_jaw_authority),
                (session_jaw, session_jaw_authority),
            ),
        )
        + _collect_lower_priority_conflicts(
            field="stage",
            selected_value=stage,
            selected=stage_authority,
            candidates=(
                (projected_stage, projected_stage_authority),
                (session_stage, session_stage_authority),
            ),
        )
    )
    return ExactSalesResolution(
        service_id=service_id,
        aspect=inputs.exact_aspect,
        extent=None if scope.extent == "unknown" else scope.extent,
        jaw=None if scope.jaw == "unknown" else scope.jaw,
        stage=stage,  # type: ignore[arg-type]
        service_id_authority=service_authority,
        aspect_authority=aspect_authority,
        extent_authority=extent_authority,
        jaw_authority=jaw_authority,
        stage_authority=stage_authority,
        conflicts=conflicts,
    )
