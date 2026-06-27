"""Patient situation marketing playbook — priority config (not canned copy)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.patient_situation import PatientScope, PatientSituationKind

PatientPlaybookShowWhen = Literal[
    "default",
    "bone_deficit_or_upper_jaw",
    "extraction_context",
]

PatientOptionsSource = Literal["patient_playbook"]


class PatientPlaybookAnswerStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_options: int = Field(default=4, ge=1, le=6)
    mention_consult_ct: bool = True
    avoid_single_winner: bool = True
    avoid_medical_promise: bool = True


class PatientPlaybookOptionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: str
    priority: int = 0
    role: str = ""
    positioning: str = ""
    show_when: PatientPlaybookShowWhen = "default"
    label: str | None = Field(
        default=None,
        description="Optional fallback display label; prefer catalog/pricebook title.",
    )


class PatientPlaybookSituationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_options: int = Field(default=4, ge=1, le=6)
    primary_cta: str = "consult"
    strategy: str = ""
    answer_style: PatientPlaybookAnswerStyle = Field(default_factory=PatientPlaybookAnswerStyle)
    options: list[PatientPlaybookOptionConfig] = Field(default_factory=list)


class PatientOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: str
    display_name: str
    role: str = ""
    positioning: str = ""
    priority: int = 0
    factual_snippets: list[str] = Field(default_factory=list)


class PatientOptionsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation_kind: PatientSituationKind
    patient_scope: PatientScope
    options: list[PatientOption]
    primary_cta: str = "consult"
    strategy: str = ""
    answer_style: PatientPlaybookAnswerStyle = Field(default_factory=PatientPlaybookAnswerStyle)
    source: PatientOptionsSource = "patient_playbook"
    option_service_ids: list[str] = Field(default_factory=list)
    skipped_options: list[str] = Field(default_factory=list)
