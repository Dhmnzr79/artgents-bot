"""Project TurnFrame.patient_scope to usable A9 axes (A9R1, offline/unwired)."""

from __future__ import annotations

from contracts.patient_scope_projection import (
    NATIVE_PATIENT_SCOPE_PROVENANCE_PREFIX,
    ProjectedPatientScope,
    ProjectedScopeAxis,
)
from contracts.turn_frame import FieldMeta, TurnFrame


def _is_native_provenance(provenance: str) -> bool:
    return provenance.startswith(NATIVE_PATIENT_SCOPE_PROVENANCE_PREFIX)


def _scalar_axis_usable(
    meta: FieldMeta,
    value: str,
) -> bool:
    if meta.status != "valid":
        return False
    if not _is_native_provenance(meta.provenance):
        return False
    return value != "unknown"


def _modifiers_axis_usable(
    meta: FieldMeta,
    modifiers: list[str],
) -> bool:
    if meta.status != "valid":
        return False
    if not _is_native_provenance(meta.provenance):
        return False
    return "reported_bone_deficit" in modifiers


def _project_scalar_axis(
    meta: FieldMeta,
    value: str,
) -> ProjectedScopeAxis:
    usable = _scalar_axis_usable(meta, value)
    return ProjectedScopeAxis(
        value=value if usable else None,
        provenance=meta.provenance,
        usable=usable,
    )


def _project_reported_context_axis(
    meta: FieldMeta,
    modifiers: list[str],
) -> ProjectedScopeAxis:
    usable = _modifiers_axis_usable(meta, modifiers)
    value = "reported_bone_deficit" if usable else None
    return ProjectedScopeAxis(
        value=value,
        provenance=meta.provenance,
        usable=usable,
    )


def project_patient_scope_from_turn_frame(frame: TurnFrame) -> ProjectedPatientScope:
    """Pure projection from one TurnFrame; does not merge session or UI actions."""

    scope = frame.patient_scope
    meta = frame.field_meta.patient_scope
    stage_value = scope.stage
    stage_usable = _scalar_axis_usable(meta.stage, stage_value)
    stage_projected: str | None = None
    if stage_usable and stage_value != "unknown":
        stage_projected = stage_value

    return ProjectedPatientScope(
        extent=_project_scalar_axis(meta.extent, scope.extent),
        jaw=_project_scalar_axis(meta.jaw, scope.jaw),
        stage=ProjectedScopeAxis(
            value=stage_projected,
            provenance=meta.stage.provenance,
            usable=stage_usable,
        ),
        reported_context=_project_reported_context_axis(meta.modifiers, scope.modifiers),
    )
