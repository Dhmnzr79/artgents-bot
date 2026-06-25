"""Patient situation → soft routing bias via pricebook default_unit (not contract hints)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.patient_situation import PatientScope, PatientSituationResult
from core.price_scope import PriceScopeResult, jaw_arch_service_ids, one_tooth_implant_service_ids
from core.routing_loader import THRESHOLDS

_ROUTING_SCOPES: frozenset[PatientScope] = frozenset(
    {
        "one_tooth",
        "few_teeth",
        "full_jaw",
        "upper_jaw",
        "prosthetic_stage",
    }
)

_SKIP_KINDS: frozenset[str] = frozenset(
    {
        "unknown",
        "urgent_problem",
        "generic_implant_interest",
        "bone_deficit_or_grafting",
    }
)


@dataclass(frozen=True)
class PatientScopeUnitBias:
    """Soft retrieval bias from patient_scope + pricebook units — not service_id hard routes."""

    patient_scope: PatientScope
    preferred_units: frozenset[str]
    penalized_units: frozenset[str]


def situation_routing_eligible(situation: PatientSituationResult) -> bool:
    if situation.should_clarify:
        return False
    if situation.kind in _SKIP_KINDS:
        return False
    if situation.patient_scope not in _ROUTING_SCOPES:
        return False
    return float(situation.confidence) >= float(
        THRESHOLDS.patient_situation.min_confidence_for_routing
    )


def unit_bias_for_patient_scope(scope: PatientScope) -> PatientScopeUnitBias | None:
    if scope == "one_tooth":
        return PatientScopeUnitBias(scope, frozenset({"one_tooth"}), frozenset({"jaw"}))
    if scope == "few_teeth":
        return PatientScopeUnitBias(scope, frozenset({"one_tooth"}), frozenset({"jaw"}))
    if scope in {"full_jaw", "upper_jaw"}:
        return PatientScopeUnitBias(scope, frozenset({"jaw"}), frozenset({"one_tooth"}))
    if scope == "prosthetic_stage":
        return PatientScopeUnitBias(scope, frozenset(), frozenset({"jaw"}))
    return None


def unit_bias_for_situation(
    situation: PatientSituationResult,
) -> PatientScopeUnitBias | None:
    if not situation_routing_eligible(situation):
        return None
    return unit_bias_for_patient_scope(situation.patient_scope)


def price_scope_from_situation(
    situation: PatientSituationResult,
    *,
    client_id: str | None,
    vague_price_carry: bool = False,
) -> PriceScopeResult | None:
    """Supplement price_scope when price intent is clear from situation but regex scope missed."""
    if not situation_routing_eligible(situation):
        return None
    if situation.cues.intent != "price" and not vague_price_carry:
        return None

    jaw = jaw_arch_service_ids(client_id)
    one = one_tooth_implant_service_ids(client_id)
    scope = situation.patient_scope

    if scope in {"one_tooth", "few_teeth"}:
        protocol = None
        if vague_price_carry and "classic" in one:
            # TECH_DEBT: demo-only default; next — default_one_tooth_price_service in pricebook/client config.
            protocol = "classic"
        return PriceScopeResult(
            kind="one_tooth",
            blocked_service_ids=jaw,
            protocol_service_id=protocol,
        )
    if scope == "prosthetic_stage":
        blocked = one | jaw | frozenset({"classic", "one_stage"})
        return PriceScopeResult(
            kind="prosthetic_stage",
            protocol_service_id="implant_supported_prosthetics",
            blocked_service_ids=blocked - frozenset({"implant_supported_prosthetics"}),
        )
    if scope == "full_jaw":
        return PriceScopeResult(
            kind="full_jaw",
            group_id="full_jaw",
            blocked_service_ids=one,
        )
    if scope == "upper_jaw":
        return PriceScopeResult(
            kind="upper_jaw",
            group_id="upper_jaw",
            blocked_service_ids=one,
        )
    return None


def merge_price_scope(
    primary: PriceScopeResult,
    situation: PatientSituationResult,
    *,
    client_id: str | None,
    vague_price_carry: bool = False,
) -> PriceScopeResult:
    if primary.kind != "none":
        return primary
    supplemented = price_scope_from_situation(
        situation,
        client_id=client_id,
        vague_price_carry=vague_price_carry,
    )
    return supplemented if supplemented is not None else primary
