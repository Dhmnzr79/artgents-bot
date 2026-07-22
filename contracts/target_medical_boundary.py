"""Target medical boundary detector contracts (S42, offline/unwired)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.target_response_spec import CanonicalToken
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope

TargetMedicalBoundaryDecision = Literal["none", "medical_handoff", "uncertain"]

TargetMedicalBoundaryBackendLabel = Literal["none", "medical_handoff"]

TargetMedicalBoundarySource = Literal["backend", "fail_closed"]

TargetMedicalBoundaryResultReasonCode = Literal[
    "boundary_none_confident",
    "boundary_medical_handoff_confident",
    "boundary_uncertain_low_confidence",
    "boundary_uncertain_malformed_output",
    "boundary_uncertain_backend_failure",
    "boundary_uncertain_ambiguous",
]

_UNCERTAIN_GRANULAR_REASON_CODES = frozenset(
    {
        "boundary_uncertain_low_confidence",
        "boundary_uncertain_malformed_output",
        "boundary_uncertain_backend_failure",
        "boundary_uncertain_ambiguous",
    }
)


class TargetMedicalBoundaryResult(BaseModel):
    """Immutable three-way medical boundary classification outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    decision: TargetMedicalBoundaryDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_code: TargetMedicalBoundaryResultReasonCode
    source: TargetMedicalBoundarySource

    @model_validator(mode="after")
    def _validate_consistent_fields(self) -> Self:
        if self.decision == "none":
            if self.reason_code != "boundary_none_confident" or self.source != "backend":
                raise ValueError("medical_boundary_result_inconsistent")
        elif self.decision == "medical_handoff":
            if (
                self.reason_code != "boundary_medical_handoff_confident"
                or self.source != "backend"
            ):
                raise ValueError("medical_boundary_result_inconsistent")
        elif self.reason_code not in _UNCERTAIN_GRANULAR_REASON_CODES or self.source != "fail_closed":
            raise ValueError("medical_boundary_result_inconsistent")
        return self


class TargetMedicalBoundaryTerminalEnforcement(BaseModel):
    """Fail-closed terminal enforcement for uncertain boundary outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["terminal"] = "terminal"
    terminal_mode: Literal["defer"] = "defer"
    reason_code: Literal["boundary_uncertain"] = "boundary_uncertain"


class TargetMedicalBoundaryEnvelopeEnforcement(BaseModel):
    """Envelope materialization allowed after boundary enforcement."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["envelope"] = "envelope"
    envelope: TargetTurnFramePolicyEnvelope
