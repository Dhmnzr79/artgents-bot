from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DialogFocusAttribute = Literal[
    "price",
    "duration",
    "pain",
    "warranty",
    "doctor",
    "payment",
    "included",
    "general",
    "overview",
    "unknown",
]

DialogFocusSource = Literal[
    "last_subject",
    "legacy_session",
    "explicit_service",
    "llm_gray",
    "none",
]


class DialogFocusDecision(BaseModel):
    """Per-turn dialog focus snapshot. It describes context; it is not a router."""

    model_config = ConfigDict(extra="forbid")

    focus_service_id: str | None = None
    focus_topic: str | None = None
    focus_label: str | None = None
    focus_turn_age: int | None = None
    attribute: DialogFocusAttribute = "unknown"
    explicit_topic_change: bool = False
    resolved_service_id: str | None = None
    source: DialogFocusSource = "none"
    used_llm: bool = False
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reason: str = ""
    query_rewrite: str | None = None


class DialogFocusGrayOutput(BaseModel):
    """Bounded LLM output for short gray-zone follow-ups."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["follow_up", "unclear"]
    attribute: Literal["general"] = "general"
    query_rewrite: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
