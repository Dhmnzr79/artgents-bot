from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ServiceStatus = Literal["found", "ambiguous", "not_found", "not_offered"]
PriceStatus = Literal["available", "not_available", "not_requested"]
ResolutionReason = Literal[
    "matched_service_but_no_price",
    "service_not_found",
    "low_match_score",
    "continuation_no_context",
    "not_offered",
    "price_available",
]
ContentSnippetSource = Literal["korotko", "facts", "title_only"]


class ServiceResolution(BaseModel):
    """Catalog + price resolution for price_lookup / clarify paths."""

    model_config = ConfigDict(extra="forbid")

    service_status: ServiceStatus
    price_status: PriceStatus
    resolution_reason: ResolutionReason
    matched_service_id: str | None = None
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    content_snippet_source: ContentSnippetSource | None = None
