"""Pure deterministic TurnFrame builder for governed UI scope/stage clicks."""

from __future__ import annotations

from contracts.turn_frame import (
    FieldMeta,
    PatientScopeFrame,
    PatientScopeFrameMeta,
    TurnFrame,
    TurnFrameMeta,
)
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction

_GOVERNED_UI_PROVENANCE_KIND = "governed_ui_action"


def _valid_meta(*, provenance: str) -> FieldMeta:
    return FieldMeta(confidence=1.0, provenance=provenance, status="valid")


def _default_patient_scope_meta(*, provenance: str) -> PatientScopeFrameMeta:
    defaulted = FieldMeta(confidence=0.0, provenance=provenance, status="defaulted")
    return PatientScopeFrameMeta(
        container=defaulted,
        extent=defaulted,
        jaw=defaulted,
        stage=defaulted,
        modifiers=defaulted,
    )


def _commercial_field_meta(*, provenance_ref: str) -> tuple[FieldMeta, str]:
    provenance = f"{_GOVERNED_UI_PROVENANCE_KIND}:{provenance_ref}"
    return _valid_meta(provenance=provenance), provenance


def build_typed_ui_turn_frame(
    *,
    topic: str,
    provenance_ref: str,
) -> TurnFrame:
    """Build authoritative commercial TurnFrame for a governed UI click.

    Extent/stage remain unknown on the TurnFrame; EffectiveScope owns them.
    """

    topic_eff = str(topic).strip().lower()
    if not topic_eff:
        raise ValueError("typed_ui_topic_required")
    ref = str(provenance_ref).strip()
    if not ref:
        raise ValueError("typed_ui_provenance_ref_required")

    commercial_meta, provenance = _commercial_field_meta(provenance_ref=ref)
    patient_scope_meta = _default_patient_scope_meta(provenance=provenance)
    service_meta = FieldMeta(confidence=0.0, provenance=provenance, status="defaulted")

    return TurnFrame(
        intent="price_lookup",
        topic=topic_eff,
        aspects=["price"],
        primary_aspect="price",
        emotion="none",
        specificity="unknown",
        patient_scope=PatientScopeFrame(),
        service_id=None,
        follow_up=False,
        followup_of=None,
        needs_clarification=False,
        field_meta=TurnFrameMeta(
            intent=commercial_meta,
            topic=commercial_meta,
            aspects=commercial_meta,
            primary_aspect=commercial_meta,
            emotion=_valid_meta(provenance=provenance),
            specificity=_valid_meta(provenance=provenance),
            patient_scope=patient_scope_meta,
            service_id=service_meta,
            follow_up=_valid_meta(provenance=provenance),
            followup_of=service_meta,
            needs_clarification=commercial_meta,
        ),
    )


def build_typed_ui_turn_frame_from_scope_action(action: UiScopeAction) -> TurnFrame:
    return build_typed_ui_turn_frame(topic=action.topic, provenance_ref=action.ref)


def build_typed_ui_turn_frame_from_stage_action(action: UiStageAction) -> TurnFrame:
    return build_typed_ui_turn_frame(topic=action.topic, provenance_ref=action.ref)
