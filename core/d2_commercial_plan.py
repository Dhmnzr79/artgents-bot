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
) -> D2ResolvedCommercialPlan:
    if authority is None or not service_id:
        return D2ResolvedCommercialPlan()
    profile = next((item for item in authority.service_profiles if item.service_id == service_id), None)
    if profile is None:
        return D2ResolvedCommercialPlan()
    client_id = authority.source_client_id
    promos = {item.fact_id: item for item in authority.promo_facts}
    shown = set(shown_promo_fact_ids)
    promo_blocks = tuple(
        ResolvedFactBlock(
            fact_id=fact_id,
            display_text=promos[fact_id].short_text,
            role="promo",
            source_client_id=client_id,
        )
        for fact_id in profile.promo_refs
        if fact_id in promos and fact_id not in shown
    )
    booster = None
    also = None
    if include_packages:
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
        promo_blocks=promo_blocks,
        price_booster_block=booster,
        also_list_block=also,
        compatibility_blocks=compatibility,
    )
