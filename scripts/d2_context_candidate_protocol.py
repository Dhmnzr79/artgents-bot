"""Isolated 3B native output candidate. Never imported by the bot runtime.

No conversion to the old operations, publication, routing or pending state.
Only the independent volume value type is shared with the baseline.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from contracts.d2_dialogue_result import DiscussionVolume


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Ref = Annotated[str, Field(pattern=r"^(service|topic):[^:\s]+$|^unresolved$")]
ServiceRef = Annotated[str, Field(pattern=r"^service:[^:\s]+$")]
Text = Annotated[str, Field(min_length=1, max_length=4000),
                 AfterValidator(lambda value: value if value.strip() else _blank())]


def _blank():
    raise ValueError("nonblank_text_required")


class ServiceClarification(Closed):
    missing: Literal["service"]
    choices: tuple[ServiceRef, ...] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("duplicate_choices")
        return self


class TermClarification(Closed):
    missing: Literal["term"]
    choices: tuple[str, ...] = Field(default=(), max_length=0)


class ParameterClarification(Closed):
    missing: Literal["extent", "jaw", "stage"]
    choices: tuple[str, ...] = Field(default=(), max_length=0)


Meaning = Union[ServiceClarification, TermClarification]
Clarification = Union[ServiceClarification, TermClarification, ParameterClarification]


class Scoped(Closed):
    target: Ref | None = None
    volume: DiscussionVolume | None = None

    @model_validator(mode="after")
    def pending_target(self):
        clarification = getattr(self, "clarification", None)
        if clarification and clarification.missing == "service" and self.target not in {None, "unresolved"}:
            raise ValueError("service_already_identified")
        return self


class PolicyFields(Scoped):
    age_group: Literal["adult", "child", "unknown"] = "unknown"
    context: Literal["current_care", "general_information", "past_history", "unknown"] = "general_information"
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"


class Price(PolicyFields):
    kind: Literal["price"]
    brand_id: str | None = None
    clarification: Meaning | None = None

    @model_validator(mode="after")
    def identified_price(self):
        if self.clarification is not None and self.target not in {None, "unresolved"}:
            raise ValueError("price_already_identified")
        return self


class ContentFields(Scoped):
    kind: Literal["content"]
    content_ref: str | None = None
    content_section_refs: tuple[str, ...] = ()
    brand_id: str | None = None

    @model_validator(mode="after")
    def source_binding(self):
        if self.content_ref is not None and (
            not self.content_ref.endswith(".md") or any(c in self.content_ref for c in ("/", "\\", ".."))
        ):
            raise ValueError("invalid_content_ref")
        if self.content_section_refs and self.content_ref is None:
            raise ValueError("section_without_document")
        if len(set(self.content_section_refs)) != len(self.content_section_refs):
            raise ValueError("duplicate_sections")
        return self


class CompletedContent(ContentFields):
    content_text: Text | None = None
    pending_question: None = None
    clarification: None = None


class PendingContent(ContentFields):
    pending_question: Text
    clarification: Clarification
    content_text: None = None


class Detail(Scoped):
    kind: Literal["price_detail"]
    brand_id: str | None = None
    price_detail_aspect: Literal["includes", "stages"]
    price_detail_offer_id: str | None = None
    price_detail_offer_ordinal: int | None = Field(default=None, ge=1, strict=True)
    clarification: Clarification | None = None

    @model_validator(mode="after")
    def selector(self):
        if self.price_detail_offer_id is not None and self.price_detail_offer_ordinal is not None:
            raise ValueError("conflicting_offer_selectors")
        return self


class Contact(Closed):
    kind: Literal["contact"]
    contact_fields: tuple[Literal["contact_address", "contact_phone", "contact_whatsapp",
                                  "contact_hours", "contact_parking", "contacts"], ...] = Field(min_length=1)
    contact_branch_id: str | None = None


class Doctors(Closed):
    kind: Literal["doctors"]
    target: ServiceRef


class Policy(PolicyFields):
    kind: Literal["clinic_policy"]
    policy_ids: tuple[str, ...] = ()


class Booking(PolicyFields):
    kind: Literal["booking"]
    policy_ids: tuple[str, ...] = ()


class Commercial(Scoped):
    kind: Literal["commercial_fact"]
    target: Annotated[str, Field(pattern=r"^(service|topic):[^:\s]+$|^(clinic|unresolved)$")]
    fact_ids: tuple[str, ...] = ()
    promotion_scope: Literal["none", "general", "service", "shown"] = "none"
    clarification: Meaning | None = None

    @model_validator(mode="after")
    def scope_rules(self):
        if not self.fact_ids and self.promotion_scope == "none":
            raise ValueError("commercial_task_required")
        if self.clarification is not None:
            if self.target != "unresolved":
                raise ValueError("pending_commercial_scope")
        elif self.target == "unresolved":
            raise ValueError("completed_commercial_scope")
        if self.clarification is None and self.promotion_scope == "service" and not self.target.startswith("service:"):
            raise ValueError("promotion_service_required")
        return self


class OffTopic(Closed):
    kind: Literal["off_topic"]


Block = Union[Price, CompletedContent, PendingContent, Detail, Contact, Doctors,
              Policy, Booking, Commercial, OffTopic]


class Dialogue(Closed):
    outcome: Literal["dialogue"]
    blocks: tuple[Block, ...] = Field(min_length=1)


class Admin(Closed):
    outcome: Literal["admin"]
    blocks: tuple[Block, ...] = Field(default=(), max_length=0)


REPLY = TypeAdapter(Union[Dialogue, Admin])


def schema():
    return REPLY.json_schema()


def parse(raw, *, service_ids, active_ids, topic_ids, document_sections):
    """Validate candidate directly; no raw repair or old-domain reconstruction."""
    from core.one_call_envelope_protocol import _loads_strict_json_object
    result = REPLY.validate_python(_loads_strict_json_object(raw))
    for block in result.blocks:
        target = getattr(block, "target", None)
        if target and target not in {"clinic", "unresolved"}:
            prefix, entity = target.split(":", 1)
            allowed = service_ids if prefix == "service" else topic_ids
            if entity not in allowed:
                raise ValueError("unknown_target")
        if isinstance(block, Doctors) and block.target[8:] not in active_ids:
            raise ValueError("inactive_doctors_service")
        clarification = getattr(block, "clarification", None)
        if isinstance(clarification, ServiceClarification) and any(c[8:] not in active_ids for c in clarification.choices):
            raise ValueError("inactive_clarification_choice")
        ref = getattr(block, "content_ref", None)
        if ref is not None:
            if ref not in document_sections:
                raise ValueError("unknown_document")
            if any(s not in document_sections[ref] for s in block.content_section_refs):
                raise ValueError("unknown_document_section")
    return result
