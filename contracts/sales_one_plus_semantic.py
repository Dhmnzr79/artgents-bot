"""Authoritative post-envelope semantic frame (Stage 4.3 / 5.1 / 5.1B)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.one_call_envelope import (
    OneCallClarifyAxis,
    OneCallCommercialIntent,
    OneCallEnvelope,
    OneCallExtent,
    OneCallJaw,
    OneCallPromotionScope,
    OneCallRoute,
    OneCallScenario,
)
from contracts.service_reference import AvailabilityStatus, ServiceReferenceStatus

SemanticFieldProvenance = Literal[
    "local_gate",
    "governed_ui",
    "exact_turn",
    "valid_session",
    "envelope",
    "null",
]
SemanticRebindKind = Literal["full_rebuild"]


class SalesOnePlusSemanticFrame(BaseModel):
    """Local authoritative semantic ownership after validated envelope binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    route: OneCallRoute
    service_id: str | None
    service_id_provenance: SemanticFieldProvenance
    extent: OneCallExtent | None
    extent_provenance: SemanticFieldProvenance
    jaw: OneCallJaw | None
    jaw_provenance: SemanticFieldProvenance
    stage: str | None
    stage_provenance: SemanticFieldProvenance
    scenario: OneCallScenario
    commercial_intent: OneCallCommercialIntent
    promotion_scope: OneCallPromotionScope
    clarify_axis: OneCallClarifyAxis | None
    clarify_service_options: tuple[str, ...] | None
    service_reference_status: ServiceReferenceStatus
    requested_service_id: str | None
    availability_status: AvailabilityStatus
    rebind_kind: SemanticRebindKind = "full_rebuild"

    @model_validator(mode="after")
    def _route_invariants(self) -> Self:
        if self.route == "CLARIFY":
            if self.clarify_axis is None:
                raise ValueError("clarify_axis_required")
            if self.clarify_axis == "service" and self.clarify_service_options is None:
                raise ValueError("clarify_service_options_required")
            if self.commercial_intent != "none" or self.promotion_scope != "none":
                raise ValueError("promotion_surface_forbidden")
        elif self.route == "ADMIN":
            if self.commercial_intent != "none" or self.promotion_scope != "none":
                raise ValueError("promotion_surface_forbidden")
        elif self.clarify_axis is not None or self.clarify_service_options is not None:
            raise ValueError("clarify_fields_forbidden")
        if self.commercial_intent != "promotion" and self.promotion_scope != "none":
            raise ValueError("promotion_scope_forbidden")
        return self

    @classmethod
    def from_envelope_only(cls, envelope: OneCallEnvelope) -> SalesOnePlusSemanticFrame:
        """Build a frame when only envelope authority applies (no governed UI scope)."""

        return cls(
            route=envelope.route,
            service_id=envelope.service_id,
            service_id_provenance="envelope" if envelope.service_id is not None else "null",
            extent=envelope.extent,
            extent_provenance="envelope" if envelope.extent is not None else "null",
            jaw=envelope.jaw,
            jaw_provenance="envelope" if envelope.jaw is not None else "null",
            stage=envelope.stage,
            stage_provenance="envelope" if envelope.stage is not None else "null",
            scenario=envelope.scenario,
            commercial_intent=envelope.commercial_intent,
            promotion_scope=envelope.promotion_scope,
            clarify_axis=envelope.clarify_axis,
            clarify_service_options=envelope.clarify_service_options,
            service_reference_status=envelope.service_reference_status,
            requested_service_id=envelope.requested_service_id,
            availability_status="none",
        )
