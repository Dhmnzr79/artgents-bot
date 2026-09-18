"""Pure D2 session-context TTL contracts.

This is deliberately a read projection.  It does not decide whether a new
request semantically continues a previous topic, and it does not own or update
session activity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import field_validator, model_validator

from contracts.response_plan import ResponsePlanModel, SessionKey, TerminalState
from contracts.response_plan_session import (
    HistoricalPriceOffersSnapshot,
    PersistedActiveService,
    PersistedActiveTopic,
    PersistedShownCommercialIds,
    PersistedShownOptionsSnapshot,
    PersistedSituationState,
    ResponsePlanSessionSnapshot,
    SessionDialoguePair,
)

DEFAULT_D2_SESSION_IDLE_TTL_SECONDS = 30 * 60
D2SessionContextFreshness = Literal["fresh", "expired", "unknown"]
D2SemanticContinuationOutcome = Literal[
    "clear_continuation", "ambiguous_focus", "explicit_new_topic"
]


class D2SessionContextError(ValueError):
    """An activity record or snapshot cannot safely be projected for D2."""


class D2SessionTtlPolicy(ResponsePlanModel):
    """Clinic-configurable inactivity limit; the helper never reads a clock."""

    idle_ttl_seconds: int = DEFAULT_D2_SESSION_IDLE_TTL_SECONDS

    @field_validator("idle_ttl_seconds", mode="before")
    @classmethod
    def _require_strict_positive_int(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("idle_ttl_seconds_not_strict_int")
        return value

    @model_validator(mode="after")
    def _validate_ttl(self) -> Self:
        if self.idle_ttl_seconds <= 0:
            raise ValueError("idle_ttl_seconds_not_positive")
        return self


class D2SessionActivity(ResponsePlanModel):
    """Activity supplied by the future authoritative session writer/read layer."""

    session_key: SessionKey
    last_user_turn_at: datetime

    @model_validator(mode="after")
    def _require_aware_timestamp(self) -> Self:
        if (
            self.last_user_turn_at.tzinfo is None
            or self.last_user_turn_at.utcoffset() is None
        ):
            raise ValueError("last_user_turn_at_timezone_required")
        return self


class D2OrdinarySessionContext(ResponsePlanModel):
    """Ordinary dialogue state made available by a fresh activity record only."""

    dialogue_pairs: tuple[SessionDialoguePair, ...] = ()
    active_service: PersistedActiveService | None = None
    active_topic: PersistedActiveTopic | None = None
    situation_state: PersistedSituationState | None = None
    shown_options_snapshot: PersistedShownOptionsSnapshot | None = None
    historical_price_offers: HistoricalPriceOffersSnapshot | None = None
    clarify_pending: bool = False


class D2SessionContextProjection(ResponsePlanModel):
    """TTL-gated view of a typed snapshot, not a semantic continuation decision."""

    session_key: SessionKey
    source_revision: int
    source_turn_index: int
    freshness: D2SessionContextFreshness
    last_user_turn_at: datetime | None = None
    ordinary: D2OrdinarySessionContext = D2OrdinarySessionContext()
    retained_terminal_state: TerminalState
    retained_shown_ids: PersistedShownCommercialIds


class D2EnvelopeSessionBinding(ResponsePlanModel):
    """Typed result of binding one parsed D1R envelope to a C10 projection.

    This is intentionally a decision record, not a session mutation or a
    resolver instruction.  ``carried_situation`` is present only when the
    current D1R request explicitly declares the same typed situation.
    """

    source_session_key: SessionKey
    source_revision: int
    source_turn_index: int
    outcome: D2SemanticContinuationOutcome
    resolved_topic_id: str | None = None
    carried_situation: PersistedSituationState | None = None

    @model_validator(mode="after")
    def _validate_carried_situation(self) -> Self:
        if self.carried_situation is None:
            return self
        if self.outcome != "clear_continuation":
            raise ValueError("carried_situation_requires_clear_continuation")
        if self.resolved_topic_id != self.carried_situation.topic_id:
            raise ValueError("carried_situation_topic_mismatch")
        return self
