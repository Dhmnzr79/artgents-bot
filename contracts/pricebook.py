"""PriceBook v2 — target client-pack schema (see docs/PRICEBOOK_V2.md).

Runtime: `core/pricebook_loader.py` + `core/price_answer_assembler.py` (canonical pricebook only).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.price_offer import PaymentStage, PriceOfferUnit

PriceModel = Literal["simple", "complex"]
PriceType = Literal["fixed", "from"]
FactUsableIn = Literal["price_answer", "payment_question", "retrieval", "commercial_answer"]
FollowupAction = Literal["price_service", "price_aspect", "md_ref", "price_group"]
FactKind = Literal["payment", "benefit", "promo", "warranty"]
FactRenderMode = Literal["strict", "natural"]


class PricingFact(BaseModel):
    """Reusable semantic fact — canonical meaning, not always verbatim output."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    kind: FactKind
    text_fact: str = Field(..., min_length=1)
    render_mode: FactRenderMode = "natural"
    detail_ref: str | None = None
    followup_label: str | None = None
    usable_in: list[FactUsableIn] = Field(default_factory=list)
    active_until: str | None = None


class PricingFactsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    facts: dict[str, PricingFact] = Field(default_factory=dict)


class SimplePrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_type: PriceType
    value: int = Field(..., ge=0)
    currency: Literal["RUB"] = "RUB"
    note: str | None = None


class ServicePromo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    active_until: str | None = None


class PriceFollowup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1)
    action: FollowupAction
    # price_service
    service_id: str | None = None
    # price_aspect
    aspect: Literal["includes", "excludes", "stages", "overview"] | None = None
    # md_ref / detail
    ref: str | None = None
    detail_ref: str | None = None
    # price_group
    group_id: str | None = None


class PriceVariant(BaseModel):
    """Complex offer row — aligned with contracts.price_offer.PriceOffer."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1)
    brand_label: str = Field(..., min_length=1)
    brand_group: str | None = None
    unit: PriceOfferUnit
    total: int = Field(..., ge=0)
    currency: Literal["RUB"] = "RUB"
    recommended: bool = False
    payment_stages: list[PaymentStage] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)


class PricebookServiceEntry(BaseModel):
    """One moderatable unit — simple or complex price for a catalog service_id."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., min_length=1)
    price_model: PriceModel
    display_name: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    default_unit: PriceOfferUnit | None = None
    price: SimplePrice | None = None
    variants: list[PriceVariant] = Field(default_factory=list)
    promo: ServicePromo | None = None
    fact_refs: list[str] = Field(default_factory=list)
    followups: list[PriceFollowup] = Field(default_factory=list)
    cta_key: str | None = None
    intro_text: str | None = None


class GroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    unit_hint: PriceOfferUnit | None = None
    from_total: int | None = Field(default=None, ge=0)


class PricebookGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1)
    overview_prompt: str | None = None
    unit_filter: PriceOfferUnit | None = None
    members: list[GroupMember] = Field(default_factory=list)


class PricebookManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    groups: dict[str, PricebookGroup] = Field(default_factory=dict)


# --- Planner / Assembler (runtime targets, not persisted in pack) ---

PriceScenario = Literal[
    "simple",  # S1
    "simple_with_followup",  # S2
    "overview",  # S3
    "complex",  # S4
    "unit_group",  # S5
    "brand_filter",  # S6
    "aspect_followup",  # S7
]

AnswerBlockKind = Literal[
    "intro",
    "price_line",
    "price_table",
    "mini_summary",
    "stages",
    "includes",
    "excludes",
    "promo_slot",
    "fact_refs",
    "closer",
    "followups",
]


class PriceAnswerPlan(BaseModel):
    """Output of PricePlanner — input to PriceAnswerAssembler."""

    model_config = ConfigDict(extra="forbid")

    scenario: PriceScenario
    service_id: str | None = None
    group_id: str | None = None
    unit: PriceOfferUnit | None = None
    brand_filter: str | None = None
    brand_group: str | None = None
    aspect: Literal["includes", "excludes", "stages", "overview"] | None = None
    blocks: list[AnswerBlockKind] = Field(default_factory=list)
    fact_refs: list[str] = Field(default_factory=list)
    followups: list[PriceFollowup] = Field(default_factory=list)
    llm_intro: bool = False
    llm_closer: bool = False
