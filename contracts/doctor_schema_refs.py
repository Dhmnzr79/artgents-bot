"""Pure external-reference integrity for the minimal doctor catalog (S6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, TypeAdapter, field_validator

from contracts.doctor_schema import DoctorProfileRef, TargetDoctorCatalog
from contracts.response_schema import NonBlankStr, SourceRef


class DoctorCatalogExternalIndex(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    service_ids: tuple[NonBlankStr, ...] = ()
    kb_refs: tuple[DoctorProfileRef, ...] = ()

    @field_validator("service_ids", mode="after")
    @classmethod
    def _service_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("doctor_external_service_id_duplicate")
        return value

    @field_validator("kb_refs", mode="after")
    @classmethod
    def _kb_refs_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("doctor_external_kb_ref_duplicate")
        return value


class DoctorCatalogExternalRefError(ValueError):
    code = "doctor_catalog_external_refs_missing"

    def __init__(
        self,
        *,
        missing_service_ids: tuple[str, ...],
        missing_profile_refs: tuple[str, ...],
    ) -> None:
        self.missing_service_ids = missing_service_ids
        self.missing_profile_refs = missing_profile_refs
        super().__init__(self.code)


def validate_doctor_catalog_external_refs(
    catalog: TargetDoctorCatalog,
    index: DoctorCatalogExternalIndex,
) -> None:
    """Fail once with every exact service/profile ref absent from the supplied index."""

    available_service_ids = set(index.service_ids)
    available_kb_refs = set(index.kb_refs)
    missing_service_ids: set[str] = set()
    missing_profile_refs: set[str] = set()

    for doctor in catalog.doctors.values():
        missing_service_ids.update(
            service_id
            for service_id in doctor.service_ids
            if service_id not in available_service_ids
        )
        if doctor.profile_ref not in available_kb_refs:
            missing_profile_refs.add(doctor.profile_ref)

    if missing_service_ids or missing_profile_refs:
        raise DoctorCatalogExternalRefError(
            missing_service_ids=tuple(sorted(missing_service_ids)),
            missing_profile_refs=tuple(sorted(missing_profile_refs)),
        )


def build_doctor_source_refs(catalog: TargetDoctorCatalog) -> tuple[SourceRef, ...]:
    """Build one exact, sorted ``doctor:`` ref for every catalog key."""

    adapter = TypeAdapter(SourceRef)
    return tuple(
        sorted(adapter.validate_python(f"doctor:{doctor_id}") for doctor_id in catalog.doctors)
    )
