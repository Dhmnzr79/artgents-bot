"""Planner attempt envelope for single-call dual-branch outcome (A7 contract only)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.turn_frame import PatientScopeFrameMeta, TurnFrame, TurnFrameMeta
from contracts.turn_plan import TurnPlan

ShadowAttemptStatus = Literal["ok", "partial", "not_available", "degraded"]


def turn_frame_has_invalid_or_missing(frame: TurnFrame) -> bool:
    """Return whether any top-level or nested scope axis is invalid/missing."""
    meta = frame.field_meta
    for name in TurnFrameMeta.model_fields:
        field_meta = getattr(meta, name)
        if name == "patient_scope":
            if not isinstance(field_meta, PatientScopeFrameMeta):  # pragma: no cover - typed contract
                raise TypeError("patient_scope_meta_type_invalid")
            if any(
                getattr(field_meta, subfield).status in {"invalid", "missing"}
                for subfield in PatientScopeFrameMeta.model_fields
            ):
                return True
            continue
        if field_meta.status in {"invalid", "missing"}:
            return True
    return False


class PlannerAttempt(BaseModel):
    """Technical envelope for one planner LLM call; not a product route."""

    model_config = ConfigDict(extra="forbid")

    legacy_plan: TurnPlan | None
    shadow_frame: TurnFrame | None
    shadow_status: ShadowAttemptStatus

    @model_validator(mode="after")
    def _shadow_status_invariants(self) -> "PlannerAttempt":
        status = self.shadow_status
        if status == "ok":
            if self.legacy_plan is None or self.shadow_frame is None:
                raise ValueError("ok_requires_legacy_plan_and_shadow_frame")
            if turn_frame_has_invalid_or_missing(self.shadow_frame):
                raise ValueError("ok_forbids_invalid_or_missing_metadata")
        elif status == "partial":
            if self.shadow_frame is None:
                raise ValueError("partial_requires_shadow_frame")
            has_issue = self.legacy_plan is None or turn_frame_has_invalid_or_missing(
                self.shadow_frame
            )
            if not has_issue:
                raise ValueError("partial_requires_legacy_none_or_invalid_metadata")
        elif status == "not_available":
            if self.legacy_plan is not None or self.shadow_frame is not None:
                raise ValueError("not_available_requires_both_none")
        elif status == "degraded":
            if self.shadow_frame is not None:
                raise ValueError("degraded_forbids_shadow_frame")
        return self
