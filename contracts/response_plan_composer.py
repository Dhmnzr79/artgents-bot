"""Canonical response-plan Composer contract types, parser, and decision adapter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Self, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from contracts.answer_plan import AspectKind
from contracts.response_plan import (
    ALLOWED_ROUTE_MODE_PAIRS,
    ContextStrategy,
    FactApplicability,
    ResponseRoute,
    ResponseMode,
    RouteModePair,
)
from contracts.target_composer_source_identity import TargetComposerSourceIdentity

PUBLISHED_TARGET_KEYS: frozenset[str] = frozenset(
    {
        "route",
        "mode",
        "patient_text",
        "service_reference_kind",
        "topic_id",
        "explicit_service_id",
        "requested_aspect_ids",
        "patient_situation",
        "requested_fact_ids",
        "source_identity",
    }
)
CORE_RESPONSE_FIELDS: frozenset[str] = frozenset(
    {
        "route",
        "mode",
        "patient_text",
        "service_reference_kind",
        "topic_id",
        "explicit_service_id",
        "requested_aspect_ids",
        "patient_situation",
        "requested_fact_ids",
    }
)
FORBIDDEN_LEGACY_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "text",
        "direct_fact_ids",
        "decision",
        "commercial_intent",
        "price_text",
        "recommended_service_ids",
        "selected_service_id",
        "service_id",
    }
)

ServiceReferenceKind = Literal["none", "explicit_current", "active_session"]
SituationExtent = Literal["unknown", "one_tooth", "few_teeth", "full_arch"]
SituationJaw = Literal["unknown", "upper", "lower", "both"]
SituationStage = Literal[
    "unknown",
    "natural_tooth_present",
    "extraction_context",
    "implant_placed",
]
SituationModifier = Literal["reported_bone_deficit"]

_VALID_ASPECT_IDS: frozenset[str] = frozenset(get_args(AspectKind))
_VALID_EXTENTS: frozenset[str] = frozenset(get_args(SituationExtent))
_VALID_JAWS: frozenset[str] = frozenset(get_args(SituationJaw))
_VALID_STAGES: frozenset[str] = frozenset(get_args(SituationStage))
_VALID_MODIFIERS: frozenset[str] = frozenset(get_args(SituationModifier))

ComposerParserErrorCode = Literal[
    "json_invalid",
    "json_duplicate_key",
    "json_root_not_object",
    "json_missing_core_field",
    "json_extra_field",
    "field_type_invalid",
    "identifier_invalid",
    "route_mode_invalid",
    "output_shape_invalid",
    "service_reference_invalid",
    "aspect_invalid",
    "situation_invalid",
]

ComposerAdapterErrorCode = Literal[
    "composer_forbidden_for_bypass",
    "route_mode_not_allowed",
]

ComposerDecisionDiagnosticCode = Literal[
    "topic_id_not_allowed",
    "service_id_not_allowed",
    "active_session_service_unavailable",
    "requested_fact_unknown",
    "source_ref_not_allowed",
    "terminal_fields_normalized",
]

COMPOSER_DECISION_DIAGNOSTIC_CODES: frozenset[str] = frozenset(
    get_args(ComposerDecisionDiagnosticCode)
)

ComposerProvenanceWarningCode = Literal[
    "source_identity_missing",
    "source_identity_invalid_type",
    "source_identity_invalid_shape",
    "source_identity_invalid_ref",
    "source_identity_duplicate_ref",
    "source_identity_primary_not_used",
    "source_identity_empty",
    "source_identity_forbidden_for_route",
]

_ROUTE_PURPOSES: dict[tuple[ResponseRoute, ResponseMode], str] = {
    ("ANSWER", "standard"): "ordinary_useful_answer",
    ("ANSWER", "contacts"): "explicit_contact_request_code_owned_visible",
    ("ADMIN", "standard"): "complaint_or_escalation_code_owned_visible",
    ("ADMIN", "medical_terminal"): "medical_safety_terminal_code_owned_visible",
    ("CLARIFY", "standard"): "clarification_question",
}
_TERMINAL_CODE_OWNED_PAIRS: frozenset[tuple[ResponseRoute, ResponseMode]] = frozenset(
    {
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    }
)
_SOURCE_REF_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_URI_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:[/\\]")


class ComposerContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _require_exact_non_blank(value: str) -> str:
    if not value:
        raise ValueError("string_must_not_be_blank")
    if value != value.strip():
        raise ValueError("string_whitespace_padded")
    return value


def _unique_non_blank_ids(values: tuple[str, ...], *, duplicate_error: str) -> tuple[str, ...]:
    seen: set[str] = set()
    for item in values:
        if item != item.strip():
            raise ValueError("identifier_whitespace_padded")
        if not item:
            raise ValueError("identifier_blank")
        if item in seen:
            raise ValueError(duplicate_error)
        seen.add(item)
    return values


ExactNonBlankStr = Annotated[str, AfterValidator(_require_exact_non_blank)]
UniqueFactIds = Annotated[tuple[str, ...], AfterValidator(lambda v: _unique_non_blank_ids(v, duplicate_error="fact_id_duplicate"))]
UniqueServiceIds = Annotated[
    tuple[str, ...],
    AfterValidator(lambda v: _unique_non_blank_ids(v, duplicate_error="allowed_service_id_duplicate")),
]
UniqueTopicIds = Annotated[
    tuple[str, ...],
    AfterValidator(lambda v: _unique_non_blank_ids(v, duplicate_error="allowed_topic_id_duplicate")),
]


def source_ref_invalid_reason(ref: str) -> str | None:
    if not ref:
        return "blank"
    if ref != ref.strip():
        return "padded"
    if _SOURCE_REF_CONTROL_CHARS.search(ref):
        return "control_character"
    if ref.startswith("/"):
        return "absolute"
    if "\\" in ref:
        return "backslash"
    if _WINDOWS_DRIVE_PREFIX.match(ref):
        return "drive_prefix"
    if _URI_SCHEME.match(ref):
        return "uri_scheme"
    if not ref.endswith(".md"):
        return "extension"
    if "//" in ref:
        return "empty_segment"
    segments = ref.split("/")
    for segment in segments:
        if not segment:
            return "empty_segment"
        if segment in (".", ".."):
            return "parent_segment"
    return None


def is_valid_source_ref(ref: str) -> bool:
    return source_ref_invalid_reason(ref) is None


def source_ref_basename_invalid_reason(ref: str) -> str | None:
    return source_ref_invalid_reason(ref)


def is_valid_source_ref_basename(ref: str) -> bool:
    return is_valid_source_ref(ref)


class ComposerParserError(ValueError):
    """Fatal structural parser error for Composer JSON."""

    def __init__(self, code: ComposerParserErrorCode, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


class ComposerAdapterError(ValueError):
    """Decision adapter boundary error."""

    def __init__(self, code: ComposerAdapterErrorCode, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ComposerProvenanceWarning:
    code: ComposerProvenanceWarningCode
    detail: object = None


@dataclass(frozen=True, slots=True)
class ComposerDecisionDiagnostic:
    code: ComposerDecisionDiagnosticCode
    detail: object = None


@dataclass(frozen=True, slots=True)
class ComposerSourceIdentityEnvelope:
    primary_content_ref: str | None
    used_content_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComposerPatientSituation:
    extent: SituationExtent
    jaw: SituationJaw
    stage: SituationStage
    modifiers: tuple[SituationModifier, ...]


@dataclass(frozen=True, slots=True)
class ComposerDecision:
    route: ResponseRoute
    mode: ResponseMode
    patient_text: str | None
    service_reference_kind: ServiceReferenceKind
    topic_id: str | None
    explicit_service_id: str | None
    requested_aspect_ids: tuple[AspectKind, ...]
    patient_situation: ComposerPatientSituation
    requested_fact_ids: tuple[str, ...]
    source_identity: ComposerSourceIdentityEnvelope | None


@dataclass(frozen=True, slots=True)
class ParsedComposerEnvelope:
    envelope: ComposerDecision
    warnings: tuple[ComposerProvenanceWarning, ...]


@dataclass(frozen=True, slots=True)
class AdaptedComposerDecision:
    decision: ComposerDecision
    source_identity: TargetComposerSourceIdentity | None
    warnings: tuple[ComposerProvenanceWarning, ...]
    diagnostics: tuple[ComposerDecisionDiagnostic, ...] = ()


AdaptedComposerOutput = AdaptedComposerDecision


@dataclass(frozen=True, slots=True)
class ComposerDecisionAuthority:
    """Plan-agnostic authority for adapting parsed Composer output."""

    source_client_id: str
    allowed_route_modes: tuple[RouteModePair, ...]
    allowed_topic_ids: tuple[str, ...]
    service_descriptors: tuple["ServiceDescriptor", ...]
    allowed_source_refs: tuple[str, ...] = ()
    bypass: bool = False
    active_session_service_id: str | None = None
    context_strategy: ContextStrategy = "full_context"
    history_turn_count: int = 0
    allowed_aspect_ids: tuple[AspectKind, ...] = ()
    requestable_facts: tuple[RequestableFactDescriptor, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_client_id:
            raise ValueError("source_client_id_blank")
        if self.source_client_id != self.source_client_id.strip():
            raise ValueError("source_client_id_padded")

        seen_service_ids: set[str] = set()
        for descriptor in self.service_descriptors:
            if descriptor.service_id in seen_service_ids:
                raise ValueError("service_descriptor_id_duplicate")
            seen_service_ids.add(descriptor.service_id)

        seen_source_refs: set[str] = set()
        for ref in self.allowed_source_refs:
            if not ref:
                raise ValueError("allowed_source_ref_blank")
            if ref != ref.strip():
                raise ValueError("allowed_source_ref_padded")
            invalid_reason = source_ref_invalid_reason(ref)
            if invalid_reason is not None:
                raise ValueError(f"allowed_source_ref_invalid:{invalid_reason}")
            if ref in seen_source_refs:
                raise ValueError("allowed_source_ref_duplicate")
            seen_source_refs.add(ref)

        if self.active_session_service_id is not None:
            session_service_id = self.active_session_service_id
            if not session_service_id:
                raise ValueError("active_session_service_id_blank")
            if session_service_id != session_service_id.strip():
                raise ValueError("active_session_service_id_padded")


def authority_allowed_service_ids(authority: ComposerDecisionAuthority) -> frozenset[str]:
    return frozenset(descriptor.service_id for descriptor in authority.service_descriptors)


class RoutePolicyEntry(ComposerContractModel):
    route: ResponseRoute
    mode: ResponseMode
    purpose: ExactNonBlankStr
    code_owned_visible_response: bool

    @model_validator(mode="after")
    def _validate_pair(self) -> Self:
        pair = (self.route, self.mode)
        if pair not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        canonical_purpose = _ROUTE_PURPOSES.get(pair)
        if canonical_purpose is None or self.purpose != canonical_purpose:
            raise ValueError("route_purpose_mismatch")
        canonical_code_owned = pair in _TERMINAL_CODE_OWNED_PAIRS
        if self.code_owned_visible_response != canonical_code_owned:
            raise ValueError("code_owned_visible_response_mismatch")
        return self


COMPOSER_PRICE_HANDLING = "code_owned_after_decision"


class RequestableFactDescriptor(ComposerContractModel):
    fact_id: ExactNonBlankStr
    meaning: ExactNonBlankStr
    explicit_only: bool
    applicability: FactApplicability
    allowed_service_ids: UniqueServiceIds = ()
    allowed_topic_ids: UniqueTopicIds = ()
    requires_implant_scope: bool = False

    @model_validator(mode="after")
    def _validate_applicability(self) -> Self:
        if self.applicability == "clinic_wide":
            if self.allowed_service_ids or self.allowed_topic_ids:
                raise ValueError("clinic_wide_forbids_scope_allowlists")
            if self.requires_implant_scope:
                raise ValueError("clinic_wide_forbids_implant_scope")
            return self
        if self.applicability == "topic_scoped":
            if not self.allowed_topic_ids:
                raise ValueError("topic_scoped_requires_topic_ids")
            if self.allowed_service_ids:
                raise ValueError("topic_scoped_forbids_service_ids")
            return self
        if self.applicability == "service_scoped":
            if not self.allowed_service_ids:
                raise ValueError("service_scoped_requires_service_ids")
            if self.allowed_topic_ids:
                raise ValueError("service_scoped_forbids_topic_ids")
            if self.requires_implant_scope and not self.allowed_service_ids:
                raise ValueError("requires_implant_scope_requires_service_scope")
            return self
        raise ValueError("applicability_invalid")


class ServiceDescriptor(ComposerContractModel):
    service_id: ExactNonBlankStr
    label: ExactNonBlankStr
    aliases: tuple[ExactNonBlankStr, ...]
    short_meaning: ExactNonBlankStr

    @model_validator(mode="after")
    def _validate_descriptor(self) -> Self:
        seen_aliases: set[str] = set()
        for alias in self.aliases:
            if alias in seen_aliases:
                raise ValueError("service_descriptor_alias_duplicate")
            seen_aliases.add(alias)
        return self


class ComposerPolicySidecar(ComposerContractModel):
    """Policy/control sidecar for Composer input. Not a complete Composer prompt."""

    kind: Literal["policy_control"] = "policy_control"
    allowed_route_modes: tuple[RoutePolicyEntry, ...]
    allowed_topic_ids: UniqueTopicIds
    service_descriptors: tuple[ServiceDescriptor, ...]
    allowed_source_refs: tuple[str, ...] = ()
    active_session_service_id: str | None = None
    context_strategy: ContextStrategy
    history_turn_count: int = Field(ge=0)
    price_handling: Literal["code_owned_after_decision"] = COMPOSER_PRICE_HANDLING
    allowed_aspect_ids: tuple[AspectKind, ...]
    requestable_facts: tuple[RequestableFactDescriptor, ...] = ()

    @model_validator(mode="after")
    def _validate_sidecar(self) -> Self:
        if not self.allowed_route_modes:
            raise ValueError("allowed_route_modes_empty")
        pairs = [(item.route, item.mode) for item in self.allowed_route_modes]
        if len(pairs) != len(set(pairs)):
            raise ValueError("allowed_route_modes_duplicate")
        seen_fact_ids: set[str] = set()
        for descriptor in self.requestable_facts:
            if descriptor.fact_id in seen_fact_ids:
                raise ValueError("requestable_fact_id_duplicate")
            seen_fact_ids.add(descriptor.fact_id)
        if self.active_session_service_id is not None and (
            not self.active_session_service_id
            or self.active_session_service_id != self.active_session_service_id.strip()
        ):
            raise ValueError("active_session_service_id_invalid")
        if not self.allowed_aspect_ids:
            raise ValueError("allowed_aspect_ids_empty")
        if len(self.allowed_aspect_ids) != len(set(self.allowed_aspect_ids)):
            raise ValueError("allowed_aspect_ids_duplicate")
        for aspect in self.allowed_aspect_ids:
            if aspect not in _VALID_ASPECT_IDS:
                raise ValueError("allowed_aspect_id_invalid")
        seen_service_ids: set[str] = set()
        for descriptor in self.service_descriptors:
            if descriptor.service_id in seen_service_ids:
                raise ValueError("service_descriptor_id_duplicate")
            seen_service_ids.add(descriptor.service_id)
        return self


def published_target_schema_example() -> dict[str, object]:
    return {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "Естественный ответ пациенту.",
        "service_reference_kind": "none",
        "topic_id": None,
        "explicit_service_id": None,
        "requested_aspect_ids": [],
        "patient_situation": {
            "extent": "unknown",
            "jaw": "unknown",
            "stage": "unknown",
            "modifiers": [],
        },
        "requested_fact_ids": [],
        "source_identity": {
            "primary_content_ref": "clinic__info__consultation.md",
            "used_content_refs": ["clinic__info__consultation.md"],
        },
    }


def future_prompt_composition_parts() -> tuple[str, ...]:
    return (
        "static Composer instructions",
        "current-client validated model FullContext corpus",
        "document index",
        "serialized policy/control sidecar",
        "normalized session context",
        "recent dialogue history",
        "current user message",
    )


def _warning(
    code: ComposerProvenanceWarningCode,
    detail: object = None,
) -> ComposerProvenanceWarning:
    return ComposerProvenanceWarning(code=code, detail=detail)


def _detect_duplicate_keys(pairs: list[tuple[str, Any]], *, path: str) -> None:
    seen: set[str] = set()
    for key, _ in pairs:
        if not isinstance(key, str):
            raise ComposerParserError("field_type_invalid", (path, "non_string_key"))
        if key in seen:
            raise ComposerParserError("json_duplicate_key", f"{path}.{key}" if path else key)
        seen.add(key)


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if not stripped:
        raise ComposerParserError("json_invalid", "empty")
    if stripped.startswith("```") or stripped.endswith("```"):
        raise ComposerParserError("json_invalid", "markdown_fence")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_strict_object_pairs_hook)
        value, end = decoder.raw_decode(stripped)
    except ComposerParserError:
        raise
    except json.JSONDecodeError as exc:
        raise ComposerParserError("json_invalid", str(exc)) from exc
    if end != len(stripped):
        raise ComposerParserError("json_invalid", "trailing_prose")
    if not isinstance(value, dict):
        raise ComposerParserError("json_root_not_object", type(value).__name__)
    return value


def _strict_object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    _detect_duplicate_keys(pairs, path="")
    return dict(pairs)


def _require_exact_route(value: object) -> ResponseRoute:
    if not isinstance(value, str):
        raise ComposerParserError("field_type_invalid", ("route", type(value).__name__))
    if value != value.strip():
        raise ComposerParserError("route_mode_invalid", ("route", value))
    if value not in {"ANSWER", "ADMIN", "CLARIFY"}:
        raise ComposerParserError("route_mode_invalid", ("route", value))
    return value  # type: ignore[return-value]


def _require_exact_mode(value: object) -> ResponseMode:
    if not isinstance(value, str):
        raise ComposerParserError("field_type_invalid", ("mode", type(value).__name__))
    if value != value.strip():
        raise ComposerParserError("route_mode_invalid", ("mode", value))
    if value not in {"standard", "contacts", "medical_terminal"}:
        raise ComposerParserError("route_mode_invalid", ("mode", value))
    return value  # type: ignore[return-value]


def _require_nullable_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ComposerParserError("field_type_invalid", (field, type(value).__name__))
    return value


def _require_service_reference_kind(value: object) -> ServiceReferenceKind:
    if not isinstance(value, str):
        raise ComposerParserError("field_type_invalid", ("service_reference_kind", type(value).__name__))
    if value != value.strip():
        raise ComposerParserError("service_reference_invalid", ("service_reference_kind", "padded"))
    if value not in {"none", "explicit_current", "active_session"}:
        raise ComposerParserError("service_reference_invalid", ("service_reference_kind", value))
    return value  # type: ignore[return-value]


def _require_requested_fact_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ComposerParserError("field_type_invalid", ("requested_fact_ids", type(value).__name__))
    ids: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ComposerParserError("field_type_invalid", ("requested_fact_ids", index, type(item).__name__))
        if not item:
            raise ComposerParserError("identifier_invalid", ("requested_fact_ids", index, "blank"))
        if item != item.strip():
            raise ComposerParserError("identifier_invalid", ("requested_fact_ids", index, "padded"))
        if item in seen:
            raise ComposerParserError("identifier_invalid", ("requested_fact_ids", index, "duplicate"))
        seen.add(item)
        ids.append(item)
    return tuple(ids)


def _require_requested_aspect_ids(value: object) -> tuple[AspectKind, ...]:
    if not isinstance(value, list):
        raise ComposerParserError("field_type_invalid", ("requested_aspect_ids", type(value).__name__))
    aspects: list[AspectKind] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ComposerParserError("field_type_invalid", ("requested_aspect_ids", index, type(item).__name__))
        if item != item.strip():
            raise ComposerParserError("aspect_invalid", ("requested_aspect_ids", index, "padded"))
        if item not in _VALID_ASPECT_IDS:
            raise ComposerParserError("aspect_invalid", ("requested_aspect_ids", index, item))
        if item in seen:
            raise ComposerParserError("aspect_invalid", ("requested_aspect_ids", index, "duplicate"))
        seen.add(item)
        aspects.append(item)  # type: ignore[arg-type]
    return tuple(aspects)


def _require_patient_situation(value: object) -> ComposerPatientSituation:
    if not isinstance(value, dict):
        raise ComposerParserError("field_type_invalid", ("patient_situation", type(value).__name__))
    pairs = list(value.items())
    _detect_duplicate_keys(pairs, path="patient_situation")
    allowed = {"extent", "jaw", "stage", "modifiers"}
    keys = set(value.keys())
    if keys != allowed:
        raise ComposerParserError("situation_invalid", sorted(keys))
    extent = value.get("extent")
    jaw = value.get("jaw")
    stage = value.get("stage")
    modifiers = value.get("modifiers")
    if not isinstance(extent, str) or extent not in _VALID_EXTENTS:
        raise ComposerParserError("situation_invalid", ("extent", extent))
    if not isinstance(jaw, str) or jaw not in _VALID_JAWS:
        raise ComposerParserError("situation_invalid", ("jaw", jaw))
    if not isinstance(stage, str) or stage not in _VALID_STAGES:
        raise ComposerParserError("situation_invalid", ("stage", stage))
    if not isinstance(modifiers, list):
        raise ComposerParserError("situation_invalid", ("modifiers", type(modifiers).__name__))
    parsed_modifiers: list[SituationModifier] = []
    seen_modifiers: set[str] = set()
    for index, item in enumerate(modifiers):
        if not isinstance(item, str):
            raise ComposerParserError("situation_invalid", ("modifiers", index, type(item).__name__))
        if item not in _VALID_MODIFIERS:
            raise ComposerParserError("situation_invalid", ("modifiers", index, item))
        if item in seen_modifiers:
            raise ComposerParserError("situation_invalid", ("modifiers", index, "duplicate"))
        seen_modifiers.add(item)
        parsed_modifiers.append(item)  # type: ignore[arg-type]
    return ComposerPatientSituation(
        extent=extent,  # type: ignore[arg-type]
        jaw=jaw,  # type: ignore[arg-type]
        stage=stage,  # type: ignore[arg-type]
        modifiers=tuple(parsed_modifiers),
    )


def _validate_service_reference_invariants(
    service_reference_kind: ServiceReferenceKind,
    explicit_service_id: str | None,
) -> None:
    if service_reference_kind == "explicit_current":
        if explicit_service_id is None or not explicit_service_id or explicit_service_id != explicit_service_id.strip():
            raise ComposerParserError(
                "service_reference_invalid",
                ("explicit_service_id", "required_non_blank_for_explicit_current"),
            )
        return
    if explicit_service_id is not None:
        raise ComposerParserError(
            "service_reference_invalid",
            ("explicit_service_id", "must_be_null"),
        )


def _parse_source_identity_value(
    value: object | None,
    *,
    missing: bool,
) -> tuple[ComposerSourceIdentityEnvelope | None, tuple[ComposerProvenanceWarning, ...]]:
    if missing:
        return None, (_warning("source_identity_missing"),)
    if value is None:
        return None, ()
    if not isinstance(value, dict):
        return None, (_warning("source_identity_invalid_type", type(value).__name__),)
    try:
        pairs = list(value.items())
    except AttributeError:
        return None, (_warning("source_identity_invalid_type", type(value).__name__),)
    _detect_duplicate_keys(pairs, path="source_identity")
    allowed = {"primary_content_ref", "used_content_refs"}
    keys = set(value.keys())
    if keys != allowed:
        return None, (_warning("source_identity_invalid_shape", sorted(keys)),)
    primary = value.get("primary_content_ref")
    used = value.get("used_content_refs")
    if primary is not None and not isinstance(primary, str):
        return None, (_warning("source_identity_invalid_type", ("primary_content_ref", type(primary).__name__)),)
    if not isinstance(used, list):
        return None, (_warning("source_identity_invalid_type", ("used_content_refs", type(used).__name__)),)
    used_refs: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(used):
        if not isinstance(item, str):
            return None, (
                _warning("source_identity_invalid_type", ("used_content_refs", index, type(item).__name__)),
            )
        invalid_reason = source_ref_invalid_reason(item)
        if invalid_reason is not None:
            return None, (_warning("source_identity_invalid_ref", ("used_content_refs", index, invalid_reason)),)
        if item in seen:
            return None, (_warning("source_identity_duplicate_ref", item),)
        seen.add(item)
        used_refs.append(item)
    if primary is not None:
        if not isinstance(primary, str):
            return None, (_warning("source_identity_invalid_type", ("primary_content_ref", type(primary).__name__)),)
        invalid_reason = source_ref_invalid_reason(primary)
        if invalid_reason is not None:
            return None, (_warning("source_identity_invalid_ref", ("primary_content_ref", invalid_reason)),)
        if primary not in seen:
            return None, (_warning("source_identity_primary_not_used", primary),)
    if primary is None and not used_refs:
        return None, (_warning("source_identity_empty"),)
    return (
        ComposerSourceIdentityEnvelope(
            primary_content_ref=primary,
            used_content_refs=tuple(used_refs),
        ),
        (),
    )


def _validate_output_shape(
    route: ResponseRoute,
    mode: ResponseMode,
    *,
    patient_text: str | None,
    requested_fact_ids: tuple[str, ...],
) -> None:
    pair = (route, mode)
    if pair not in ALLOWED_ROUTE_MODE_PAIRS:
        raise ComposerParserError("route_mode_invalid", pair)
    if pair == ("ANSWER", "standard"):
        if patient_text is None or not patient_text or not patient_text.strip():
            raise ComposerParserError("output_shape_invalid", ("patient_text", "required_non_empty"))
        return
    if pair == ("ANSWER", "contacts"):
        if patient_text is not None:
            raise ComposerParserError("output_shape_invalid", ("patient_text", "must_be_null"))
        if requested_fact_ids:
            raise ComposerParserError("output_shape_invalid", ("requested_fact_ids", "must_be_empty"))
        return
    if route == "ADMIN":
        if patient_text is not None:
            raise ComposerParserError("output_shape_invalid", ("patient_text", "must_be_null"))
        if requested_fact_ids:
            raise ComposerParserError("output_shape_invalid", ("requested_fact_ids", "must_be_empty"))
        return
    if pair == ("CLARIFY", "standard"):
        if patient_text is None or not patient_text or not patient_text.strip():
            raise ComposerParserError("output_shape_invalid", ("patient_text", "required_non_empty"))
        if requested_fact_ids:
            raise ComposerParserError("output_shape_invalid", ("requested_fact_ids", "must_be_empty"))


def parse_response_plan_composer_json(raw_text: str) -> ParsedComposerEnvelope:
    """Parse raw Composer JSON without authority context."""

    payload = _parse_json_object(raw_text)
    keys = set(payload.keys())
    for legacy_key in FORBIDDEN_LEGACY_TOP_LEVEL_KEYS:
        if legacy_key in keys:
            raise ComposerParserError("json_extra_field", legacy_key)
    extra = keys - PUBLISHED_TARGET_KEYS
    if extra:
        raise ComposerParserError("json_extra_field", sorted(extra))
    for core_field in CORE_RESPONSE_FIELDS:
        if core_field not in payload:
            raise ComposerParserError("json_missing_core_field", core_field)

    route = _require_exact_route(payload["route"])
    mode = _require_exact_mode(payload["mode"])
    patient_text = _require_nullable_string(payload["patient_text"], "patient_text")
    service_reference_kind = _require_service_reference_kind(payload["service_reference_kind"])
    topic_id = _require_nullable_string(payload["topic_id"], "topic_id")
    explicit_service_id = _require_nullable_string(payload["explicit_service_id"], "explicit_service_id")
    requested_aspect_ids = _require_requested_aspect_ids(payload["requested_aspect_ids"])
    patient_situation = _require_patient_situation(payload["patient_situation"])
    requested_fact_ids = _require_requested_fact_ids(payload["requested_fact_ids"])
    source_missing = "source_identity" not in payload
    source_identity, source_warnings = _parse_source_identity_value(
        payload.get("source_identity"),
        missing=source_missing,
    )

    _validate_service_reference_invariants(service_reference_kind, explicit_service_id)
    _validate_output_shape(
        route,
        mode,
        patient_text=patient_text,
        requested_fact_ids=requested_fact_ids,
    )

    envelope = ComposerDecision(
        route=route,
        mode=mode,
        patient_text=patient_text,
        service_reference_kind=service_reference_kind,
        topic_id=topic_id,
        explicit_service_id=explicit_service_id,
        requested_aspect_ids=requested_aspect_ids,
        patient_situation=patient_situation,
        requested_fact_ids=requested_fact_ids,
        source_identity=source_identity,
    )
    return ParsedComposerEnvelope(envelope=envelope, warnings=source_warnings)


_CANONICAL_UNKNOWN_SITUATION = ComposerPatientSituation(
    extent="unknown",
    jaw="unknown",
    stage="unknown",
    modifiers=(),
)


def _diagnostic(
    code: ComposerDecisionDiagnosticCode,
    detail: object = None,
) -> ComposerDecisionDiagnostic:
    return ComposerDecisionDiagnostic(code=code, detail=detail)


def _envelope_to_domain_identity(
    envelope: ComposerSourceIdentityEnvelope,
) -> TargetComposerSourceIdentity:
    return TargetComposerSourceIdentity(
        primary_content_ref=envelope.primary_content_ref,
        used_content_refs=envelope.used_content_refs,
    )


def _decision_with_source_identity(
    decision: ComposerDecision,
    source_identity: ComposerSourceIdentityEnvelope | None,
) -> ComposerDecision:
    return ComposerDecision(
        route=decision.route,
        mode=decision.mode,
        patient_text=decision.patient_text,
        service_reference_kind=decision.service_reference_kind,
        topic_id=decision.topic_id,
        explicit_service_id=decision.explicit_service_id,
        requested_aspect_ids=decision.requested_aspect_ids,
        patient_situation=decision.patient_situation,
        requested_fact_ids=decision.requested_fact_ids,
        source_identity=source_identity,
    )


def _append_unique_source_ref_diagnostic(
    diagnostics: list[ComposerDecisionDiagnostic],
    seen_rejected: set[str],
    ref: str,
) -> None:
    if ref in seen_rejected:
        return
    seen_rejected.add(ref)
    diagnostics.append(_diagnostic("source_ref_not_allowed", ref))


def _filter_source_identity(
    envelope: ComposerSourceIdentityEnvelope | None,
    *,
    allowed_source_refs: frozenset[str],
) -> tuple[
    TargetComposerSourceIdentity | None,
    ComposerSourceIdentityEnvelope | None,
    list[ComposerDecisionDiagnostic],
]:
    if envelope is None:
        return None, None, []

    diagnostics: list[ComposerDecisionDiagnostic] = []
    rejected_seen: set[str] = set()

    if not allowed_source_refs:
        for ref in envelope.used_content_refs:
            _append_unique_source_ref_diagnostic(diagnostics, rejected_seen, ref)
        if envelope.primary_content_ref is not None:
            _append_unique_source_ref_diagnostic(diagnostics, rejected_seen, envelope.primary_content_ref)
        return None, None, diagnostics

    filtered_used: list[str] = []
    seen_used: set[str] = set()
    for ref in envelope.used_content_refs:
        if ref in allowed_source_refs:
            if ref not in seen_used:
                seen_used.add(ref)
                filtered_used.append(ref)
        else:
            _append_unique_source_ref_diagnostic(diagnostics, rejected_seen, ref)

    primary = envelope.primary_content_ref
    if primary is not None:
        if primary not in allowed_source_refs:
            _append_unique_source_ref_diagnostic(diagnostics, rejected_seen, primary)
            primary = None
        elif primary not in filtered_used:
            return None, None, diagnostics

    if primary is None:
        return None, None, diagnostics

    normalized_envelope = ComposerSourceIdentityEnvelope(
        primary_content_ref=primary,
        used_content_refs=tuple(filtered_used),
    )
    return _envelope_to_domain_identity(normalized_envelope), normalized_envelope, diagnostics


def _normalize_terminal_decision(
    decision: ComposerDecision,
) -> tuple[ComposerDecision, list[ComposerDecisionDiagnostic]]:
    normalized_fields: list[str] = []
    if decision.service_reference_kind != "none":
        normalized_fields.append("service_reference_kind")
    if decision.topic_id is not None:
        normalized_fields.append("topic_id")
    if decision.explicit_service_id is not None:
        normalized_fields.append("explicit_service_id")
    if decision.requested_aspect_ids:
        normalized_fields.append("requested_aspect_ids")
    if decision.patient_situation != _CANONICAL_UNKNOWN_SITUATION:
        normalized_fields.append("patient_situation")
    if decision.requested_fact_ids:
        normalized_fields.append("requested_fact_ids")
    if decision.source_identity is not None:
        normalized_fields.append("source_identity")

    normalized = ComposerDecision(
        route=decision.route,
        mode=decision.mode,
        patient_text=decision.patient_text,
        service_reference_kind="none",
        topic_id=None,
        explicit_service_id=None,
        requested_aspect_ids=(),
        patient_situation=_CANONICAL_UNKNOWN_SITUATION,
        requested_fact_ids=(),
        source_identity=None,
    )
    diagnostics: list[ComposerDecisionDiagnostic] = []
    if normalized_fields:
        diagnostics.append(_diagnostic("terminal_fields_normalized", tuple(normalized_fields)))
    return normalized, diagnostics


def _filter_requested_fact_ids(
    requested_fact_ids: tuple[str, ...],
    authority: ComposerDecisionAuthority,
) -> tuple[tuple[str, ...], list[ComposerDecisionDiagnostic]]:
    known_ids = {descriptor.fact_id for descriptor in authority.requestable_facts}
    kept: list[str] = []
    diagnostics: list[ComposerDecisionDiagnostic] = []
    for fact_id in requested_fact_ids:
        if fact_id in known_ids:
            kept.append(fact_id)
        else:
            diagnostics.append(_diagnostic("requested_fact_unknown", fact_id))
    return tuple(kept), diagnostics


def _apply_semantic_authority(
    decision: ComposerDecision,
    authority: ComposerDecisionAuthority,
) -> tuple[ComposerDecision, list[ComposerDecisionDiagnostic]]:
    diagnostics: list[ComposerDecisionDiagnostic] = []
    allowed_services = authority_allowed_service_ids(authority)

    topic_id = decision.topic_id
    if topic_id is not None:
        if not topic_id or topic_id != topic_id.strip() or topic_id not in authority.allowed_topic_ids:
            diagnostics.append(_diagnostic("topic_id_not_allowed", topic_id))
            topic_id = None

    service_reference_kind = decision.service_reference_kind
    explicit_service_id = decision.explicit_service_id

    if service_reference_kind == "explicit_current":
        if explicit_service_id not in allowed_services:
            diagnostics.append(_diagnostic("service_id_not_allowed", explicit_service_id))
            service_reference_kind = "none"
            explicit_service_id = None
    elif service_reference_kind == "active_session":
        active_id = authority.active_session_service_id
        if active_id is None or active_id not in allowed_services:
            diagnostics.append(_diagnostic("active_session_service_unavailable", active_id))
            service_reference_kind = "none"
            explicit_service_id = None

    requested_fact_ids, fact_diagnostics = _filter_requested_fact_ids(
        decision.requested_fact_ids,
        authority,
    )
    diagnostics.extend(fact_diagnostics)

    return (
        ComposerDecision(
            route=decision.route,
            mode=decision.mode,
            patient_text=decision.patient_text,
            service_reference_kind=service_reference_kind,
            topic_id=topic_id,
            explicit_service_id=explicit_service_id,
            requested_aspect_ids=decision.requested_aspect_ids,
            patient_situation=decision.patient_situation,
            requested_fact_ids=requested_fact_ids,
            source_identity=decision.source_identity,
        ),
        diagnostics,
    )


def adapt_composer_envelope_to_decision(
    parsed: ParsedComposerEnvelope,
    authority: ComposerDecisionAuthority,
) -> AdaptedComposerDecision:
    """Apply authority to a structurally parsed Composer envelope."""

    if authority.bypass:
        raise ComposerAdapterError("composer_forbidden_for_bypass")

    decision = parsed.envelope
    selected_pair = (decision.route, decision.mode)
    allowed_pairs = {(item.route, item.mode) for item in authority.allowed_route_modes}
    if selected_pair not in allowed_pairs:
        raise ComposerAdapterError("route_mode_not_allowed", (selected_pair, tuple(sorted(allowed_pairs))))

    warnings = list(parsed.warnings)
    diagnostics: list[ComposerDecisionDiagnostic] = []

    if selected_pair in _TERMINAL_CODE_OWNED_PAIRS:
        decision, terminal_diagnostics = _normalize_terminal_decision(decision)
        diagnostics.extend(terminal_diagnostics)
        domain_identity = None
    else:
        decision, semantic_diagnostics = _apply_semantic_authority(decision, authority)
        diagnostics.extend(semantic_diagnostics)
        if decision.source_identity is not None:
            domain_identity, normalized_envelope, source_diagnostics = _filter_source_identity(
                decision.source_identity,
                allowed_source_refs=frozenset(authority.allowed_source_refs),
            )
            diagnostics.extend(source_diagnostics)
            decision = _decision_with_source_identity(decision, normalized_envelope)
        else:
            domain_identity = None

    return AdaptedComposerDecision(
        decision=decision,
        source_identity=domain_identity,
        warnings=tuple(warnings),
        diagnostics=tuple(diagnostics),
    )


def adapt_composer_json_to_decision(
    raw_json: str,
    authority: ComposerDecisionAuthority,
) -> AdaptedComposerDecision:
    parsed = parse_response_plan_composer_json(raw_json)
    return adapt_composer_envelope_to_decision(parsed, authority)


def route_policy_entry(route: ResponseRoute, mode: ResponseMode) -> RoutePolicyEntry:
    pair = (route, mode)
    if pair not in ALLOWED_ROUTE_MODE_PAIRS:
        raise ValueError("route_mode_conflict")
    return RoutePolicyEntry(
        route=route,
        mode=mode,
        purpose=_ROUTE_PURPOSES[pair],
        code_owned_visible_response=pair in _TERMINAL_CODE_OWNED_PAIRS,
    )


PUBLISHED_COMPOSER_OUTPUT_SCHEMA_JSON = """{
  "route": "...",
  "mode": "...",
  "patient_text": null,
  "service_reference_kind": "none",
  "topic_id": null,
  "explicit_service_id": null,
  "requested_aspect_ids": [],
  "patient_situation": {
    "extent": "unknown",
    "jaw": "unknown",
    "stage": "unknown",
    "modifiers": []
  },
  "requested_fact_ids": [],
  "source_identity": null
}"""
