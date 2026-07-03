from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PriceBrandAliasesFile(BaseModel):
    """Optional client pack file: clients/{id}/price_brand_aliases.json"""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    brand_aliases: dict[str, str] = Field(default_factory=dict)
