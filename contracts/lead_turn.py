"""Lead-flow turn classification (active booking, pre-slot)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LeadTurnKind = Literal[
    "slot",
    "meta_pause",
    "meta_cancel",
    "meta_resume",
    "content",
    "booking_date",
    "defer",
    "unclear",
]

LeadContentHint = Literal["price", "contacts", "pain", "generic"]

LeadTurnGrayKind = Literal[
    "meta_pause",
    "meta_cancel",
    "content",
    "defer",
    "unclear",
]


class LeadTurnGrayOutput(BaseModel):
    """LLM gray-zone classifier output (no slot / meta_resume)."""

    model_config = ConfigDict(extra="forbid")

    kind: LeadTurnGrayKind
    content_hint: LeadContentHint | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class LeadTurnDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: LeadTurnKind
    content_hint: LeadContentHint | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    slot_value: str | None = None
