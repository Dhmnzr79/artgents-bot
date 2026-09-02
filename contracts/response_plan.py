"""Isolated response-plan contracts for the one-call lower path (RESPONSE-PLAN-1)."""

from __future__ import annotations

from typing import Annotated, Literal, Self, Union

from contracts.response_schema import RequestedDisplayPolicy

from pydantic import AfterValidator, BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

ResponseRoute = Literal["ANSWER", "ADMIN", "CLARIFY"]
ResponseMode = Literal["standard", "contacts", "medical_terminal"]
ContextStrategy = Literal["full_context", "hybrid"]
ResponseScope = Literal["service", "topic", "clinic"]
FactApplicability = Literal["clinic_wide", "topic_scoped", "service_scoped"]
PricePlanKind = Literal["none", "single", "multi"]
ExecutionKind = Literal["composer", "code_owned_terminal"]
CodeOwnedAuthority = Literal["contacts", "governed_ui", "deterministic_policy_terminal"]
ResolvedPriceOwner = Literal[
    "canonical_single",
    "canonical_multi",
]
FactRole = Literal["requested_fact", "promo", "automatic_amplifier"]
RequiredOfferConditionId = Literal[
    "per_jaw",
    "per_tooth",
    "package_includes",
    "mandatory_exclusion",
    "ct_separate",
    "bone_grafting_separate",
]
DiagnosticClass = Literal[
    "model_contract_violation",
    "canonical_correction",
    "optional_resolution",
]
PlanDiagnosticCode = Literal[
    "requested_fact_unknown",
    "requested_fact_inapplicable",
    "explicit_only_automatic_suppressed",
    "optional_candidate_unavailable",
    "service_value_out_of_scope",
    "model_contract_violation",
]
TransportKind = Literal["blocking", "streaming"]
TerminalState = Literal["none", "admin", "contacts", "clarify", "medical_terminal"]

