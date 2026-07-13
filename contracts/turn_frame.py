"""Minimal canonical turn contract (A1 shadow-only; not wired to runtime)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.answer_plan import AspectKind
from contracts.decision_frame import RouteIntent

EmotionKind = Literal["none", "fear", "doubt"]
SpecificityKind = Literal["unknown", "general", "specific"]

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
]


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


class TurnFrameMeta(BaseModel):
    """Per-field metadata for semantic TurnFrame axes."""

    model_config = ConfigDict(extra="forbid")

    intent: FieldMeta
    topic: FieldMeta
    aspects: FieldMeta
    primary_aspect: FieldMeta
    emotion: FieldMeta
    specificity: FieldMeta
    patient_scope: FieldMeta
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
    patient_scope: str | None = None
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
