"""Pure D2 session-context TTL contracts.

This is deliberately a read projection.  It does not decide whether a new
request semantically continues a previous topic, and it does not own or update
session activity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from contracts.d2_dialogue_result import ClarifiedOperation, DiscussionScope

from pydantic import field_validator, model_validator

from contracts.response_plan import NonBlankStr, ResponsePlanModel, SessionKey, TerminalState, D2ResolvedRequestPart
from contracts.response_plan_session import (
    D2ShownPriceOfferRef, PersistedShownCommercialIds, D2SelectedUiRef,
    D2DialogueReceiptRef, require_exact_nonblank_id,
    require_strict_non_negative_int, reject_non_strict_int_input,
)

DEFAULT_D2_SESSION_IDLE_TTL_SECONDS = 30 * 60
DEFAULT_D2_HISTORY_PAIR_LIMIT = 3
DEFAULT_D2_HISTORY_TEXT_MAX_CHARS = 1000
D2SessionContextFreshness = Literal["fresh", "expired", "unknown"]
class D2SessionContextError(ValueError):
    """An activity record or snapshot cannot safely be projected for D2."""


class D2SessionTtlPolicy(ResponsePlanModel):
    """Clinic-configurable inactivity limit; the helper never reads a clock."""

    idle_ttl_seconds: int = DEFAULT_D2_SESSION_IDLE_TTL_SECONDS
    history_pair_limit: int = DEFAULT_D2_HISTORY_PAIR_LIMIT
    history_text_max_chars: int = DEFAULT_D2_HISTORY_TEXT_MAX_CHARS

    @field_validator("idle_ttl_seconds", "history_pair_limit", "history_text_max_chars", mode="before")
    @classmethod
    def _require_strict_positive_int(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("idle_ttl_seconds_not_strict_int")
        return value

    @model_validator(mode="after")
    def _validate_ttl(self) -> Self:
        for field in ("idle_ttl_seconds", "history_pair_limit", "history_text_max_chars"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field}_not_positive")
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


class D2ProjectedDialoguePair(ResponsePlanModel):
    patient_text: str | None = None
    selected_ui_ref: D2SelectedUiRef | None = None
    assistant_text: str = ""
    committed_at_turn: int
    parts: tuple[D2ResolvedRequestPart, ...] = ()
    price_scope: DiscussionScope | None = None
    offers: tuple[D2ShownPriceOfferRef, ...] = ()
    detail_aspects: tuple[str, ...] = ()
    policy_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()


class D2OrdinarySessionContext(ResponsePlanModel):
    """Ordinary dialogue state made available by a fresh activity record only."""

    dialogue_pairs: tuple[D2ProjectedDialoguePair, ...] = ()
    discussion_scope: DiscussionScope | None = None
    d2_shown_price_offer_refs: tuple[D2ShownPriceOfferRef, ...] = ()
    clarify_pending: bool = False
    clarify_task: ClarifiedOperation | None = None


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


D2_SESSION_SCHEMA_VERSION = 6


class D2SessionState(ResponsePlanModel):
    """One receipt-based discussion context; no personal treatment record."""
    schema_version: int
    session_key: SessionKey
    revision: int
    last_committed_turn_index: int
    dialogue_pairs: tuple[D2DialogueReceiptRef, ...] = ()
    discussion_request_id: NonBlankStr | None = None
    accumulated_shown_ids: PersistedShownCommercialIds = PersistedShownCommercialIds()
    terminal_state: TerminalState = "none"
    clarify_pending: bool = False
    clarify_task: ClarifiedOperation | None = None

    @field_validator("schema_version", "revision", "last_committed_turn_index", mode="before")
    @classmethod
    def strict_counters(cls, value):
        return reject_non_strict_int_input("session_counter", value)

    @model_validator(mode="after")
    def validate_state(self):
        for name in ("schema_version", "revision", "last_committed_turn_index"):
            require_strict_non_negative_int(name, getattr(self, name))
        if self.schema_version != D2_SESSION_SCHEMA_VERSION:
            raise ValueError("session_schema_version_invalid")
        require_exact_nonblank_id("session_client_id", self.session_key.client_id)
        require_exact_nonblank_id("session_sid", self.session_key.sid)
        if any(p.committed_at_turn > self.last_committed_turn_index for p in self.dialogue_pairs):
            raise ValueError("dialogue_pair_future_turn")
        if self.clarify_task is not None and not self.clarify_pending:
            raise ValueError("clarify_task_requires_pending")
        return self


class D2SessionSnapshot(ResponsePlanModel):
    state: D2SessionState
    exists_in_store: bool = False

    @property
    def current_turn_index(self):
        return self.state.last_committed_turn_index + 1


def empty_d2_session_snapshot(session_key):
    return D2SessionSnapshot(state=D2SessionState(
        schema_version=D2_SESSION_SCHEMA_VERSION, session_key=session_key,
        revision=0, last_committed_turn_index=0,
    ))
