"""Explicit non-A9 request contract for deterministic target ResponsePolicy S33."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.target_response_spec import (
    CanonicalToken,
    TargetResponseComponent,
    TargetResponseMode,
)


class TargetResponsePolicyRequest(BaseModel):
    """Strict policy inputs supplied by a future authorized upstream boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    response_mode: TargetResponseMode
    service_id: CanonicalToken | None = None
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
        return self
