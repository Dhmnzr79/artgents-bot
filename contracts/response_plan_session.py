"""Typed session persistence contracts for RESPONSE-SESSION-CONTINUITY-1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from contracts.response_plan import (
    FrozenPriceOfferRow,
    ResponsePlanModel,
    ResponseUIProjection,
    ResolvedResponsePlan,
    SessionKey,
    TerminalState,
    TransportKind,
)
from contracts.response_plan_composer import AdaptedComposerDecision
from contracts.response_plan_dialogue_context import (
    ShownOptionsProvenance,
    require_non_negative_int,
)
from contracts.response_plan_materialization import MaterializedResponseOutcome
from contracts.response_plan_post_composer import (
    PostComposerSelectionPlan,
    ResponseSituationState,
    SituationExtent,
    SituationJaw,
    SituationModifier,
    SituationStage,
)

SESSION_SCHEMA_VERSION = 1
FINGERPRINT_FORMAT_VERSION = 3

ActiveServiceProvenance = Literal["explicit_current", "active_session"]
ActiveTopicProvenance = Literal[
    "explicit_current",
    "active_session",
    "explicit_topic",
    "shown_options",
]


class ResponsePlanSessionError(ValueError):
    """Base typed session persistence error."""


class ResponsePlanSessionOwnershipError(ResponsePlanSessionError):
    """Ownership mismatch for session-scoped objects."""


class ResponsePlanSessionContractError(ResponsePlanSessionError):
    """Invalid session contract input."""


class ResponsePlanSessionRevisionConflict(ResponsePlanSessionError):
    """Stale expected_revision on commit."""


class ResponsePlanSessionIdempotencyConflict(ResponsePlanSessionError):
    """Same request_id with a different prepared update fingerprint."""


class ResponsePlanSessionReceiptMismatch(ResponsePlanSessionError):
    """Completion receipt does not match prepared update."""


class ResponsePlanSessionPayloadError(ResponsePlanSessionError):
    """Stored payload failed runtime validation."""


def require_strict_positive_int(field: str, value: object) -> int:
    if type(value) is bool:
        raise ValueError(f"{field}_bool_forbidden")
    if isinstance(value, float):
        raise ValueError(f"{field}_float_forbidden")
    if isinstance(value, str):
        raise ValueError(f"{field}_string_forbidden")
    if not isinstance(value, int):
        raise ValueError(f"{field}_not_int")
    if value <= 0:
        raise ValueError(f"{field}_not_positive")
    return value


def require_strict_non_negative_int(field: str, value: object) -> int:
    if type(value) is bool:
        raise ValueError(f"{field}_bool_forbidden")
    if isinstance(value, float):
        raise ValueError(f"{field}_float_forbidden")
    if isinstance(value, str):
        raise ValueError(f"{field}_string_forbidden")
    if not isinstance(value, int):
        raise ValueError(f"{field}_not_int")
    if value < 0:
        raise ValueError(f"{field}_negative")
    return value


def reject_non_strict_int_input(field: str, value: object) -> object:
    if type(value) is bool or isinstance(value, float) or isinstance(value, str):
        raise ValueError(f"{field}_invalid_type")
    return value


def require_exact_nonblank_id(field: str, value: str) -> str:
    if not value:
        raise ValueError(f"{field}_blank")
    if value != value.strip():
        raise ValueError(f"{field}_padded")
    return value


def _validate_unique_ids(field: str, values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    for value in values:
        require_exact_nonblank_id(field, value)
        if value in seen:
            raise ValueError(f"{field}_duplicate")
        seen.add(value)
    return values


class SessionContinuityPolicy(ResponsePlanModel):
    active_service_max_age_turns: int
    active_topic_max_age_turns: int
    situation_max_age_turns: int
    shown_options_max_age_turns: int
    history_pair_limit: int

    @field_validator(
        "active_service_max_age_turns",
        "active_topic_max_age_turns",
        "situation_max_age_turns",
        "shown_options_max_age_turns",
        "history_pair_limit",
        mode="before",
    )
    @classmethod
    def _reject_non_strict_int(cls, value: object) -> object:
        return reject_non_strict_int_input("policy_field", value)

    @model_validator(mode="after")
    def _validate_limits(self) -> Self:
        for field in (
            "active_service_max_age_turns",
            "active_topic_max_age_turns",
            "situation_max_age_turns",
            "shown_options_max_age_turns",
        ):
            require_strict_non_negative_int(field, getattr(self, field))
        require_strict_positive_int("history_pair_limit", self.history_pair_limit)
        return self


class PersistedActiveService(ResponsePlanModel):
    service_id: str
    provenance: ActiveServiceProvenance
    set_at_turn: int

    @field_validator("set_at_turn", mode="before")
    @classmethod
    def _strict_set_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("set_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("set_at_turn", self.set_at_turn)
        require_exact_nonblank_id("active_service_id", self.service_id)
        return self


class PersistedActiveTopic(ResponsePlanModel):
    topic_id: str
    provenance: ActiveTopicProvenance
    set_at_turn: int

    @field_validator("set_at_turn", mode="before")
    @classmethod
    def _strict_set_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("set_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("set_at_turn", self.set_at_turn)
        require_exact_nonblank_id("active_topic_id", self.topic_id)
        return self


class SessionDialoguePair(ResponsePlanModel):
    patient_text: str
    assistant_text: str
    committed_at_turn: int

    @field_validator("committed_at_turn", mode="before")
    @classmethod
    def _strict_committed_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("committed_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("committed_at_turn", self.committed_at_turn)
        if not self.patient_text or not self.patient_text.strip():
            raise ValueError("dialogue_patient_blank")
        if not self.assistant_text or not self.assistant_text.strip():
            raise ValueError("dialogue_assistant_blank")
        return self


class PersistedShownCommercialIds(ResponsePlanModel):
    requested_fact_ids: tuple[str, ...] = ()
    promo_fact_ids: tuple[str, ...] = ()
    amplifier_fact_ids: tuple[str, ...] = ()
    service_value_ids: tuple[str, ...] = ()
    price_offer_ids: tuple[str, ...] = ()
    required_offer_condition_ids: tuple[str, ...] = ()
    shown_service_option_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_ids(self) -> Self:
        _validate_unique_ids("requested_fact_ids", self.requested_fact_ids)
        _validate_unique_ids("promo_fact_ids", self.promo_fact_ids)
        _validate_unique_ids("amplifier_fact_ids", self.amplifier_fact_ids)
        _validate_unique_ids("service_value_ids", self.service_value_ids)
        _validate_unique_ids("price_offer_ids", self.price_offer_ids)
        _validate_unique_ids("required_offer_condition_ids", self.required_offer_condition_ids)
        _validate_unique_ids("shown_service_option_ids", self.shown_service_option_ids)
        return self


class PersistedSituationState(ResponsePlanModel):
    session_key: SessionKey
    topic_id: str
    extent: SituationExtent
    jaw: SituationJaw
    stage: SituationStage
    modifiers: tuple[SituationModifier, ...]
    set_at_turn: int

    @field_validator("set_at_turn", mode="before")
    @classmethod
    def _strict_set_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("set_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("set_at_turn", self.set_at_turn)
        require_exact_nonblank_id("situation_topic_id", self.topic_id)
        return self

    def to_runtime(self) -> ResponseSituationState:
        return ResponseSituationState(
            session_key=self.session_key,
            topic_id=self.topic_id,
            extent=self.extent,
            jaw=self.jaw,
            stage=self.stage,
            modifiers=self.modifiers,
            set_at_turn=self.set_at_turn,
        )

    @classmethod
    def from_runtime(cls, state: ResponseSituationState) -> PersistedSituationState:
        return cls(
            session_key=state.session_key,
            topic_id=state.topic_id,
            extent=state.extent,
            jaw=state.jaw,
            stage=state.stage,
            modifiers=state.modifiers,
            set_at_turn=state.set_at_turn,
        )


class PersistedShownOptionsSnapshot(ResponsePlanModel):
    session_key: SessionKey
    topic_id: str
    service_ids: tuple[str, ...]
    shown_at_turn: int
    provenance: ShownOptionsProvenance = "finalized_plan_service_options"

    @field_validator("shown_at_turn", mode="before")
    @classmethod
    def _strict_shown_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("shown_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("shown_at_turn", self.shown_at_turn)
        require_exact_nonblank_id("shown_topic_id", self.topic_id)
        if not self.service_ids:
            raise ValueError("shown_service_ids_empty")
        _validate_unique_ids("shown_service_ids", self.service_ids)
        return self

    def to_runtime(self) -> ShownServiceOptionsSnapshot:
        from contracts.response_plan_dialogue_context import ShownServiceOptionsSnapshot

        return ShownServiceOptionsSnapshot(
            session_key=self.session_key,
            topic_id=self.topic_id,
            service_ids=self.service_ids,
            shown_at_turn=self.shown_at_turn,
            provenance=self.provenance,
        )

    @classmethod
    def from_runtime(cls, snapshot: ShownServiceOptionsSnapshot) -> PersistedShownOptionsSnapshot:
        return cls(
            session_key=snapshot.session_key,
            topic_id=snapshot.topic_id,
            service_ids=snapshot.service_ids,
            shown_at_turn=snapshot.shown_at_turn,
            provenance=snapshot.provenance,
        )


class HistoricalPriceOffersSnapshot(ResponsePlanModel):
    rows: tuple[FrozenPriceOfferRow, ...]
    shown_at_turn: int
    topic_id: str | None = None

    @field_validator("shown_at_turn", mode="before")
    @classmethod
    def _strict_shown_at_turn(cls, value: object) -> object:
        return reject_non_strict_int_input("shown_at_turn", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("shown_at_turn", self.shown_at_turn)
        if not self.rows:
            raise ValueError("historical_price_rows_empty")
        seen: set[str] = set()
        for row in self.rows:
            if row.offer_id in seen:
                raise ValueError("historical_price_duplicate_offer")
            seen.add(row.offer_id)
        if self.topic_id is not None:
            require_exact_nonblank_id("historical_price_topic_id", self.topic_id)
        return self


class ResponsePlanSessionState(ResponsePlanModel):
    schema_version: int
    session_key: SessionKey
    revision: int
    last_committed_turn_index: int
    dialogue_pairs: tuple[SessionDialoguePair, ...] = ()
    active_service: PersistedActiveService | None = None
    active_topic: PersistedActiveTopic | None = None
    situation_state: PersistedSituationState | None = None
    shown_options_snapshot: PersistedShownOptionsSnapshot | None = None
    historical_price_offers: HistoricalPriceOffersSnapshot | None = None
    accumulated_shown_ids: PersistedShownCommercialIds = Field(
        default_factory=PersistedShownCommercialIds
    )
    terminal_state: TerminalState = "none"
    clarify_pending: bool = False

    @field_validator("schema_version", "revision", "last_committed_turn_index", mode="before")
    @classmethod
    def _strict_counters(cls, value: object) -> object:
        return reject_non_strict_int_input("session_counter", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("schema_version", self.schema_version)
        require_strict_non_negative_int("revision", self.revision)
        require_strict_non_negative_int("last_committed_turn_index", self.last_committed_turn_index)
        if self.schema_version != SESSION_SCHEMA_VERSION:
            raise ValueError("session_schema_version_invalid")
        require_exact_nonblank_id("session_client_id", self.session_key.client_id)
        require_exact_nonblank_id("session_sid", self.session_key.sid)
        if self.situation_state is not None and self.situation_state.session_key != self.session_key:
            raise ValueError("situation_session_key_mismatch")
        if (
            self.shown_options_snapshot is not None
            and self.shown_options_snapshot.session_key != self.session_key
        ):
            raise ValueError("shown_options_session_key_mismatch")
        if self.historical_price_offers is not None:
            client_id = self.session_key.client_id
            for row in self.historical_price_offers.rows:
                if row.source_client_id != client_id:
                    raise ValueError("historical_price_row_client_mismatch")
        for pair in self.dialogue_pairs:
            if pair.committed_at_turn > self.last_committed_turn_index:
                raise ValueError("dialogue_pair_future_turn")
        return self


class ResponsePlanSessionSnapshot(ResponsePlanModel):
    state: ResponsePlanSessionState
    exists_in_store: bool = False

    @property
    def current_turn_index(self) -> int:
        return self.state.last_committed_turn_index + 1


def empty_session_snapshot(session_key: SessionKey) -> ResponsePlanSessionSnapshot:
    return ResponsePlanSessionSnapshot(
        state=ResponsePlanSessionState(
            schema_version=SESSION_SCHEMA_VERSION,
            session_key=session_key,
            revision=0,
            last_committed_turn_index=0,
        ),
        exists_in_store=False,
    )


class SessionSnapshotIdentity(ResponsePlanModel):
    session_key: SessionKey
    revision: int
    last_committed_turn_index: int
    schema_version: int

    @field_validator(
        "revision",
        "last_committed_turn_index",
        "schema_version",
        mode="before",
    )
    @classmethod
    def _strict_counters(cls, value: object) -> object:
        return reject_non_strict_int_input("snapshot_identity_counter", value)

    @classmethod
    def from_snapshot(cls, snapshot: ResponsePlanSessionSnapshot) -> SessionSnapshotIdentity:
        state = snapshot.state
        return cls(
            session_key=state.session_key,
            revision=state.revision,
            last_committed_turn_index=state.last_committed_turn_index,
            schema_version=state.schema_version,
        )

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("revision", self.revision)
        require_strict_non_negative_int("last_committed_turn_index", self.last_committed_turn_index)
        require_strict_non_negative_int("schema_version", self.schema_version)
        if self.schema_version != SESSION_SCHEMA_VERSION:
            raise ValueError("snapshot_identity_schema_invalid")
        return self


class TurnRequestBinding(ResponsePlanModel):
    session_key: SessionKey
    request_id: str
    expected_revision: int
    current_turn_index: int
    patient_message: str
    snapshot_identity: SessionSnapshotIdentity

    @field_validator("expected_revision", mode="before")
    @classmethod
    def _strict_expected_revision(cls, value: object) -> object:
        return reject_non_strict_int_input("expected_revision", value)

    @field_validator("current_turn_index", mode="before")
    @classmethod
    def _strict_current_turn_index(cls, value: object) -> object:
        return reject_non_strict_int_input("current_turn_index", value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        require_strict_non_negative_int("expected_revision", self.expected_revision)
        require_strict_positive_int("current_turn_index", self.current_turn_index)
        if not self.request_id or not self.request_id.strip():
            raise ValueError("request_id_blank")
        if not self.patient_message or not self.patient_message.strip():
            raise ValueError("patient_message_blank")
        if self.snapshot_identity.session_key != self.session_key:
            raise ValueError("binding_snapshot_session_mismatch")
        if self.snapshot_identity.revision != self.expected_revision:
            raise ValueError("binding_snapshot_revision_mismatch")
        return self


class TurnPipelineOutcome(ResponsePlanModel):
    request_binding: TurnRequestBinding
    adapted: AdaptedComposerDecision
    selection: PostComposerSelectionPlan
    materialized: MaterializedResponseOutcome
    rendered_text: str
    ui_projection: ResponseUIProjection

    @model_validator(mode="after")
    def _validate_binding(self) -> Self:
        binding = self.request_binding
        if binding.session_key != self.selection.session_key:
            raise ResponsePlanSessionContractError("pipeline_selection_session_mismatch")
        if binding.session_key.client_id != self.selection.source_client_id:
            raise ResponsePlanSessionContractError("pipeline_selection_client_mismatch")
        if self.adapted.decision != self.selection.decision:
            raise ResponsePlanSessionContractError("pipeline_adapted_decision_mismatch")
        if self.materialized.resolved.session_delta.session_key != binding.session_key:
            raise ResponsePlanSessionContractError("pipeline_resolved_session_mismatch")
        if self.materialized.situation_delta != self.selection.situation_delta:
            raise ResponsePlanSessionContractError("pipeline_situation_delta_mismatch")
        if self.materialized.rendered_text != self.rendered_text:
            raise ResponsePlanSessionContractError("pipeline_rendered_text_mismatch")
        if self.materialized.ui_projection != self.ui_projection:
            raise ResponsePlanSessionContractError("pipeline_ui_projection_mismatch")
        return self


class PreparedSessionUpdate(ResponsePlanModel):
    request_binding: TurnRequestBinding
    patient_message: str
    rendered_text: str
    proposed_state: ResponsePlanSessionState
    resolved_plan: ResolvedResponsePlan
    ui_projection: ResponseUIProjection
    selection: PostComposerSelectionPlan
    topic_restoration_shown_snapshot: PersistedShownOptionsSnapshot | None = None
    update_fingerprint: str

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.patient_message != self.request_binding.patient_message:
            raise ResponsePlanSessionContractError("prepared_patient_message_binding_mismatch")
        if self.request_binding.session_key != self.proposed_state.session_key:
            raise ResponsePlanSessionContractError("prepared_state_session_mismatch")
        if self.resolved_plan.session_delta.session_key != self.proposed_state.session_key:
            raise ResponsePlanSessionContractError("prepared_resolved_session_mismatch")
        if self.selection.session_key != self.proposed_state.session_key:
            raise ResponsePlanSessionContractError("prepared_selection_session_mismatch")
        return self


class SessionCompletionReceipt(ResponsePlanModel):
    session_key: SessionKey
    request_id: str
    update_fingerprint: str
    transport_kind: TransportKind
    delivery_succeeded: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.request_id or not self.request_id.strip():
            raise ValueError("receipt_request_id_blank")
        if not self.update_fingerprint or not self.update_fingerprint.strip():
            raise ValueError("receipt_fingerprint_blank")
        if not self.delivery_succeeded:
            raise ValueError("receipt_delivery_not_succeeded")
        return self


class SessionCommitResult(ResponsePlanModel):
    session_key: SessionKey
    revision: int
    last_committed_turn_index: int
    idempotent_replay: bool = False


def _resolved_fingerprint_payload(resolved: ResolvedResponsePlan) -> dict[str, object]:
    return resolved.model_dump(mode="json")


def fingerprint_payload_dict(prepared: PreparedSessionUpdate) -> dict[str, object]:
    return {
        "format_version": FINGERPRINT_FORMAT_VERSION,
        "request_binding": prepared.request_binding.model_dump(mode="json"),
        "snapshot_identity": prepared.request_binding.snapshot_identity.model_dump(mode="json"),
        "patient_message": prepared.patient_message,
        "rendered_text": prepared.rendered_text,
        "resolved_plan": _resolved_fingerprint_payload(prepared.resolved_plan),
        "ui_projection": prepared.ui_projection.model_dump(mode="json"),
        "selection": {
            "decision": asdict(prepared.selection.decision),
            "situation_delta_action": prepared.selection.situation_delta.action,
            "resolved_topic_id": prepared.selection.resolved_topic_id,
        },
        "topic_restoration_shown_snapshot": (
            prepared.topic_restoration_shown_snapshot.model_dump(mode="json")
            if prepared.topic_restoration_shown_snapshot is not None
            else None
        ),
        "proposed_state": prepared.proposed_state.model_dump(mode="json"),
    }


def compute_update_fingerprint(prepared: PreparedSessionUpdate) -> str:
    canonical = json.dumps(
        fingerprint_payload_dict(prepared),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attach_update_fingerprint(prepared: PreparedSessionUpdate) -> PreparedSessionUpdate:
    fingerprint = compute_update_fingerprint(prepared)
    if prepared.update_fingerprint and prepared.update_fingerprint != fingerprint:
        raise ResponsePlanSessionContractError("prepared_fingerprint_mismatch")
    return prepared.model_copy(update={"update_fingerprint": fingerprint})
