"""Minimal offline target doctor-data contracts (S5, unwired)."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, field_validator

from contracts.response_schema import NonBlankStr, SourceRef


def _require_doctor_id(value: str) -> str:
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value) is None:
        raise ValueError("doctor_id_invalid")
    return value


def _require_doctor_profile_ref(value: str) -> str:
    if not value.startswith("kb:"):
        raise ValueError("doctor_profile_ref_requires_kb_prefix")
    document, _chunk = value.removeprefix("kb:").split("#", 1)
    if not document.endswith(".md"):
        raise ValueError("doctor_profile_ref_requires_md_document")
    return value


DoctorId = Annotated[str, AfterValidator(_require_doctor_id)]
DoctorProfileRef = Annotated[SourceRef, AfterValidator(_require_doctor_profile_ref)]
ExperienceYears = Annotated[StrictInt, Field(ge=0)]


class TargetDoctorSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetDoctor(TargetDoctorSchemaModel):
    name: NonBlankStr
    position: NonBlankStr
    experience_years: ExperienceYears
    service_ids: list[NonBlankStr]
    profile_ref: DoctorProfileRef

    @field_validator("service_ids", mode="after")
    @classmethod
    def _service_ids_non_empty_unique(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("doctor_service_ids_empty")
        if len(value) != len(set(value)):
            raise ValueError("doctor_service_id_duplicate")
        return value


class TargetDoctorCatalog(TargetDoctorSchemaModel):
    doctors: dict[DoctorId, TargetDoctor]
