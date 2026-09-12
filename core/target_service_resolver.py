"""Pure active target service-term resolution (S26, offline and unwired)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import TargetService


@dataclass(frozen=True, slots=True)
class TargetServiceResolution:
    service_id: str
    service: TargetService


class TargetServiceResolutionError(ValueError):
    """Typed error for invalid or ambiguous S26 service-term inputs."""

    def __init__(
        self,
        code: str,
        value: object,
        candidate_service_ids: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.value = value
        self.candidate_service_ids = candidate_service_ids
        super().__init__(f"{code}: {value!r}")


def _normalize(value: str) -> str:
    return value.strip().casefold()


def resolve_target_service_term(
    services: dict[str, TargetService],
    service_term: str,
) -> TargetServiceResolution | None:
    """Resolve one already-extracted term to one exact active target service."""

    if type(services) is not dict:
        raise TargetServiceResolutionError(
            "service_resolution_catalog_invalid", services
        )
    for service_id, service in services.items():
        if not isinstance(service_id, str) or not service_id.strip():
            raise TargetServiceResolutionError(
                "service_resolution_catalog_invalid", service_id
            )
        if not isinstance(service, TargetService):
            raise TargetServiceResolutionError(
                "service_resolution_catalog_invalid", service
            )
    if not isinstance(service_term, str) or not service_term.strip():
        raise TargetServiceResolutionError(
            "service_resolution_term_invalid", service_term
        )

    normalized_term = _normalize(service_term)
    candidate_service_ids: list[str] = []
    for service_id, service in services.items():
        if not service.active:
            continue
        lookup_values = (service_id, service.name, *service.aliases)
        if any(_normalize(value) == normalized_term for value in lookup_values):
            candidate_service_ids.append(service_id)

    if not candidate_service_ids:
        return None
    if len(candidate_service_ids) > 1:
        raise TargetServiceResolutionError(
            "service_resolution_ambiguous",
            service_term,
            tuple(candidate_service_ids),
        )

    service_id = candidate_service_ids[0]
    return TargetServiceResolution(
        service_id=service_id,
        service=services[service_id].model_copy(deep=True),
    )
