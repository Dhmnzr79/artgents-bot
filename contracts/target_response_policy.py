"""Explicit non-A9 request contract for deterministic target ResponsePolicy S33."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.target_response_spec import (
    CanonicalToken,
    TargetResponseComponent,
    TargetResponseMode,
)
from contracts.target_response_stage import ResponseStage


class TargetResponsePolicyRequest(BaseModel):
    """Strict policy inputs supplied by a future authorized upstream boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    response_mode: TargetResponseMode
    service_id: CanonicalToken | None = None
    response_stage: ResponseStage | None = None
    scope_price_topic: CanonicalToken | None = None
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    requested_components: tuple[TargetResponseComponent, ...]
    primary_component: TargetResponseComponent | None = None
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False

    @model_validator(mode="after")
    def _valid_component_focus(self) -> "TargetResponsePolicyRequest":
        if self.response_mode in {"clarify", "defer"}:
            if self.primary_component is not None:
                raise ValueError("terminal_primary_component_forbidden")
            return self
        if (
            self.primary_component is not None
            and self.primary_component not in self.requested_components
        ):
            raise ValueError("policy_primary_component_missing")
        if (
            self.primary_component is None
            and "content" in self.requested_components
            and "price" in self.requested_components
        ):
            raise ValueError("policy_followup_source_ambiguous")
        if self.response_stage is not None:
            if self.service_id is not None and self.response_stage not in {
                "concrete_service_price",
                "scoped_family_price",
            }:
                raise ValueError("scope_price_service_id_forbidden")
            if self.scope_price_topic is None and self.response_stage != "concrete_service_price":
                raise ValueError("scope_price_topic_required")
            if self.requested_components != ("price",):
                raise ValueError("scope_price_components_invalid")
            if self.primary_component is not None:
                raise ValueError("scope_price_primary_forbidden")
            if self.response_stage == "stage_clarify" and (
                self.allow_marketing_facts or self.allow_cta
            ):
                raise ValueError("stage_clarify_marketing_forbidden")
        return self
