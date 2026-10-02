"""Single D2 semantic result: ordered, narrow operations and local clarification.

Read-only scope projections below expose one target to domain helpers. They
never infer meaning from text/context and are not additional stored fields.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from contracts.request_understanding import (
    RequestUnderstandingSubject, RequestTreatmentSituation,
)


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


Target = Annotated[Union[ServiceTarget, TopicTarget, UnresolvedTarget], Field(discriminator="type")]


class Operation(Closed):
    request_id: str = Field(pattern=r"^r[1-9][0-9]*$")


class ScopedOperation(Operation):
    target: Target | None = None
    subject: RequestUnderstandingSubject | None = None
    situation: RequestTreatmentSituation | None = None
    context: Literal["current_care", "general_information", "past_history", "unknown"] = "general_information"

    @property
    def service_id(self):
        return self.target.id if isinstance(self.target, ServiceTarget) else None

    @property
    def topic_id(self):
        return self.target.id if isinstance(self.target, TopicTarget) else None

    @property
    def subject_id(self):
        return self.subject.subject_id if self.subject else None

    @model_validator(mode="after")
    def situation_owner(self):
        if self.situation is not None and self.situation.continuity == "same" and self.subject is None:
            raise ValueError("treatment_same_requires_subject")
        return self


class PriceOperation(ScopedOperation):
    kind: Literal["price"]
    brand_id: str | None = None
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"


class ExplanationOperation(ScopedOperation):
    # Keep the domain spelling 'content'; it is a single connected explanation,
    # not a mandatory classification of each sentence/question.
    kind: Literal["content"]
    content_text: str = Field(min_length=1, max_length=4000)
    content_realization: Literal["model_prose", "authored"] = "model_prose"
    content_ref: str | None = None
    content_section_refs: tuple[str, ...] = ()
    content_fallback_section_ref: str | None = None
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
        if self.content_fallback_section_ref is not None and (
            self.content_realization != "model_prose"
            or self.content_fallback_section_ref not in self.content_section_refs
        ):
            raise ValueError("content_fallback_not_grounded")
        return self


class DetailOperation(ScopedOperation):
    kind: Literal["price_detail"]
    price_detail_aspect: Literal["includes", "stages"]
    price_detail_offer_id: str | None = None
    price_detail_offer_ordinal: int | None = Field(default=None, ge=1)

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


class PolicyOperation(ScopedOperation):
    kind: Literal["clinic_policy"]
    policy_ids: tuple[str, ...] = ()
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"


class BookingOperation(ScopedOperation):
    kind: Literal["booking"]
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"
    policy_ids: tuple[str, ...] = ()


class CommercialOperation(ScopedOperation):
    kind: Literal["commercial_fact"]
    fact_ids: tuple[str, ...] = ()
    promotion_scope: Literal["none", "general", "service", "shown"] = "none"


class OffTopicOperation(Operation):
    """Existing polite clinic-boundary response, not a medical terminal."""
    kind: Literal["off_topic"]


PendingOperation = Annotated[Union[PriceOperation, ExplanationOperation, DetailOperation], Field(discriminator="kind")]


class UnresolvedPriceOperation(PriceOperation):
    """Only an unidentified price subject can wait for model clarification."""
    target: UnresolvedTarget | None = None


MeaningPendingOperation = Annotated[Union[UnresolvedPriceOperation, ExplanationOperation, DetailOperation], Field(discriminator="kind")]
ParameterPendingOperation = Annotated[Union[ExplanationOperation, DetailOperation], Field(discriminator="kind")]


class MeaningClarifyTask(Closed):
    missing: Literal["service", "term"]
    operation: MeaningPendingOperation


class ParameterClarifyTask(Closed):
    missing: Literal["extent", "jaw", "stage"]
    operation: ParameterPendingOperation


ClarifyTask = Annotated[Union[MeaningClarifyTask, ParameterClarifyTask], Field(discriminator="missing")]
CLARIFY_TASK_ADAPTER = TypeAdapter(ClarifyTask)


class ClarificationOperation(Operation):
    kind: Literal["clarification"]
    # Only the narrow subclasses below are accepted by the model contract.
    choices: tuple[str, ...] = ()

    @model_validator(mode="after")
    def local_task(self):
        if self.request_id != self.operation.request_id:
            raise ValueError("clarification_identity_mismatch")
        if self.missing == "service":
            if not 2 <= len(self.choices) <= 3 or len(set(self.choices)) != len(self.choices):
                raise ValueError("clarify_service_options_invalid")
            if self.operation.target is not None and not isinstance(self.operation.target, UnresolvedTarget):
                raise ValueError("clarify_service_already_known")
        elif self.choices:
            raise ValueError("clarify_options_forbidden")
        return self


class MeaningClarificationOperation(MeaningClarifyTask, ClarificationOperation):
    pass


class ParameterClarificationOperation(ParameterClarifyTask, ClarificationOperation):
    pass


Clarification = Annotated[Union[MeaningClarificationOperation, ParameterClarificationOperation], Field(discriminator="missing")]


Block = Annotated[Union[PriceOperation, ExplanationOperation, DetailOperation,
    ContactOperation, PolicyOperation, BookingOperation, CommercialOperation,
    Clarification, OffTopicOperation, DoctorsOperation], Field(discriminator="kind")]


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
        if sum(getattr(b, "situation", None) is not None for b in self.requests) > 1:
            raise ValueError("treatment_multiple_situations")
        subjects = {}
        for block in self.requests:
            subject = getattr(block, "subject", None)
            if subject is not None:
                if subject.subject_id in subjects and subjects[subject.subject_id] != subject:
                    raise ValueError("subject_binding_conflict")
                subjects[subject.subject_id] = subject
        return self

    @property
    def requests(self):
        """One ordered domain view, no reclassification or copied payload."""
        return tuple(b.operation if isinstance(b, ClarificationOperation) else b for b in self.blocks)

    @property
    def subjects(self):
        return tuple({b.subject.subject_id: b.subject for b in self.requests
                      if getattr(b, "subject", None) is not None}.values())


def validate_d2_payload(payload: dict, *, active_service_ids: frozenset[str], known_task=None):
    if known_task is not None:
        expected = tuple(b for b in known_task.blocks if isinstance(b, ExplanationOperation))
        items = payload.get("explanations")
        if set(payload) != {"explanations"} or not isinstance(items, list) or len(items) != len(expected):
            raise ValueError("known_task_explanations_required")
        replacements = {}
        for original, item in zip(expected, items):
            if not isinstance(item, dict) or set(item) - {"request_id", "content_text", "content_realization"} or item.get("request_id") != original.request_id:
                raise ValueError("known_task_explanation_invalid")
            if not isinstance(item.get("content_text"), str) or not item["content_text"].strip():
                raise ValueError("known_task_explanation_text_required")
            values = original.model_dump()
            values.update(item)
            values.setdefault("content_realization", "model_prose")
            if "content_realization" not in item:
                values["content_realization"] = "model_prose"
            replacements[original.request_id] = ExplanationOperation.model_validate(values)
        result = known_task.model_copy(update={"blocks": tuple(replacements.get(b.request_id, b) for b in known_task.blocks)})
    else:
        result = D2DialogueResult.model_validate(payload)
    for block in result.blocks:
        if isinstance(block, DoctorsOperation) and block.service_id not in active_service_ids:
            raise ValueError("doctors_service_not_active")
        if isinstance(block, ClarificationOperation) and any(c not in active_service_ids for c in block.choices):
            raise ValueError("clarify_service_not_active")
    return result