ALLOWED_ROUTE_MODE_PAIRS: frozenset[tuple[ResponseRoute, ResponseMode]] = frozenset(
    {
        ("ANSWER", "standard"),
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
        ("CLARIFY", "standard"),
    }
)
COMPOSER_ROUTE_MODE_PAIRS: frozenset[tuple[ResponseRoute, ResponseMode]] = frozenset(
    {
        ("ANSWER", "standard"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
        ("CLARIFY", "standard"),
    }
)
CODE_OWNED_ROUTE_MODE_PAIRS: frozenset[tuple[ResponseRoute, ResponseMode]] = frozenset(
    {
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    }
)
COMPOSER_TERMINAL_OUTCOME_PAIRS: frozenset[tuple[ResponseRoute, ResponseMode]] = frozenset(
    {
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    }
)

DIAGNOSTIC_CLASSIFICATION: dict[PlanDiagnosticCode, DiagnosticClass] = {
    "requested_fact_unknown": "model_contract_violation",
    "requested_fact_inapplicable": "model_contract_violation",
    "optional_candidate_unavailable": "optional_resolution",
    "explicit_only_automatic_suppressed": "optional_resolution",
    "service_value_out_of_scope": "optional_resolution",
    "model_contract_violation": "model_contract_violation",
}

EXPECTED_TERMINAL_STATE: dict[tuple[ResponseRoute, ResponseMode], tuple[TerminalState, bool]] = {
    ("ANSWER", "standard"): ("none", False),
    ("ANSWER", "contacts"): ("contacts", False),
    ("ADMIN", "standard"): ("admin", False),
    ("ADMIN", "medical_terminal"): ("medical_terminal", False),
    ("CLARIFY", "standard"): ("clarify", True),
}


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("string_must_not_be_blank")
    return value


def _unique_non_blank_ids(values: tuple[str, ...], *, duplicate_error: str) -> tuple[str, ...]:
    seen: set[str] = set()
    for item in values:
        if item != item.strip():
            raise ValueError("candidate_id_whitespace_padded")
        if not item:
            raise ValueError("candidate_id_blank")
        if item in seen:
            raise ValueError(duplicate_error)
        seen.add(item)
    return values


def _unique_requested_fact_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return _unique_non_blank_ids(values, duplicate_error="requested_fact_id_duplicate")


def _unique_promo_candidate_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return _unique_non_blank_ids(values, duplicate_error="promo_candidate_id_duplicate")


def _unique_amplifier_candidate_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return _unique_non_blank_ids(values, duplicate_error="amplifier_candidate_id_duplicate")


def _unique_commercial_facts(
    facts: tuple["CommercialFactCandidate", ...],
) -> tuple["CommercialFactCandidate", ...]:
    seen: set[str] = set()
    for fact in facts:
        if fact.fact_id in seen:
            raise ValueError("commercial_fact_id_duplicate")
        seen.add(fact.fact_id)
    return facts


def _unique_required_conditions(
    conditions: tuple["RequiredOfferConditionBlock", ...],
) -> tuple["RequiredOfferConditionBlock", ...]:
    seen: set[str] = set()
    for condition in conditions:
        if condition.condition_id in seen:
            raise ValueError("required_condition_id_duplicate")
        seen.add(condition.condition_id)
    return conditions


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
UniqueRequestedFactIds = Annotated[tuple[str, ...], AfterValidator(_unique_requested_fact_ids)]
UniquePromoCandidateIds = Annotated[tuple[str, ...], AfterValidator(_unique_promo_candidate_ids)]
UniqueAmplifierCandidateIds = Annotated[
    tuple[str, ...],
    AfterValidator(_unique_amplifier_candidate_ids),
]
UniqueCommercialFacts = Annotated[
    tuple["CommercialFactCandidate", ...],
    AfterValidator(_unique_commercial_facts),
]
UniqueRequiredOfferConditions = Annotated[
    tuple["RequiredOfferConditionBlock", ...],
    AfterValidator(_unique_required_conditions),
]


class ResponsePlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SessionKey(ResponsePlanModel):
    client_id: NonBlankStr
    sid: NonBlankStr


class RouteModePair(ResponsePlanModel):
    route: ResponseRoute
    mode: ResponseMode

    @model_validator(mode="after")
    def _validate_pair(self) -> Self:
        if (self.route, self.mode) not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        return self


def all_allowed_route_mode_pairs() -> tuple[RouteModePair, ...]:
    return tuple(
        RouteModePair(route=route, mode=mode)
        for route, mode in sorted(ALLOWED_ROUTE_MODE_PAIRS)
    )


class PlanDiagnostic(ResponsePlanModel):
    code: PlanDiagnosticCode
    detail: str | None = None
    classification: DiagnosticClass

    @model_validator(mode="before")
    @classmethod
    def _assign_classification(cls, data: object) -> object:
        if isinstance(data, dict) and "classification" not in data:
            code = data.get("code")
            if code in DIAGNOSTIC_CLASSIFICATION:
                data = {**data, "classification": DIAGNOSTIC_CLASSIFICATION[code]}
        return data

    @model_validator(mode="after")
    def _validate_classification(self) -> Self:
        expected = DIAGNOSTIC_CLASSIFICATION[self.code]
        if self.classification != expected:
            raise ValueError("diagnostic_classification_mismatch")
        return self


class ResponseCaps(ResponsePlanModel):
    max_service_value: int = Field(default=1, ge=0)
    max_promo: int = Field(default=2, ge=0)
    max_automatic_amplifiers: int = Field(default=2, ge=0)


class CanonicalContactCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    phone: NonBlankStr


class CodeOwnedTerminalCandidate(ResponsePlanModel):
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


class ComposerSelectedRouteAuthority(ResponsePlanModel):
    kind: Literal["composer_selected"] = "composer_selected"
    allowed_route_modes: tuple[RouteModePair, ...]
    terminal_candidates: tuple[CodeOwnedTerminalCandidate, ...] = ()

    @model_validator(mode="after")
    def _validate_authority(self) -> Self:
        if not self.allowed_route_modes:
            raise ValueError("allowed_route_modes_empty")
        allowed_pairs = [(item.route, item.mode) for item in self.allowed_route_modes]
        if len(allowed_pairs) != len(set(allowed_pairs)):
            raise ValueError("allowed_route_modes_duplicate")
        candidate_pairs = {(item.route, item.mode) for item in self.terminal_candidates}
        if len(candidate_pairs) != len(self.terminal_candidates):
            raise ValueError("terminal_candidate_duplicate")
        for pair in allowed_pairs:
            if pair not in ALLOWED_ROUTE_MODE_PAIRS:
                raise ValueError("route_mode_conflict")
            if pair in COMPOSER_TERMINAL_OUTCOME_PAIRS and pair not in candidate_pairs:
                raise ValueError("terminal_candidate_missing")
        for terminal in self.terminal_candidates:
            pair = (terminal.route, terminal.mode)
            if pair not in COMPOSER_TERMINAL_OUTCOME_PAIRS:
                raise ValueError("terminal_candidate_invalid_pair")
            if pair not in allowed_pairs:
                raise ValueError("terminal_candidate_not_allowed")
        return self


class DeterministicBypassRouteAuthority(ResponsePlanModel):
    kind: Literal["deterministic_bypass"] = "deterministic_bypass"
    route_mode: RouteModePair
    terminal_candidate: CodeOwnedTerminalCandidate

    @model_validator(mode="after")
    def _validate_authority(self) -> Self:
        pair = (self.route_mode.route, self.route_mode.mode)
        if pair not in CODE_OWNED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        if (self.terminal_candidate.route, self.terminal_candidate.mode) != pair:
            raise ValueError("terminal_candidate_mismatch")
        return self


def _route_authority_discriminator(value: object) -> str:
    if isinstance(value, dict):
        kind = value.get("kind")
        if kind in {"composer_selected", "deterministic_bypass"}:
            return kind
    kind = getattr(value, "kind", None)
    if kind in {"composer_selected", "deterministic_bypass"}:
        return kind
    raise ValueError("route_authority_kind_invalid")


RouteAuthority = Annotated[
    Union[
        Annotated[ComposerSelectedRouteAuthority, Tag("composer_selected")],
        Annotated[DeterministicBypassRouteAuthority, Tag("deterministic_bypass")],
    ],
    Discriminator(_route_authority_discriminator),
]


class CanonicalSinglePriceCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    offer_id: NonBlankStr
    display_text: NonBlankStr
    amount: int = Field(ge=0)
    currency: NonBlankStr
    billing_unit: NonBlankStr


class CanonicalMultiPriceCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    offer_ids: tuple[NonBlankStr, ...]
    display_text: NonBlankStr

    @model_validator(mode="after")
    def _validate_offer_ids(self) -> Self:
        if not (2 <= len(self.offer_ids) <= 3):
            raise ValueError("multi_price_requires_two_or_three_offers")
        if len(self.offer_ids) != len(set(self.offer_ids)):
            raise ValueError("multi_price_duplicate_offer_ids")
        return self


class PricePlan(ResponsePlanModel):
    kind: PricePlanKind
    single: CanonicalSinglePriceCandidate | None = None
    multi: CanonicalMultiPriceCandidate | None = None
    offer_applicable: bool = True

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if self.kind == "none":
            if self.single is not None or self.multi is not None:
                raise ValueError("none_price_plan_must_be_empty")
            return self
        if self.kind == "single":
            if self.single is None or self.multi is not None:
                raise ValueError("single_price_plan_requires_one_block")
            return self
        if self.kind == "multi":
            if self.single is not None or self.multi is None:
                raise ValueError("multi_price_plan_requires_combined_block")
            return self
        raise ValueError("unknown_price_plan_kind")


class RequiredOfferConditionBlock(ResponsePlanModel):
    source_client_id: NonBlankStr
    condition_id: RequiredOfferConditionId
    display_text: NonBlankStr


class CommercialFactCandidate(ResponsePlanModel):
    fact_id: NonBlankStr
    display_text: NonBlankStr
    explicit_only: bool = False
    allowed_roles: tuple[FactRole, ...]
    applicability: FactApplicability
    allowed_topic_ids: tuple[str, ...] = ()
    allowed_service_ids: tuple[str, ...] = ()
    source_client_id: NonBlankStr
    requires_implant_scope: bool = False
    requested_display_policy: RequestedDisplayPolicy | None = None

    @model_validator(mode="after")
    def _validate_roles(self) -> Self:
        if not self.allowed_roles:
            raise ValueError("commercial_fact_requires_allowed_roles")
        if self.explicit_only and "requested_fact" not in self.allowed_roles:
            raise ValueError("explicit_only_requires_requested_fact_role")
        if self.requires_implant_scope and not self.allowed_topic_ids and not self.allowed_service_ids:
            raise ValueError("implant_scope_requires_allowed_metadata")
        return self


class ServiceValueCandidate(ResponsePlanModel):
    fact_id: NonBlankStr
    display_text: NonBlankStr
    source_client_id: NonBlankStr


class TextualCtaCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    text: NonBlankStr


class UiQuickReplyCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    reply_id: NonBlankStr
    label: NonBlankStr


class UiButtonCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    button_id: NonBlankStr
    label: NonBlankStr
    action_kind: Literal["contact", "cta", "widget", "video"]


class UiWidgetCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    widget_offer_id: NonBlankStr


class UiVideoCandidate(ResponsePlanModel):
    source_client_id: NonBlankStr
    video_id: NonBlankStr


class UiPlanCandidates(ResponsePlanModel):
    quick_replies: tuple[UiQuickReplyCandidate, ...] = ()
    buttons: tuple[UiButtonCandidate, ...] = ()
    widget: UiWidgetCandidate | None = None
    video: UiVideoCandidate | None = None


class PreComposerPlan(ResponsePlanModel):
    session_key: SessionKey
    context_strategy: ContextStrategy
    route_authority: RouteAuthority
    response_scope: ResponseScope
    selected_service_id: str | None = None
    active_session_service_id: str | None = None
    selected_topic_id: str | None = None
    history_turn_count: int = Field(default=0, ge=0)
    price_plan: PricePlan
    required_offer_conditions: UniqueRequiredOfferConditions = ()
    commercial_facts: UniqueCommercialFacts = ()
    promo_candidate_ids: UniquePromoCandidateIds = ()
    automatic_amplifier_candidate_ids: UniqueAmplifierCandidateIds = ()
    service_value_candidate: ServiceValueCandidate | None = None
    textual_cta_candidate: TextualCtaCandidate | None = None
    normal_caps: ResponseCaps = Field(default_factory=ResponseCaps)
    price_caps: ResponseCaps = Field(
        default_factory=lambda: ResponseCaps(
            max_service_value=0,
            max_promo=2,
            max_automatic_amplifiers=4,
        )
    )
    ui_candidates: UiPlanCandidates = Field(default_factory=UiPlanCandidates)
    transport_kind: TransportKind = "blocking"

    @model_validator(mode="after")
    def _validate_scope(self) -> Self:
        if self.selected_service_id is not None and not self.selected_service_id.strip():
            raise ValueError("selected_service_id_blank_forbidden")
        if (
            self.active_session_service_id is not None
            and not self.active_session_service_id.strip()
        ):
            raise ValueError("active_session_service_id_blank_forbidden")
        if self.selected_topic_id is not None and not self.selected_topic_id.strip():
            raise ValueError("selected_topic_id_blank_forbidden")
        if self.response_scope == "service":
            if self.selected_service_id is None:
                raise ValueError("service_scope_requires_selected_service_id")
        elif self.response_scope == "topic":
            if self.selected_topic_id is None:
                raise ValueError("topic_scope_requires_selected_topic_id")
            if self.selected_service_id is not None:
                raise ValueError("topic_scope_forbids_selected_service_id")
        elif self.response_scope == "clinic":
            if self.selected_service_id is not None:
                raise ValueError("clinic_scope_forbids_selected_service_id")
            if self.selected_topic_id is not None:
                raise ValueError("clinic_scope_forbids_selected_topic_id")
        return self

    @model_validator(mode="after")
    def _validate_caps(self) -> Self:
        normal = self.normal_caps
        if normal.max_service_value > 1:
            raise ValueError("normal_caps_max_service_value_exceeded")
        if normal.max_promo > 2:
            raise ValueError("normal_caps_max_promo_exceeded")
        if normal.max_automatic_amplifiers > 2:
            raise ValueError("normal_caps_max_amplifiers_exceeded")
        price = self.price_caps
        if price.max_service_value != 0:
            raise ValueError("price_caps_max_service_value_must_be_zero")
        if price.max_promo > 2:
            raise ValueError("price_caps_max_promo_exceeded")
        if price.max_automatic_amplifiers > 4:
            raise ValueError("price_caps_max_amplifiers_exceeded")
        return self

    @property
    def client_id(self) -> str:
        return self.session_key.client_id


class ComposerResult(ResponsePlanModel):
    route: ResponseRoute
    mode: ResponseMode = "standard"
    patient_text: str | None = None
    requested_fact_ids: UniqueRequestedFactIds = ()

    @model_validator(mode="after")
    def _validate_pair_and_invariants(self) -> Self:
        pair = (self.route, self.mode)
        if pair not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")
        if pair == ("ANSWER", "standard"):
            if not (self.patient_text and self.patient_text.strip()):
                raise ValueError("answer_requires_patient_text")
        elif pair == ("ANSWER", "contacts"):
            if self.patient_text is not None:
                raise ValueError("contacts_requires_null_patient_text")
            if self.requested_fact_ids:
                raise ValueError("contacts_forbids_requested_facts")
        elif self.route == "ADMIN":
            if self.patient_text is not None:
                raise ValueError("admin_requires_null_patient_text")
            if self.requested_fact_ids:
                raise ValueError("admin_forbids_requested_facts")
        elif self.route == "CLARIFY":
            if not (self.patient_text and self.patient_text.strip()):
                raise ValueError("clarify_requires_patient_text")
            if self.requested_fact_ids:
                raise ValueError("clarify_forbids_requested_facts")
        return self


class ResolvedPriceBlock(ResponsePlanModel):
    source_client_id: NonBlankStr
    offer_ids: tuple[NonBlankStr, ...]
    display_text: NonBlankStr
    owner: ResolvedPriceOwner
    amount: int | None = Field(default=None, ge=0)
    currency: NonBlankStr | None = None
    billing_unit: NonBlankStr | None = None

    @model_validator(mode="after")
    def _validate_offer_ids(self) -> Self:
        if not self.offer_ids:
            raise ValueError("price_block_requires_offer_ids")
        if len(self.offer_ids) != len(set(self.offer_ids)):
            raise ValueError("price_block_duplicate_offer_ids")
        if len(self.offer_ids) == 1:
            if self.owner != "canonical_single":
                raise ValueError("single_price_invalid_owner")
            if self.amount is None or self.currency is None or self.billing_unit is None:
                raise ValueError("single_price_requires_amount_metadata")
            return self
        if not (2 <= len(self.offer_ids) <= 3):
            raise ValueError("multi_price_requires_two_or_three_offers")
        if self.owner != "canonical_multi":
            raise ValueError("multi_price_invalid_owner")
        if self.amount is not None or self.currency is not None or self.billing_unit is not None:
            raise ValueError("multi_price_forbids_amount_metadata")
        return self


class ResolvedFactBlock(ResponsePlanModel):
    fact_id: NonBlankStr
    display_text: NonBlankStr
    role: FactRole
    source_client_id: NonBlankStr


class ResolvedServiceValueBlock(ResponsePlanModel):
    fact_id: NonBlankStr
    display_text: NonBlankStr
    source_client_id: NonBlankStr


class ResolvedTextualCtaBlock(ResponsePlanModel):
    source_client_id: NonBlankStr
    text: NonBlankStr


class ResolvedUiPlan(ResponsePlanModel):
    quick_replies: tuple[UiQuickReplyCandidate, ...] = ()
    buttons: tuple[UiButtonCandidate, ...] = ()
    widget: UiWidgetCandidate | None = None
    video: UiVideoCandidate | None = None
    contact: CanonicalContactCandidate | None = None


class FinalizedCommercialIds(ResponsePlanModel):
    requested_fact_ids: tuple[str, ...] = ()
    promo_fact_ids: tuple[str, ...] = ()
    amplifier_fact_ids: tuple[str, ...] = ()
    service_value_ids: tuple[str, ...] = ()
    price_offer_ids: tuple[str, ...] = ()
    required_offer_condition_ids: tuple[str, ...] = ()


class ResponseSessionDelta(ResponsePlanModel):
    session_key: SessionKey
    active_service_id: str | None = None
    active_topic_id: str | None = None
    shown_requested_fact_ids: tuple[str, ...] = ()
    shown_promo_ids: tuple[str, ...] = ()
    shown_amplifier_ids: tuple[str, ...] = ()
    shown_service_value_ids: tuple[str, ...] = ()
    shown_price_offer_ids: tuple[str, ...] = ()
    shown_required_offer_condition_ids: tuple[str, ...] = ()
    terminal_state: TerminalState = "none"
    clarify_pending: bool = False


def _assert_no_commerce(plan: ResolvedResponsePlan) -> None:
    if plan.price_block is not None:
        raise ValueError("terminal_plan_forbids_price_block")
    if plan.required_offer_conditions:
        raise ValueError("terminal_plan_forbids_required_conditions")
    if plan.requested_fact_blocks:
        raise ValueError("terminal_plan_forbids_requested_facts")
    if plan.service_value_block is not None:
        raise ValueError("terminal_plan_forbids_service_value")
    if plan.promo_blocks:
        raise ValueError("terminal_plan_forbids_promo")
    if plan.automatic_amplifier_blocks:
        raise ValueError("terminal_plan_forbids_amplifiers")
    if plan.textual_cta_block is not None:
        raise ValueError("terminal_plan_forbids_textual_cta")
    finalized = plan.finalized_commercial_ids
    if any(
        (
            finalized.requested_fact_ids,
            finalized.promo_fact_ids,
            finalized.amplifier_fact_ids,
            finalized.service_value_ids,
            finalized.price_offer_ids,
            finalized.required_offer_condition_ids,
        )
    ):
        raise ValueError("terminal_plan_forbids_finalized_commercial_ids")
    delta = plan.session_delta
    if any(
        (
            delta.shown_requested_fact_ids,
            delta.shown_promo_ids,
            delta.shown_amplifier_ids,
            delta.shown_service_value_ids,
            delta.shown_price_offer_ids,
            delta.shown_required_offer_condition_ids,
        )
    ):
        raise ValueError("terminal_plan_forbids_session_shown_ids")


def _validate_fact_role_uniqueness(plan: ResolvedResponsePlan) -> None:
    groups = {
        "requested": tuple(block.fact_id for block in plan.requested_fact_blocks),
        "service_value": (
            (plan.service_value_block.fact_id,) if plan.service_value_block is not None else ()
        ),
        "promo": tuple(block.fact_id for block in plan.promo_blocks),
        "amplifier": tuple(block.fact_id for block in plan.automatic_amplifier_blocks),
    }
    for name, ids in groups.items():
        if len(ids) != len(set(ids)):
            raise ValueError(f"{name}_fact_ids_not_unique")
    seen: set[str] = set()
    for name, ids in groups.items():
        for fact_id in ids:
            if fact_id in seen:
                raise ValueError("visible_fact_id_role_conflict")
            seen.add(fact_id)


def _validate_finalized_ids(plan: ResolvedResponsePlan) -> None:
    finalized = plan.finalized_commercial_ids
    if finalized.requested_fact_ids != tuple(block.fact_id for block in plan.requested_fact_blocks):
        raise ValueError("finalized_requested_fact_ids_mismatch")
    if finalized.promo_fact_ids != tuple(block.fact_id for block in plan.promo_blocks):
        raise ValueError("finalized_promo_fact_ids_mismatch")
    if finalized.amplifier_fact_ids != tuple(
        block.fact_id for block in plan.automatic_amplifier_blocks
    ):
        raise ValueError("finalized_amplifier_fact_ids_mismatch")
    if finalized.service_value_ids != (
        (plan.service_value_block.fact_id,) if plan.service_value_block is not None else ()
    ):
        raise ValueError("finalized_service_value_ids_mismatch")
    if finalized.price_offer_ids != (
        tuple(plan.price_block.offer_ids) if plan.price_block is not None else ()
    ):
        raise ValueError("finalized_price_offer_ids_mismatch")
    if finalized.required_offer_condition_ids != tuple(
        block.condition_id for block in plan.required_offer_conditions
    ):
        raise ValueError("finalized_required_condition_ids_mismatch")
    if plan.price_block is None and finalized.required_offer_condition_ids:
        raise ValueError("finalized_condition_ids_without_price_block")


def _validate_session_delta_ids(plan: ResolvedResponsePlan) -> None:
    finalized = plan.finalized_commercial_ids
    delta = plan.session_delta
    if delta.shown_requested_fact_ids != finalized.requested_fact_ids:
        raise ValueError("session_requested_fact_ids_mismatch")
    if delta.shown_promo_ids != finalized.promo_fact_ids:
        raise ValueError("session_promo_ids_mismatch")
    if delta.shown_amplifier_ids != finalized.amplifier_fact_ids:
        raise ValueError("session_amplifier_ids_mismatch")
    if delta.shown_service_value_ids != finalized.service_value_ids:
        raise ValueError("session_service_value_ids_mismatch")
    if delta.shown_price_offer_ids != finalized.price_offer_ids:
        raise ValueError("session_price_offer_ids_mismatch")
    if delta.shown_required_offer_condition_ids != finalized.required_offer_condition_ids:
        raise ValueError("session_required_condition_ids_mismatch")


def _validate_session_scope(plan: ResolvedResponsePlan) -> None:
    delta = plan.session_delta
    if plan.response_scope == "service":
        if delta.active_service_id is None or not delta.active_service_id.strip():
            raise ValueError("service_scope_requires_active_service_id")
    elif plan.response_scope == "topic":
        if delta.active_service_id is not None:
            raise ValueError("topic_scope_forbids_active_service_id")
        if delta.active_topic_id is None or not delta.active_topic_id.strip():
            raise ValueError("topic_scope_requires_active_topic_id")
    elif plan.response_scope == "clinic":
        if delta.active_service_id is not None:
            raise ValueError("clinic_scope_forbids_active_service_id")
        if delta.active_topic_id is not None:
            raise ValueError("clinic_scope_forbids_active_topic_id")


def _validate_terminal_state(plan: ResolvedResponsePlan) -> None:
    pair = (plan.route, plan.mode)
    expected_state, expected_clarify = EXPECTED_TERMINAL_STATE[pair]
    delta = plan.session_delta
    if delta.terminal_state != expected_state:
        raise ValueError("session_terminal_state_mismatch")
    if delta.clarify_pending != expected_clarify:
        raise ValueError("session_clarify_pending_mismatch")


def _validate_block_roles(plan: ResolvedResponsePlan) -> None:
    for block in plan.requested_fact_blocks:
        if block.role != "requested_fact":
            raise ValueError("requested_block_wrong_role")
    for block in plan.promo_blocks:
        if block.role != "promo":
            raise ValueError("promo_block_wrong_role")
    for block in plan.automatic_amplifier_blocks:
        if block.role != "automatic_amplifier":
            raise ValueError("amplifier_block_wrong_role")


def _validate_resolved_client_ownership(plan: ResolvedResponsePlan) -> None:
    client_id = plan.session_delta.session_key.client_id

    def _check(item: object) -> None:
        source_client_id = getattr(item, "source_client_id", None)
        if source_client_id != client_id:
            raise ValueError("client_source_mismatch")

    if plan.price_block is not None:
        _check(plan.price_block)
    for condition in plan.required_offer_conditions:
        _check(condition)
    for block in plan.requested_fact_blocks:
        _check(block)
    if plan.service_value_block is not None:
        _check(plan.service_value_block)
    for block in plan.promo_blocks:
        _check(block)
    for block in plan.automatic_amplifier_blocks:
        _check(block)
    if plan.textual_cta_block is not None:
        _check(plan.textual_cta_block)
    ui = plan.ui_plan
    for item in ui.quick_replies:
        _check(item)
    for item in ui.buttons:
        _check(item)
    if ui.widget is not None:
        _check(ui.widget)
    if ui.video is not None:
        _check(ui.video)
    if ui.contact is not None:
        _check(ui.contact)


class ResolvedResponsePlan(ResponsePlanModel):
    route: ResponseRoute
    mode: ResponseMode
    context_strategy: ContextStrategy
    response_scope: ResponseScope
    transport_kind: TransportKind
    patient_text: str | None = None
    terminal_text: str | None = None
    price_block: ResolvedPriceBlock | None = None
    required_offer_conditions: tuple[RequiredOfferConditionBlock, ...] = ()
    requested_fact_blocks: tuple[ResolvedFactBlock, ...] = ()
    service_value_block: ResolvedServiceValueBlock | None = None
    promo_blocks: tuple[ResolvedFactBlock, ...] = ()
    automatic_amplifier_blocks: tuple[ResolvedFactBlock, ...] = ()
    textual_cta_block: ResolvedTextualCtaBlock | None = None
    ui_plan: ResolvedUiPlan
    diagnostics: tuple[PlanDiagnostic, ...] = ()
    finalized_commercial_ids: FinalizedCommercialIds
    session_delta: ResponseSessionDelta

    @property
    def is_price_answer(self) -> bool:
        return self.price_block is not None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        pair = (self.route, self.mode)
        if pair not in ALLOWED_ROUTE_MODE_PAIRS:
            raise ValueError("route_mode_conflict")

        if pair == ("ANSWER", "standard"):
            if not (self.patient_text and self.patient_text.strip()):
                raise ValueError("answer_requires_patient_text")
            if self.terminal_text is not None:
                raise ValueError("answer_standard_forbids_terminal_text")
        elif pair == ("ANSWER", "contacts"):
            if self.patient_text is not None:
                raise ValueError("contacts_requires_null_patient_text")
            if not (self.terminal_text and self.terminal_text.strip()):
                raise ValueError("contacts_requires_terminal_text")
            _assert_no_commerce(self)
        elif pair[0] == "ADMIN":
            if self.patient_text is not None:
                raise ValueError("admin_requires_null_patient_text")
            if not (self.terminal_text and self.terminal_text.strip()):
                raise ValueError("admin_requires_terminal_text")
            _assert_no_commerce(self)
        elif pair == ("CLARIFY", "standard"):
            if not (self.patient_text and self.patient_text.strip()):
                raise ValueError("clarify_requires_patient_text")
            if self.terminal_text is not None:
                raise ValueError("clarify_forbids_terminal_text")
            _assert_no_commerce(self)

        if self.required_offer_conditions and self.price_block is None:
            raise ValueError("conditions_require_price_block")

        if self.required_offer_conditions:
            condition_ids = [block.condition_id for block in self.required_offer_conditions]
            if len(condition_ids) != len(set(condition_ids)):
                raise ValueError("required_condition_ids_not_unique")

        _validate_fact_role_uniqueness(self)
        _validate_block_roles(self)
        _validate_finalized_ids(self)
        _validate_session_delta_ids(self)
        _validate_session_scope(self)
        _validate_terminal_state(self)
        _validate_resolved_client_ownership(self)
        return self


class ResponseUIProjection(ResponsePlanModel):
    quick_replies: tuple[UiQuickReplyCandidate, ...] = ()
    buttons: tuple[UiButtonCandidate, ...] = ()
    widget: UiWidgetCandidate | None = None
    video: UiVideoCandidate | None = None
    contact: CanonicalContactCandidate | None = None
    projected_commercial_ids: FinalizedCommercialIds
    transport_kind: TransportKind = "blocking"


class ResponsePlanContractError(ValueError):
    """Typed contract error for invalid plan/composer combinations."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
