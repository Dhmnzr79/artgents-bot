from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PriceOfferUnit = Literal["one_tooth", "one_implant", "one_site", "jaw", "full_mouth"]


class PaymentStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    amount: int = Field(..., ge=0)


class PriceOffer(BaseModel):
    """Structured price package for one service variant (see clients/{id}/price_offers.json)."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(..., min_length=1)
    service_id: str = Field(..., min_length=1)
    unit: PriceOfferUnit
    brand: str = Field(..., min_length=1)
    brand_label: str = Field(..., min_length=1)
    recommended: bool = False
    total: int = Field(..., ge=0)
    currency: Literal["RUB"] = "RUB"
    payment_stages: list[PaymentStage] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)


class PriceOffersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    offers: list[PriceOffer] = Field(default_factory=list)
