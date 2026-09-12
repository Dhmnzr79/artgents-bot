"""Code-owned commercial block renderer for a selected offer set (Stage B)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact, TargetOffer
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from contracts.turn_frame import TurnFrame
from core.answer_planner import detect_aspects_regex
from core.one_call_direct_commercial import _fact_is_eligible
from core.one_call_price_microfacts import _select_auto_microfact_ids
from core.one_call_payment_stages_policy import payment_stages_materialization_allowed
from core.one_call_price_text import is_pure_price_only_request
from core.sales_fast_authoritative_commerce import (
    build_payment_stages_display_block,
    offer_row_label,
    resolve_payment_stages_target_offers,
)

CommercialTopic = Literal[
    "price",
    "package_contents",
    "excluded_items",
    "payment_stages",
    "installment",
    "promotion",
    "warranty",
    "free_explanation",
]

CommercialPresentationMode = Literal["exact", "multiple", "broad", "none"]

_CODE_OWNED_TOPICS = frozenset(
    {
        "price",
        "package_contents",
        "excluded_items",
        "payment_stages",
        "installment",
        "promotion",
        "warranty",
    }
)

_MICROFACT_KINDS = frozenset({"payment", "promo"})
_DETAIL_FACT_KINDS = frozenset({"payment", "promo", "warranty"})
_MAX_AUTO_MICROFACTS = 2

_UNKNOWN_COMMERCIAL = "В материалах клиники это условие не указано."


@dataclass(frozen=True, slots=True)
class ResolvedCommercialTopics:
    topics: frozenset[str]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OfferCommercialBlocksResult:
    text_blocks: tuple[str, ...]
    rendered_offer_ids: tuple[str, ...]
    rendered_fact_ids: tuple[str, ...]
    covered_topics: frozenset[str]
    diagnostics: tuple[str, ...] = ()
    suppress_model_prose: bool = False
    skip_price_mandatory_exclusion: bool = False
    microfact_fact_ids: tuple[str, ...] = ()
    clarify_required: bool = False


@dataclass(frozen=True, slots=True)
class _PackageSnapshot:
    includes: tuple[str, ...]
    excludes: tuple[str, ...]


def _normalize_items(items: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in items if str(item).strip())


def _package_snapshot(offer: TargetOffer) -> _PackageSnapshot:
    package = offer.package
    return _PackageSnapshot(
        includes=_normalize_items(tuple(package.includes)),
        excludes=_normalize_items(tuple(package.excludes)),
    )


def resolve_requested_commercial_topics(
    *,
    semantic: SalesOnePlusSemanticFrame,
    turn_frame: TurnFrame,
    user_message: str,
    payment_stages_allowed: bool,
) -> ResolvedCommercialTopics:
    """Derive requested commercial topics from structured turn signals only."""

    topics: set[str] = set()
    diagnostics: list[str] = []

    aspects = tuple(detect_aspects_regex(user_message))
    intent = semantic.commercial_intent

    if intent == "price" or "price" in aspects:
        topics.add("price")
    if intent == "included" or "included" in aspects:
        topics.update({"package_contents", "excluded_items"})
    if intent == "promotion" or any(
        token in (user_message or "").casefold() for token in ("скидк", "акци")
    ):
        topics.add("promotion")
    if payment_stages_allowed:
        topics.add("payment_stages")
    if intent == "payment" or "payment" in aspects:
        topics.add("installment")
    elif re.search(r"рассроч", user_message or "", re.I | re.U):
        topics.add("installment")
    if "warranty" in aspects:
        topics.add("warranty")

    if re_free_explanation_requested(user_message):
        topics.add("free_explanation")

    if not is_pure_price_only_request(user_message):
        supplemental = [aspect for aspect in aspects if aspect not in {"price", "overview"}]
        if supplemental or intent not in _CODE_OWNED_TOPICS and intent != "none":
            if intent == "none" and not topics:
                pass
            elif any(aspect in {"pain", "duration", "comparison"} for aspect in aspects):
                topics.add("free_explanation")

    if not topics and intent == "none" and "overview" in aspects:
        diagnostics.append("no_commercial_topics")

    suppressible = topics - {"free_explanation"}
    if suppressible and "free_explanation" not in topics:
        diagnostics.append("commercial_only_turn")

    return ResolvedCommercialTopics(
        topics=frozenset(topics),
        diagnostics=tuple(diagnostics),
    )


def re_free_explanation_requested(user_message: str) -> bool:
    text = (user_message or "").strip()
    if not text:
        return False
    return bool(
        re.search(
            r"\b(?:почему|зачем|как\s+работает|объясните|расскажите\s+подробнее)\b",
            text,
            re.I | re.U,
        )
    )


def should_suppress_model_prose(topics: frozenset[str]) -> bool:
    if not topics:
        return False
    if "free_explanation" in topics:
        return False
    return topics.issubset(_CODE_OWNED_TOPICS)


def _format_bullet_block(header: str, items: tuple[str, ...]) -> str:
    if not items:
        return ""
    lines = [header, *[f"- {item}" for item in items]]
    return "\n".join(lines)


def _format_excludes_condition(excludes: tuple[str, ...]) -> str | None:
    if not excludes:
        return None
    if len(excludes) == 1:
        return f"{excludes[0]} — отдельно"
    joined = ", ".join(excludes[:-1]) + f" и {excludes[-1]}"
    return f"{joined} — отдельно"


def build_package_contents_block(
    *,
    bundle: ResponseSchemaBundle,
    offers: tuple[TargetOffer, ...],
    include_includes: bool,
    include_excludes: bool,
) -> tuple[str | None, bool]:
    """Return package block text and whether excludes were rendered."""

    if not offers:
        return None, False
    snapshots = {offer.offer_id: _package_snapshot(offer) for offer in offers}
    unique_includes = {snap.includes for snap in snapshots.values() if snap.includes}
    unique_excludes = {snap.excludes for snap in snapshots.values() if snap.excludes}

    if len(offers) > 1 and (len(unique_includes) > 1 or len(unique_excludes) > 1):
        sections: list[str] = []
        excludes_rendered = False
        for offer in offers:
            snap = snapshots[offer.offer_id]
            label = offer_row_label(bundle, offer) or offer.offer_id
            parts: list[str] = []
            if include_includes and snap.includes:
                parts.append(_format_bullet_block("В предложение входят:", snap.includes))
            if include_excludes and snap.excludes:
                parts.append(
                    _format_bullet_block("Отдельно оплачиваются:", snap.excludes)
                )
                excludes_rendered = True
            if parts:
                sections.append(f"{label}:\n" + "\n\n".join(parts))
        if not sections:
            return None, False
        return "\n\n".join(sections), excludes_rendered

    snap = snapshots[offers[0].offer_id]
    parts: list[str] = []
    excludes_rendered = False
    if include_includes and snap.includes:
        parts.append(_format_bullet_block("В предложение входят:", snap.includes))
    if include_excludes and snap.excludes:
        parts.append(_format_bullet_block("Отдельно оплачиваются:", snap.excludes))
        excludes_rendered = True
    if not parts:
        return None, False
    return "\n\n".join(parts), excludes_rendered


def build_price_conditions_block(
    offers: tuple[TargetOffer, ...],
    *,
    skip_when_excludes_in_package_block: bool,
) -> str | None:
    if skip_when_excludes_in_package_block or not offers:
        return None
    if len(offers) == 1:
        condition = _format_excludes_condition(_package_snapshot(offers[0]).excludes)
        return condition
    texts: set[str] = set()
    for offer in offers:
        condition = _format_excludes_condition(_package_snapshot(offer).excludes)
        if condition:
            texts.add(condition)
    if not texts:
        return None
    if len(texts) == 1:
        return next(iter(texts))
    return "; ".join(sorted(texts))


def _fact_ids_for_topic(
    offers: tuple[TargetOffer, ...],
    bundle: ResponseSchemaBundle,
    *,
    kinds: frozenset[str],
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for offer in offers:
        for fact_id in offer.fact_refs:
            if fact_id in seen:
                continue
            fact = bundle.facts.get(fact_id)
            if fact is None or str(fact.kind) not in kinds:
                continue
            seen.add(fact_id)
            ordered.append(fact_id)
    return tuple(ordered)


def _eligible_fact(
    *,
    bundle: ResponseSchemaBundle,
    fact_id: str,
    offers: tuple[TargetOffer, ...],
    authoritative_service_id: str | None,
    today: date,
) -> TargetCommercialFact | None:
    if not any(fact_id in (offer.fact_refs or ()) for offer in offers):
        return None
    if not _fact_is_eligible(
        bundle=bundle,
        fact_id=fact_id,
        authoritative_service_id=authoritative_service_id,
        today=today,
    ):
        return None
    return bundle.facts.get(fact_id)


def _microfact_text(fact: TargetCommercialFact) -> str | None:
    micro = getattr(fact, "microfact_text", None)
    if micro is not None and str(micro).strip():
        return str(micro).strip()
    return None


def resolve_auto_microfacts(
    *,
    bundle: ResponseSchemaBundle,
    offers: tuple[TargetOffer, ...],
    authoritative_service_id: str | None,
    today: date,
    exclude_fact_ids: frozenset[str] = frozenset(),
    covered_fact_ids: frozenset[str] = frozenset(),
) -> tuple[tuple[str, str], ...]:
    """Return (fact_id, display_text) short facts from offer.fact_refs."""

    resolved: list[tuple[str, str]] = []
    for fact_id in _select_auto_microfact_ids(bundle=bundle, offers=offers):
        if fact_id in exclude_fact_ids or fact_id in covered_fact_ids:
            continue
        if len(resolved) >= _MAX_AUTO_MICROFACTS:
            break
        fact = _eligible_fact(
            bundle=bundle,
            fact_id=fact_id,
            offers=offers,
            authoritative_service_id=authoritative_service_id,
            today=today,
        )
        if fact is None:
            continue
        display = _microfact_text(fact)
        if not display:
            continue
        resolved.append((fact_id, display))
    return tuple(resolved)


def build_detailed_fact_block(
    *,
    bundle: ResponseSchemaBundle,
    offers: tuple[TargetOffer, ...],
    topic: CommercialTopic,
    authoritative_service_id: str | None,
    today: date,
) -> tuple[str | None, tuple[str, ...]]:
    kind_map = {
        "installment": frozenset({"payment"}),
        "promotion": frozenset({"promo"}),
        "warranty": frozenset({"warranty"}),
    }
    kinds = kind_map.get(topic)
    if kinds is None:
        return None, ()
    texts: list[str] = []
    rendered: list[str] = []
    for fact_id in _fact_ids_for_topic(offers, bundle, kinds=kinds):
        fact = _eligible_fact(
            bundle=bundle,
            fact_id=fact_id,
            offers=offers,
            authoritative_service_id=authoritative_service_id,
            today=today,
        )
        if fact is None:
            continue
        text = str(fact.text_fact).strip()
        if not text or text in texts:
            continue
        texts.append(text)
        rendered.append(fact_id)
    if not texts:
        return None, ()
    return "\n\n".join(texts), tuple(rendered)


def render_offer_commercial_blocks(
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    topics: frozenset[str],
    presentation_mode: CommercialPresentationMode,
    price_line: str | None,
    price_visible: bool,
    payment_stages_allowed: bool,
    authoritative_service_id: str | None,
    today: date,
    selected_exact_offer: TargetOffer | None = None,
    selected_brand_id: str | None = None,
    exclude_fact_ids: frozenset[str] = frozenset(),
) -> OfferCommercialBlocksResult:
    """Dormant universal commercial renderer — not wired in active presentation.

    Active path uses ``sales_fast_authoritative_commerce`` plus
    ``enrich_price_line_with_mandatory_conditions``. Kept for Stage A/B tests and
    helper reuse only; do not reconnect without owner decision.
    """

    if not displayed_offers:
        if topics & _CODE_OWNED_TOPICS:
            return OfferCommercialBlocksResult(
                text_blocks=(_UNKNOWN_COMMERCIAL,),
                rendered_offer_ids=(),
                rendered_fact_ids=(),
                covered_topics=topics & _CODE_OWNED_TOPICS,
                diagnostics=("no_displayed_offers",),
            )
        return OfferCommercialBlocksResult(
            text_blocks=(),
            rendered_offer_ids=(),
            rendered_fact_ids=(),
            covered_topics=frozenset(),
        )

    rendered_offer_ids = tuple(offer.offer_id for offer in displayed_offers)
    blocks: list[str] = []
    covered: set[str] = set()
    rendered_facts: list[str] = []
    diagnostics: list[str] = []
    skip_price_exclusion = False
    microfact_pairs: tuple[tuple[str, str], ...] = ()

    wants_package = "package_contents" in topics or "excluded_items" in topics
    include_includes = "package_contents" in topics
    include_excludes = "excluded_items" in topics or (
        wants_package and "excluded_items" not in topics and "package_contents" in topics
    )

    if "price" in topics and price_visible and price_line and price_line.strip():
        blocks.append(price_line.strip())
        covered.add("price")

    package_block: str | None = None
    excludes_in_package = False
    if wants_package:
        package_block, excludes_in_package = build_package_contents_block(
            bundle=bundle,
            offers=displayed_offers,
            include_includes=include_includes,
            include_excludes=include_excludes or include_includes,
        )
        if package_block:
            blocks.append(package_block)
            if include_includes:
                covered.add("package_contents")
            if include_excludes or excludes_in_package:
                covered.add("excluded_items")
                skip_price_exclusion = True
        elif topics & {"package_contents", "excluded_items"} == {"package_contents", "excluded_items"}:
            diagnostics.append("package_contents_unresolved")

    if "price" in topics and price_visible and not skip_price_exclusion:
        condition = build_price_conditions_block(
            displayed_offers,
            skip_when_excludes_in_package_block=skip_price_exclusion,
        )
        if condition:
            blocks.append(condition)

    if "payment_stages" in topics and payment_stages_allowed:
        stage_offers = resolve_payment_stages_target_offers(
            displayed_offers=displayed_offers,
            selected_exact_offer=selected_exact_offer,
            selected_brand_id=selected_brand_id,
        )
        stage_block = build_payment_stages_display_block(stage_offers, bundle=bundle)
        if stage_block:
            blocks.append(stage_block)
            covered.add("payment_stages")

    for topic in ("installment", "promotion", "warranty"):
        if topic not in topics:
            continue
        block, fact_ids = build_detailed_fact_block(
            bundle=bundle,
            offers=displayed_offers,
            topic=topic,
            authoritative_service_id=authoritative_service_id,
            today=today,
        )
        if block:
            blocks.append(block)
            covered.add(topic)
            rendered_facts.extend(fact_ids)
        elif topic in topics:
            blocks.append(_UNKNOWN_COMMERCIAL)
            covered.add(topic)
            diagnostics.append(f"missing_{topic}")

    covered_fact_ids = frozenset(rendered_facts)
    if "price" in topics and presentation_mode in {"exact", "multiple"}:
        microfact_pairs = resolve_auto_microfacts(
            bundle=bundle,
            offers=displayed_offers,
            authoritative_service_id=authoritative_service_id,
            today=today,
            exclude_fact_ids=exclude_fact_ids,
            covered_fact_ids=covered_fact_ids,
        )
        if microfact_pairs:
            blocks.append("\n".join(text for _, text in microfact_pairs))
            rendered_facts.extend(fact_id for fact_id, _ in microfact_pairs)

    return OfferCommercialBlocksResult(
        text_blocks=tuple(blocks),
        rendered_offer_ids=rendered_offer_ids,
        rendered_fact_ids=tuple(dict.fromkeys(rendered_facts)),
        covered_topics=frozenset(covered),
        diagnostics=tuple(diagnostics),
        suppress_model_prose=should_suppress_model_prose(topics),
        skip_price_mandatory_exclusion=skip_price_exclusion,
        microfact_fact_ids=tuple(fact_id for fact_id, _ in microfact_pairs),
    )


def assemble_commercial_visible_text(
    *,
    commercial: OfferCommercialBlocksResult,
    patient_text: str,
) -> str:
    parts = [block for block in commercial.text_blocks if block.strip()]
    if not commercial.suppress_model_prose and patient_text.strip():
        parts.append(patient_text.strip())
    return "\n\n".join(parts).strip()
