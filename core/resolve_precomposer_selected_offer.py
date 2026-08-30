"""Pure pre-Composer fixed-offer resolver (CP-EXACT-1B-SINGLE / MULTI-V1)."""

from __future__ import annotations

from dataclasses import replace

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.exact_sales_resolution import (
    ExactSalesFieldAuthority,
    ExactSalesResolution,
)
from contracts.precomposer_selected_offer import (
    PrecomposerOfferDiagnostic,
    PrecomposerSelectedOfferContractError,
    PrecomposerSelectedOfferResult,
)
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from core.service_data_context import build_service_data_context
from core.target_brand_mention_extraction import extract_brand_mentions_from_message
from core.target_brand_resolver import TargetBrandResolutionError
from core.target_offer_extent_applicability import filter_offers_for_extent
from core.target_runtime_session import TargetRuntimeSessionState
from core.target_strategy_context import strategy_match_from_effective_scope
from core.sales_fast_service_identity import SalesFastServiceIdentity

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
    if not str(offer.package.label or "").strip():
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


def _eligible_scope_offers(
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    service_id: str,
    strategy_context,
    selected_option_id: str | None,
) -> tuple[TargetOffer, ...]:
    context = build_service_data_context(bundle, doctor_catalog, service_id)
    options_by_id = {option.option_id: option for option in context.service.options}
    eligible: list[TargetOffer] = []
    if not context.service.active:
        return ()
    for offer in context.offers:
        if not offer.active:
            continue
        if selected_option_id is not None:
            if offer.option_id != selected_option_id:
                continue
            if options_by_id[selected_option_id].active is False:
                continue
        elif offer.option_id is not None:
            if options_by_id[offer.option_id].active is False:
                continue
        eligible.append(offer.model_copy(deep=True))
    if strategy_context.extent is not None:
        eligible = list(
            filter_offers_for_extent(
                tuple(eligible),
                context.service,
                strategy_context.extent,  # type: ignore[arg-type]
            )
        )
    return tuple(eligible)


def _brand_catalog_order(bundle: ResponseSchemaBundle) -> dict[str, int]:
    return {
        brand_id: index for index, brand_id in enumerate(bundle.brands.brands.keys())
    }


def _option_catalog_order(bundle: ResponseSchemaBundle, service_id: str) -> dict[str, int]:
    service = bundle.services.get(service_id)
    if service is None:
        return {}
    return {option.option_id: index for index, option in enumerate(service.options)}


def order_precomposer_offers_neutral(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> tuple[TargetOffer, ...]:
    """Expose neutral authored order for formatter and resolver consumers."""

    brand_order = _brand_catalog_order(bundle)
    option_order = _option_catalog_order(bundle, service_id)

    def sort_key(offer: TargetOffer) -> tuple[int, int, str]:
        if offer.brand_id:
            return (0, brand_order.get(offer.brand_id, 10_000), offer.offer_id)
        if offer.option_id:
            return (1, option_order.get(offer.option_id, 10_000), offer.offer_id)
        return (2, 10_000, offer.offer_id)

    return tuple(sorted(offers, key=sort_key))


def _resolve_eligible_offers(
    *,
    service_id: str,
    eligible: tuple[TargetOffer, ...],
    bundle: ResponseSchemaBundle,
) -> PrecomposerSelectedOfferResult:
    if not eligible:
        return PrecomposerSelectedOfferResult(availability="none")

    if len(eligible) == 1:
        offer = eligible[0]
        if _fixed_offer_valid(offer):
            return PrecomposerSelectedOfferResult(
                availability="selected",
                offer=offer,
                service_id=service_id,
            )
        return PrecomposerSelectedOfferResult(availability="none")

    price_modes = {offer.price.mode for offer in eligible}
    has_fixed = "fixed" in price_modes
    has_non_fixed = any(mode != "fixed" for mode in price_modes)
    if has_fixed and has_non_fixed:
        return PrecomposerSelectedOfferResult(
            availability="none",
            diagnostic="multi_offer_mixed_price_modes",
        )

    if not all(_fixed_offer_valid(offer) for offer in eligible):
        return PrecomposerSelectedOfferResult(
            availability="none",
            diagnostic="multi_offer_malformed",
        )

    billing_units = {
        str(offer.price.billing_unit or "").strip() for offer in eligible
    }
    if len(billing_units) > 1:
        return PrecomposerSelectedOfferResult(
            availability="none",
            diagnostic="multi_offer_unsafe_scope",
        )
    if billing_units != {"jaw"}:
        return PrecomposerSelectedOfferResult(availability="none")

    if len(eligible) > 3:
        return PrecomposerSelectedOfferResult(
            availability="none",
            diagnostic="multi_offer_too_many",
        )

    ordered = order_precomposer_offers_neutral(
        eligible,
        bundle=bundle,
        service_id=service_id,
    )
    if 2 <= len(ordered) <= 3:
        try:
            return PrecomposerSelectedOfferResult(
                availability="multiple",
                offers=ordered,
                service_id=service_id,
            )
        except PrecomposerSelectedOfferContractError:
            return PrecomposerSelectedOfferResult(
                availability="none",
                diagnostic="multi_offer_malformed",
            )
    return PrecomposerSelectedOfferResult(
        availability="none",
        diagnostic="multi_offer_too_many",
    )


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

    effective_resolution = _effective_precomposer_resolution(
        resolution,
        service_identity=service_identity,
        session_state=session_state,
    )
    if len(brand_mentions) == 1:
        return resolve_precomposer_selected_offer(
            bundle=bundle,
            doctor_catalog=doctor_catalog,
            resolution=effective_resolution,
            selected_brand_id=brand_mentions[0],
            brand_id_authoritative=True,
        )
    if len(brand_mentions) >= 2:
        return resolve_precomposer_selected_offer(
            bundle=bundle,
            doctor_catalog=doctor_catalog,
            resolution=effective_resolution,
            selected_brand_ids=brand_mentions,
            brand_ids_authoritative=True,
        )
    return resolve_precomposer_selected_offer(
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        resolution=effective_resolution,
    )


def resolve_precomposer_selected_offer(
    *,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    resolution: ExactSalesResolution,
    selected_brand_id: str | None = None,
    selected_brand_ids: tuple[str, ...] = (),
    selected_option_id: str | None = None,
    brand_id_authoritative: bool = False,
    brand_ids_authoritative: bool = False,
    option_id_authoritative: bool = False,
) -> PrecomposerSelectedOfferResult:
    """Return zero, one, or 2–3 active fixed offers when authoritative inputs allow."""

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

    brand_filter: frozenset[str] | None = None
    if brand_ids_authoritative and selected_brand_ids:
        brand_filter = frozenset(selected_brand_ids)
    elif brand_id_authoritative and selected_brand_id:
        brand_filter = frozenset({selected_brand_id})

    option_pin = selected_option_id if option_id_authoritative and selected_option_id else None

    effective_scope = _effective_scope_from_resolution(resolution)
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        stage=resolution.stage,  # type: ignore[arg-type]
        jaw=resolution.jaw,  # type: ignore[arg-type]
    )
    eligible = _eligible_scope_offers(
        bundle=bundle,
        doctor_catalog=doctor_catalog,
        service_id=service_id,
        strategy_context=strategy_context,
        selected_option_id=option_pin,
    )
    if brand_filter is not None:
        eligible = tuple(offer for offer in eligible if offer.brand_id in brand_filter)

    return _resolve_eligible_offers(
        service_id=service_id,
        eligible=eligible,
        bundle=bundle,
    )
