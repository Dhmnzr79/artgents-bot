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


class ResponsePlanMaterializationSources(ResponsePlanModel):
    session_key: SessionKey
    context_strategy: ContextStrategy
    transport_kind: TransportKind = "blocking"
    material_authority: PostComposerMaterialAuthority
    condition_evidence_by_offer: dict[str, OfferConditionEvidence] = Field(default_factory=dict)
    terminal_authorities: tuple[ResponsePlanAdapterTerminalAuthority, ...] = ()
    ui_authority: ResponsePlanAdapterUiAuthority | None = None
    textual_cta_authority: ResponsePlanAdapterTextualCtaAuthority | None = None
    shown_requested_fact_ids: tuple[str, ...] = ()
    shown_promo_fact_ids: tuple[str, ...] = ()
    shown_amplifier_fact_ids: tuple[str, ...] = ()
    shown_service_value_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_ownership(self) -> Self:
        client_id = self.session_key.client_id
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
