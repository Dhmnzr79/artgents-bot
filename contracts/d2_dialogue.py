"""Narrow internal A08 entry contracts; no transport or legacy memory."""

from dataclasses import dataclass
from typing import Protocol, Self

from pydantic import model_validator

from contracts.d2_session_context import D2PlanFocusSeed, D2SessionActivity, D2SessionContextProjection
from contracts.d2_tenant_snapshot import D2ModelView
from contracts.response_plan import ResponsePlanModel
from contracts.response_plan_materialization import MaterializedResponseOutcome
from contracts.response_plan_session import ResponsePlanSessionState


class D2DialogueRecord(ResponsePlanModel):
    state: ResponsePlanSessionState
    activity: D2SessionActivity
    tenant_fingerprint: str

    @model_validator(mode="after")
    def _same_session(self) -> Self:
        if self.state.session_key != self.activity.session_key:
            raise ValueError("d2_activity_owner_mismatch")
        if not self.tenant_fingerprint:
            raise ValueError("d2_tenant_fingerprint_required")
        return self


@dataclass(frozen=True)
class D2ProviderInput:
    user_message: str
    model_view: D2ModelView
    context: D2SessionContextProjection


class D2RawProvider(Protocol):
    def generate(self, request: D2ProviderInput) -> str:
        """Return raw production D1R JSON text, never a parsed envelope."""
        ...


@dataclass(frozen=True)
class D2DialogueTurn:
    response: MaterializedResponseOutcome
    context: D2SessionContextProjection
    focus: D2PlanFocusSeed
    committed_revision: int
