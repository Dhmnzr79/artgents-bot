"""Resolve D2 commercial blocks from the tenant commercial contract before freeze."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_plan import D2CommercialPackageBlock, D2CompatibilityBlock, ResolvedFactBlock
from contracts.response_plan_materialization import D2CommercialAuthority


@dataclass(frozen=True, slots=True)
class D2ResolvedCommercialPlan:
    promo_blocks: tuple[ResolvedFactBlock, ...] = ()
    price_booster_block: D2CommercialPackageBlock | None = None
    also_list_block: D2CommercialPackageBlock | None = None
    compatibility_blocks: tuple[D2CompatibilityBlock, ...] = ()


def resolve_d2_commercial_plan(
    *,
    authority: D2CommercialAuthority | None,
    service_id: str | None,
    include_packages: bool,
    shown_promo_fact_ids: tuple[str, ...] = (),
    offer_ids: tuple[str, ...] = (),
    promo_form: str = "short",
    promotion_scope: str = "service",
    skip_shown: bool = True,
    max_promo: int = 2,
    active_promo_ids: frozenset[str] | None = None,
) -> D2ResolvedCommercialPlan:
    if authority is None:
        return D2ResolvedCommercialPlan()
    client_id = authority.source_client_id
    promos = {item.fact_id: item for item in authority.promo_facts}
    profiles = {item.service_id: item for item in authority.service_profiles}
    profile = profiles.get(service_id) if service_id else None
    if promotion_scope == "general":
        candidate_ids = tuple(item.fact_id for item in authority.promo_facts)
    elif promotion_scope == "shown":
        allowed = set(profile.promo_refs) if profile is not None else set(promos)
        candidate_ids = tuple(
            fact_id for fact_id in shown_promo_fact_ids
            if fact_id in promos and fact_id in allowed
        )
    else:
        if profile is None:
            return D2ResolvedCommercialPlan()
        candidate_ids = profile.promo_refs
    shown = set(shown_promo_fact_ids) if skip_shown else set()
    promo_blocks = []
    for fact_id in candidate_ids:
        promo = promos.get(fact_id)
        if promo is None or fact_id in shown:
            continue
        if active_promo_ids is not None and fact_id not in active_promo_ids:
            continue
        display_text = promo.full_text if promo_form == "full" else promo.short_text
        promo_blocks.append(
            ResolvedFactBlock(
                fact_id=fact_id,
                display_text=display_text,
                role="promo",
                source_client_id=client_id,
            )
        )
        if len(promo_blocks) >= max_promo:
            break
    booster = None
    also = None
    if include_packages and profile is not None:
        boosters = {item.package_id: item for item in authority.price_booster_packages}
        also_lists = {item.package_id: item for item in authority.also_list_packages}
        if profile.price_booster_id is not None and profile.price_booster_id in boosters:
            package = boosters[profile.price_booster_id]
            booster = D2CommercialPackageBlock(
                source_client_id=client_id,
                package_id=package.package_id,
                name=package.name,
                body_text=package.body_text,
            )
        if profile.also_list_id is not None and profile.also_list_id in also_lists:
            package = also_lists[profile.also_list_id]
            also = D2CommercialPackageBlock(
                source_client_id=client_id,
                package_id=package.package_id,
                name=package.name,
                body_text=package.body_text,
            )
    selected = {block.fact_id for block in promo_blocks} | set(offer_ids)
    compatibility = tuple(
        D2CompatibilityBlock(
            source_client_id=client_id,
            group_id=group.group_id,
            member_ids=tuple(member for member in group.offer_or_fact_ids if member in selected),
            explanation_text=group.explanation_text,
        )
        for group in authority.incompatibility_groups
        if sum(member in selected for member in group.offer_or_fact_ids) >= 2
    )
    return D2ResolvedCommercialPlan(
        promo_blocks=tuple(promo_blocks),
        price_booster_block=booster,
        also_list_block=also,
        compatibility_blocks=compatibility,
    )
