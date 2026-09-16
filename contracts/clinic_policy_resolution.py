"""Resolver result types for clinic policy decisions (Demo D1R)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

PolicyDecisionOutcome = Literal[
    "allowed_by_known_rules",
    "blocked",
    "needs_clarification",
    "no_applicable_rule",
    "unsupported",
]

LedgerRequestStatus = Literal[
    "answered",
    "blocked",
    "clarification_needed",
    "unsupported",
    "deferred",
]


class ClinicPolicyRequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_id: str
    policy_key: str | None
    outcome: PolicyDecisionOutcome
    subject_id: str | None = None
    reason_code: str | None = None


class RequestLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_id: str
    kind: str
    status: LedgerRequestStatus
    text: str | None = None
    subject_id: str | None = None


class ClinicPolicyResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    decisions: tuple[ClinicPolicyRequestDecision, ...]
    ledger: tuple[RequestLedgerEntry, ...]
    suppress_forbidden_booking_cta: bool = False
    active_booking_request_id: str | None = None
