"""Typed UI stage click contract (AC3)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contracts.target_service_applicability import PatientStage

UI_STAGE_REF_PREFIX = "target:ui_stage/"
_UI_STAGE_REF_RE = re.compile(
    r"^target:ui_stage/(?P<topic>[a-z0-9_]+)/(?P<stage>natural_tooth_present|extraction_context|implant_placed)$"
)


class UiStageAction(BaseModel):
    """Canonical stage from a governed UI ref click; label is not authoritative."""

    model_config = ConfigDict(extra="forbid")

    stage: PatientStage
    topic: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    provenance: Literal["ui_stage_ref"] = "ui_stage_ref"

    @field_validator("topic", mode="after")
    @classmethod
    def _normalize_topic(cls, value: str) -> str:
        topic = str(value).strip().lower()
        if not topic:
            raise ValueError("topic_required")
        return topic


def is_ui_stage_ref(ref: str) -> bool:
    return str(ref or "").strip().startswith(UI_STAGE_REF_PREFIX)


def build_ui_stage_ref(*, topic: str, stage: PatientStage) -> str:
    topic_eff = str(topic).strip().lower()
    if not topic_eff:
        raise ValueError("topic_required")
    return f"{UI_STAGE_REF_PREFIX}{topic_eff}/{stage}"


def parse_ui_stage_ref(ref: str) -> UiStageAction | None:
    ref_eff = str(ref or "").strip()
    match = _UI_STAGE_REF_RE.match(ref_eff)
    if match is None:
        return None
    return UiStageAction(
        stage=match.group("stage"),  # type: ignore[arg-type]
        topic=match.group("topic"),
        ref=ref_eff,
    )
