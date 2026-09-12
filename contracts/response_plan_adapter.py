"""Isolated adapter source contracts for RESPONSE-ADAPTER-1 (unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from contracts.response_plan import (
    ALLOWED_ROUTE_MODE_PAIRS,
    CanonicalContactCandidate,
    CodeOwnedAuthority,
    CodeOwnedTerminalCandidate,
    ComposerResult,
    ContextStrategy,
    RequiredOfferConditionBlock,
    ResponseRoute,
    ResponseMode,
    SessionKey,
    TransportKind,
    _require_non_blank,
)
from contracts.response_plan_composer import (
    AdaptedComposerDecision,
    ComposerAdapterError,
    ComposerDecisionAuthority,
    ComposerParserError,
    ParsedComposerEnvelope,
    adapt_composer_envelope_to_decision,
    adapt_composer_json_to_decision,
    parse_response_plan_composer_json,
)
from contracts.turn_frame import TurnFrame

NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]


@runtime_checkable
class ResponsePlanAdapterMaterialPackageShape(Protocol):
    materials: object
    plan: object
    selected_followups: object
    navigation_followups: tuple[object, ...]


@runtime_checkable
class ResponsePlanAdapterBoundPackageShape(Protocol):
    spec: object
    package: ResponsePlanAdapterMaterialPackageShape
    selected_cta_key: str | None


@dataclass(frozen=True, slots=True)
class ResponsePlanAdapterMaterialPackage:
    """Contract-owned structural view of nested material package evidence."""

    materials: object
    plan: object
    selected_followups: object
    navigation_followups: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class ResponsePlanAdapterBoundPackage:
    """Contract-owned structural view of a materialized offline bound package."""

    spec: object
    package: ResponsePlanAdapterMaterialPackage
    selected_cta_key: str | None = None


def material_bound_package_invalid_reason(value: object) -> str | None:
    """Return a stable reason code when value is not a valid material bound package."""

    if isinstance(value, ResponsePlanAdapterBoundPackage):
        return None
    if not isinstance(value, ResponsePlanAdapterBoundPackageShape):
        return "bound_package_shape_invalid"
    if value.spec is None:
        return "missing_spec"
    package = value.package
    if package is None:
        return "missing_package"
    if not isinstance(package, ResponsePlanAdapterMaterialPackageShape):
        return "package_shape_invalid"
    if package.materials is None:
        return "missing_materials"
    if package.plan is None:
        return "missing_plan"
    if package.selected_followups is None:
        return "missing_selected_followups"
    navigation = package.navigation_followups
    if navigation is None:
        navigation = ()
    if not isinstance(navigation, tuple):
        return "navigation_followups_must_be_tuple"
    cta_key = value.selected_cta_key
    if cta_key is not None:
        if not isinstance(cta_key, str):
            return "selected_cta_key_invalid_type"
        if not cta_key or cta_key != cta_key.strip():
            return "selected_cta_key_invalid"
    return None


def coerce_material_bound_package(value: object) -> ResponsePlanAdapterBoundPackage:
    """Validate structural shape and return a contract-owned bound-package view."""

    reason = material_bound_package_invalid_reason(value)
    if reason is not None:
        raise ValueError(reason)
    if isinstance(value, ResponsePlanAdapterBoundPackage):
        return value
    package = value.package
    navigation = package.navigation_followups
    if navigation is None:
        navigation = ()
    return ResponsePlanAdapterBoundPackage(
        spec=value.spec,
        package=ResponsePlanAdapterMaterialPackage(
            materials=package.materials,
            plan=package.plan,
            selected_followups=package.selected_followups,
            navigation_followups=navigation,
        ),
        selected_cta_key=value.selected_cta_key,
    )


ValidatedMaterialBoundPackage = Annotated[
    ResponsePlanAdapterBoundPackage,
    BeforeValidator(coerce_material_bound_package),
]

ResponsePlanAdapterErrorCode = Literal[
    "adapter_client_mismatch",
    "adapter_spec_turn_conflict",
    "adapter_route_mode_unsupported",
    "adapter_scope_unavailable",
    "adapter_package_source_incoherent",
    "adapter_material_authority_required",
    "adapter_material_authority_forbidden",
    "adapter_price_intent_without_offer",
    "adapter_price_shape_unsupported",
    "adapter_price_metadata_incomplete",
    "adapter_price_conditions_unavailable",
    "adapter_fact_source_missing",
    "adapter_fact_role_unsupported",
    "adapter_service_value_source_missing",
    "adapter_ui_source_invalid",
    "adapter_terminal_authority_invalid",
    "adapter_composer_contract_incompatible",
    "adapter_composer_envelope_invalid",
    "adapter_composer_route_mismatch",
]

ADAPTER_ERROR_CODES: frozenset[str] = frozenset(
    {
        "adapter_client_mismatch",
        "adapter_spec_turn_conflict",
        "adapter_route_mode_unsupported",
        "adapter_scope_unavailable",
        "adapter_package_source_incoherent",
        "adapter_material_authority_required",
        "adapter_material_authority_forbidden",
        "adapter_price_intent_without_offer",
        "adapter_price_shape_unsupported",
        "adapter_price_metadata_incomplete",
        "adapter_price_conditions_unavailable",
        "adapter_fact_source_missing",
        "adapter_fact_role_unsupported",
        "adapter_service_value_source_missing",
        "adapter_ui_source_invalid",
        "adapter_terminal_authority_invalid",
        "adapter_composer_contract_incompatible",
        "adapter_composer_envelope_invalid",
        "adapter_composer_route_mismatch",
    }
)


class ResponsePlanAdapterError(Exception):
    """Typed fail-closed adapter boundary error."""

    def __init__(self, code: ResponsePlanAdapterErrorCode, detail: object = None) -> None:
        if code not in ADAPTER_ERROR_CODES:
            raise ValueError("adapter_error_code_invalid")
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


class ResponsePlanAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResponsePlanAdapterSessionState(ResponsePlanAdapterModel):
    last_service_id: str | None = None
    history_turn_count: int = Field(default=0, ge=0)


class ResponsePlanAdapterMaterialAuthority(ResponsePlanAdapterModel):
    """Typed ownership for one materialized offline response package."""

    source_client_id: NonBlankStr
    bound_package: ValidatedMaterialBoundPackage


class ResponsePlanAdapterComposerRouteAuthority(ResponsePlanAdapterModel):
    kind: Literal["composer_selected"] = "composer_selected"


class ResponsePlanAdapterDeterministicRouteAuthority(ResponsePlanAdapterModel):
    kind: Literal["deterministic_bypass"] = "deterministic_bypass"
    route: ResponseRoute
    mode: ResponseMode = "standard"

    @model_validator(mode="after")
    def _validate_pair(self) -> Self:
        if (self.route, self.mode) not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        return self


ResponsePlanAdapterRouteAuthority = (
    ResponsePlanAdapterComposerRouteAuthority | ResponsePlanAdapterDeterministicRouteAuthority
)


class ResponsePlanAdapterConditionAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    required_conditions: tuple[RequiredOfferConditionBlock, ...] = ()
    price_response_requires_conditions: bool = False


class ResponsePlanAdapterTextualCtaAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    text: NonBlankStr


class ResponsePlanAdapterUiButtonAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    button_id: NonBlankStr
    label: NonBlankStr
    action_kind: Literal["contact", "cta", "widget", "video"]


class ResponsePlanAdapterUiWidgetAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    widget_offer_id: NonBlankStr


class ResponsePlanAdapterUiVideoAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    video_id: NonBlankStr


class ResponsePlanAdapterUiAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    buttons: tuple[ResponsePlanAdapterUiButtonAuthority, ...] = ()
    widget: ResponsePlanAdapterUiWidgetAuthority | None = None
    video: ResponsePlanAdapterUiVideoAuthority | None = None


class ResponsePlanAdapterTerminalAuthority(ResponsePlanAdapterModel):
    source_client_id: NonBlankStr
    route: ResponseRoute
    mode: ResponseMode
    authority: CodeOwnedAuthority
    display_text: NonBlankStr
    canonical_contact: CanonicalContactCandidate | None = None

    @model_validator(mode="after")
    def _validate_terminal(self) -> Self:
        if (self.route, self.mode) not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        if self.route == "ANSWER" and self.mode == "contacts":
            if self.authority != "contacts":
                raise ValueError("terminal_authority_invalid")
            if self.canonical_contact is None:
                raise ValueError("contacts_terminal_requires_contact")
        if self.route == "ADMIN":
            if self.authority not in {"governed_ui", "deterministic_policy_terminal"}:
                raise ValueError("terminal_authority_invalid")
        if self.route == "CLARIFY":
            raise ValueError("clarify_terminal_forbidden")
        return self


class ResponsePlanAdapterSources(ResponsePlanAdapterModel):
    session_key: SessionKey
    context_strategy: ContextStrategy
    transport_kind: TransportKind = "blocking"
    turn_frame: TurnFrame
    material_authority: ResponsePlanAdapterMaterialAuthority | None = None
    allowed_topic_ids: tuple[str, ...]
    session_state: ResponsePlanAdapterSessionState = Field(
        default_factory=ResponsePlanAdapterSessionState
    )
    route_authority: ResponsePlanAdapterRouteAuthority
    condition_authority: ResponsePlanAdapterConditionAuthority | None = None
    terminal_authorities: tuple[ResponsePlanAdapterTerminalAuthority, ...] = ()
    ui_authority: ResponsePlanAdapterUiAuthority | None = None
    textual_cta_authority: ResponsePlanAdapterTextualCtaAuthority | None = None


FORBIDDEN_LEGACY_COMPOSER_TYPE_NAMES: frozenset[str] = frozenset(
    {
        "TargetUnverifiedComposedResponse",
        "TargetVerifiedComposedResponse",
    }
)


def assert_not_legacy_composer_output(source: object) -> None:
    """Reject current incompatible Composer outputs at the adapter boundary."""

    type_name = type(source).__name__
    if type_name in FORBIDDEN_LEGACY_COMPOSER_TYPE_NAMES:
        raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", type_name)
    if isinstance(source, dict):
        if "direct_fact_ids" in source:
            raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", "direct_fact_ids")
        if "text" in source and "patient_text" not in source and "requested_fact_ids" not in source:
            raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", "legacy_text_field")
    raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", type_name)


def adapt_composer_json_to_decision(
    raw_json: str,
    authority: ComposerDecisionAuthority,
) -> AdaptedComposerDecision:
    """Thin delegation to canonical parser and decision adapter."""

    try:
        parsed = parse_response_plan_composer_json(raw_json)
    except ComposerParserError as exc:
        raise ResponsePlanAdapterError("adapter_composer_envelope_invalid", exc) from exc
    try:
        return adapt_composer_envelope_to_decision(parsed, authority)
    except ComposerAdapterError as exc:
        if exc.code == "composer_forbidden_for_bypass":
            raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", exc.detail) from exc
        if exc.code == "route_mode_not_allowed":
            raise ResponsePlanAdapterError("adapter_composer_route_mismatch", exc.detail) from exc
        raise ResponsePlanAdapterError("adapter_composer_envelope_invalid", exc) from exc


def adapt_parsed_composer_envelope_to_decision(
    parsed: ParsedComposerEnvelope,
    authority: ComposerDecisionAuthority,
) -> AdaptedComposerDecision:
    """Thin delegation for callers that already parsed Composer JSON."""

    try:
        return adapt_composer_envelope_to_decision(parsed, authority)
    except ComposerAdapterError as exc:
        if exc.code == "composer_forbidden_for_bypass":
            raise ResponsePlanAdapterError("adapter_composer_contract_incompatible", exc.detail) from exc
        if exc.code == "route_mode_not_allowed":
            raise ResponsePlanAdapterError("adapter_composer_route_mismatch", exc.detail) from exc
        raise ResponsePlanAdapterError("adapter_composer_envelope_invalid", exc) from exc
