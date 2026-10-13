"""Resolve D2 commercial blocks from the tenant commercial contract before freeze."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from contracts.response_schema import ResponseDataCatalog
from core.response_plan_fact_projection import fact_active_as_of

from contracts.response_plan import D2CommercialPackageBlock, D2CompatibilityBlock, ResolvedFactBlock
from contracts.response_plan_materialization import D2CommercialAuthority


@dataclass(frozen=True, slots=True)
class D2ResolvedCommercialPlan:
    promo_blocks: tuple[ResolvedFactBlock, ...] = ()
    price_booster_block: D2CommercialPackageBlock | None = None
    also_list_block: D2CommercialPackageBlock | None = None


def resolve_d2_commercial_plan(
    *,
    authority: D2CommercialAuthority | None,
    bundle: ResponseDataCatalog,
    as_of: date,
    service_id: str | None,
    topic_id: str | None = None,
    include_packages: bool,
    shown_promo_fact_ids: tuple[str, ...] = (),
    promo_form: str = "short",
    promotion_scope: str = "service",
    skip_shown: bool = True,
    max_promo: int | None = 2,
) -> D2ResolvedCommercialPlan:
    if authority is None:
        return D2ResolvedCommercialPlan()
    client_id = authority.source_client_id
    profiles = {item.service_id: item for item in authority.service_profiles}
    profile = profiles.get(service_id) if service_id else None
    shown = set(shown_promo_fact_ids) if skip_shown else set()
    promo_blocks = []
    for fact_id, fact in sorted(bundle.facts.items()):
        if fact.kind != "promo" or not fact_active_as_of(fact, as_of) or fact_id in shown:
            continue
        if promotion_scope == "shown" and fact_id not in shown_promo_fact_ids:
            continue
        if promotion_scope != "general":
            if service_id is not None:
                if service_id not in fact.allowed_service_ids or service_id in fact.excluded_service_ids:
                    continue
            elif topic_id is None or topic_id not in fact.allowed_topics:
                continue
        display_text = fact.text_fact if promo_form == "full" else fact.microfact_text
        if not display_text:
            raise ValueError("commercial_promo_short_missing")
        promo_blocks.append(ResolvedFactBlock(
            fact_id=fact_id, display_text=display_text, role="promo", source_client_id=client_id,
        ))
        if max_promo is not None and len(promo_blocks) >= max_promo:
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
    return D2ResolvedCommercialPlan(
        promo_blocks=tuple(promo_blocks),
        price_booster_block=booster,
        also_list_block=also,
    )


def resolve_d2_commercial_compatibility(
    *, authority: D2CommercialAuthority | None, published_ids: frozenset[str],
) -> tuple[D2CompatibilityBlock, ...]:
    """Check authored groups once, against the complete published positive set."""
    if authority is None:
        return ()
    return tuple(
        D2CompatibilityBlock(
            source_client_id=authority.source_client_id,
            group_id=group.group_id,
            member_ids=tuple(member for member in group.offer_or_fact_ids if member in published_ids),
            explanation_text=group.explanation_text,
        )
        for group in authority.incompatibility_groups
        if sum(member in published_ids for member in group.offer_or_fact_ids) >= 2
    )
