"""Bounded LLM output for composite aspect planning (composer roadmap phase 1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.answer_plan import AspectKind


class AspectPlannerOutput(BaseModel):
    """Structured aspects subset for one user question."""

    model_config = ConfigDict(extra="forbid")

    aspects: list[AspectKind] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
