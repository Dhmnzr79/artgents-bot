"""Answer packet snapshot (composer roadmap phase 0 — observability only)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.answer_plan import AspectKind, PlanAppendKind

PacketCardKind = Literal[
    "content",
    "price",
    "promo",
    "payment",
    "warranty",
    "cta",
    "buttons",
]

PacketSnapshotStage = Literal["plan", "apply", "assembled"]


class PromoDecisionRecord(BaseModel):
    """Telemetry for marketing gate on promo facts (phase 2 assembler)."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    allowed: bool
    reason: str
    promo_key: str | None = None
    aspect: str | None = None


class PacketCard(BaseModel):
    """One allowed material slot in the answer packet (structure, not wording)."""

    model_config = ConfigDict(extra="forbid")

    aspect: AspectKind | None = None
    kind: PacketCardKind
    source_ref: str | None = None
    fact_id: str | None = None
    promo_decision: str | None = None
    cta_key: str | None = None
    button_refs: list[str] = Field(default_factory=list)
    included_reason: str | None = None
    suppressed_reason: str | None = None


class AnswerPacketSnapshot(BaseModel):
    """Deterministic packet snapshot for telemetry and eval (phase 0: derived from AnswerPlan)."""

    model_config = ConfigDict(extra="forbid")

    cards: list[PacketCard] = Field(default_factory=list)
    service_id: str | None = None
    topic: str | None = None
    primary_aspect: AspectKind | None = None
    plan_reason: str = ""
    snapshot_stage: PacketSnapshotStage = "plan"
    suppressed_append: list[PlanAppendKind] = Field(default_factory=list)
    promo_decisions: list[PromoDecisionRecord] = Field(default_factory=list)
