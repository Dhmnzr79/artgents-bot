"""Typed result of the local pre-composer problem gate.

The gate deliberately makes only high-precision decisions.  It is not a
medical classifier and carries no user text in its result.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


LocalProblemGateDecision = Literal["spam", "admin", "pass"]
LocalProblemGateReasonCode = Literal[
    "obvious_text_noise",
    "current_symptom",
    "complaint_or_management",
    "diagnosis_request",
    "personal_treatment_request",
    "post_procedure_complication",
    "no_high_precision_match",
    "governed_typed_ui",
]


class LocalProblemGateResult(BaseModel):
    """One of three local routing decisions, without retaining raw input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    decision: LocalProblemGateDecision
    reason_code: LocalProblemGateReasonCode

    @model_validator(mode="after")
    def _consistent_reason(self) -> Self:
        if self.decision == "spam":
            expected = {"obvious_text_noise"}
        elif self.decision == "admin":
            expected = {
                "current_symptom",
                "complaint_or_management",
                "diagnosis_request",
                "personal_treatment_request",
                "post_procedure_complication",
            }
        else:
            expected = {"no_high_precision_match", "governed_typed_ui"}
        if self.reason_code not in expected:
            raise ValueError("local_problem_gate_result_inconsistent")
        return self
