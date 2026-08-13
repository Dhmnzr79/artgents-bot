"""Production v4 typed model control envelope (Stage 4.2 / 5.1 / 5.1B)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from contracts.service_reference import ServiceReferenceStatus

OneCallRoute = Literal["ANSWER", "ADMIN", "CLARIFY"]
OneCallExtent = Literal["one_tooth", "few_teeth", "full_arch"]
OneCallJaw = Literal["upper", "lower", "both"]
OneCallScenario = Literal[
    "pain_fear",
    "cost",
    "time",
    "doctor_trust",
    "result_reliability",
    "none",
]
OneCallCommercialIntent = Literal["none", "price", "payment", "included", "promotion"]
OneCallPromotionScope = Literal["none", "general", "service", "shown"]
OneCallClarifyAxis = Literal["service", "extent", "jaw", "stage"]

_REQUIRED_FIELD_NAMES = frozenset(
    {
        "route",
        "service_id",
        "extent",
        "jaw",
        "stage",
        "scenario",
        "commercial_intent",
        "promotion_scope",
        "clarify_axis",
        "clarify_service_options",
        "patient_text",
        "service_reference_status",
        "requested_service_id",
    }
)


def _require_nonblank(value: str, *, code: str) -> str:
    token = value.strip()
    if not token:
        raise ValueError(code)
    return token


def _validate_clarify_service_options(options: tuple[str, ...] | None) -> None:
    if options is None:
        return
    if len(options) < 2 or len(options) > 3:
        raise ValueError("clarify_service_options_invalid")
    normalized: list[str] = []
    for item in options:
        token = _require_nonblank(item, code="clarify_service_options_invalid")
        if token in normalized:
            raise ValueError("clarify_service_options_invalid")
        normalized.append(token)


class OneCallEnvelope(BaseModel):
    """Exactly thirteen model-returned control fields — no extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    route: OneCallRoute
    service_id: str | None
    extent: OneCallExtent | None
    jaw: OneCallJaw | None
    stage: str | None
    scenario: OneCallScenario
    commercial_intent: OneCallCommercialIntent
    promotion_scope: OneCallPromotionScope
    clarify_axis: OneCallClarifyAxis | None
    clarify_service_options: tuple[str, ...] | None
    patient_text: str | None
    service_reference_status: ServiceReferenceStatus
    requested_service_id: str | None

    @model_validator(mode="after")
    def _field_and_route_invariants(self) -> Self:
        if self.service_id is not None and not self.service_id.strip():
            raise ValueError("service_id_invalid")
        if self.stage is not None and not self.stage.strip():
            raise ValueError("stage_invalid")

        _validate_clarify_service_options(self.clarify_service_options)

        if self.service_reference_status == "none":
            if self.requested_service_id is not None:
                raise ValueError("requested_service_id_forbidden_for_none")
        elif self.service_reference_status == "unresolved":
            if self.requested_service_id is not None:
                raise ValueError("requested_service_id_forbidden_for_unresolved")
        elif self.service_reference_status == "resolved":
            if self.requested_service_id is None:
                raise ValueError("requested_service_id_required_for_resolved")

        if self.commercial_intent != "promotion" and self.promotion_scope != "none":
            raise ValueError("promotion_scope_forbidden")
        if self.commercial_intent == "promotion":
            if self.promotion_scope not in {"general", "service", "shown"}:
                raise ValueError("promotion_scope_invalid")

        if self.route == "ANSWER":
            if not self.patient_text or not self.patient_text.strip():
                raise ValueError("patient_text_required")
            if self.clarify_axis is not None:
                raise ValueError("clarify_axis_forbidden_for_answer")
            if self.clarify_service_options is not None:
                raise ValueError("clarify_service_options_forbidden_for_answer")
        elif self.route == "ADMIN":
            if self.patient_text is not None:
                raise ValueError("patient_text_forbidden_for_admin")
            if self.clarify_axis is not None:
                raise ValueError("clarify_axis_forbidden_for_admin")
            if self.clarify_service_options is not None:
                raise ValueError("clarify_service_options_forbidden_for_admin")
            if self.promotion_scope != "none":
                raise ValueError("promotion_scope_forbidden")
        elif self.route == "CLARIFY":
            if not self.patient_text or not self.patient_text.strip():
                raise ValueError("patient_text_required")
            if self.clarify_axis is None:
                raise ValueError("clarify_axis_required_for_clarify")
            if self.clarify_axis != "service" and self.clarify_service_options is not None:
                raise ValueError("clarify_service_options_forbidden_for_axis")
            if self.clarify_axis == "service" and self.clarify_service_options is None:
                raise ValueError("clarify_service_options_invalid")
            if self.promotion_scope != "none":
                raise ValueError("promotion_scope_forbidden")
        return self


def required_envelope_field_names() -> frozenset[str]:
    return _REQUIRED_FIELD_NAMES
