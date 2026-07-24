"""service_catalog.selection applicability gate (AC2)."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetOptionSelection,
    TargetService,
    TargetServiceSelection,
    TargetStrategyMatch,
)
from contracts.target_service_applicability import (
    SelectionPatientContext,
    TargetApplicableService,
)
from contracts.target_service_content_topic import service_catalog_content_topic_matches


def _patient_axis(
    patient: SelectionPatientContext,
    field: str,
) -> str | None:
    if field == "extent":
        if patient.extent == "unknown":
            return None
        return patient.extent
    return getattr(patient, field)


def _axis_matches(
    required: Sequence[str] | None,
    patient_value: str | None,
) -> bool:
    if required is None:
        return True
    if patient_value is None:
        return False
    return patient_value in required


def _selection_matches(
    selection: TargetServiceSelection | TargetOptionSelection,
    patient: SelectionPatientContext,
) -> bool:
    for field in ("extent", "stage", "jaw", "reported_context"):
        required = getattr(selection, field, None)
        if not _axis_matches(required, _patient_axis(patient, field)):
            return False
    return True


def _eligible_option_ids(
    service: TargetService,
    patient: SelectionPatientContext,
) -> tuple[str, ...]:
    if not service.options:
        return ()
    eligible: list[str] = []
    for option in service.options:
        if option.active is False:
            continue
        if option.selection is None:
            eligible.append(option.option_id)
            continue
        if _selection_matches(option.selection, patient):
            eligible.append(option.option_id)
    return tuple(eligible)


def _service_applicable(
    service: TargetService,
    *,
    patient: SelectionPatientContext,
    explicit_service_id: str | None,
    service_id: str,
) -> bool:
    if not service.active:
        return False
    selection = service.selection
    mode = selection.mode
    if mode == "direct":
        return explicit_service_id == service_id
    if mode == "context":
        has_constraints = any(
            getattr(selection, field) is not None
            for field in ("extent", "stage", "jaw", "reported_context")
        )
        if not has_constraints:
            return explicit_service_id == service_id
        return _selection_matches(selection, patient)
    if mode == "scope":
        return _selection_matches(selection, patient)
    return False


def filter_applicable_services(
    bundle: ResponseSchemaBundle,
    *,
    topic: str,
    strategy_context: TargetStrategyMatch | None = None,
    patient: SelectionPatientContext | None = None,
    explicit_service_id: str | None = None,
) -> tuple[TargetApplicableService, ...]:
    """Return active topic-matched services that pass authored selection rules."""

    if patient is None:
        extent: str = "unknown"
        if strategy_context is not None and strategy_context.extent is not None:
            extent = strategy_context.extent
        patient = SelectionPatientContext(
            extent=extent,  # type: ignore[arg-type]
            stage=strategy_context.stage if strategy_context else None,
            jaw=strategy_context.jaw if strategy_context else None,
            reported_context=strategy_context.reported_context if strategy_context else None,
        )

    applicable: list[TargetApplicableService] = []
    for service_id, service in bundle.services.items():
        if explicit_service_id is not None and service_id != explicit_service_id:
            continue
        content_ref = service.content_ref
        if explicit_service_id is None:
            if content_ref is None or not service_catalog_content_topic_matches(content_ref, topic):
                continue
        if not _service_applicable(
            service,
            patient=patient,
            explicit_service_id=explicit_service_id,
            service_id=service_id,
        ):
            continue
        applicable.append(
            TargetApplicableService(
                service_id=service_id,
                service=service.model_copy(deep=True),
                eligible_option_ids=_eligible_option_ids(service, patient),
            )
        )
    return tuple(applicable)


def exclusion_codes_for_service(
    service: TargetService,
    *,
    patient: SelectionPatientContext,
    explicit_service_id: str | None,
    service_id: str,
) -> tuple[str, ...]:
    """Minimal typed exclusion metadata for diagnostics/tests."""

    if not service.active:
        return ("inactive_service",)
    if service.selection.mode == "direct" and explicit_service_id != service_id:
        return ("selection_mode_direct",)
    if not _selection_matches(service.selection, patient):
        return ("selection_axes_mismatch",)
    return ()
