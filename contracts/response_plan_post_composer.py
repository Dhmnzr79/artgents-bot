"""Post-Composer selection contracts (SITUATION-FACTS-SELECTION-1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.response_plan import CommercialFactCandidate, SessionKey
from contracts.response_plan_composer import (
    ComposerDecision,
    ComposerDecisionDiagnostic,
    SituationExtent,
    SituationJaw,
    SituationModifier,
    SituationStage,
    _VALID_EXTENTS,
    _VALID_JAWS,
    _VALID_MODIFIERS,
    _VALID_STAGES,
)
from contracts.response_plan_dialogue_context import require_non_negative_int
from contracts.response_schema import ResponseSchemaBundle
from contracts.effective_scope import EffectiveScope

PostComposerDiagnosticCode = Literal[
    "post_composer_client_mismatch",
    "post_composer_active_service_unavailable",
    "post_composer_topic_unavailable",
    "situation_session_stale",
    "situation_session_topic_changed",
    "explicit_service_situation_conflict",
    "reference_service_rejected",
    "reference_service_unavailable",
    "shown_options_snapshot_unavailable",
    "shown_options_snapshot_stale",
    "shown_options_topic_mismatch",
    "explicit_service_not_in_shown_options",
    "insufficient_comparison_candidates",
    "no_applicable_services",
    "requested_fact_unavailable",
    "requested_fact_inapplicable",
    "requested_fact_expired",
    "requested_fact_incompatible",
]

ReferenceServiceStatus = Literal[
    "none",
    "compatible",
    "conflict",
    "unknown",
]

_VALID_REFERENCE_SERVICE_STATUSES = frozenset({"none", "compatible", "conflict", "unknown"})
_VALID_SELECTION_BASES = frozenset({"referenced_service", "current_situation", "shown_options", "none"})
_VALID_SELECTION_INTENTS = frozenset(
    {"none", "service_options", "price_candidates", "comparison_candidates"}
)
_VALID_RESPONSE_SCOPES = frozenset({"service", "topic", "clinic"})

SelectionPresentationIntent = Literal[
    "none",
    "service_options",
    "price_candidates",
    "comparison_candidates",
]

SelectionBasis = Literal[
    "referenced_service",
    "current_situation",
    "shown_options",
    "none",
]

SituationDeltaAction = Literal["keep", "upsert", "clear"]

ResponseScopeKind = Literal["service", "topic", "clinic"]


class PostComposerOwnershipError(ValueError):
    """Strict ownership/session mismatch; not a patient-facing diagnostic."""


class PostComposerSituationError(ValueError):
    """Strict situation continuity input violation."""


class PostComposerSelectionError(ValueError):
    """Strict post-Composer selection contract violation."""


@dataclass(frozen=True, slots=True)
class PostComposerDiagnostic:
    code: PostComposerDiagnosticCode
    detail: object = None


@dataclass(frozen=True, slots=True)
class PostComposerMaterialAuthority:
    source_client_id: str
    bundle: ResponseSchemaBundle

    def __post_init__(self) -> None:
        if not self.source_client_id or not self.source_client_id.strip():
            raise ValueError("source_client_id_blank")
        if self.source_client_id != self.source_client_id.strip():
            raise ValueError("source_client_id_padded")


@dataclass(frozen=True, slots=True)
class ResponseSituationState:
    session_key: SessionKey
    topic_id: str
    extent: SituationExtent
    jaw: SituationJaw
    stage: SituationStage
    modifiers: tuple[SituationModifier, ...]
    set_at_turn: int

    def __post_init__(self) -> None:
        require_non_negative_int("set_at_turn", self.set_at_turn)
        if self.extent not in _VALID_EXTENTS:
            raise ValueError("situation_extent_invalid")
        if self.jaw not in _VALID_JAWS:
            raise ValueError("situation_jaw_invalid")
        if self.stage not in _VALID_STAGES:
            raise ValueError("situation_stage_invalid")
        seen_modifiers: set[str] = set()
        for modifier in self.modifiers:
            if modifier not in _VALID_MODIFIERS:
                raise ValueError("situation_modifier_invalid")
            if modifier in seen_modifiers:
                raise ValueError("situation_modifier_duplicate")
            seen_modifiers.add(modifier)
        if not self.topic_id or not self.topic_id.strip():
            raise ValueError("situation_topic_blank")
        if self.topic_id != self.topic_id.strip():
            raise ValueError("situation_topic_padded")


@dataclass(frozen=True, slots=True)
class SituationContinuityPolicy:
    max_age_turns: int

    def __post_init__(self) -> None:
        require_non_negative_int("max_age_turns", self.max_age_turns)


@dataclass(frozen=True, slots=True)
class ResponseSituationDelta:
    action: SituationDeltaAction
    state: ResponseSituationState | None = None

    def __post_init__(self) -> None:
        if self.action not in {"keep", "upsert", "clear"}:
            raise ValueError("situation_delta_action_invalid")
        if self.action == "upsert":
            if self.state is None:
                raise ValueError("situation_upsert_requires_state")
        elif self.state is not None:
            raise ValueError("situation_keep_clear_forbids_state")


@dataclass(frozen=True, slots=True)
class PostComposerSelectionPlan:
    session_key: SessionKey
    source_client_id: str

    decision: ComposerDecision
    resolved_topic_id: str | None
    response_scope: ResponseScopeKind

    reference_service_id: str | None
    reference_service_status: ReferenceServiceStatus

    effective_scope: EffectiveScope

    ranked_service_ids: tuple[str, ...]
    visible_service_option_ids: tuple[str, ...]
    price_candidate_service_ids: tuple[str, ...]
    comparison_service_ids: tuple[str, ...]
    selection_basis: SelectionBasis
    selection_intent: SelectionPresentationIntent

    requested_fact_candidates: tuple[CommercialFactCandidate, ...]

    situation_delta: ResponseSituationDelta
    adapter_diagnostics: tuple[ComposerDecisionDiagnostic, ...]
    diagnostics: tuple[PostComposerDiagnostic, ...]

    def __post_init__(self) -> None:
        if not self.source_client_id or not self.source_client_id.strip():
            raise PostComposerSelectionError("source_client_id_blank")
        if self.source_client_id != self.source_client_id.strip():
            raise PostComposerSelectionError("source_client_id_padded")
        if self.session_key.client_id != self.source_client_id:
            raise PostComposerSelectionError("post_composer_client_mismatch")
        if self.response_scope not in _VALID_RESPONSE_SCOPES:
            raise PostComposerSelectionError("response_scope_invalid")
        if self.reference_service_status not in _VALID_REFERENCE_SERVICE_STATUSES:
            raise PostComposerSelectionError("reference_service_status_invalid")
        if self.selection_basis not in _VALID_SELECTION_BASES:
            raise PostComposerSelectionError("selection_basis_invalid")
        if self.selection_intent not in _VALID_SELECTION_INTENTS:
            raise PostComposerSelectionError("selection_intent_invalid")
        if self.reference_service_id is not None:
            if not self.reference_service_id or not self.reference_service_id.strip():
                raise PostComposerSelectionError("reference_service_id_blank")
            if self.reference_service_id != self.reference_service_id.strip():
                raise PostComposerSelectionError("reference_service_id_padded")
        if self.reference_service_id is None and self.reference_service_status != "none":
            raise PostComposerSelectionError("reference_status_without_service_id")
        seen_ranked: set[str] = set()
        for service_id in self.ranked_service_ids:
            if not service_id or service_id != service_id.strip():
                raise PostComposerSelectionError("ranked_service_id_invalid")
            if service_id in seen_ranked:
                raise PostComposerSelectionError("ranked_service_id_duplicate")
            seen_ranked.add(service_id)
        if self.situation_delta.state is not None:
            if self.situation_delta.state.session_key != self.session_key:
                raise PostComposerSelectionError("situation_state_session_mismatch")
        route = self.decision.route
        mode = self.decision.mode
        if route in {"ADMIN", "CLARIFY"} or (route == "ANSWER" and mode == "contacts"):
            if self.ranked_service_ids or self.visible_service_option_ids:
                raise PostComposerSelectionError("terminal_route_forbids_selection")
            if self.price_candidate_service_ids or self.comparison_service_ids:
                raise PostComposerSelectionError("terminal_route_forbids_price_selection")
            if self.requested_fact_candidates:
                raise PostComposerSelectionError("terminal_route_forbids_fact_candidates")
        if len(self.visible_service_option_ids) > 3:
            raise PostComposerSelectionError("visible_service_options_exceeds_max")
        if len(self.price_candidate_service_ids) > 3:
            raise PostComposerSelectionError("price_candidate_service_ids_exceeds_max")
        ranked = self.ranked_service_ids
        visible = self.visible_service_option_ids
        if visible and any(service_id not in ranked for service_id in visible):
            raise PostComposerSelectionError("visible_options_not_subset_of_ranked")
        if visible:
            visible_index = {service_id: index for index, service_id in enumerate(visible)}
            ranked_visible = [sid for sid in ranked if sid in visible_index]
            if tuple(ranked_visible) != visible:
                raise PostComposerSelectionError("visible_options_order_mismatch")
        if self.comparison_service_ids and self.selection_basis != "shown_options":
            raise PostComposerSelectionError("comparison_requires_shown_options_basis")
        if self.selection_basis == "shown_options" and self.decision.option_reference_kind != "shown_options":
            raise PostComposerSelectionError("shown_options_basis_requires_option_reference")
        if self.resolved_topic_id is not None and self.response_scope == "clinic":
            raise PostComposerSelectionError("topic_scope_incoherent")
