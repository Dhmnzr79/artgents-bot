"""Single D2 semantic result: ordered, narrow operations and local clarification.

Read-only scope projections below expose one target to domain helpers. They
never infer meaning from text/context and are not additional stored fields.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServiceTarget(Closed):
    type: Literal["service"]
    id: str = Field(min_length=1)


class TopicTarget(Closed):
    type: Literal["topic"]
    id: str = Field(min_length=1)


class UnresolvedTarget(Closed):
    type: Literal["unresolved"]


class ClinicTarget(Closed):
    """Explicit clinic-wide commercial meaning, never an omitted target."""
    type: Literal["clinic"]


Target = Annotated[Union[ServiceTarget, TopicTarget, UnresolvedTarget], Field(discriminator="type")]


class Operation(Closed):
    request_id: str = Field(pattern=r"^r[1-9][0-9]*$")


class DiscussionVolume(Closed):
    """Parameters of the current discussion, without patient ownership."""
    extent: Literal["unknown", "one_tooth", "few_teeth", "full_arch"] = "unknown"
    tooth_count: int | None = Field(default=None, strict=True, ge=1)
    jaw: Literal["unknown", "upper", "lower", "both"] = "unknown"

    @model_validator(mode="after")
    def count_matches_extent(self):
        if self.extent == "unknown" and self.tooth_count is not None:
            raise ValueError("discussion_unknown_extent_forbids_count")
        if self.extent == "one_tooth" and self.tooth_count not in {None, 1}:
            raise ValueError("discussion_count_extent_conflict")
        if self.extent == "few_teeth" and self.tooth_count == 1:
            raise ValueError("discussion_count_extent_conflict")
        return self


class DiscussionScope(Closed):
    """Frozen parameters of one discussed option, shared by receipts and input."""
    target: Annotated[Union[ServiceTarget, TopicTarget], Field(discriminator="type")]
    volume: DiscussionVolume | None = None
    brand_id: str | None = None

    @property
    def service_id(self):
        return self.target.id if isinstance(self.target, ServiceTarget) else None

    @property
    def topic_id(self):
        return self.target.id if isinstance(self.target, TopicTarget) else None


class ScopedOperation(Operation):
    target: Target | None = None
    volume: DiscussionVolume | None = None

    @property
    def service_id(self):
        return self.target.id if isinstance(self.target, ServiceTarget) else None

    @property
    def topic_id(self):
        return self.target.id if isinstance(self.target, TopicTarget) else None

    @model_validator(mode="after")
    def service_clarification_target(self):
        clarification = getattr(self, "clarification", None)
        if clarification is not None and clarification.missing == "service" and (
            self.target is not None and not isinstance(self.target, UnresolvedTarget)
        ):
            raise ValueError("clarify_service_already_known")
        return self


class PolicyScope(ScopedOperation):
    age_group: Literal["adult", "child", "unknown"] = "unknown"
    context: Literal["current_care", "general_information", "past_history", "unknown"] = "general_information"


class PriceOperation(PolicyScope):
    kind: Literal["price"]
    brand_id: str | None = None
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"


class ExplanationFields(ScopedOperation):
    # Keep the domain spelling 'content'; it is a single connected explanation,
    # not a mandatory classification of each sentence/question.
    kind: Literal["content"]
    content_ref: str | None = None
    content_section_refs: tuple[str, ...] = ()
    brand_id: str | None = None

    @model_validator(mode="after")
    def source_binding(self):
        if self.content_ref is not None and (
            not self.content_ref.endswith(".md") or "/" in self.content_ref
            or "\\" in self.content_ref or ".." in self.content_ref
        ):
            raise ValueError("content_ref_invalid")
        if self.content_section_refs and self.content_ref is None:
            raise ValueError("content_section_refs_forbidden")
        if len(set(self.content_section_refs)) != len(self.content_section_refs):
            raise ValueError("content_section_refs_duplicate")
        return self


class ExplanationOperation(ExplanationFields):
    """Completed explanation; unfinished questions cannot occupy this field."""
    content_text: str = Field(min_length=1, max_length=4000)


class DetailOperation(ScopedOperation):
    brand_id: str | None = None
    kind: Literal["price_detail"]
    price_detail_aspect: Literal["includes", "stages"]
    price_detail_offer_id: str | None = None
    price_detail_offer_ordinal: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def selector(self):
        if self.price_detail_offer_id is not None and self.price_detail_offer_ordinal is not None:
            raise ValueError("price_detail_selector_conflict")
        return self


class ContactOperation(Operation):
    kind: Literal["contact"]
    contact_fields: tuple[Literal["contact_address", "contact_phone", "contact_whatsapp", "contact_hours", "contact_parking", "contacts"], ...] = Field(min_length=1)
    contact_branch_id: str | None = None


class DoctorsOperation(Operation):
    kind: Literal["doctors"]
    target: ServiceTarget

    @property
    def service_id(self):
        return self.target.id


class PolicyOperation(PolicyScope):
    kind: Literal["clinic_policy"]
    policy_ids: tuple[str, ...] = ()
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"


class BookingOperation(PolicyScope):
    kind: Literal["booking"]
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"
    policy_ids: tuple[str, ...] = ()


class CommercialFields(ScopedOperation):
    kind: Literal["commercial_fact"]
    fact_ids: tuple[str, ...] = ()
    promotion_scope: Literal["none", "general", "service", "shown"] = "none"

    @model_validator(mode="after")
    def commercial_task_required(self):
        if not self.fact_ids and self.promotion_scope == "none":
            raise ValueError("commercial_task_required")
        return self


class CommercialOperation(CommercialFields):
    target: Annotated[Union[ServiceTarget, TopicTarget, ClinicTarget], Field(discriminator="type")]

    @model_validator(mode="after")
    def promotion_service_required(self):
        if self.promotion_scope == "service" and self.service_id is None:
            raise ValueError("d2_promotion_service_required")
        return self


class OffTopicOperation(Operation):
    """Existing polite clinic-boundary response, not a medical terminal."""
    kind: Literal["off_topic"]


class ServiceClarification(Closed):
    missing: Literal["service"]
    choices: tuple[str, ...] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique_choices(self):
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("clarify_service_options_invalid")
        return self


class TermClarification(Closed):
    missing: Literal["term"]
    choices: tuple[str, ...] = Field(default=(), max_length=0)


class ParameterClarification(Closed):
    missing: Literal["extent", "jaw", "stage"]
    choices: tuple[str, ...] = Field(default=(), max_length=0)


MeaningClarification = Annotated[Union[ServiceClarification, TermClarification], Field(discriminator="missing")]
Clarification = Annotated[Union[ServiceClarification, TermClarification, ParameterClarification], Field(discriminator="missing")]


class PendingPriceOperation(PriceOperation):
    target: UnresolvedTarget | None = None
    clarification: MeaningClarification


class PendingExplanationOperation(ExplanationFields):
    """An ordinary question that still requires clarification."""
    pending_question: str = Field(min_length=1, max_length=4000)
    clarification: Clarification


class PendingDetailOperation(DetailOperation):
    clarification: Clarification


class PendingCommercialOperation(CommercialFields):
    target: UnresolvedTarget
    clarification: MeaningClarification


PendingOperation = Annotated[Union[PendingPriceOperation, PendingExplanationOperation,
    PendingDetailOperation, PendingCommercialOperation], Field(discriminator="kind")]


# A storage boundary on the same operation types, not a persisted wrapper.
ClarifiedOperation = PendingOperation


Block = Union[PriceOperation, PendingPriceOperation, ExplanationOperation,
    PendingExplanationOperation, DetailOperation, PendingDetailOperation,
    ContactOperation, PolicyOperation, BookingOperation, CommercialOperation, PendingCommercialOperation,
    OffTopicOperation, DoctorsOperation]


class D2DialogueResult(Closed):
    outcome: Literal["dialogue", "admin"]
    blocks: tuple[Block, ...] = ()

    @model_validator(mode="after")
    def shape(self):
        if self.outcome == "admin" and self.blocks:
            raise ValueError("admin_blocks_forbidden")
        if self.outcome == "dialogue" and not self.blocks:
            raise ValueError("dialogue_blocks_required")
        if len({b.request_id for b in self.blocks}) != len(self.blocks):
            raise ValueError("request_id_duplicate")
        return self

    @property
    def requests(self):
        """One ordered domain view, no reclassification or copied payload."""
        return self.blocks

class AuthorizedExplanationOperation(ExplanationFields):
    """Server-owned source/scope after a verified click; never ordinary output."""
    pending_question: str = Field(min_length=1, max_length=4000)


class D2ExplanationTask(Closed):
    outcome: Literal["dialogue"] = "dialogue"
    blocks: tuple[AuthorizedExplanationOperation, ...] = Field(min_length=1)


def validate_d2_payload(payload: dict, *, active_service_ids: frozenset[str], known_task=None):
    if known_task is not None:
        expected = known_task.blocks
        items = payload.get("explanations")
        if set(payload) != {"explanations"} or not isinstance(items, list) or len(items) != len(expected):
            raise ValueError("known_task_explanations_required")
        completed = []
        for original, item in zip(expected, items):
            if not isinstance(item, dict) or set(item) - {"request_id", "content_text"} or item.get("request_id") != original.request_id:
                raise ValueError("known_task_explanation_invalid")
            if not isinstance(item.get("content_text"), str) or not item["content_text"].strip():
                raise ValueError("known_task_explanation_text_required")
            values = original.model_dump()
            values.pop("pending_question")
            values.update(item)
            completed.append(ExplanationOperation.model_validate(values))
        result = D2DialogueResult.model_validate({
            "outcome": known_task.outcome,
            "blocks": tuple(completed),
        })
    else:
        result = D2DialogueResult.model_validate(payload)
    for block in result.blocks:
        if isinstance(block, DoctorsOperation) and block.service_id not in active_service_ids:
            raise ValueError("doctors_service_not_active")
        clarification = getattr(block, "clarification", None)
        if clarification is not None and any(c not in active_service_ids for c in clarification.choices):
            raise ValueError("clarify_service_not_active")
    return result
