from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.answer_plan import AspectKind
from contracts.decision_frame import RouteIntent
from contracts.patient_situation import PatientSituationKind


class TurnBrandFilter(BaseModel):
    """Optional deterministic PriceBook filter requested by the patient."""

    model_config = ConfigDict(extra="forbid")

    brand_group: str | None = None
    brand: str | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "TurnBrandFilter":
        if not (self.brand_group or self.brand):
            raise ValueError("brand_filter_empty")
        return self


class TurnPlan(BaseModel):
    """Single-turn LLM plan.

    `followup_of` is the service_id of the previous dialog focus when the
    current question continues that topic; otherwise it is null. `service_id`
    is the resolved service for the current turn. For "а сколько стоит?" after
    All-on-4 both fields are `all_on_4`; for a topic switch like "а виниры
    сколько?" after All-on-4, `followup_of` is null and `service_id` is
    `veneers`.
    """

    model_config = ConfigDict(extra="forbid")

    route: RouteIntent
    aspects: list[AspectKind] = Field(min_length=1)
    service_id: str | None = None
    followup_of: str | None = None
    needs_clarify: bool = False
    patient_situation: PatientSituationKind | None = None
    brand_filter: TurnBrandFilter | None = None
