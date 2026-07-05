"""Dormant TurnPlan -> PriceScopeResult mapper (5.5a-2 step 1a)."""
from __future__ import annotations

from contracts.turn_plan import TurnPlan
from core.price_scope import (
    PriceScopeResult,
    jaw_arch_service_ids,
    one_tooth_implant_service_ids,
)

_ONE_TOOTH_PROTOCOLS = frozenset({"classic", "one_stage"})
_JAW_PROTOCOLS = frozenset({"all_on_4", "all_on_6", "zygomatic_implants", "pterygoid_implants"})
_SPECIFIC_PROTOCOLS = _ONE_TOOTH_PROTOCOLS | _JAW_PROTOCOLS
_PROSTHETIC_STAGE_SERVICE_ID = "implant_supported_prosthetics"


def _has_price_intent(plan: TurnPlan) -> bool:
    route = str(plan.route or "").strip()
    aspects = {str(aspect or "").strip() for aspect in (plan.aspects or [])}
    return route == "price_lookup" or "price" in aspects


def _prosthetic_stage_scope(client_id: str | None) -> PriceScopeResult:
    one_tooth_ids = one_tooth_implant_service_ids(client_id)
    jaw_arch = jaw_arch_service_ids(client_id)
    blocked = one_tooth_ids | jaw_arch | frozenset({"classic", "one_stage"})
    return PriceScopeResult(
        kind="prosthetic_stage",
        protocol_service_id=_PROSTHETIC_STAGE_SERVICE_ID,
        blocked_service_ids=blocked - frozenset({_PROSTHETIC_STAGE_SERVICE_ID}),
    )


def _specific_protocol_scope(service_id: str, client_id: str | None) -> PriceScopeResult:
    one_tooth_ids = one_tooth_implant_service_ids(client_id)
    jaw_arch = jaw_arch_service_ids(client_id)
    if service_id in {"classic", "one_stage"}:
        blocked = jaw_arch
    elif service_id in {"all_on_4", "all_on_6"}:
        blocked = one_tooth_ids
    elif service_id == "zygomatic_implants":
        blocked = one_tooth_ids | frozenset({"all_on_4", "all_on_6"})
    elif service_id == "pterygoid_implants":
        blocked = jaw_arch - frozenset({"pterygoid_implants"})
    else:
        blocked = frozenset()
    return PriceScopeResult(
        kind="specific_protocol",
        protocol_service_id=service_id,
        blocked_service_ids=blocked,
    )


def price_scope_from_plan(plan: TurnPlan, client_id: str | None) -> PriceScopeResult:
    """Map an already-built TurnPlan to the legacy PriceScopeResult contract."""
    if not _has_price_intent(plan):
        return PriceScopeResult.none()

    service_id = str(plan.service_id or "").strip()
    situation = str(plan.patient_situation or "").strip()

    if service_id == _PROSTHETIC_STAGE_SERVICE_ID or situation == "existing_implant_prosthetic_stage":
        return _prosthetic_stage_scope(client_id)

    if service_id in _SPECIFIC_PROTOCOLS:
        return _specific_protocol_scope(service_id, client_id)

    if situation == "upper_jaw_missing_or_complex":
        return PriceScopeResult(
            kind="upper_jaw",
            group_id="upper_jaw",
            blocked_service_ids=one_tooth_implant_service_ids(client_id),
        )
    if situation == "full_arch_missing":
        return PriceScopeResult(
            kind="full_jaw",
            group_id="full_jaw",
            blocked_service_ids=one_tooth_implant_service_ids(client_id),
        )
    if situation in {"one_tooth_missing", "extraction_then_implant"}:
        return PriceScopeResult(
            kind="one_tooth",
            blocked_service_ids=jaw_arch_service_ids(client_id),
        )
    if situation == "generic_implant_interest":
        return PriceScopeResult(
            kind="generic_implantation",
            group_id="implantation",
        )

    return PriceScopeResult.none()
