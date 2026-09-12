"""Assigned short price microfacts after canonical price lines (BOT-CLEANUP-1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact, TargetOffer
from core.one_call_direct_commercial import _fact_is_eligible

_PRICE_MICROFACTS = Path("price_microfacts.yaml")
_MAX_MICROFACTS = 2
_INSTALLMENT_EXPLAINED_RE = re.compile(
    r"рассроч\w*[^.!?]{0,80}?\b12\s*месяц",
    re.IGNORECASE,
)
_DISCOUNT_15_EXPLAINED_RE = re.compile(
    r"скидк\w*[^.!?]{0,80}?\b15\s*%",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass(frozen=True, slots=True)
class ResolvedPriceMicrofact:
    fact_id: str
    display_text: str
    detail_ref: str | None
    service_id: str | None
    offer_ids: tuple[str, ...]


def _microfact_display_text(fact: TargetCommercialFact) -> str | None:
    micro = getattr(fact, "microfact_text", None)
    if micro is not None and str(micro).strip():
        return str(micro).strip()
    return None


def _select_auto_microfact_ids(
    *,
    bundle: ResponseSchemaBundle,
    offers: tuple[TargetOffer, ...],
) -> tuple[str, ...]:
    """Pick up to two short payment/promo facts from offer.fact_refs."""

    payment_ids: list[str] = []
    strict_promo_ids: list[str] = []
    natural_promo_ids: list[str] = []
    seen: set[str] = set()
    for offer in offers:
        for fact_id in offer.fact_refs:
            token = str(fact_id).strip()
            if not token or token in seen:
                continue
            fact = bundle.facts.get(token)
            if fact is None or str(fact.kind) not in {"payment", "promo"}:
                continue
            if not _microfact_display_text(fact):
                continue
            seen.add(token)
            if str(fact.kind) == "payment":
                payment_ids.append(token)
            elif str(getattr(fact, "render_mode", "") or "") == "strict":
                strict_promo_ids.append(token)
            else:
                natural_promo_ids.append(token)

    selected: list[str] = []
    if payment_ids:
        selected.append(payment_ids[0])
    for promo_id in (*strict_promo_ids, *natural_promo_ids):
        if promo_id not in selected:
            selected.append(promo_id)
        if len(selected) >= _MAX_MICROFACTS:
            break
    return tuple(selected[:_MAX_MICROFACTS])


def _clause_explains_installment(clause: str) -> bool:
    return _INSTALLMENT_EXPLAINED_RE.search(clause) is not None


def _clause_explains_same_day_discount(clause: str) -> bool:
    return _DISCOUNT_15_EXPLAINED_RE.search(clause) is not None


def microfact_explained_in_patient_text(
    patient_text: str,
    fact: TargetCommercialFact,
    *,
    fact_id: str,
) -> bool:
    """Detect when a short microfact is already covered by model prose.

    Exact microfact/text_fact substrings or clause-local anchor patterns only.
    """

    text = str(patient_text or "")
    if not text.strip():
        return False

    micro = _microfact_display_text(fact)
    if micro and micro.casefold() in text.casefold():
        return True

    text_fact = str(fact.text_fact or "").strip()
    if len(text_fact) >= 40 and text_fact in text:
        return True

    clauses: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        clauses.extend(part.strip() for part in re.split(r"[,;]\s*", sentence) if part.strip())

    if fact_id == "installment_12":
        return any(_clause_explains_installment(clause) for clause in clauses)

    if fact_id == "implant_same_day_discount":
        return any(_clause_explains_same_day_discount(clause) for clause in clauses)

    return False


def microfact_ids_explained_in_patient_text(
    patient_text: str,
    bundle: ResponseSchemaBundle,
    candidate_fact_ids: tuple[str, ...] = (),
) -> frozenset[str]:
    explained: set[str] = set()
    for fact_id in candidate_fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is None:
            continue
        if microfact_explained_in_patient_text(patient_text, fact, fact_id=fact_id):
            explained.add(fact_id)
    return frozenset(explained)


def load_price_microfact_assignments(target_root: Path) -> dict[str, tuple[str, ...]]:
    path = target_root / _PRICE_MICROFACTS
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    services = raw.get("services") or {}
    if not isinstance(services, dict):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for service_id, fact_ids in services.items():
        if not isinstance(service_id, str) or not isinstance(fact_ids, list):
            continue
        normalized = tuple(
            str(item).strip()
            for item in fact_ids
            if isinstance(item, str) and str(item).strip()
        )
        if normalized:
            out[service_id] = normalized[:_MAX_MICROFACTS]
    return out


def _offer_supports_fact(
    *,
    bundle: ResponseSchemaBundle,
    offer: TargetOffer,
    fact_id: str,
) -> bool:
    refs = tuple(str(ref).strip() for ref in (offer.fact_refs or ()))
    return fact_id in refs


def _displayed_offers(
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...] = (),
    offer_ids: tuple[str, ...] = (),
) -> tuple[TargetOffer, ...]:
    if displayed_offers:
        return displayed_offers
    if not offer_ids:
        return ()
    by_id = {offer.offer_id: offer for offer in bundle.offers}
    return tuple(by_id[offer_id] for offer_id in offer_ids if offer_id in by_id)


def _assigned_fact_ids_from_offers(
    offers: tuple[TargetOffer, ...],
    bundle: ResponseSchemaBundle,
) -> tuple[str, ...]:
    return _select_auto_microfact_ids(bundle=bundle, offers=offers)


def resolve_price_microfacts(
    *,
    bundle: ResponseSchemaBundle,
    target_root: Path,
    service_id: str | None,
    displayed_offers: tuple[TargetOffer, ...] = (),
    offer_ids: tuple[str, ...] = (),
    authoritative_service_id: str | None = None,
    today: date,
    exclude_fact_ids: frozenset[str] = frozenset(),
) -> tuple[ResolvedPriceMicrofact, ...]:
    """Return up to two applicable short facts from offer.fact_refs."""

    del target_root  # dormant: price_microfacts.yaml retained for Stage C only
    if not service_id:
        return ()
    offers = _displayed_offers(
        bundle=bundle,
        displayed_offers=displayed_offers,
        offer_ids=offer_ids,
    )
    if not offers:
        return ()

    service_for_eligibility = authoritative_service_id or service_id
    assigned = _assigned_fact_ids_from_offers(offers, bundle)
    if not assigned:
        return ()

    resolved: list[ResolvedPriceMicrofact] = []
    for fact_id in assigned:
        if fact_id in exclude_fact_ids:
            continue
        if len(resolved) >= _MAX_MICROFACTS:
            break
        if not _fact_is_eligible(
            bundle=bundle,
            fact_id=fact_id,
            authoritative_service_id=service_for_eligibility,
            today=today,
        ):
            continue
        fact = bundle.facts.get(fact_id)
        if fact is None:
            continue
        applicable_offer_ids = tuple(
            offer.offer_id
            for offer in offers
            if _offer_supports_fact(bundle=bundle, offer=offer, fact_id=fact_id)
        )
        if not applicable_offer_ids:
            continue
        display = _microfact_display_text(fact)
        if not display:
            continue
        resolved.append(
            ResolvedPriceMicrofact(
                fact_id=fact_id,
                display_text=display,
                detail_ref=fact.detail_ref,
                service_id=service_id,
                offer_ids=applicable_offer_ids,
            )
        )
    return tuple(resolved)


def format_price_microfact_suffix(
    microfacts: tuple[ResolvedPriceMicrofact, ...],
    *,
    displayed_offer_ids: tuple[str, ...],
) -> str:
    """Shared suffix only for facts applicable to every displayed offer."""

    if not microfacts or not displayed_offer_ids:
        return ""
    displayed = frozenset(displayed_offer_ids)
    lines: list[str] = []
    for item in microfacts:
        if frozenset(item.offer_ids) != displayed:
            continue
        if item.display_text.strip():
            lines.append(item.display_text.strip())
    return "\n".join(lines)


def apply_microfacts_to_price_block(
    price_block: str,
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    microfacts: tuple[ResolvedPriceMicrofact, ...],
) -> tuple[str, tuple[ResolvedPriceMicrofact, ...]]:
    """Place shared and per-offer microfacts; return only facts actually rendered."""

    if not price_block.strip() or not microfacts or not displayed_offers:
        return price_block, ()

    from core.sales_fast_authoritative_commerce import offer_row_label

    displayed_ids = frozenset(offer.offer_id for offer in displayed_offers)
    shared_facts = tuple(
        item
        for item in microfacts
        if frozenset(item.offer_ids) == displayed_ids and item.display_text.strip()
    )
    partial_facts = tuple(
        item
        for item in microfacts
        if frozenset(item.offer_ids) < displayed_ids and item.display_text.strip()
    )
    partial_by_offer: dict[str, list[ResolvedPriceMicrofact]] = {}
    for item in partial_facts:
        for offer_id in item.offer_ids:
            if offer_id in displayed_ids:
                partial_by_offer.setdefault(offer_id, []).append(item)

    rendered_ids: set[str] = set()
    lines = price_block.splitlines()
    out: list[str] = []
    row_matched = False
    for line in lines:
        out.append(line)
        if not line.startswith("- "):
            continue
        for offer in displayed_offers:
            label = offer_row_label(bundle, offer)
            if not label or f"- {label} —" not in line:
                continue
            row_matched = True
            for item in partial_by_offer.get(offer.offer_id, ()):
                out.append(f"  {item.display_text.strip()}")
                rendered_ids.add(item.fact_id)

    result = "\n".join(out)
    if shared_facts:
        shared_text = "\n".join(item.display_text.strip() for item in shared_facts)
        result = f"{result.rstrip()}\n\n{shared_text}"
        rendered_ids.update(item.fact_id for item in shared_facts)

    if not row_matched and len(displayed_offers) == 1:
        pending = tuple(
            item
            for item in microfacts
            if displayed_offers[0].offer_id in item.offer_ids
            and item.fact_id not in rendered_ids
            and item.display_text.strip()
        )
        if pending:
            suffix = "\n".join(item.display_text.strip() for item in pending)
            result = f"{result.rstrip()}\n\n{suffix}"
            rendered_ids.update(item.fact_id for item in pending)

    rendered = tuple(item for item in microfacts if item.fact_id in rendered_ids)
    return result, rendered


def inject_offer_scoped_microfacts_into_multi_block(
    price_block: str,
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    microfacts: tuple[ResolvedPriceMicrofact, ...],
) -> str:
    """Backward-compatible wrapper around apply_microfacts_to_price_block."""

    enriched, _ = apply_microfacts_to_price_block(
        price_block,
        bundle=bundle,
        displayed_offers=displayed_offers,
        microfacts=microfacts,
    )
    return enriched
