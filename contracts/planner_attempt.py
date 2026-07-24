"""Planner attempt envelope for single-call frame-first outcome (C2b)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.turn_frame import PatientScopeFrameMeta, TurnFrame, TurnFrameMeta

FrameAttemptStatus = Literal["ok", "partial", "not_available", "degraded"]

# Historical alias for offline eval contracts.
ShadowAttemptStatus = FrameAttemptStatus


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

    frame: TurnFrame | None
    status: FrameAttemptStatus

    @property
    def shadow_frame(self) -> TurnFrame | None:
        """Historical alias for A9/offline eval readers."""
        return self.frame

    @property
    def shadow_status(self) -> FrameAttemptStatus:
        """Historical alias for A9/offline eval readers."""
        return self.status

    @model_validator(mode="after")
    def _status_invariants(self) -> "PlannerAttempt":
        status = self.status
        if status == "ok":
            if self.frame is None:
                raise ValueError("ok_requires_frame")
            if turn_frame_has_invalid_or_missing(self.frame):
                raise ValueError("ok_forbids_invalid_or_missing_metadata")
        elif status == "partial":
            if self.frame is None:
                raise ValueError("partial_requires_frame")
            if not turn_frame_has_invalid_or_missing(self.frame):
                raise ValueError("partial_requires_invalid_or_missing_metadata")
        elif status == "not_available":
            if self.frame is not None:
                raise ValueError("not_available_forbids_frame")
        elif status == "degraded":
            if self.frame is not None:
                raise ValueError("degraded_forbids_frame")
        return self
