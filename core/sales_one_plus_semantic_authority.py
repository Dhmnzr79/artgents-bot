"""Bind validated envelope + governed UI into authoritative semantic frame (Stage 4.3)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallCommercialIntent, OneCallEnvelope
from contracts.response_schema import ResponseSchemaBundle
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame, SemanticFieldProvenance
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot


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


def bind_semantic_frame(
    *,
    envelope: OneCallEnvelope,
    governed_ui: GovernedUiSemanticAuthority,
    active_service_catalog: ActiveServiceCatalogSnapshot,
) -> SalesOnePlusSemanticFrame:
    """Pure local binder — no provider calls, no regex, no client reload."""

    service_id, service_id_provenance = _merge_field(
        field="service_id",
        ui_value=governed_ui.service_id,
        envelope_value=envelope.service_id,
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

    commercial_intent: OneCallCommercialIntent = (
        "none" if envelope.route == "CLARIFY" else envelope.commercial_intent
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
        clarify_axis=envelope.clarify_axis,
        clarify_service_options=envelope.clarify_service_options,
    )


def presentation_commercial_intent(
    semantic: SalesOnePlusSemanticFrame,
) -> OneCallCommercialIntent:
    """Route-aware presentation intent — CLARIFY is always non-commercial."""

    if semantic.route == "CLARIFY":
        return "none"
    return semantic.commercial_intent
