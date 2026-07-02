from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ServiceSelection(BaseModel):
    """LLM service pick for composer price card (null service_id = group/defer)."""

    model_config = ConfigDict(extra="forbid")

    service_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
