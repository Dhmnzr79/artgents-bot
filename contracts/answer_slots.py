from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnswerSlotKind = Literal["clinic_note", "consult_value", "promo_note"]


class PromoNoteMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    active_until: str | None = None


class H3SlotOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_note: str | None = None
    consult_value: str | None = None
    promo_note: PromoNoteMeta | None = None


class AnswerSlotsTelemetry(BaseModel):
    """Runtime telemetry for eval / logs (see meta.answer_slots)."""

    model_config = ConfigDict(extra="forbid")

    appended: list[AnswerSlotKind] = Field(default_factory=list)
    skipped_cooldown: list[AnswerSlotKind] = Field(default_factory=list)
    suppressed: dict[str, str] = Field(default_factory=dict)
