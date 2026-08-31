"""Isolated adapter source contracts for RESPONSE-ADAPTER-1 (unwired)."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from contracts.response_plan import (
    ALLOWED_ROUTE_MODE_PAIRS,
    CanonicalContactCandidate,
    CodeOwnedAuthority,
    CodeOwnedTerminalCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    ContextStrategy,
    DeterministicBypassRouteAuthority,
    PreComposerPlan,
    RequiredOfferConditionBlock,
    ResponseRoute,
    ResponseMode,
    RouteModePair,
    SessionKey,
    TransportKind,
    UniqueRequestedFactIds,
    all_allowed_route_mode_pairs,
    _require_non_blank,
    _unique_requested_fact_ids,
)
from contracts.turn_frame import TurnFrame
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
UniqueRequestedFactIdsEnvelope = Annotated[tuple[str, ...], AfterValidator(_unique_requested_fact_ids)]

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
    bound_package: TargetSpecBoundOfflineResponsePackage


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


class StrictTargetComposerEnvelope(ResponsePlanAdapterModel):
    route: ResponseRoute
    mode: ResponseMode = "standard"
    patient_text: str | None = None
    price_text: str | None = None
    requested_fact_ids: UniqueRequestedFactIdsEnvelope = ()


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


def envelope_to_composer_result(envelope: StrictTargetComposerEnvelope) -> ComposerResult:
    """Convert strict isolated envelope into target ComposerResult."""

    try:
        return ComposerResult(
            route=envelope.route,
            mode=envelope.mode,
            patient_text=envelope.patient_text,
            price_text=envelope.price_text,
            requested_fact_ids=envelope.requested_fact_ids,
        )
    except Exception as exc:
        raise ResponsePlanAdapterError("adapter_composer_envelope_invalid", exc) from exc


def assert_envelope_matches_plan(
    envelope: StrictTargetComposerEnvelope,
    plan: PreComposerPlan,
) -> None:
    authority = plan.route_authority
    if not isinstance(authority, ComposerSelectedRouteAuthority):
        raise ResponsePlanAdapterError(
            "adapter_composer_contract_incompatible",
            "deterministic_bypass",
        )
    allowed = {(item.route, item.mode) for item in authority.allowed_route_modes}
    if (envelope.route, envelope.mode) not in allowed:
        raise ResponsePlanAdapterError(
            "adapter_composer_route_mismatch",
            (envelope.route, envelope.mode, tuple(sorted(allowed))),
        )
