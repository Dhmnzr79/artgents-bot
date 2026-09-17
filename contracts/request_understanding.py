"""Typed request_understanding contract (Demo D1R checkpoint B)."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

SubjectRelation = Literal["self", "other", "unknown"]
AgeGroup = Literal["adult", "child", "unknown"]
RequestKind = Literal["clinic_policy", "booking", "price", "contact", "content", "other"]
RequestContext = Literal["current_care", "general_information", "past_history", "unknown"]
PaymentScheme = Literal["oms", "dms", "self_pay", "unspecified"]
PaymentSchemeIntent = Literal[
    "eligibility_question",
    "requested_payment",
    "not_requested",
    "unspecified",
]
ScopeCommitment = Literal["unknown", "none", "reported", "correction", "hypothetical"]
RequestStatementMode = Literal["question", "statement", "correction", "hypothesis"]
TreatmentScopeCommitment = Literal["unknown", "reported", "correction", "hypothetical", "reset"]
TreatmentExtent = Literal["unknown", "one_tooth", "few_teeth", "full_arch"]
TreatmentJaw = Literal["unknown", "upper", "lower", "both"]
TreatmentContinuity = Literal["new", "same", "unknown"]

_SUBJECT_ID_RE = re.compile(r"^s[1-9][0-9]*$")
_REQUEST_ID_RE = re.compile(r"^r[1-9][0-9]*$")
_MAX_CONTENT_TEXT_CODEPOINTS = 4000

_KNOWN_CONTACT_FIELDS = frozenset(
    {
        "contact_address",
        "contact_phone",
        "contact_whatsapp",
        "contact_hours",
        "contact_parking",
        "contacts",
    }
)


class RequestUnderstandingSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    subject_id: str
    relation: SubjectRelation
    age_group: AgeGroup

    @field_validator("subject_id")
    @classmethod
    def _validate_subject_id(cls, value: str) -> str:
        token = value.strip()
        if not _SUBJECT_ID_RE.match(token):
            raise ValueError("subject_id_invalid")
        return token


class RequestTreatmentSituation(BaseModel):
    """Turn-local treatment facts attached to one D1R request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scope_commitment: TreatmentScopeCommitment
    extent: TreatmentExtent
    tooth_count: int | None = None
    jaw: TreatmentJaw
    continuity: TreatmentContinuity

    @field_validator("tooth_count")
    @classmethod
    def _validate_tooth_count(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("treatment_tooth_count_invalid")
        return value

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if self.extent == "one_tooth" and self.tooth_count not in {None, 1}:
            raise ValueError("treatment_count_extent_conflict")
        if self.extent == "few_teeth" and self.tooth_count is not None and self.tooth_count < 2:
            raise ValueError("treatment_count_extent_conflict")
        if self.extent == "unknown" and self.tooth_count is not None:
            raise ValueError("treatment_unknown_extent_forbids_count")
        if self.scope_commitment == "reset" and (
            self.extent != "unknown" or self.jaw != "unknown" or self.tooth_count is not None
        ):
            raise ValueError("treatment_reset_requires_unknown_facts")
        return self


class RequestUnderstandingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_id: str
    kind: RequestKind
    subject_id: str | None
    context: RequestContext
    policy_ids: tuple[str, ...] = ()
    payment_scheme: PaymentScheme = "unspecified"
    payment_scheme_intent: PaymentSchemeIntent = "unspecified"
    contact_fields: tuple[str, ...] = ()
    content_text: str | None = None
    content_ref: str | None = None
    service_id: str | None = None
    topic_id: str | None = None
    statement_mode: RequestStatementMode = "question"
    situation: RequestTreatmentSituation | None = None

    @field_validator("request_id")
    @classmethod
    def _validate_request_id(cls, value: str) -> str:
        token = value.strip()
        if not _REQUEST_ID_RE.match(token):
            raise ValueError("request_id_invalid")
        return token

    @field_validator("policy_ids", "contact_fields", mode="before")
    @classmethod
    def _coerce_list_to_tuple(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("contact_fields")
    @classmethod
    def _validate_contact_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for field in value:
            if field not in _KNOWN_CONTACT_FIELDS:
                raise ValueError("contact_fields_invalid")
        return value

    @field_validator("content_ref")
    @classmethod
    def _validate_content_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip().replace("\\", "/")
        if (
            token != value
            or not token.endswith(".md")
            or "/" in token
            or ".." in token
        ):
            raise ValueError("content_ref_invalid")
        return token

    @field_validator("service_id", "topic_id")
    @classmethod
    def _validate_semantic_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        if not token or token != value:
            raise ValueError("semantic_ref_invalid")
        return token

    @model_validator(mode="after")
    def _kind_field_rules(self) -> Self:
        if self.content_text is not None and len(self.content_text) > _MAX_CONTENT_TEXT_CODEPOINTS:
            raise ValueError("content_text_too_long")
        if self.kind != "contact" and self.contact_fields:
            raise ValueError("contact_fields_forbidden")
        if self.kind not in {"clinic_policy", "content", "other"} and self.policy_ids:
            raise ValueError("policy_ids_forbidden")
        if self.kind not in {"content", "other"} and self.content_text is not None:
            raise ValueError("content_text_forbidden")
        if self.kind not in {"content", "other"} and self.content_ref is not None:
            raise ValueError("content_ref_forbidden")
        if self.content_ref is not None and self.content_text is None:
            raise ValueError("content_ref_without_content_text")
        if self.situation is not None and self.situation.continuity == "same" and self.subject_id is None:
            raise ValueError("treatment_same_requires_subject")
        return self


class RequestUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    subjects: tuple[RequestUnderstandingSubject, ...]
    requests: tuple[RequestUnderstandingRequest, ...]
    scope_commitment: ScopeCommitment = "unknown"
    tooth_count: int | None = None

    @field_validator("tooth_count")
    @classmethod
    def _validate_tooth_count(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("tooth_count_invalid")
        return value

    @field_validator("subjects", "requests", mode="before")
    @classmethod
    def _coerce_list_to_tuple(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _unique_ids_and_subject_refs(self) -> Self:
        subject_ids: set[str] = set()
        for subj in self.subjects:
            if subj.subject_id in subject_ids:
                raise ValueError("subject_id_duplicate")
            subject_ids.add(subj.subject_id)
        request_ids: set[str] = set()
        treatment_situation_count = 0
        for req in self.requests:
            if req.request_id in request_ids:
                raise ValueError("request_id_duplicate")
            request_ids.add(req.request_id)
            if req.subject_id is not None and req.subject_id not in subject_ids:
                raise ValueError("subject_id_unresolved")
            if req.situation is not None:
                treatment_situation_count += 1
        if treatment_situation_count > 1:
            raise ValueError("treatment_situation_multiple")
        if treatment_situation_count and (
            self.scope_commitment != "unknown" or self.tooth_count is not None
        ):
            raise ValueError("treatment_situation_legacy_conflict")
        return self


def total_content_text_codepoints(understanding: RequestUnderstanding) -> int:
    total = 0
    for req in understanding.requests:
        if req.content_text:
            total += len(req.content_text)
    return total


def minimal_content_understanding(text: str, *, request_id: str = "r1") -> RequestUnderstanding:
    """Default single content request for tests and legacy answer helpers."""

    body = (text or "").strip()
    return RequestUnderstanding(
        subjects=(),
        requests=(
            RequestUnderstandingRequest(
                request_id=request_id,
                kind="content",
                subject_id=None,
                context="general_information",
                content_text=body or "Ответ.",
            ),
        ),
    )
