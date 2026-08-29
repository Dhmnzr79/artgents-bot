"""Pure pre-Composer single fixed-offer resolver (CP-EXACT-1B-SINGLE)."""

from __future__ import annotations

from dataclasses import replace

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.exact_sales_resolution import (
    ExactSalesFieldAuthority,
    ExactSalesResolution,
)
from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from core.sales_fast_service_identity import SalesFastServiceIdentity
from core.service_data_context import build_service_data_context
from core.target_brand_mention_extraction import extract_brand_mentions_from_message
from core.target_brand_offer_projection import project_target_service_brand_offers
from core.target_brand_resolver import TargetBrandResolutionError
from core.target_offer_projection import project_target_service_offers
from core.target_runtime_session import TargetRuntimeSessionState
from core.target_strategy_context import strategy_match_from_effective_scope

_AUTHORITATIVE_FIELD_AUTHORITIES = frozenset({"governed_ui", "exact_turn", "valid_session"})


def _axis_authoritative(authority: str) -> bool:
    return authority in _AUTHORITATIVE_FIELD_AUTHORITIES


def _service_id_authoritative(resolution: ExactSalesResolution) -> bool:
    return (
        resolution.service_id is not None
        and _axis_authoritative(resolution.service_id_authority.authority)
    )


def _scope_axis_authoritative(resolution: ExactSalesResolution, field: str) -> bool:
    value = getattr(resolution, field)
    authority = getattr(resolution, f"{field}_authority")
    if value is None:
        return True
    return _axis_authoritative(authority.authority)


def _fixed_offer_valid(offer: TargetOffer) -> bool:
    price = offer.price
    if price.mode != "fixed":
        return False
    if price.amount is None or int(price.amount) < 0:
        return False
    if not str(price.currency or "").strip():
        return False
    if not str(price.billing_unit or "").strip():
        return False
    return True


def _effective_scope_from_resolution(resolution: ExactSalesResolution) -> EffectiveScope:
    unknown_axis = ScopeAxisProvenance(source="unknown", provenance="precomposer")
    envelope_axis = ScopeAxisProvenance(source="unknown", provenance="envelope")
    return EffectiveScope(
        extent=resolution.extent or "unknown",  # type: ignore[arg-type]
        jaw=resolution.jaw or "unknown",  # type: ignore[arg-type]
        stage=resolution.stage,
        topic=None,
        source="unknown",
        provenance="precomposer_selected_offer",
        extent_axis=envelope_axis if resolution.extent is not None else unknown_axis,
        jaw_axis=envelope_axis if resolution.jaw is not None else unknown_axis,
        stage_axis=envelope_axis if resolution.stage is not None else unknown_axis,
    )


def _project_offers(
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    service_id: str,
    strategy_context,
    selected_brand_id: str | None,
    selected_option_id: str | None,
) -> tuple[TargetOffer, ...]:
    context = build_service_data_context(bundle, doctor_catalog, service_id)
    if selected_brand_id is not None:
        brand_projection = project_target_service_brand_offers(
            context,
            bundle.brands,
            bundle.strategy,
            strategy_context,
            selected_brand_id=selected_brand_id,
            selected_option_id=selected_option_id,
        )
        return brand_projection.offers
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_context,
        selected_option_id=selected_option_id,
    )
    return projection.offers


def _effective_precomposer_resolution(
    resolution: ExactSalesResolution,
    *,
    service_identity: SalesFastServiceIdentity,
    session_state: TargetRuntimeSessionState,
) -> ExactSalesResolution:
    if _service_id_authoritative(resolution):
        return resolution
    if service_identity.explicit_service_id:
        return resolution
    if not session_state.is_service_focus_fresh():
        return resolution
    session_service_id = str(session_state.last_service_id or "").strip() or None
    if not session_service_id:
        return resolution
    return replace(
        resolution,
        service_id=session_service_id,
        service_id_authority=ExactSalesFieldAuthority(
            authority="valid_session",
            provenance="session.last_service_id",
        ),
    )


def resolve_precomposer_selected_offer_for_turn(
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    resolution: ExactSalesResolution,
    user_message: str,
    service_identity: SalesFastServiceIdentity,
    session_state: TargetRuntimeSessionState,
) -> PrecomposerSelectedOfferResult:
    try:
        brand_mentions = extract_brand_mentions_from_message(bundle.brands, user_message)
    except TargetBrandResolutionError:
        return PrecomposerSelectedOfferResult(availability="none")
    if len(brand_mentions) > 1:
        return PrecomposerSelectedOfferResult(availability="none")

    effective_resolution = _effective_precomposer_resolution(
        resolution,
        service_identity=service_identity,
        session_state=session_state,
    )
    return resolve_precomposer_selected_offer(
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        resolution=effective_resolution,
        selected_brand_id=brand_mentions[0] if len(brand_mentions) == 1 else None,
        brand_id_authoritative=len(brand_mentions) == 1,
    )


def resolve_precomposer_selected_offer(
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    resolution: ExactSalesResolution,
    selected_brand_id: str | None = None,
    selected_option_id: str | None = None,
    brand_id_authoritative: bool = False,
    option_id_authoritative: bool = False,
) -> PrecomposerSelectedOfferResult:
    """Return one active fixed offer only when authoritative inputs narrow to exactly one."""

    if not _service_id_authoritative(resolution):
        return PrecomposerSelectedOfferResult(availability="none")
    if resolution.conflicts:
        return PrecomposerSelectedOfferResult(availability="none")
    if not _scope_axis_authoritative(resolution, "extent"):
        return PrecomposerSelectedOfferResult(availability="none")
    if not _scope_axis_authoritative(resolution, "jaw"):
        return PrecomposerSelectedOfferResult(availability="none")
    if not _scope_axis_authoritative(resolution, "stage"):
        return PrecomposerSelectedOfferResult(availability="none")
    if resolution.jaw == "both":
        return PrecomposerSelectedOfferResult(availability="none")
    if resolution.extent == "few_teeth":
        return PrecomposerSelectedOfferResult(availability="none")

    service_id = resolution.service_id
    assert service_id is not None
    service = bundle.services.get(service_id)
    if service is None or not service.active:
        return PrecomposerSelectedOfferResult(availability="none")

    brand_pin = selected_brand_id if brand_id_authoritative and selected_brand_id else None
    option_pin = selected_option_id if option_id_authoritative and selected_option_id else None

    effective_scope = _effective_scope_from_resolution(resolution)
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        stage=resolution.stage,  # type: ignore[arg-type]
        jaw=resolution.jaw,  # type: ignore[arg-type]
    )
    offers = _project_offers(
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        service_id=service_id,
        strategy_context=strategy_context,
        selected_brand_id=brand_pin,
        selected_option_id=option_pin,
    )
    active_fixed = tuple(offer for offer in offers if offer.active and _fixed_offer_valid(offer))
    if len(active_fixed) != 1:
        return PrecomposerSelectedOfferResult(availability="none")
    return PrecomposerSelectedOfferResult(
        availability="selected",
        offer=active_fixed[0],
        service_id=service_id,
    )
