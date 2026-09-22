"""Typed contracts for post-Composer response materialization (RESPONSE-MATERIALIZATION-1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Literal, Self

from pydantic import Field, model_validator

from contracts.response_plan import (
    CommercialFactCandidate,
    ComposerResult,
    ContextStrategy,
    PreComposerPlan,
    RequiredOfferConditionBlock,
    RequiredOfferConditionCompleteness,
    ResponsePlanModel,
    ResolvedResponsePlan,
    ResponseUIProjection,
    ServiceOptionsBlock,
    SessionKey,
    TransportKind,
    UiButtonCandidate,
    UiQuickReplyCandidate,
    UiVideoCandidate,
)
from contracts.response_plan_adapter import (
    ResponsePlanAdapterTerminalAuthority,
    ResponsePlanAdapterTextualCtaAuthority,
    ResponsePlanAdapterUiAuthority,
)
from contracts.response_plan_composer import AdaptedComposerDecision
from contracts.response_plan_post_composer import (
    PostComposerDiagnostic,
    PostComposerMaterialAuthority,
    PostComposerSelectionPlan,
    ResponseSituationDelta,
)

PriceLookupMode = Literal["catalog_reference", "situation_selection"]
OfferExclusionReason = Literal[
    "inactive_offer",
    "inactive_service_option",
    "invalid_service_option",
    "unsupported_price_mode",
    "conditions_unknown",
    "conditions_incomplete",
    "foreign_offer",
    "foreign_service",
]
MaterializationDiagnosticCode = Literal[
    "materialization_unsupported_price_mode",
    "materialization_price_conditions_incomplete",
    "materialization_price_conditions_unknown",
    "materialization_price_unit_incompatible",
    "materialization_offer_excluded",
    "materialization_no_price_candidates",
    "materialization_optional_unavailable",
    "materialization_foreign_material",
    "materialization_terminal_authority_missing",
]

_CONDITION_COMPLETENESS_VALUES = frozenset({"complete", "unknown", "incomplete"})
_PRICE_LOOKUP_MODES = frozenset({"catalog_reference", "situation_selection"})
_EXCLUSION_REASONS = frozenset(
    {
        "inactive_offer",
        "inactive_service_option",
        "invalid_service_option",
        "unsupported_price_mode",
        "conditions_unknown",
        "conditions_incomplete",
        "foreign_offer",
        "foreign_service",
    }
)
_DIAGNOSTIC_CODES = frozenset(
    {
        "materialization_unsupported_price_mode",
        "materialization_price_conditions_incomplete",
        "materialization_price_conditions_unknown",
        "materialization_price_unit_incompatible",
        "materialization_offer_excluded",
        "materialization_no_price_candidates",
        "materialization_optional_unavailable",
        "materialization_foreign_material",
        "materialization_terminal_authority_missing",
    }
)


class MaterializationOwnershipError(ValueError):
    """Strict ownership/session mismatch at materialization boundary."""


class MaterializationContractError(ValueError):
    """Invalid materialization contract input."""


class D2AuthoredContentAuthority(ResponsePlanModel):
    """Clinic-owned text that may be selected by a D1R content request."""

    source_client_id: str
    content_ref: str
    display_text: str
    allowed_service_ids: tuple[str, ...] = ()
    sections: tuple["D2AuthoredContentSection", ...] = ()

    @model_validator(mode="after")
    def _validate_d2_content(self) -> Self:
        for value, code in (
            (self.source_client_id, "d2_content_client_invalid"),
            (self.content_ref, "d2_content_ref_invalid"),
            (self.display_text, "d2_content_text_invalid"),
        ):
            if not value or value != value.strip():
                raise ValueError(code)
        if len(self.allowed_service_ids) != len(set(self.allowed_service_ids)):
            raise ValueError("d2_content_service_duplicate")
        if any(not value or value != value.strip() for value in self.allowed_service_ids):
            raise ValueError("d2_content_service_invalid")
        refs = [section.section_ref for section in self.sections]
        if len(refs) != len(set(refs)):
            raise ValueError("d2_content_section_duplicate")
        return self


class D2AuthoredContentSection(ResponsePlanModel):
    """One exact structural section of an approved content document."""

    section_ref: str
    display_text: str

    @model_validator(mode="after")
    def _validate_section(self) -> Self:
        if not self.section_ref or self.section_ref != self.section_ref.strip():
            raise ValueError("d2_content_section_ref_invalid")
        if not self.display_text or self.display_text != self.display_text.strip():
            raise ValueError("d2_content_section_text_invalid")
        return self


class D2DirectionAuthority(ResponsePlanModel):
    """Clinic-approved services available for one broad treatment direction."""

    source_client_id: str
    topic_id: str
    service_ids: tuple[str, ...]
    ordered_offer_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_d2_direction(self) -> Self:
        for value, code in (
            (self.source_client_id, "d2_direction_client_invalid"),
            (self.topic_id, "d2_direction_topic_invalid"),
        ):
            if not value or value != value.strip():
                raise ValueError(code)
        if not self.service_ids or len(self.service_ids) != len(set(self.service_ids)):
            raise ValueError("d2_direction_services_invalid")
        if any(not value or value != value.strip() for value in self.service_ids):
            raise ValueError("d2_direction_service_invalid")
        if (len(self.ordered_offer_ids) != len(set(self.ordered_offer_ids))
                or any(not value or value != value.strip() for value in self.ordered_offer_ids)):
            raise ValueError("d2_direction_offers_invalid")
        return self


class D2VolumeChoice(ResponsePlanModel):
    extent: Literal["one_tooth", "few_teeth", "full_arch", "unknown"]
    candidate: UiQuickReplyCandidate


class D2DirectionPricePresentation(ResponsePlanModel):
    source_client_id: str
    topic_id: str
    introduction_text: str
    unknown_extent_text: str
    volume_choices: tuple[D2VolumeChoice, ...] = ()

    @model_validator(mode="after")
    def _validate_d2_direction_price_presentation(self) -> Self:
        if any(not value or value != value.strip() for value in (
            self.source_client_id, self.topic_id, self.introduction_text, self.unknown_extent_text,
        )):
            raise ValueError("d2_direction_price_presentation_invalid")
        extents = [item.extent for item in self.volume_choices]
        replies = [item.candidate.reply_id for item in self.volume_choices]
        if len(extents) != len(set(extents)) or len(replies) != len(set(replies)):
            raise ValueError("d2_direction_price_presentation_duplicate")
        if any(item.candidate.source_client_id != self.source_client_id for item in self.volume_choices):
            raise ValueError("d2_direction_price_presentation_client_mismatch")
        return self


class D2SourceUiAuthority(ResponsePlanModel):
    """Source-owned navigation candidates for one approved D2 material."""

    source_client_id: str
    content_ref: str
    quick_replies: tuple[UiQuickReplyCandidate, ...] = ()
    video: UiVideoCandidate | None = None
    cta: UiButtonCandidate | None = None

    @model_validator(mode="after")
    def _validate_d2_source_ui(self) -> Self:
        for value, code in (
            (self.source_client_id, "d2_source_ui_client_invalid"),
            (self.content_ref, "d2_source_ui_ref_invalid"),
        ):
            if not value or value != value.strip():
                raise ValueError(code)
        # Navigation is optional.  Candidate-level problems are deliberately
        # diagnosed and omitted by the D2 materializer so they cannot suppress
        # an otherwise valid approved text.  The authority itself remains
        # tenant-bound below in ResponsePlanMaterializationSources.
        return self


class D2PartFailureAuthority(ResponsePlanModel):
    """Clinic-owned text for one recoverable D2 request-part failure."""

    source_client_id: str
    message_id: str
    reason: Literal[
        "d2_no_price_candidates",
        "d2_no_scope_price_candidates",
        "d2_model_prose_empty",
        "d2_model_prose_money",
        "d2_model_prose_link",
        "d2_content_source_missing",
    ]
    display_text: str

    @model_validator(mode="after")
    def _validate_d2_part_failure(self) -> Self:
        for value, code in (
            (self.source_client_id, "d2_part_failure_client_invalid"),
            (self.message_id, "d2_part_failure_message_invalid"),
            (self.display_text, "d2_part_failure_text_invalid"),
        ):
            if not value or value != value.strip():
                raise ValueError(code)
        return self


class OfferConditionEvidence(ResponsePlanModel):
    source_client_id: str
    offer_id: str
    completeness: RequiredOfferConditionCompleteness
    conditions: tuple[RequiredOfferConditionBlock, ...] = ()

    @model_validator(mode="after")
    def _validate_evidence(self) -> Self:
        if not self.offer_id or self.offer_id != self.offer_id.strip():
            raise ValueError("offer_condition_evidence_offer_id_invalid")
        if not self.source_client_id or self.source_client_id != self.source_client_id.strip():
            raise ValueError("offer_condition_evidence_client_id_invalid")
        if self.completeness not in _CONDITION_COMPLETENESS_VALUES:
            raise ValueError("offer_condition_evidence_completeness_invalid")
        if self.completeness == "complete" and self.conditions:
            for block in self.conditions:
                if block.completeness != "complete":
                    raise ValueError("offer_condition_evidence_completeness_mismatch")
                if block.source_client_id != self.source_client_id:
                    raise ValueError("offer_condition_evidence_block_client_mismatch")
                if block.display_text and block.entries:
                    raise ValueError("offer_condition_evidence_block_form_conflict")
                for entry in block.entries:
                    if entry.offer_id != self.offer_id:
                        raise ValueError("offer_condition_evidence_entry_offer_mismatch")
        return self


class D2CommercialPromoAuthority(ResponsePlanModel):
    source_client_id: str
    fact_id: str
    short_text: str
    full_text: str


class D2CommercialPackageAuthority(ResponsePlanModel):
    source_client_id: str
    package_id: str
    name: str
    body_text: str


class D2ServiceCommercialProfileAuthority(ResponsePlanModel):
    source_client_id: str
    service_id: str
    promo_refs: tuple[str, ...] = ()
    price_booster_id: str | None = None
    also_list_id: str | None = None


class D2CompatibilityGroupAuthority(ResponsePlanModel):
    source_client_id: str
    group_id: str
    offer_or_fact_ids: tuple[str, ...]
    explanation_text: str


class D2CommercialAuthority(ResponsePlanModel):
    source_client_id: str
    promo_facts: tuple[D2CommercialPromoAuthority, ...] = ()
    price_booster_packages: tuple[D2CommercialPackageAuthority, ...] = ()
    also_list_packages: tuple[D2CommercialPackageAuthority, ...] = ()
    service_profiles: tuple[D2ServiceCommercialProfileAuthority, ...] = ()
    incompatibility_groups: tuple[D2CompatibilityGroupAuthority, ...] = ()


class ResponsePlanMaterializationSources(ResponsePlanModel):
    session_key: SessionKey
    context_strategy: ContextStrategy
    transport_kind: TransportKind = "blocking"
    material_authority: PostComposerMaterialAuthority
    condition_evidence_by_offer: dict[str, OfferConditionEvidence] = Field(default_factory=dict)
    d2_published_terms_by_offer: dict[str, D2PublishedOfferTerms] = Field(default_factory=dict)
    terminal_authorities: tuple[ResponsePlanAdapterTerminalAuthority, ...] = ()
    ui_authority: ResponsePlanAdapterUiAuthority | None = None
    textual_cta_authority: ResponsePlanAdapterTextualCtaAuthority | None = None
    shown_requested_fact_ids: tuple[str, ...] = ()
    shown_promo_fact_ids: tuple[str, ...] = ()
    shown_amplifier_fact_ids: tuple[str, ...] = ()
    shown_service_value_ids: tuple[str, ...] = ()
    d2_authored_content: tuple[D2AuthoredContentAuthority, ...] = ()
    d2_directions: tuple[D2DirectionAuthority, ...] = ()
    d2_direction_price_presentations: tuple[D2DirectionPricePresentation, ...] = ()
    d2_source_ui: tuple[D2SourceUiAuthority, ...] = ()
    d2_part_failures: tuple[D2PartFailureAuthority, ...] = ()
    shown_d2_secondary_ref_ids: tuple[str, ...] = ()
    d2_snapshot_fingerprint: str = "fixture"
    d2_commercial: D2CommercialAuthority | None = None

    @model_validator(mode="after")
    def _validate_ownership(self) -> Self:
        client_id = self.session_key.client_id
        if not self.d2_snapshot_fingerprint or self.d2_snapshot_fingerprint != self.d2_snapshot_fingerprint.strip():
            raise ValueError("materialization_d2_snapshot_fingerprint_invalid")
        if self.material_authority.source_client_id != client_id:
            raise ValueError("materialization_client_mismatch")
        for authority in self.terminal_authorities:
            if authority.source_client_id != client_id:
                raise ValueError("materialization_terminal_client_mismatch")
        if self.ui_authority is not None and self.ui_authority.source_client_id != client_id:
            raise ValueError("materialization_ui_client_mismatch")
        if (
            self.textual_cta_authority is not None
            and self.textual_cta_authority.source_client_id != client_id
        ):
            raise ValueError("materialization_cta_client_mismatch")
        for key, evidence in self.condition_evidence_by_offer.items():
            if key != evidence.offer_id:
                raise ValueError("materialization_condition_key_mismatch")
            if evidence.source_client_id != client_id:
                raise ValueError("materialization_condition_client_mismatch")
        for key, terms in self.d2_published_terms_by_offer.items():
            if key != terms.offer_id:
                raise ValueError("materialization_d2_terms_key_mismatch")
            if terms.source_client_id != client_id:
                raise ValueError("materialization_d2_terms_client_mismatch")
        content_refs: set[str] = set()
        for content in self.d2_authored_content:
            if content.source_client_id != client_id:
                raise ValueError("materialization_d2_content_client_mismatch")
            if content.content_ref in content_refs:
                raise ValueError("materialization_d2_content_ref_duplicate")
            content_refs.add(content.content_ref)
        direction_topics: set[str] = set()
        for direction in self.d2_directions:
            if direction.source_client_id != client_id:
                raise ValueError("materialization_d2_direction_client_mismatch")
            if direction.topic_id in direction_topics:
                raise ValueError("materialization_d2_direction_topic_duplicate")
            direction_topics.add(direction.topic_id)
        presentation_topics: set[str] = set()
        for presentation in self.d2_direction_price_presentations:
            if presentation.source_client_id != client_id:
                raise ValueError("materialization_d2_direction_presentation_client_mismatch")
            if presentation.topic_id not in direction_topics:
                raise ValueError("materialization_d2_direction_presentation_unknown_topic")
            if presentation.topic_id in presentation_topics:
                raise ValueError("materialization_d2_direction_presentation_topic_duplicate")
            presentation_topics.add(presentation.topic_id)
        source_ui_refs: set[str] = set()
        for source_ui in self.d2_source_ui:
            if source_ui.source_client_id != client_id:
                raise ValueError("materialization_d2_source_ui_client_mismatch")
            if source_ui.content_ref not in content_refs:
                raise ValueError("materialization_d2_source_ui_unknown_content_ref")
            if source_ui.content_ref in source_ui_refs:
                raise ValueError("materialization_d2_source_ui_ref_duplicate")
            source_ui_refs.add(source_ui.content_ref)
        failure_reasons: set[str] = set()
        failure_message_ids: set[str] = set()
        for failure in self.d2_part_failures:
            if failure.source_client_id != client_id:
                raise ValueError("materialization_d2_part_failure_client_mismatch")
            if failure.reason in failure_reasons:
                raise ValueError("materialization_d2_part_failure_reason_duplicate")
            if failure.message_id in failure_message_ids:
                raise ValueError("materialization_d2_part_failure_message_duplicate")
            failure_reasons.add(failure.reason)
            failure_message_ids.add(failure.message_id)
        if len(self.shown_d2_secondary_ref_ids) != len(set(self.shown_d2_secondary_ref_ids)):
            raise ValueError("materialization_d2_shown_secondary_duplicate")
        if any(not value or value != value.strip() for value in self.shown_d2_secondary_ref_ids):
            raise ValueError("materialization_d2_shown_secondary_invalid")
        if self.d2_commercial is not None and self.d2_commercial.source_client_id != client_id:
            raise ValueError("materialization_d2_commercial_client_mismatch")
        return self


class D2PublishedOfferTerms(ResponsePlanModel):
    """Exact published price terms; missing optional metadata never blocks a price."""

    source_client_id: str
    offer_id: str
    package_label: str
    condition_texts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_terms(self) -> Self:
        if not self.source_client_id or self.source_client_id != self.source_client_id.strip():
            raise ValueError("d2_terms_client_invalid")
        if not self.offer_id or self.offer_id != self.offer_id.strip():
            raise ValueError("d2_terms_offer_invalid")
        if not self.package_label or self.package_label != self.package_label.strip():
            raise ValueError("d2_terms_package_invalid")
        if any(not item or item != item.strip() for item in self.condition_texts):
            raise ValueError("d2_terms_condition_invalid")
        return self


@dataclass(frozen=True, slots=True)
class MaterializationDiagnostic:
    code: MaterializationDiagnosticCode
    detail: object = None

    def __post_init__(self) -> None:
        if self.code not in _DIAGNOSTIC_CODES:
            raise MaterializationContractError("materialization_diagnostic_code_invalid")


@dataclass(frozen=True, slots=True)
class ConsideredOfferTrace:
    offer_id: str
    service_id: str
    excluded: bool
    exclusion_reason: OfferExclusionReason | None = None

    def __post_init__(self) -> None:
        if not self.offer_id or not self.offer_id.strip():
            raise MaterializationContractError("considered_offer_id_invalid")
        if not self.service_id or not self.service_id.strip():
            raise MaterializationContractError("considered_service_id_invalid")
        if self.excluded:
            if self.exclusion_reason not in _EXCLUSION_REASONS:
                raise MaterializationContractError("considered_exclusion_reason_invalid")
        elif self.exclusion_reason is not None:
            raise MaterializationContractError("considered_non_excluded_has_reason")


@dataclass(frozen=True, slots=True)
class SelectedOfferTrace:
    offer_id: str
    service_id: str
    amount: int | None
    currency: str | None
    billing_unit: str | None

    def __post_init__(self) -> None:
        if not self.offer_id or not self.offer_id.strip():
            raise MaterializationContractError("selected_offer_id_invalid")
        if not self.service_id or not self.service_id.strip():
            raise MaterializationContractError("selected_service_id_invalid")
        if self.amount is not None:
            if type(self.amount) is not int or isinstance(self.amount, bool):
                raise MaterializationContractError("selected_offer_amount_invalid")
            if self.amount < 0:
                raise MaterializationContractError("selected_offer_amount_negative")


@dataclass(frozen=True, slots=True)
class FinalizedOfferTrace:
    offer_id: str
    service_id: str
    source_client_id: str
    amount: int
    currency: str
    billing_unit: str
    offer_label: str

    def __post_init__(self) -> None:
        if not self.offer_id or not self.offer_id.strip():
            raise MaterializationContractError("finalized_offer_id_invalid")
        if not self.service_id or not self.service_id.strip():
            raise MaterializationContractError("finalized_service_id_invalid")
        if not self.source_client_id or not self.source_client_id.strip():
            raise MaterializationContractError("finalized_offer_client_invalid")
        if type(self.amount) is not int or isinstance(self.amount, bool):
            raise MaterializationContractError("finalized_offer_amount_invalid")
        if self.amount < 0:
            raise MaterializationContractError("finalized_offer_amount_negative")
        if not self.currency or not self.currency.strip():
            raise MaterializationContractError("finalized_offer_currency_invalid")
        if not self.billing_unit or not self.billing_unit.strip():
            raise MaterializationContractError("finalized_offer_billing_unit_invalid")
        if not self.offer_label or not self.offer_label.strip():
            raise MaterializationContractError("finalized_offer_label_invalid")


@dataclass(frozen=True, slots=True)
class MaterializationTrace:
    price_lookup_mode: PriceLookupMode | None
    considered_offers: tuple[ConsideredOfferTrace, ...]
    selected_offers: tuple[SelectedOfferTrace, ...]
    finalized_offers: tuple[FinalizedOfferTrace, ...] = ()
    visible_service_option_ids: tuple[str, ...] = ()
    price_candidate_service_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.price_lookup_mode is not None and self.price_lookup_mode not in _PRICE_LOOKUP_MODES:
            raise MaterializationContractError("materialization_trace_lookup_mode_invalid")
        selected_ids = [item.offer_id for item in self.selected_offers]
        if len(selected_ids) != len(set(selected_ids)):
            raise MaterializationContractError("materialization_trace_selected_duplicate")
        finalized_ids = [item.offer_id for item in self.finalized_offers]
        if len(finalized_ids) != len(set(finalized_ids)):
            raise MaterializationContractError("materialization_trace_finalized_duplicate")
        if finalized_ids and finalized_ids != selected_ids[: len(finalized_ids)]:
            # finalized must be ordered prefix of selected when both non-empty and subset
            if set(finalized_ids) - set(selected_ids):
                raise MaterializationContractError("materialization_trace_finalized_foreign")


@dataclass(frozen=True, slots=True)
class MaterializedPreComposerPayload:
    plan: PreComposerPlan
    composer_result: ComposerResult
    materialization_diagnostics: tuple[MaterializationDiagnostic, ...]
    selection_diagnostics: tuple[PostComposerDiagnostic, ...]
    adapter_diagnostics: tuple[object, ...]
    situation_delta: ResponseSituationDelta
    trace: MaterializationTrace


@dataclass(frozen=True, slots=True)
class MaterializedResponseOutcome:
    resolved: ResolvedResponsePlan
    rendered_text: str
    ui_projection: ResponseUIProjection
    materialization_diagnostics: tuple[MaterializationDiagnostic, ...]
    selection_diagnostics: tuple[PostComposerDiagnostic, ...]
    adapter_diagnostics: tuple[object, ...]
    situation_delta: ResponseSituationDelta
    trace: MaterializationTrace
