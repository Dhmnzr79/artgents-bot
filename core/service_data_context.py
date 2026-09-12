"""Pure target service/offer/doctor context assembly (S10, offline and unwired)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetService


@dataclass(frozen=True, slots=True)
class ServiceDoctorContext:
    doctor_id: str
    name: str
    position: str
    experience_years: int
    profile_ref: str


@dataclass(frozen=True, slots=True)
class ServiceDataContext:
    service_id: str
    service: TargetService
    offers: tuple[TargetOffer, ...]
    doctors: tuple[ServiceDoctorContext, ...]


class ServiceDataContextError(ValueError):
    """Typed error for an invalid or unknown exact service identifier."""

    def __init__(self, code: str, service_id: object) -> None:
        self.code = code
        self.service_id = service_id
        super().__init__(f"{code}: {service_id!r}")


def build_service_data_context(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    service_id: str,
) -> ServiceDataContext:
    """Join already validated target records without selection or product authority."""

    if not isinstance(service_id, str) or not service_id.strip():
        raise ServiceDataContextError("service_id_invalid", service_id)

    service = bundle.services.get(service_id)
    if service is None:
        raise ServiceDataContextError("service_not_found", service_id)

    offers = tuple(
        offer.model_copy(deep=True)
        for offer in bundle.offers
        if offer.service_id == service_id
    )
    doctors = tuple(
        ServiceDoctorContext(
            doctor_id=doctor_id,
            name=doctor.name,
            position=doctor.position,
            experience_years=doctor.experience_years,
            profile_ref=doctor.profile_ref,
        )
        for doctor_id, doctor in doctor_catalog.doctors.items()
        if service_id in doctor.service_ids
    )
    return ServiceDataContext(
        service_id=service_id,
        service=service.model_copy(deep=True),
        offers=offers,
        doctors=doctors,
    )
