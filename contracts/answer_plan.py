from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AspectKind = Literal[
    "price",
    "payment",
    "warranty",
    "pain",
    "included",
    "duration",
    "comparison",
    "stages",
    "overview",
]

PlanAppendKind = Literal["price_offer", "payment_terms", "boundary"]

PlanRiskKind = Literal["price", "warranty", "pain", "included"]


class AnswerPlan(BaseModel):
    """Deterministic answer plan (stage 4b planner-lite). Not a route decision."""

    model_config = ConfigDict(extra="forbid")

    aspects: list[AspectKind] = Field(default_factory=list)
    primary_aspect: AspectKind | None = None
    service_id: str | None = None
    topic: str | None = None
    primary_chunk_ref: str | None = None
    append: list[PlanAppendKind] = Field(default_factory=list)
    risk: list[PlanRiskKind] = Field(default_factory=list)
    suppressed_append: list[PlanAppendKind] = Field(default_factory=list)
    plan_reason: str = ""
