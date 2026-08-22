"""Bind validated envelope + governed UI into authoritative semantic frame (Stage 4.3 / 5.1B)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallCommercialIntent, OneCallEnvelope, OneCallPromotionScope
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame, SemanticFieldProvenance
from contracts.service_reference import AvailabilityStatus
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot


class SalesOnePlusSemanticConflictError(ValueError):
    """Typed UI/envelope semantic conflict — stable reason code only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GovernedUiSemanticAuthority:
    service_id: str | None
    extent: str | None
    jaw: str | None
    stage: str | None


def governed_ui_authority_from_resolution(
    resolution: ExactSalesResolution,
) -> GovernedUiSemanticAuthority:
    return GovernedUiSemanticAuthority(
        service_id=_value_if_governed(resolution.service_id, resolution.service_id_authority),
        extent=_value_if_governed(resolution.extent, resolution.extent_authority),
        jaw=_value_if_governed(resolution.jaw, resolution.jaw_authority),
        stage=_value_if_governed(resolution.stage, resolution.stage_authority),
    )


def _value_if_governed(value: object, authority: ExactSalesFieldAuthority) -> str | None:
    if authority.authority != "governed_ui":
        return None
    if value is None:
        return None
    token = str(value).strip()
    return token or None


def _merge_field(
    *,
    field: str,
    ui_value: str | None,
    envelope_value: str | None,
) -> tuple[str | None, SemanticFieldProvenance]:
    if ui_value is not None:
        if envelope_value is not None and envelope_value != ui_value:
            raise SalesOnePlusSemanticConflictError(f"semantic_ui_envelope_conflict_{field}")
        return ui_value, "governed_ui"
    if envelope_value is not None:
        return envelope_value, "envelope"
    return None, "null"


def _resolve_availability_status(
    *,
    service_reference_status: str,
    requested_service_id: str | None,
    reference_catalog: ServiceReferenceCatalogSnapshot,
) -> AvailabilityStatus:
    if service_reference_status == "unresolved":
        return "unresolved"
    if service_reference_status == "none":
        return "none"
    if service_reference_status != "resolved" or requested_service_id is None:
        return "none"
    active = reference_catalog.is_active(requested_service_id)
    if active is True:
        return "offered"
    if active is False:
        return "known_not_offered"
    return "unresolved"


def _envelope_service_candidates(envelope: OneCallEnvelope) -> tuple[str, ...]:
    candidates: list[str] = []
    if envelope.service_id is not None:
        candidates.append(envelope.service_id)
    if envelope.service_reference_status == "resolved" and envelope.requested_service_id is not None:
        candidates.append(envelope.requested_service_id)
    return tuple(dict.fromkeys(candidates))


def _assert_no_envelope_service_conflict(
    *,
    selected_service_id: str,
    envelope: OneCallEnvelope,
    conflict_code: str,
) -> None:
    for candidate in _envelope_service_candidates(envelope):
        if candidate != selected_service_id:
            raise SalesOnePlusSemanticConflictError(conflict_code)


def _project_active_service_id(
    *,
    envelope: OneCallEnvelope,
    governed_ui: GovernedUiSemanticAuthority,
    reference_catalog: ServiceReferenceCatalogSnapshot,
    explicit_catalog_service_id: str | None = None,
    session_service_id: str | None = None,
) -> tuple[str | None, SemanticFieldProvenance]:
    if governed_ui.service_id is not None:
        if governed_ui.service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        if envelope.service_reference_status == "resolved":
            requested = envelope.requested_service_id
            if requested is not None and requested != governed_ui.service_id:
                raise SalesOnePlusSemanticConflictError("semantic_ui_envelope_conflict_service_id")
        return governed_ui.service_id, "governed_ui"

    if explicit_catalog_service_id is not None:
        if explicit_catalog_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        _assert_no_envelope_service_conflict(
            selected_service_id=explicit_catalog_service_id,
            envelope=envelope,
            conflict_code="semantic_catalog_envelope_conflict_service_id",
        )
        return explicit_catalog_service_id, "exact_turn"

    if session_service_id is not None:
        if session_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        _assert_no_envelope_service_conflict(
            selected_service_id=session_service_id,
            envelope=envelope,
            conflict_code="semantic_session_envelope_conflict_service_id",
        )
        return session_service_id, "valid_session"

    envelope_service_id = envelope.service_id
    if envelope.service_reference_status == "resolved":
        requested = envelope.requested_service_id
        if requested is None:
            raise SalesOnePlusSemanticConflictError("requested_service_id_required_for_resolved")
        is_active = reference_catalog.is_active(requested)
        if is_active is False:
            if envelope_service_id is not None:
                raise SalesOnePlusSemanticConflictError("service_id_conflict_inactive_reference")
            return None, "null"
        if is_active is None:
            raise SalesOnePlusSemanticConflictError("requested_service_id_invalid")
        if envelope_service_id is not None and envelope_service_id != requested:
            raise SalesOnePlusSemanticConflictError("semantic_envelope_service_id_conflict")
        return requested, "envelope"

    if envelope_service_id is not None:
        if envelope_service_id not in reference_catalog.active_service_ids:
            raise SalesOnePlusSemanticConflictError("service_id_inactive")
        return envelope_service_id, "envelope"
    return None, "null"


