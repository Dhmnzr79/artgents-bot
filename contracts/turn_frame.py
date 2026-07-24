"""Minimal canonical turn contract (A1 shadow-only; not wired to runtime)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.answer_plan import AspectKind
from contracts.decision_frame import RouteIntent

EmotionKind = Literal["none", "fear", "doubt"]
SpecificityKind = Literal["unknown", "general", "specific"]

PatientExtent = Literal["unknown", "one_tooth", "few_teeth", "full_arch"]
PatientJaw = Literal["unknown", "upper", "lower", "both"]
PatientCareStage = Literal[
    "unknown",
    "natural_tooth_present",
    "extraction_context",
    "implant_placed",
]
PatientScopeModifier = Literal["reported_bone_deficit"]

FieldStatus = Literal["valid", "defaulted", "missing", "invalid"]

FieldErrorReason = Literal[
    "aspects_empty",
    "aspects_invalid_type",
    "aspect_not_allowed",
    "primary_aspect_unavailable",
    "topic_not_allowed",
    "topic_invalid_type",
    "topic_confidence_invalid",
    "route_invalid",
    "service_id_invalid_type",
    "service_id_not_allowed",
    "followup_of_invalid_type",
    "followup_of_not_allowed",
    "follow_up_unavailable",
    "needs_clarification_invalid_type",
    "patient_extent_invalid_type",
    "patient_extent_not_allowed",
    "patient_jaw_invalid_type",
    "patient_jaw_not_allowed",
    "patient_stage_invalid_type",
    "patient_stage_not_allowed",
    "patient_modifiers_invalid_type",
    "patient_modifier_not_allowed",
    "patient_scope_invalid_type",
    "patient_scope_extra_field",
]


class PatientScopeFrame(BaseModel):
    """Composable, unknown-safe patient situation scope (shadow-only)."""

    model_config = ConfigDict(extra="forbid")

    extent: PatientExtent = "unknown"
    jaw: PatientJaw = "unknown"
    stage: PatientCareStage = "unknown"
    modifiers: list[PatientScopeModifier] = Field(default_factory=list)

    @field_validator("modifiers", mode="after")
    @classmethod
    def _canonical_modifiers(
        cls,
        value: list[PatientScopeModifier],
    ) -> list[PatientScopeModifier]:
        return sorted(set(value))


class FieldMeta(BaseModel):
    """Shared confidence/provenance/status metadata for one TurnFrame axis."""

    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: str = Field(..., min_length=1)
    status: FieldStatus
    error: FieldErrorReason | None = None

    @model_validator(mode="after")
    def _status_error_invariant(self) -> "FieldMeta":
        if self.status == "invalid":
            if self.error is None:
                raise ValueError("invalid_requires_error")
        elif self.error is not None:
            raise ValueError("non_invalid_forbids_error")
        return self


class PatientScopeFrameMeta(BaseModel):
    """Per-subfield metadata for composable patient scope."""

    model_config = ConfigDict(extra="forbid")

    container: FieldMeta
    extent: FieldMeta
    jaw: FieldMeta
    stage: FieldMeta
    modifiers: FieldMeta


class TurnFrameMeta(BaseModel):
    """Per-field metadata for semantic TurnFrame axes."""

    model_config = ConfigDict(extra="forbid")

    intent: FieldMeta
    topic: FieldMeta
    aspects: FieldMeta
    primary_aspect: FieldMeta
    emotion: FieldMeta
    specificity: FieldMeta
    patient_scope: PatientScopeFrameMeta
    service_id: FieldMeta
    follow_up: FieldMeta
    followup_of: FieldMeta
    needs_clarification: FieldMeta


class TurnFrame(BaseModel):
    """Single-turn semantic frame for future backbone wiring (A1 contract only)."""

    model_config = ConfigDict(extra="forbid")

    intent: RouteIntent
    topic: str | None = None
    aspects: list[AspectKind] = Field(default_factory=list)
    primary_aspect: AspectKind | None = None
    emotion: EmotionKind = "none"
    specificity: SpecificityKind = "unknown"
    patient_scope: PatientScopeFrame = Field(default_factory=PatientScopeFrame)
    service_id: str | None = None
    follow_up: bool = False
    followup_of: str | None = None
    needs_clarification: bool = False
    field_meta: TurnFrameMeta

    @model_validator(mode="after")
    def _primary_aspect_in_aspects(self) -> "TurnFrame":
        if self.primary_aspect is None:
            return self
        if self.primary_aspect not in self.aspects:
            raise ValueError("primary_aspect_not_in_aspects")
        return self
