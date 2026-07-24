"""Canonical target ResponseSpec contract (S32, offline/unwired).

``medical_handoff`` is a mandatory downstream safety boundary: consumers may use only
source-owned general facts and policy-permitted sales material, never diagnosis,
differential diagnosis, personal eligibility, or treatment choice. Manual-contact
hard-stops occur before this contract.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator, model_validator

from contracts.target_response_stage import ResponseStage, is_scope_aware_price_stage


def _canonical_token(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("canonical_token_invalid")
    return value


CanonicalToken = Annotated[str, AfterValidator(_canonical_token)]
TargetResponseMode: TypeAlias = Literal[
    "answer",
    "clarify",
    "defer",
    "medical_handoff",
]
TargetResponseComponent: TypeAlias = Literal["content", "price", "doctors"]
TargetFollowupSource: TypeAlias = Literal["content", "price"]


class TargetResponseSpec(BaseModel):
    """Strict immutable declaration for future response policy consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    response_mode: TargetResponseMode
    service_id: CanonicalToken | None = None
    response_stage: ResponseStage | None = None
    scope_price_topic: CanonicalToken | None = None
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    required_components: tuple[TargetResponseComponent, ...]
    followup_source: TargetFollowupSource | None = None
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False

    @field_validator("allowed_topics", mode="after")
    @classmethod
    def _allowed_topics_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_topic_duplicate")
        return value

    @field_validator("forbidden_topics", mode="after")
    @classmethod
    def _forbidden_topics_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("forbidden_topic_duplicate")
        return value

    @field_validator("required_fact_ids", mode="after")
    @classmethod
    def _required_fact_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("required_fact_id_duplicate")
        return value

    @field_validator("required_components", mode="after")
    @classmethod
    def _required_components_unique(
        cls,
        value: tuple[TargetResponseComponent, ...],
    ) -> tuple[TargetResponseComponent, ...]:
        if len(value) != len(set(value)):
            raise ValueError("required_component_duplicate")
        return value

    @model_validator(mode="after")
    def _consistent_scope_and_payload(self) -> "TargetResponseSpec":
        if set(self.allowed_topics) & set(self.forbidden_topics):
            raise ValueError("response_topic_scope_overlap")
        if self.response_mode in {"answer", "medical_handoff"} and not self.allowed_topics:
            raise ValueError("response_scope_empty")
        if self.response_mode == "answer" and not self.required_components:
            raise ValueError("response_components_empty")
        if self.response_mode in {"clarify", "defer"} and (
            self.required_fact_ids
            or self.required_components
            or self.followup_source is not None
            or self.allow_marketing_facts
            or self.allow_consultation_close
            or self.allow_cta
        ):
            raise ValueError("terminal_response_payload_forbidden")
        if self.followup_source is not None and self.followup_source not in self.required_components:
            raise ValueError("followup_source_component_missing")
        if self.response_stage is not None:
            if self.scope_price_topic is None and self.response_stage != "concrete_service_price":
                raise ValueError("scope_price_topic_required")
            if self.service_id is not None and self.response_stage not in {
                "concrete_service_price",
                "scoped_family_price",
            }:
                raise ValueError("scope_price_service_id_forbidden")
            if self.required_components != ("price",) and self.response_stage in {
                "broad_family_price",
                "scoped_family_price",
                "stage_clarify",
                "data_gap",
            }:
                raise ValueError("scope_price_components_invalid")
            if self.response_stage == "stage_clarify" and (
                self.followup_source is not None
                or self.allow_marketing_facts
                or self.allow_cta
            ):
                raise ValueError("stage_clarify_payload_forbidden")
            if self.response_stage == "broad_family_price" and self.followup_source is not None:
                raise ValueError("broad_family_price_followups_forbidden")
        if self.response_mode == "medical_handoff" and not self.forbidden_topics:
            raise ValueError("medical_forbidden_topics_empty")
        return self
