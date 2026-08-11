"""Authoritative commerce ownership for sales-fast patient text and widget offer."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetGenericPricePolicy,
    TargetOffer,
    TargetStrategyMatch,
)
from core.generic_price_policy_resolution import resolve_effective_generic_price_policy
from core.response_strategy import resolve_target_strategy
from core.sales_fast_strict_evidence import _needs_admin_quote, _offer_price_text
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

_CURRENCY_AMOUNT_RE = re.compile(
    r"(?<!\d)(?:от\s+)?\d[\d\s\u00a0]*(?:\d{3})*(?:[.,]\d+)?\s*(?:₽|руб\.?|rub)(?!\w)",
    re.IGNORECASE,
)
_FORBIDDEN_TOTAL_LINE_RE = re.compile(
    r"(?:^|\n)\s*итого\s*[:\-—]?\s*\d",
    re.IGNORECASE,
)
_ROUTE_HEADER_RE = re.compile(
    r"^route:\s*ANSWER\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_METADATA_LINE_RE = re.compile(
    r"^(?:service_id|extent|jaw|stage|scenario):\s*.+$",
    re.IGNORECASE | re.MULTILINE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|\n+")

AuthoritativeCommercePresentationMode = Literal[
    "none",
    "exact_offer",
    "overview",
    "entry_from",
    "featured_single",
]


@dataclass(frozen=True, slots=True)
class AuthoritativeCommerceResult:
    service_id: str | None
    presentation_mode: AuthoritativeCommercePresentationMode
    entry_price_amount: int | None
    entry_price_text: str | None
    ordered_offers: tuple[TargetOffer, ...]
    featured_offer_id: str | None
    selected_exact_offer: TargetOffer | None
    needs_consultation_quote: bool
    authoritative_amounts: frozenset[int]
    patient_price_block: str | None
    widget_offer_payload: dict[str, object] | None


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


def _fixed_amount(offer: TargetOffer) -> int | None:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return int(price.amount)
    return None


def _offers_by_id(offers: tuple[TargetOffer, ...]) -> dict[str, TargetOffer]:
    return {offer.offer_id: offer for offer in offers}


def _brand_label(bundle: ResponseSchemaBundle, brand_id: str | None) -> str:
    if not brand_id:
        return ""
    brand = bundle.brands.brands.get(brand_id)
    return brand.canonical_name if brand is not None else brand_id


def _offer_amount_only(offer: TargetOffer) -> str:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return _rubles(int(price.amount))
    if price.mode == "from" and price.min_amount is not None:
        return "от " + _rubles(int(price.min_amount))
    return _offer_price_text(offer)


def _package_scope_hint(offer: TargetOffer) -> str:
    label = str(offer.package.label or "").strip()
    if not label:
        return ""
    return label.split(";", 1)[0].strip()


def _ordered_display_offers(
    ranked_offers: tuple[TargetOffer, ...],
    *,
    featured_offer_id: str | None,
) -> tuple[TargetOffer, ...]:
    if not featured_offer_id:
        return ranked_offers
    featured = tuple(o for o in ranked_offers if o.offer_id == featured_offer_id)
    rest = tuple(o for o in ranked_offers if o.offer_id != featured_offer_id)
    return featured + rest


def _entry_amount_from_offers(offers: tuple[TargetOffer, ...]) -> int | None:
    amounts = [_fixed_amount(offer) for offer in offers]
    fixed = [amount for amount in amounts if amount is not None]
    return min(fixed) if fixed else None


def _authoritative_amounts_from_offers(offers: tuple[TargetOffer, ...]) -> frozenset[int]:
    amounts = {
        amount
        for offer in offers
        for amount in [_fixed_amount(offer)]
        if amount is not None
    }
    return frozenset(amounts)


def _explicit_offer_id_from_materials(
    offers: tuple[TargetOffer, ...],
    *,
    selected_brand_id: str | None,
) -> str | None:
    if not selected_brand_id:
        return None
    brand = selected_brand_id.strip().lower()
    for offer in offers:
        if str(offer.brand_id or "").strip().lower() == brand:
            return offer.offer_id
    return None


def _ranked_offers_for_context(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch,
    explicit_offer_id: str | None,
    max_options: int,
) -> tuple[TargetOffer, ...]:
    if not offers:
        return ()
    offer_ids = tuple(offer.offer_id for offer in offers)
    strategy_resolution = resolve_target_strategy(
        bundle.strategy,
        strategy_context,
        offer_ids=offer_ids,
        explicit_offer_id=explicit_offer_id,
    )
    by_id = _offers_by_id(offers)
    ranked = tuple(
        by_id[offer_id] for offer_id in strategy_resolution.offer_ids if offer_id in by_id
    )
    limit = min(max_options, len(ranked))
    return ranked[:limit]


def _build_entry_line(
    *,
    bundle: ResponseSchemaBundle,
    service_id: str,
    offers: tuple[TargetOffer, ...],
    entry_amount: int,
) -> str:
    service = bundle.services.get(service_id)
    service_name = service.name if service is not None else service_id
    scope_hint = _package_scope_hint(offers[0]) if offers else ""
    subject = f"{service_name} {scope_hint}".strip()
    return f"{subject} — от {_rubles(entry_amount)}."


def _build_overview_lines(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
    featured_offer_id: str | None,
) -> str:
    lines: list[str] = []
    for offer in offers:
        amount_text = _offer_amount_only(offer)
        if not amount_text:
            continue
        label = _brand_label(bundle, offer.brand_id)
        suffix = " (рекомендуемый)" if featured_offer_id == offer.offer_id else ""
        lines.append(f"- {label} — {amount_text}{suffix}")
    return "\n".join(lines)


def _build_exact_offer_block(
    offer: TargetOffer,
    *,
    bundle: ResponseSchemaBundle,
) -> str:
    service = bundle.services.get(offer.service_id)
    service_name = service.name if service is not None else offer.service_id
    price_text = _offer_price_text(offer)
    return f"Стоимость {service_name} — {price_text}."


def _build_widget_offer_payload(
    *,
    presentation_mode: AuthoritativeCommercePresentationMode,
    ordered_offers: tuple[TargetOffer, ...],
    featured_offer_id: str | None,
    selected_exact_offer: TargetOffer | None,
    entry_price_amount: int | None,
    bundle: ResponseSchemaBundle,
) -> dict[str, object] | None:
    if presentation_mode == "none":
        return None
    if presentation_mode == "exact_offer" and selected_exact_offer is not None:
        amount = _fixed_amount(selected_exact_offer)
        return {
            "mode": "exact_offer",
            "offer_id": selected_exact_offer.offer_id,
            "amount": amount,
            "brand": _brand_label(bundle, selected_exact_offer.brand_id),
        }
    offer_rows: list[dict[str, object]] = []
    for offer in ordered_offers:
        offer_rows.append(
            {
                "offer_id": offer.offer_id,
                "amount": _fixed_amount(offer),
                "brand": _brand_label(bundle, offer.brand_id),
                "featured": offer.offer_id == featured_offer_id,
            }
        )
    return {
        "mode": presentation_mode,
        "entry_amount": entry_price_amount,
        "featured_offer_id": featured_offer_id,
        "offers": offer_rows,
    }


def resolve_authoritative_commerce(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch,
    service_id: str | None,
    explicit_offer_id: str | None = None,
    max_options: int,
    needs_consultation_quote: bool,
    consultation_text: str | None,
) -> AuthoritativeCommerceResult:
    if needs_consultation_quote:
        return AuthoritativeCommerceResult(
            service_id=service_id,
            presentation_mode="none",
            entry_price_amount=None,
            entry_price_text=None,
            ordered_offers=(),
            featured_offer_id=None,
            selected_exact_offer=None,
            needs_consultation_quote=True,
            authoritative_amounts=frozenset(),
            patient_price_block=consultation_text,
            widget_offer_payload=None,
        )

    if explicit_offer_id is not None:
        by_id = _offers_by_id(offers)
        if explicit_offer_id in by_id:
            exact = by_id[explicit_offer_id]
            amounts = _authoritative_amounts_from_offers((exact,))
            block = _build_exact_offer_block(exact, bundle=bundle)
            widget = _build_widget_offer_payload(
                presentation_mode="exact_offer",
                ordered_offers=(exact,),
                featured_offer_id=None,
                selected_exact_offer=exact,
                entry_price_amount=None,
                bundle=bundle,
            )
            return AuthoritativeCommerceResult(
                service_id=exact.service_id,
                presentation_mode="exact_offer",
                entry_price_amount=_fixed_amount(exact),
                entry_price_text=None,
                ordered_offers=(exact,),
                featured_offer_id=None,
                selected_exact_offer=exact,
                needs_consultation_quote=False,
                authoritative_amounts=amounts,
                patient_price_block=block,
                widget_offer_payload=widget,
            )

    ranked_offers = _ranked_offers_for_context(
        offers,
        bundle=bundle,
        strategy_context=strategy_context,
        explicit_offer_id=None,
        max_options=max_options,
    )
    if not ranked_offers:
        return AuthoritativeCommerceResult(
            service_id=service_id,
            presentation_mode="none",
            entry_price_amount=None,
            entry_price_text=None,
            ordered_offers=(),
            featured_offer_id=None,
            selected_exact_offer=None,
            needs_consultation_quote=False,
            authoritative_amounts=frozenset(),
            patient_price_block=None,
            widget_offer_payload=None,
        )

    if len(ranked_offers) == 1:
        exact = ranked_offers[0]
        amounts = _authoritative_amounts_from_offers((exact,))
        block = _build_exact_offer_block(exact, bundle=bundle)
        widget = _build_widget_offer_payload(
            presentation_mode="exact_offer",
            ordered_offers=(exact,),
            featured_offer_id=None,
            selected_exact_offer=exact,
            entry_price_amount=None,
            bundle=bundle,
        )
        return AuthoritativeCommerceResult(
            service_id=exact.service_id,
            presentation_mode="exact_offer",
            entry_price_amount=_fixed_amount(exact),
            entry_price_text=None,
            ordered_offers=(exact,),
            featured_offer_id=None,
            selected_exact_offer=exact,
            needs_consultation_quote=False,
            authoritative_amounts=amounts,
            patient_price_block=block,
            widget_offer_payload=widget,
        )

    policy = resolve_effective_generic_price_policy(bundle.strategy, strategy_context)
    featured_offer_id = policy.featured_offer_id if policy is not None else None
    policy_max = policy.max_price_options if policy is not None else None
    if policy_max is not None:
        ranked_offers = ranked_offers[:policy_max]

    if policy is None or policy.mode == "overview":
        mode: AuthoritativeCommercePresentationMode = "overview"
    elif policy.mode == "entry_from":
        mode = "entry_from"
    elif policy.mode == "featured_single":
        mode = "featured_single"
        if featured_offer_id is None:
            mode = "overview"
    else:
        mode = "overview"

    display_offers = _ordered_display_offers(
        ranked_offers,
        featured_offer_id=featured_offer_id,
    )
    entry_amount = _entry_amount_from_offers(ranked_offers)

    if mode == "featured_single" and featured_offer_id is not None:
        by_id = _offers_by_id(ranked_offers)
        featured = by_id.get(featured_offer_id)
        if featured is not None:
            amounts = _authoritative_amounts_from_offers((featured,))
            block = _build_exact_offer_block(featured, bundle=bundle)
            widget = _build_widget_offer_payload(
                presentation_mode="featured_single",
                ordered_offers=(featured,),
                featured_offer_id=featured_offer_id,
                selected_exact_offer=featured,
                entry_price_amount=_fixed_amount(featured),
                bundle=bundle,
            )
            return AuthoritativeCommerceResult(
                service_id=featured.service_id,
                presentation_mode="featured_single",
                entry_price_amount=_fixed_amount(featured),
                entry_price_text=None,
                ordered_offers=(featured,),
                featured_offer_id=featured_offer_id,
                selected_exact_offer=featured,
                needs_consultation_quote=False,
                authoritative_amounts=amounts,
                patient_price_block=block,
                widget_offer_payload=widget,
            )
        mode = "overview"

    amounts = _authoritative_amounts_from_offers(ranked_offers)
    blocks: list[str] = []
    entry_text = None
    if entry_amount is not None and service_id is not None:
        entry_text = _build_entry_line(
            bundle=bundle,
            service_id=service_id,
            offers=ranked_offers,
            entry_amount=entry_amount,
        )
        if mode in {"overview", "entry_from"}:
            blocks.append(entry_text)
    if mode == "overview":
        overview = _build_overview_lines(
            display_offers,
            bundle=bundle,
            featured_offer_id=featured_offer_id,
        )
        if overview:
            blocks.append(overview)

    patient_block = "\n\n".join(blocks) if blocks else None
    widget = _build_widget_offer_payload(
        presentation_mode=mode,
        ordered_offers=display_offers,
        featured_offer_id=featured_offer_id,
        selected_exact_offer=None,
        entry_price_amount=entry_amount,
        bundle=bundle,
    )
    return AuthoritativeCommerceResult(
        service_id=service_id,
        presentation_mode=mode,
        entry_price_amount=entry_amount,
        entry_price_text=entry_text,
        ordered_offers=display_offers,
        featured_offer_id=featured_offer_id,
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=amounts,
        patient_price_block=patient_block,
        widget_offer_payload=widget,
    )


def build_authoritative_commerce_result(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    resolution: ExactSalesResolution,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch,
) -> AuthoritativeCommerceResult:
    materials = bound_package.package.materials
    offers = tuple(materials.offers)
    needs_quote = _needs_admin_quote(resolution, offers=offers)
    consultation_text = None
    if materials.consultation_close is not None:
        consultation_text = str(materials.consultation_close.value or "").strip() or None

    explicit_offer_id = _explicit_offer_id_from_materials(
        offers,
        selected_brand_id=materials.selected_brand_id,
    )
    service_id = materials.service_id or resolution.service_id
    return resolve_authoritative_commerce(
        offers,
        bundle=bundle,
        strategy_context=strategy_context,
        service_id=service_id,
        explicit_offer_id=explicit_offer_id,
        max_options=materials.max_options,
        needs_consultation_quote=needs_quote,
        consultation_text=consultation_text,
    )


# Backward-compatible aliases for transitional imports.
AuthoritativeCommerceSnapshot = AuthoritativeCommerceResult
build_authoritative_commerce_snapshot = build_authoritative_commerce_result


def select_primary_authoritative_offer(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch | None = None,
    explicit_offer_id: str | None = None,
) -> TargetOffer | None:
    if strategy_context is None:
        return offers[0] if len(offers) == 1 else None
    result = resolve_authoritative_commerce(
        offers,
        bundle=bundle,
        strategy_context=strategy_context,
        service_id=offers[0].service_id if offers else None,
        explicit_offer_id=explicit_offer_id,
        max_options=len(offers),
        needs_consultation_quote=False,
        consultation_text=None,
    )
    return result.selected_exact_offer


def _strip_route_metadata(text: str) -> str:
    cleaned = _ROUTE_HEADER_RE.sub("", text)
    cleaned = _METADATA_LINE_RE.sub("", cleaned)
    return cleaned.strip()


def _normalize_digits(value: str) -> str:
    return re.sub(r"[\s\u00a0]", "", value)


def _amounts_in_text(text: str) -> set[int]:
    amounts: set[int] = set()
    for match in _CURRENCY_AMOUNT_RE.finditer(text):
        digits = re.sub(r"[^\d]", "", match.group(0))
        if digits:
            amounts.add(int(digits))
    return amounts


def _sentence_has_unauthorized_amount(sentence: str, allowed_amounts: frozenset[int]) -> bool:
    amounts = _amounts_in_text(sentence)
    if not amounts:
        return False
    if not allowed_amounts:
        return True
    return not amounts.issubset(allowed_amounts)


def _remove_unauthorized_currency_sentences(
    text: str,
    *,
    allowed_amounts: frozenset[int],
) -> str:
    if not text.strip():
        return text
    paragraphs = re.split(r"\n\s*\n", text)
    kept_paragraphs: list[str] = []
    for paragraph in paragraphs:
        parts = _SENTENCE_SPLIT_RE.split(paragraph)
        kept_parts: list[str] = []
        for part in parts:
            sentence = part.strip()
            if not sentence:
                continue
            if _FORBIDDEN_TOTAL_LINE_RE.search(sentence):
                continue
            if _sentence_has_unauthorized_amount(sentence, allowed_amounts):
                continue
            kept_parts.append(sentence)
        if kept_parts:
            kept_paragraphs.append(" ".join(kept_parts))
    return "\n\n".join(kept_paragraphs).strip()


def apply_authoritative_commerce_to_patient_text(
    patient_text: str,
    commerce: AuthoritativeCommerceResult,
) -> str:
    text = _strip_route_metadata(patient_text)

    if commerce.needs_consultation_quote:
        text = _remove_unauthorized_currency_sentences(text, allowed_amounts=frozenset())
        if commerce.patient_price_block and commerce.patient_price_block not in text:
            separator = "\n\n" if text.strip() else ""
            text = f"{text.rstrip()}{separator}{commerce.patient_price_block}"
        return text.strip()

    if commerce.authoritative_amounts:
        text = _remove_unauthorized_currency_sentences(
            text,
            allowed_amounts=commerce.authoritative_amounts,
        )
    if commerce.patient_price_block:
        normalized_block = _normalize_digits(commerce.patient_price_block)
        if normalized_block not in _normalize_digits(text):
            separator = "\n\n" if text.strip() else ""
            text = f"{text.rstrip()}{separator}{commerce.patient_price_block}"
    return text.strip()
