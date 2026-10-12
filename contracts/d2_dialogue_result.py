"""Single D2 semantic result: ordered, narrow operations and local clarification.

Read-only scope projections below expose one target to domain helpers. They
never infer meaning from text/context and are not additional stored fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

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
    option_id: str | None = Field(default=None, strict=True, min_length=1, description="Named variant ID from this service's catalog; omit when no variant is specified.")
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"
    clarification: MeaningClarification | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def price_form(self):
        if self.option_id is not None and not isinstance(self.target, ServiceTarget):
            raise ValueError("price_option_service_required")
        if "clarification" in self.model_fields_set and self.clarification is None:
            raise ValueError("clarification_required")
        if self.clarification is not None and self.target is not None and not isinstance(self.target, UnresolvedTarget):
            raise ValueError("clarify_price_already_known")
        return self


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
    """Published prose, including natural questions to the user."""
    content_text: str = Field(min_length=1)


class DetailOperation(ScopedOperation):
    """Server-only execution of a verified card button; absent from model output."""
    brand_id: str | None = None
    kind: Literal["price_detail"]
    price_detail_aspect: Literal["includes", "stages"]


class ContactOperation(Operation):
    kind: Literal["contact"]
    contact_fields: tuple[Literal["contact_address", "contact_phone", "contact_whatsapp", "contact_hours", "contact_parking", "contacts"], ...] = Field(min_length=1)
    contact_branch_id: str | None = None


class BookingOperation(PolicyScope):
    kind: Literal["booking"]
    payment_scheme: Literal["oms", "dms", "self_pay", "unspecified"] = "unspecified"
    payment_scheme_intent: Literal["eligibility_question", "requested_payment", "not_requested", "unspecified"] = "unspecified"
    policy_ids: tuple[str, ...] = ()


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


MeaningClarification = Annotated[Union[ServiceClarification, TermClarification], Field(discriminator="missing")]


PriceOperation.model_rebuild()


def _require_pending_operation(operation):
    """The existing storage slot holds an unfinished operation only."""
    if operation.clarification is None:
        raise ValueError("clarify_task_requires_clarification")
    return operation


ClarifiedOperation = Annotated[
    PriceOperation, AfterValidator(_require_pending_operation),
]


Block = Annotated[Union[PriceOperation, ExplanationOperation,
    ContactOperation, BookingOperation,
    OffTopicOperation], Field(discriminator="kind")]


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


class D2ExplanationReplyItem(Operation):
    """Only the text of an already authorized operation crosses this wire."""
    content_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonblank_text(self):
        if not self.content_text.strip():
            raise ValueError("known_task_explanation_text_required")
        return self


class D2ExplanationReply(Closed):
    """Existing known-task reply, shared by schema generation and parsing."""
    explanations: tuple[D2ExplanationReplyItem, ...] = Field(min_length=1)


@dataclass(frozen=True)
class D2RejectedOperation:
    """Internal validation outcome, never a command in the model schema."""
    request_id: str
    kind: str


@dataclass(frozen=True)
class D2ParsedDialogueResult:
    """Ordered acceptance results consumed directly by the existing executor."""
    outcome: str
    blocks: tuple
    source_claims: tuple[ExplanationFields, ...] | None = None

    @property
    def requests(self):
        return self.blocks


_operation_adapter = TypeAdapter(Block)


def validate_d2_payload(payload: dict, *, active_service_ids: frozenset[str], known_task=None):
    if known_task is not None:
        expected = known_task.blocks
        items = payload.get("explanations")
        if set(payload) != {"explanations"} or not isinstance(items, list) or len(items) != len(expected):
            raise ValueError("known_task_explanations_required")
        errors = ()
        reply = None
        try:
            reply = D2ExplanationReply.model_validate(payload)
        except ValidationError as exc:
            errors = exc.errors()
        # Select the former first error in wire order: shape/identity before
        # text for each item. Structural evidence comes from the single typed
        # validator, not another hand-written schema. Ignore tuple-length
        # errors caused by invalid children; input count was checked above.
        for index, (original, raw_item) in enumerate(zip(expected, items)):
            item_errors = [e for e in errors if e["loc"][:2] == ("explanations", index)]
            if any(e["type"] in {"model_type", "extra_forbidden"}
                   or "request_id" in e["loc"] for e in item_errors):
                raise ValueError("known_task_explanation_invalid")
            if raw_item.get("request_id") != original.request_id:
                raise ValueError("known_task_explanation_invalid")
            if item_errors:
                raise ValueError("known_task_explanation_text_required")
        if reply is None:
            raise ValueError("known_task_explanation_invalid")
        completed = []
        for original, item in zip(expected, reply.explanations):
            values = original.model_dump()
            values.pop("pending_question")
            values.update(item.model_dump())
            completed.append(ExplanationOperation.model_validate(values))
        result = D2DialogueResult.model_validate({
            "outcome": known_task.outcome,
            "blocks": tuple(completed),
        })
    else:
        # Root/terminal identity is indivisible; an ordinary list is not.
        if set(payload) != {"outcome", "blocks"} or payload.get("outcome") != "dialogue":
            return D2DialogueResult.model_validate(payload)
        items = payload["blocks"]
        if not isinstance(items, list) or not items:
            return D2DialogueResult.model_validate(payload)
        accepted = []
        first_error = None
        for index, item in enumerate(items, 1):
            identity = f"r{index}"
            kind = item.get("kind") if isinstance(item, dict) else None
            try:
                if not isinstance(item, dict):
                    raise ValueError("operation_object_required")
                if kind == "content" and item.get("clarification") is None and "pending_question" not in item:
                    # Text and optional claims have separate authority. Neither
                    # projection is a retry of a rejected whole operation.
                    block = ExplanationOperation.model_validate({
                        "kind": kind, "request_id": identity, "content_text": item.get("content_text"),
                    })
                    if block.content_text is not None and not block.content_text.strip():
                        raise ValueError("completed_explanation_text_required")
                    claim_fields = {key: item[key] for key in (
                        "target", "volume", "brand_id", "content_ref", "content_section_refs"
                    ) if key in item}
                    try:
                        claims = ExplanationFields.model_validate({
                            "kind": kind, "request_id": identity, **claim_fields,
                        })
                    except ValidationError:
                        claims = None
                    if claims is not None:
                        block = block.model_copy(update={key: getattr(claims, key)
                            for key in type(claims).model_fields if key not in {"kind", "request_id"}})
                else:
                    block = _operation_adapter.validate_python({**item, "request_id": identity})
                clarification = getattr(block, "clarification", None)
                if clarification is not None and any(c not in active_service_ids for c in clarification.choices):
                    raise ValueError("clarify_service_not_active")
                accepted.append(block)
            except (ValidationError, ValueError) as exc:
                first_error = first_error or exc
                accepted.append(D2RejectedOperation(identity, kind if isinstance(kind, str) and kind in {
                    "content", "price", "contact", "booking", "off_topic"
                } else "reference"))
        if all(isinstance(block, D2RejectedOperation) for block in accepted):
            raise first_error
        return D2ParsedDialogueResult("dialogue", tuple(accepted))
    for block in result.blocks:
        clarification = getattr(block, "clarification", None)
        if clarification is not None and any(c not in active_service_ids for c in clarification.choices):
            raise ValueError("clarify_service_not_active")
    return result


# Optional informational metadata and non-price actions. Price uses its API tool.
OPEN = "<D2_META>"
CLOSE = "</D2_META>"
ACTION_TYPES = {
    "show_contacts":(ContactOperation,"contact"),
    "start_booking":(BookingOperation,"booking"),
    "off_topic":(OffTopicOperation,"off_topic"),
}


def split_d2_text_reply(raw):
    """Exact reserved line only; no repairs or guesses about misspelled markers."""
    if not isinstance(raw, str):
        raise ValueError("text_tail_string_required")
    lines = raw.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        if line.rstrip("\r\n") == OPEN:
            offsets.append(offset)
        offset += len(line)
    if not offsets:
        return raw.strip(), None
    text = raw[:offsets[0]].strip()
    tail = raw[offsets[0]:]
    if len(offsets) != 1 or tail.count(CLOSE) != 1:
        return text, None
    if sum(line.rstrip("\r\n")==CLOSE for line in tail.splitlines(keepends=True)) != 1:
        return text, None
    body, trailing = tail[len(OPEN):].split(CLOSE, 1)
    if trailing.strip():
        return text, None
    from core.one_call_envelope_protocol import _loads_strict_json_object
    try:
        metadata = _loads_strict_json_object(body.strip())
        if set(metadata) - {"sources", "actions"}:
            return text, None
        if any(not isinstance(metadata.get(key, []), list) for key in ("sources", "actions")):
            return text, None
    except (ValueError, TypeError):
        return text, None
    return text, metadata


def parse_d2_text_reply(raw, *, active_service_ids, known_task=None):
    text, metadata = split_d2_text_reply(raw)
    if known_task is not None:
        if len(known_task.blocks) != 1 or not text:
            raise ValueError("known_task_explanation_text_required")
        original = known_task.blocks[0]
        return D2ParsedDialogueResult("dialogue", (
            ExplanationOperation(**original.model_dump(exclude={"pending_question"}), content_text=text),
        ))
    actions, claims = [], []
    for item in (metadata or {}).get("actions", []):
        identity = f"r{len(actions)+2 if text else len(actions)+1}"
        name = item.get("name") if isinstance(item, dict) else None
        kind = ACTION_TYPES.get(name, (None,"reference"))[1] if isinstance(name,str) else "reference"
        try:
            if not isinstance(item, dict) or set(item) != {"name","arguments"}:
                raise ValueError("text_tail_action_shape_invalid")
            args = item["arguments"]
            if not isinstance(args, dict) or {"request_id","kind","content_text"}.intersection(args):
                raise ValueError("text_tail_server_fields_forbidden")
            if name == "handoff":
                if args:
                    raise ValueError("handoff_arguments_forbidden")
                return D2ParsedDialogueResult("admin", ())
            model, kind = ACTION_TYPES[name]
            action = model.model_validate(dict(args, kind=kind, request_id=identity))
            clarification = getattr(action, "clarification", None)
            if clarification is not None and any(c not in active_service_ids for c in clarification.choices):
                raise ValueError("clarify_service_not_active")
            actions.append(action)
        except (ValueError, TypeError, KeyError):
            actions.append(D2RejectedOperation(identity, kind))
    for i, source in enumerate((metadata or {}).get("sources", []), 1):
        identity = f"r{i}"
        try:
            if not isinstance(source, dict) or {"kind","request_id","content_text","clarification","pending_question"}.intersection(source):
                raise ValueError("text_tail_source_shape_invalid")
            claims.append(ExplanationFields.model_validate(dict(source, kind="content", request_id=identity)))
        except (ValueError, TypeError):
            # Multiplicity and invalid siblings must survive authority checking.
            claims.append(ExplanationFields(kind="content", request_id=identity))
    blocks = ((ExplanationOperation(kind="content", request_id="r1", content_text=text),) if text else ()) + tuple(actions)
    if not blocks or all(isinstance(b,D2RejectedOperation) for b in blocks):
        raise ValueError("text_tail_empty_or_rejected")
    return D2ParsedDialogueResult("dialogue", blocks, tuple(claims) if text and metadata is not None else None)
