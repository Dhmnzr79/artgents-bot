"""Shared requested-fact display policy contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from contracts.response_schema import RequestedDisplayPolicy

RequestedFactDisplayOutcome = Literal[
    "allowed",
    "restricted_scope",
    "missing_display_permission",
    "missing_implant_scope",
    "inactive",
    "unavailable",
]


class RequestedFactPolicyContext(BaseModel):
    """Applicability context shared by post-Composer projection and Resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response_scope: Literal["service", "topic", "clinic"]
    resolved_topic_id: str | None = None
    reference_service_id: str | None = None
    implant_context_confirmed: bool = False


__all__ = [
    "RequestedDisplayPolicy",
    "RequestedFactDisplayOutcome",
    "RequestedFactPolicyContext",
]
