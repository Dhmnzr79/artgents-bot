"""Typed governed UI action context for target Composer (POST_RETRY3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.target_service_applicability import PatientStage
from contracts.ui_scope_action import ScopeExtent

ComposerActionKind = Literal["ui_scope", "ui_stage"]


class TargetComposerActionContext(BaseModel):
    """Session-bound UI click semantics for Composer; label/продолжить are not authoritative."""

    model_config = ConfigDict(extra="forbid")

    action_kind: ComposerActionKind
    topic: str = Field(..., min_length=1)
    governed_ref: str = Field(..., min_length=1)
    response_stage: str = Field(..., min_length=1)
    extent: ScopeExtent | None = None
    stage: PatientStage | None = None

    @model_validator(mode="after")
    def _kind_fields_match(self) -> TargetComposerActionContext:
        if self.action_kind == "ui_scope":
            if self.extent is None or self.stage is not None:
                raise ValueError("ui_scope_requires_extent_only")
        elif self.action_kind == "ui_stage":
            if self.stage is None or self.extent is not None:
                raise ValueError("ui_stage_requires_stage_only")
        return self
