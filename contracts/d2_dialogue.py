"""Internal D2 turn contracts; no transport or legacy memory."""

from dataclasses import dataclass
from typing import Literal, Protocol, Self

from pydantic import model_validator

from contracts.d2_session_context import D2PlanFocusSeed, D2SessionActivity, D2SessionContextProjection
from contracts.d2_tenant_snapshot import D2ModelView
from contracts.response_plan import ResponsePlanModel
from contracts.response_plan_materialization import MaterializedResponseOutcome
from contracts.response_plan_session import D2SelectedUiRef, ResponsePlanSessionState


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


D2LeadEffectStatus = Literal["not_requested", "pending", "sent", "failed", "unknown", "demo_stub"]


class D2LeadEffect(ResponsePlanModel):
    """PII-free receipt for an already-authorized existing lead-flow effect."""

    effect_id: str | None = None
    status: D2LeadEffectStatus = "not_requested"

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if self.status == "not_requested":
            if self.effect_id is not None:
                raise ValueError("d2_lead_effect_id_without_effect")
        elif not self.effect_id or not self.effect_id.strip():
            raise ValueError("d2_lead_effect_id_required")
        return self


@dataclass(frozen=True)
class D2ProviderInput:
    user_message: str
    model_view: D2ModelView
    context: D2SessionContextProjection
    selected_ui_ref: D2SelectedUiRef | None = None


class D2RawProvider(Protocol):
    def generate(self, request: D2ProviderInput) -> str:
        """Return raw production D1R JSON text, never a parsed envelope."""
        ...


class D2LeadEffectDispatcher(Protocol):
    """One-shot bridge to the existing lead flow; it never receives model input."""

    def dispatch(self, *, effect_id: str) -> D2LeadEffectStatus:
        """Return a terminal status, without automatic retry semantics."""
        ...


class D2CompletedTurn(ResponsePlanModel):
    """Durable final result for exactly one client/session/request triple."""

    request_id: str
    request_fingerprint: str
    response: MaterializedResponseOutcome
    context: D2SessionContextProjection
    focus: D2PlanFocusSeed
    committed_revision: int
    lead_effect: D2LeadEffect = D2LeadEffect()

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        if not self.request_id.strip():
            raise ValueError("d2_request_id_required")
        if not self.request_fingerprint.strip():
            raise ValueError("d2_request_fingerprint_required")
        if self.committed_revision < 1:
            raise ValueError("d2_committed_revision_invalid")
        return self


@dataclass(frozen=True)
class D2DialogueTurn:
    response: MaterializedResponseOutcome
    context: D2SessionContextProjection
    focus: D2PlanFocusSeed
    committed_revision: int
    request_id: str
    idempotent_replay: bool = False
    lead_effect: D2LeadEffect = D2LeadEffect()
