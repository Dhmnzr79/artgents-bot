"""Patient situation — semantic business scope (not route→file)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PatientSituationKind = Literal[
    "one_tooth_missing",
    "few_teeth_missing",
    "full_arch_missing",
    "upper_jaw_missing_or_complex",
    "existing_implant_prosthetic_stage",
    "extraction_then_implant",
    "bone_deficit_or_grafting",
    "urgent_problem",
    "generic_implant_interest",
    "unknown",
]

PatientScope = Literal[
    "one_tooth",
    "few_teeth",
    "full_jaw",
    "upper_jaw",
    "prosthetic_stage",
    "adjunct",
    "urgent",
    "generic",
    "unknown",
]

PatientNextBestAction = Literal[
    "consult",
    "ct",
    "price_estimate",
    "doctor_lookup",
    "urgent_booking",
    "clarify",
    "none",
]

PatientSituationSource = Literal["rule_based", "llm_fallback", "unknown"]

CueQuantity = Literal["one", "few", "many", "all", "jaw", "unknown"]

CueIntent = Literal[
    "price",
    "choose_solution",
    "restore",
    "compare",
    "doctor",
    "warranty",
    "unknown",
]


class PatientSituationCues(BaseModel):
    """Structured cues extracted before kind resolution."""

    model_config = ConfigDict(extra="forbid")

    quantity: CueQuantity = "unknown"
    anatomy: list[str] = Field(default_factory=list)
    state: list[str] = Field(default_factory=list)
    intent: CueIntent = "unknown"


class PatientSituationSessionContext(BaseModel):
    """Optional session hints for detection (Slice 1: accepted, not required)."""

    model_config = ConfigDict(extra="forbid")

    last_question: str | None = None
    last_subject: str | None = None


class PatientSituationResult(BaseModel):
    """Semantic patient situation — primary output is kind + scope, not doc/service route."""

    model_config = ConfigDict(extra="forbid")

    kind: PatientSituationKind
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: PatientSituationSource
    evidence: list[str] = Field(default_factory=list)
    patient_scope: PatientScope
    exclude_service_ids: list[str] = Field(
        default_factory=list,
        description="Telemetry/contract only in Slice 1. Slice 2: no hard routing blocklist from this field.",
    )
    preferred_service_ids: list[str] = Field(
        default_factory=list,
        description="Telemetry/contract only in Slice 1. Slice 2: no hard route→service from this field.",
    )
    preferred_groups: list[str] = Field(
        default_factory=list,
        description="Telemetry/contract only in Slice 1. Slice 2: soft group bias via pricebook/scope only.",
    )
    next_best_action: PatientNextBestAction = "none"
    should_clarify: bool = False
    clarify_question: str | None = None
    clarification_reason: str | None = None
    cues: PatientSituationCues = Field(default_factory=PatientSituationCues)
