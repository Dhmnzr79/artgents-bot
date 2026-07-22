"""Explicit policy envelope for TurnFrame dispatch (S41, offline/unwired)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.target_response_spec import CanonicalToken


class TargetTurnFramePolicyEnvelope(BaseModel):
    """Caller-owned policy and confidence floors; TurnFrame never supplies these fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    boundary_decision: Literal["none", "medical_handoff"]
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False
    min_topic_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_service_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_intent_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