def bind_semantic_frame(
    *,
    envelope: OneCallEnvelope,
    governed_ui: GovernedUiSemanticAuthority,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    explicit_catalog_service_id: str | None = None,
    session_service_id: str | None = None,
) -> SalesOnePlusSemanticFrame:
    """Pure local binder — no provider calls, no regex, no client reload."""

    service_id, service_id_provenance = _project_active_service_id(
        envelope=envelope,
        governed_ui=governed_ui,
        reference_catalog=service_reference_catalog,
        explicit_catalog_service_id=explicit_catalog_service_id,
        session_service_id=session_service_id,
    )
    extent, extent_provenance = _merge_field(
        field="extent",
        ui_value=governed_ui.extent,
        envelope_value=envelope.extent,
    )
    jaw, jaw_provenance = _merge_field(
        field="jaw",
        ui_value=governed_ui.jaw,
        envelope_value=envelope.jaw,
    )
    stage, stage_provenance = _merge_field(
        field="stage",
        ui_value=governed_ui.stage,
        envelope_value=envelope.stage,
    )

    if service_id is not None and service_id not in active_service_catalog.active_service_ids:
        raise SalesOnePlusSemanticConflictError("service_id_inactive")
    if stage is not None and stage not in active_service_catalog.allowed_patient_stages:
        raise SalesOnePlusSemanticConflictError("stage_not_allowed")
    if envelope.clarify_service_options is not None:
        for option_id in envelope.clarify_service_options:
            if option_id not in active_service_catalog.active_service_ids:
                raise SalesOnePlusSemanticConflictError("clarify_service_options_invalid")

    availability_status = _resolve_availability_status(
        service_reference_status=envelope.service_reference_status,
        requested_service_id=envelope.requested_service_id,
        reference_catalog=service_reference_catalog,
    )

    commercial_intent: OneCallCommercialIntent = (
        "none" if envelope.route == "CLARIFY" else envelope.commercial_intent
    )
    promotion_scope: OneCallPromotionScope = (
        "none" if envelope.route in {"CLARIFY", "ADMIN"} else envelope.promotion_scope
    )
    return SalesOnePlusSemanticFrame(
        route=envelope.route,
        service_id=service_id,
        service_id_provenance=service_id_provenance,
        extent=extent,  # type: ignore[arg-type]
        extent_provenance=extent_provenance,
        jaw=jaw,  # type: ignore[arg-type]
        jaw_provenance=jaw_provenance,
        stage=stage,
        stage_provenance=stage_provenance,
        scenario=envelope.scenario,
        commercial_intent=commercial_intent,
        promotion_scope=promotion_scope,
        clarify_axis=envelope.clarify_axis,
        clarify_service_options=envelope.clarify_service_options,
        service_reference_status=envelope.service_reference_status,
        requested_service_id=envelope.requested_service_id,
        availability_status=availability_status,
        direct_fact_ids=envelope.references.direct_fact_ids,
    )


def presentation_commercial_intent(
    semantic: SalesOnePlusSemanticFrame,
) -> OneCallCommercialIntent:
    """Route-aware presentation intent — CLARIFY/ADMIN close commercial surfaces."""

    if semantic.route in {"CLARIFY", "ADMIN"}:
        return "none"
    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return "none"
    return semantic.commercial_intent


def presentation_promotion_scope(
    semantic: SalesOnePlusSemanticFrame,
) -> OneCallPromotionScope:
    """Route-aware promotion scope — CLARIFY/ADMIN close promotion surface."""

    if semantic.route in {"CLARIFY", "ADMIN"}:
        return "none"
    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return "none"
    return semantic.promotion_scope


def presentation_active_service_id(semantic: SalesOnePlusSemanticFrame) -> str | None:
    """Active service focus for commerce/marketing — unavailable axes force null."""

    if semantic.availability_status in {"known_not_offered", "unresolved"}:
        return None
    return semantic.service_id
