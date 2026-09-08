"""Authoritative commerce ownership for sales-fast patient text and widget offer."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.one_call_envelope import OneCallCommercialIntent
from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetGenericPricePolicy,
    TargetOffer,
    TargetPaymentStage,
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
_PERCENT_LITERAL_RE = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?\s*(?:%|процент(?:а|ов)?)",
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
_COMMERCIAL_PERCENT_CLAIM_MARKER_RE = re.compile(
    r"\b(?:скидк\w*|акци\w*|промо\w*)\b",
    re.IGNORECASE,
)

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


@dataclass(frozen=True, slots=True)
class ServiceLevelOverviewLine:
    line: str
    entry_offer: TargetOffer
    condition_text: str | None
    authoritative_amounts: frozenset[int]


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


def _fixed_amount(offer: TargetOffer) -> int | None:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return int(price.amount)
    return None


def _from_min_amount(offer: TargetOffer) -> int | None:
    price = offer.price
    if price.mode == "from" and price.min_amount is not None:
        return int(price.min_amount)
    return None


def _offer_widget_amount(offer: TargetOffer) -> int | None:
    return _fixed_amount(offer) if offer.price.mode == "fixed" else _from_min_amount(offer)


def _offers_by_id(offers: tuple[TargetOffer, ...]) -> dict[str, TargetOffer]:
    return {offer.offer_id: offer for offer in offers}


def _brand_label(bundle: ResponseSchemaBundle, brand_id: str | None) -> str:
    if not brand_id:
        return ""
    brand = bundle.brands.brands.get(brand_id)
    return brand.canonical_name if brand is not None else brand_id


def offer_row_label(bundle: ResponseSchemaBundle, offer: TargetOffer) -> str | None:
    """Patient-facing label for a price offer row (brand or service option)."""

    if offer.brand_id:
        brand = bundle.brands.brands.get(offer.brand_id)
        if brand is not None and str(brand.canonical_name).strip():
            return str(brand.canonical_name).strip()
    if offer.option_id:
        service = bundle.services.get(offer.service_id)
        if service is not None:
            for option in service.options:
                if option.option_id == offer.option_id:
                    label = str(option.name).strip()
                    if label:
                        return label
    return None


def _offer_amount_only(offer: TargetOffer) -> str:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return _rubles(int(price.amount))
    if price.mode == "from" and price.min_amount is not None:
        return "от " + _rubles(int(price.min_amount))
    return _offer_price_text(offer)


def _billing_unit_key(offer: TargetOffer) -> str:
    return str(offer.price.billing_unit or "").strip()


def _published_price_offers(offers: tuple[TargetOffer, ...]) -> tuple[TargetOffer, ...]:
    return tuple(
        offer
        for offer in offers
        if offer.price.mode in {"fixed", "from", "range"}
    )


def _no_public_price_offers(offers: tuple[TargetOffer, ...]) -> tuple[TargetOffer, ...]:
    return tuple(offer for offer in offers if offer.price.mode == "no_public_price")


def _comparable_amount(offer: TargetOffer) -> int | None:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return int(price.amount)
    if price.mode in {"from", "range"} and price.min_amount is not None:
        return int(price.min_amount)
    return None


def _authoritative_amounts_for_published_offers(
    offers: tuple[TargetOffer, ...],
) -> frozenset[int]:
    amounts: set[int] = set()
    for offer in _published_price_offers(offers):
        comparable = _comparable_amount(offer)
        if comparable is not None:
            amounts.add(comparable)
        price = offer.price
        if price.mode == "range" and price.max_amount is not None:
            amounts.add(int(price.max_amount))
    return frozenset(amounts)


def _condition_texts_for_offer(offer: TargetOffer) -> tuple[str, ...]:
    metadata = offer.required_conditions_metadata
    if metadata is None:
        return ()
    return tuple(
        str(entry.display_text).strip()
        for entry in metadata.conditions
        if str(entry.display_text).strip()
    )


def _service_condition_text(offers: tuple[TargetOffer, ...]) -> str | None:
    texts: set[str] = set()
    for offer in offers:
        texts.update(_condition_texts_for_offer(offer))
    if not texts:
        return None
    if len(texts) == 1:
        return next(iter(texts))
    return "; ".join(sorted(texts))


def format_service_level_amount_text(offers: tuple[TargetOffer, ...]) -> str | None:
    """Service-level price orient for broad/scoped family overview rows."""

    published = _published_price_offers(offers)
    if not published:
        no_public = _no_public_price_offers(offers)
        if len(no_public) == 1:
            return str(no_public[0].price.approved_text).strip()
        return None

    if len(published) == 1:
        offer = published[0]
        price = offer.price
        if price.mode == "fixed" and price.amount is not None:
            return _rubles(int(price.amount))
        if price.mode == "from" and price.min_amount is not None:
            return "от " + _rubles(int(price.min_amount))
        if (
            price.mode == "range"
            and price.min_amount is not None
            and price.max_amount is not None
        ):
            return (
                f"{_rubles(int(price.min_amount))}–{_rubles(int(price.max_amount))}"
            )
        return None

    amounts = [
        amount
        for amount in (_comparable_amount(offer) for offer in published)
        if amount is not None
    ]
    if not amounts:
        return None

    modes = {offer.price.mode for offer in published}
    units = {_billing_unit_key(offer) for offer in published if _billing_unit_key(offer)}
    if modes == {"fixed"} and len(set(amounts)) == 1 and len(units) <= 1:
        return _rubles(amounts[0])
    return "от " + _rubles(min(amounts))


def build_service_level_overview_line(
    *,
    service_name: str,
    offers: tuple[TargetOffer, ...],
) -> ServiceLevelOverviewLine | None:
    from core.target_family_price_resolution import _BILLING_UNIT_PATIENT_LABELS

    published = _published_price_offers(offers)
    no_public = _no_public_price_offers(offers)
    if not published and not no_public:
        return None

    if not published and no_public:
        entry_offer = no_public[0]
        approved = str(entry_offer.price.approved_text).strip()
        if not approved:
            return None
        return ServiceLevelOverviewLine(
            line=f"{service_name} — {approved}",
            entry_offer=entry_offer,
            condition_text=_service_condition_text(offers),
            authoritative_amounts=frozenset(),
        )

    amount_text = format_service_level_amount_text(offers)
    if not amount_text:
        return None
    entry_offer = min(
        published,
        key=lambda offer: _comparable_amount(offer) or 10**12,
    )
    unit_label = _BILLING_UNIT_PATIENT_LABELS.get(_billing_unit_key(entry_offer), "")
    if unit_label:
        line = f"{service_name} — {amount_text} {unit_label}"
    else:
        line = f"{service_name} — {amount_text}"
    return ServiceLevelOverviewLine(
        line=line,
        entry_offer=entry_offer,
        condition_text=_service_condition_text(offers),
        authoritative_amounts=_authoritative_amounts_for_published_offers(offers),
    )


def assemble_service_level_overview_block(
    service_lines: tuple[ServiceLevelOverviewLine, ...],
) -> str:
    if not service_lines:
        return ""

    condition_texts = tuple(
        row.condition_text.strip()
        for row in service_lines
        if row.condition_text and str(row.condition_text).strip()
    )
    shared_condition: str | None = None
    if len(service_lines) > 1 and condition_texts:
        if (
            len(condition_texts) == len(service_lines)
            and len(set(condition_texts)) == 1
        ):
            shared_condition = condition_texts[0]

    rendered_lines: list[str] = []
    for row in service_lines:
        line = row.line
        if (
            row.condition_text
            and shared_condition is None
            and len(service_lines) > 1
        ):
            line = f"{line}; {row.condition_text}"
        rendered_lines.append(line)

    block = "\n".join(rendered_lines)
    if shared_condition:
        block = f"{block}\n\n{shared_condition}"
    elif len(service_lines) == 1:
        condition = service_lines[0].condition_text
        if condition and str(condition).strip():
            block = f"{block}\n\n{str(condition).strip()}"
    return block


def _build_service_overview_commerce_block(
    service_lines: tuple[ServiceLevelOverviewLine, ...],
) -> tuple[str, tuple[TargetOffer, ...], frozenset[int]] | None:
    if not service_lines:
        return None
    patient_block = assemble_service_level_overview_block(service_lines)
    if not patient_block.strip():
        return None
    entry_offers = tuple(row.entry_offer for row in service_lines)
    amounts: set[int] = set()
    for row in service_lines:
        amounts.update(row.authoritative_amounts)
    return patient_block, entry_offers, frozenset(amounts)


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
    amounts = [_offer_widget_amount(offer) for offer in offers]
    priced = [amount for amount in amounts if amount is not None]
    return min(priced) if priced else None


def _authoritative_amounts_from_offers(offers: tuple[TargetOffer, ...]) -> frozenset[int]:
    amounts = {
        amount
        for offer in offers
        for amount in [_offer_widget_amount(offer)]
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
        label = offer_row_label(bundle, offer)
        if not label:
            continue
        suffix = " (рекомендуемый)" if featured_offer_id == offer.offer_id else ""
        lines.append(f"- {label} — {amount_text}{suffix}")
    return "\n".join(lines)


def _format_exact_offer_price_line(
    *,
    service_name: str,
    price_text: str,
    brand: str | None = None,
) -> str:
    if brand:
        return f"{service_name} ({brand}) — {price_text}."
    return f"{service_name} — {price_text}."


def _build_exact_offer_block(
    offer: TargetOffer,
    *,
    bundle: ResponseSchemaBundle,
) -> str:
    service = bundle.services.get(offer.service_id)
    service_name = service.name if service is not None else offer.service_id
    price_text = _offer_price_text(offer)
    brand = _brand_label(bundle, offer.brand_id)
    return _format_exact_offer_price_line(
        service_name=service_name,
        price_text=price_text,
        brand=brand,
    )


def build_offer_payment_stages_block(offer: TargetOffer) -> str | None:
    """Code-owned payment-stage amounts for a selected offer."""

    stages = offer.payment_stages
    if not stages:
        return None
    entries: list[str] = []
    for stage in stages:
        entry = _format_payment_stage_entry(stage)
        if entry:
            entries.append(entry)
    if not entries:
        return None
    return "\n\n".join(entries)


def _format_payment_stage_entry(stage: TargetPaymentStage) -> str | None:
    label = str(stage.label or "").strip()
    amount = stage.amount
    if amount is None:
        return None
    amount_text = _rubles(int(amount))
    line = f"{label} — {amount_text}." if label else f"{amount_text}."
    timing = str(stage.timing_text or "").strip()
    if timing:
        line = f"{line}\n{timing}"
    return line


def _payment_stages_section_intro(
    *,
    bundle: ResponseSchemaBundle,
    offer: TargetOffer,
    stage_count: int,
    include_brand_in_intro: bool,
) -> str:
    if stage_count == 2:
        base = "Оплата делится на два этапа:"
    else:
        base = "Оплата распределяется по этапам:"
    if not include_brand_in_intro or not offer.brand_id:
        return base
    brand = _brand_label(bundle, offer.brand_id)
    if not brand:
        return base
    if stage_count == 2:
        return f"Для варианта {brand} оплата делится на два этапа:"
    return f"Для варианта {brand} оплата распределяется по этапам:"


def resolve_payment_stages_target_offers(
    *,
    displayed_offers: tuple[TargetOffer, ...],
    selected_exact_offer: TargetOffer | None = None,
    selected_brand_id: str | None = None,
) -> tuple[TargetOffer, ...]:
    """Resolve which offers should contribute code-owned payment stages."""

    if selected_exact_offer is not None:
        return (selected_exact_offer,)
    if selected_brand_id:
        brand = selected_brand_id.strip().lower()
        matched = tuple(
            offer
            for offer in displayed_offers
            if str(offer.brand_id or "").strip().lower() == brand
        )
        if len(matched) == 1:
            return matched
        return ()
    if len(displayed_offers) == 1:
        return displayed_offers
    if len(displayed_offers) > 1:
        return displayed_offers
    return ()


PAYMENT_STAGES_UNAVAILABLE_TEXT = (
    "Для этого варианта в прайсе клиники нет разбивки оплаты по этапам. "
    "Администратор клиники уточнит детали при записи."
)


def _active_offers_by_id(bundle: ResponseSchemaBundle) -> dict[str, TargetOffer]:
    return {
        str(offer.offer_id): offer
        for offer in bundle.offers
        if offer.active
    }


def _session_payment_stage_offers(
    *,
    bundle: ResponseSchemaBundle,
    service_id: str,
    session_state: object,
) -> tuple[TargetOffer, ...]:
    from core.target_runtime_session import TargetRuntimeSessionState

    if not isinstance(session_state, TargetRuntimeSessionState):
        return ()
    offers_by_id = _active_offers_by_id(bundle)
    displayed_ids = tuple(
        str(offer_id).strip()
        for offer_id in session_state.last_displayed_offer_ids
        if str(offer_id).strip()
    )
    session_offers = tuple(
        offers_by_id[offer_id]
        for offer_id in displayed_ids
        if offer_id in offers_by_id
        and offers_by_id[offer_id].service_id == service_id
        and offers_by_id[offer_id].payment_stages
    )
    if not session_offers:
        return ()

    selected_id = str(session_state.last_selected_offer_id or "").strip()
    if selected_id and selected_id in offers_by_id:
        selected = offers_by_id[selected_id]
        if selected.service_id == service_id and selected.payment_stages:
            return (selected,)
    return session_offers


def _catalog_payment_stage_offers(
    *,
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> tuple[TargetOffer, ...]:
    return tuple(
        offer
        for offer in bundle.offers
        if offer.active
        and offer.service_id == service_id
        and offer.payment_stages
    )


def resolve_payment_stages_offers_for_turn(
    *,
    bundle: ResponseSchemaBundle,
    nav_ref: str | None,
    session_state: object,
    displayed_offers: tuple[TargetOffer, ...],
    selected_exact_offer: TargetOffer | None = None,
    selected_brand_id: str | None = None,
    followups: tuple = (),
) -> tuple[TargetOffer, ...]:
    """Resolve offers for payment-stages turns, including session/catalog recovery."""

    from core.one_call_payment_stages_policy import governed_payment_stages_ui_ref
    from core.price_ref_routing import parse_price_widget_ref

    stages_ref = governed_payment_stages_ui_ref(nav_ref)
    ref_eff = str(nav_ref or "").strip()
    if stages_ref:
        if followups and not any(str(item.ref or "").strip() == ref_eff for item in followups):
            return ()
        parsed = parse_price_widget_ref(ref_eff)
        if parsed is None:
            return ()
        service_id = str(parsed.get("service_id") or "").strip()
        if not service_id:
            return ()

        session_offers = _session_payment_stage_offers(
            bundle=bundle,
            service_id=service_id,
            session_state=session_state,
        )
        if session_offers:
            resolved = resolve_payment_stages_target_offers(
                displayed_offers=session_offers,
                selected_exact_offer=selected_exact_offer,
                selected_brand_id=selected_brand_id,
            )
            if resolved:
                return resolved

        catalog_offers = _catalog_payment_stage_offers(
            bundle=bundle,
            service_id=service_id,
        )
        if not catalog_offers:
            return ()
        if len(catalog_offers) == 1:
            return catalog_offers
        resolved = resolve_payment_stages_target_offers(
            displayed_offers=catalog_offers,
            selected_exact_offer=selected_exact_offer,
            selected_brand_id=selected_brand_id,
        )
        return resolved or catalog_offers

    if displayed_offers:
        return resolve_payment_stages_target_offers(
            displayed_offers=displayed_offers,
            selected_exact_offer=selected_exact_offer,
            selected_brand_id=selected_brand_id,
        )

    return ()


def build_payment_stages_display_block(
    offers: tuple[TargetOffer, ...],
    *,
    bundle: ResponseSchemaBundle,
) -> str | None:
    """Build labeled payment-stage blocks for one or more offers."""

    if not offers:
        return None
    sections: list[str] = []
    for offer in offers:
        block = build_offer_payment_stages_block(offer)
        if not block:
            continue
        stage_count = len(offer.payment_stages or ())
        intro = _payment_stages_section_intro(
            bundle=bundle,
            offer=offer,
            stage_count=stage_count,
            include_brand_in_intro=len(offers) == 1,
        )
        section = f"{intro}\n\n{block}"
        if len(offers) > 1:
            label = _brand_label(bundle, offer.brand_id) or offer.offer_id
            section = f"{label}:\n{section}"
        sections.append(section)
    if not sections:
        return None
    return "\n\n".join(sections)


def append_code_owned_commerce_blocks(
    patient_text: str,
    commerce: AuthoritativeCommerceResult,
) -> str:
    """Append code-owned price blocks without stripping model commercial prose."""

    text = _strip_route_metadata(patient_text).strip()
    if commerce.patient_price_block:
        block = commerce.patient_price_block.strip()
        if block and block not in text:
            separator = "\n\n" if text else ""
            text = f"{text}{separator}{block}" if text else block
    return text.strip()


def build_canonical_exact_offer_price_line(
    *,
    offer: TargetOffer,
    bundle: ResponseSchemaBundle,
) -> str:
    """Canonical fixed-price line for one selected offer — single formatter owner."""

    return _build_exact_offer_block(offer, bundle=bundle)


def build_precomposer_single_offer_commerce(
    offer: TargetOffer,
    *,
    bundle: ResponseSchemaBundle,
) -> AuthoritativeCommerceResult:
    """Widget metadata for one pre-selected fixed offer without legacy price block."""

    amounts = _authoritative_amounts_from_offers((offer,))
    widget = _build_widget_offer_payload(
        presentation_mode="exact_offer",
        ordered_offers=(offer,),
        featured_offer_id=None,
        selected_exact_offer=offer,
        entry_price_amount=None,
        bundle=bundle,
    )
    return AuthoritativeCommerceResult(
        service_id=offer.service_id,
        presentation_mode="exact_offer",
        entry_price_amount=_offer_widget_amount(offer),
        entry_price_text=None,
        ordered_offers=(offer,),
        featured_offer_id=None,
        selected_exact_offer=offer,
        needs_consultation_quote=False,
        authoritative_amounts=amounts,
        patient_price_block=None,
        widget_offer_payload=widget,
    )


def build_precomposer_multi_offer_commerce(
    offers: tuple[TargetOffer, ...],
    *,
    service_id: str,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch,
) -> AuthoritativeCommerceResult:
    """Marketing-only commerce metadata for a canonical multi-offer price turn."""

    policy = resolve_effective_generic_price_policy(bundle.strategy, strategy_context)
    featured_offer_id = policy.featured_offer_id if policy is not None else None
    display_offers = _ordered_display_offers(
        offers,
        featured_offer_id=featured_offer_id,
    )
    amounts = _authoritative_amounts_from_offers(display_offers)
    entry_amount = _entry_amount_from_offers(display_offers)
    widget = _build_widget_offer_payload(
        presentation_mode="overview",
        ordered_offers=display_offers,
        featured_offer_id=featured_offer_id,
        selected_exact_offer=None,
        entry_price_amount=entry_amount,
        bundle=bundle,
    )
    return AuthoritativeCommerceResult(
        service_id=service_id,
        presentation_mode="overview",
        entry_price_amount=entry_amount,
        entry_price_text=None,
        ordered_offers=display_offers,
        featured_offer_id=featured_offer_id,
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=amounts,
        patient_price_block=None,
        widget_offer_payload=widget,
    )


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
        amount = _offer_widget_amount(selected_exact_offer)
        payload: dict[str, object] = {
            "mode": "exact_offer",
            "offer_id": selected_exact_offer.offer_id,
            "amount": amount,
            "brand": _brand_label(bundle, selected_exact_offer.brand_id),
            "price_mode": selected_exact_offer.price.mode,
        }
        if selected_exact_offer.price.mode == "from":
            payload["min_amount"] = amount
        return payload
    offer_rows: list[dict[str, object]] = []
    for offer in ordered_offers:
        amount = _offer_widget_amount(offer)
        row: dict[str, object] = {
            "offer_id": offer.offer_id,
            "amount": amount,
            "brand": _brand_label(bundle, offer.brand_id),
            "featured": offer.offer_id == featured_offer_id,
            "price_mode": offer.price.mode,
        }
        if offer.price.mode == "from":
            row["min_amount"] = amount
        offer_rows.append(row)
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


def gate_commerce_result_by_intent(
    commerce: AuthoritativeCommerceResult,
    *,
    commercial_intent: OneCallCommercialIntent,
) -> AuthoritativeCommerceResult:
    """Open only the commercial surface matching envelope commercial_intent."""

    if commercial_intent == "none":
        return AuthoritativeCommerceResult(
            service_id=commerce.service_id,
            presentation_mode="none",
            entry_price_amount=None,
            entry_price_text=None,
            ordered_offers=(),
            featured_offer_id=None,
            selected_exact_offer=None,
            needs_consultation_quote=commerce.needs_consultation_quote,
            authoritative_amounts=frozenset(),
            patient_price_block=commerce.patient_price_block if commerce.needs_consultation_quote else None,
            widget_offer_payload=None,
        )
    if commercial_intent == "price":
        return commerce
    if commercial_intent in {"payment", "payment_stages", "included"}:
        return AuthoritativeCommerceResult(
            service_id=commerce.service_id,
            presentation_mode="none",
            entry_price_amount=None,
            entry_price_text=None,
            ordered_offers=(),
            featured_offer_id=None,
            selected_exact_offer=None,
            needs_consultation_quote=commerce.needs_consultation_quote,
            authoritative_amounts=frozenset(),
            patient_price_block=None,
            widget_offer_payload=None,
        )
    if commercial_intent == "promotion":
        return AuthoritativeCommerceResult(
            service_id=commerce.service_id,
            presentation_mode="none",
            entry_price_amount=None,
            entry_price_text=None,
            ordered_offers=(),
            featured_offer_id=None,
            selected_exact_offer=None,
            needs_consultation_quote=commerce.needs_consultation_quote,
            authoritative_amounts=frozenset(),
            patient_price_block=None,
            widget_offer_payload=None,
        )
    return AuthoritativeCommerceResult(
        service_id=commerce.service_id,
        presentation_mode="none",
        entry_price_amount=None,
        entry_price_text=None,
        ordered_offers=(),
        featured_offer_id=None,
        selected_exact_offer=None,
        needs_consultation_quote=commerce.needs_consultation_quote,
        authoritative_amounts=frozenset(),
        patient_price_block=None,
        widget_offer_payload=None,
    )


def build_broad_family_price_commerce_result(
    *,
    bound_package: object,
    bundle: ResponseSchemaBundle,
    doctor_catalog: object,
    effective_scope: object,
) -> AuthoritativeCommerceResult | None:
    """Code-owned broad implantation price anchors for one_tooth and full_arch."""

    from contracts.effective_scope import EffectiveScope
    from contracts.doctor_schema import TargetDoctorCatalog
    from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
    from core.service_data_context import build_service_data_context
    from core.target_offer_projection import project_target_service_offers
    from core.target_scope_aware_selection import run_target_scope_aware_selection
    from core.target_strategy_context import strategy_match_from_effective_scope

    if not isinstance(bound_package, TargetSpecBoundOfflineResponsePackage):
        return None
    if not isinstance(effective_scope, EffectiveScope):
        return None
    if not isinstance(doctor_catalog, TargetDoctorCatalog):
        return None

    spec = bound_package.spec
    if spec.response_stage != "broad_family_price" or not spec.scope_price_topic:
        return None

    selection = run_target_scope_aware_selection(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=spec.scope_price_topic,
    )
    if selection.kind != "broad_anchors":
        return None

    overview_extents = ("one_tooth", "full_arch")
    service_lines: list[ServiceLevelOverviewLine] = []

    for anchor in selection.anchors:
        if anchor.extent not in overview_extents:
            continue
        scoped_scope = effective_scope.model_copy(update={"extent": anchor.extent})
        strategy = strategy_match_from_effective_scope(scoped_scope)
        context = build_service_data_context(bundle, doctor_catalog, anchor.service_id)
        projection = project_target_service_offers(context, bundle.strategy, strategy)
        overview_line = build_service_level_overview_line(
            service_name=(
                bundle.services.get(anchor.service_id).name
                if bundle.services.get(anchor.service_id) is not None
                else anchor.service_id
            ),
            offers=projection.offers,
        )
        if overview_line is not None:
            service_lines.append(overview_line)

    commerce_block = _build_service_overview_commerce_block(tuple(service_lines))
    if commerce_block is None:
        return None
    patient_block, anchor_offers, amounts = commerce_block
    widget = _build_widget_offer_payload(
        presentation_mode="overview",
        ordered_offers=anchor_offers,
        featured_offer_id=None,
        selected_exact_offer=None,
        entry_price_amount=min(amounts) if amounts else None,
        bundle=bundle,
    )
    return AuthoritativeCommerceResult(
        service_id=None,
        presentation_mode="overview",
        entry_price_amount=min(amounts) if amounts else None,
        entry_price_text=None,
        ordered_offers=anchor_offers,
        featured_offer_id=None,
        selected_exact_offer=None,
        needs_consultation_quote=False,
        authoritative_amounts=amounts,
        patient_price_block=patient_block,
        widget_offer_payload=widget,
    )


def build_scoped_family_price_commerce_result(
    *,
    bound_package: object,
    bundle: ResponseSchemaBundle,
    doctor_catalog: object,
    effective_scope: object,
) -> AuthoritativeCommerceResult | None:
    """Code-owned scoped-family service entry prices for a known extent."""

    from contracts.doctor_schema import TargetDoctorCatalog
    from contracts.effective_scope import EffectiveScope
    from core.target_scope_aware_selection import run_target_scope_aware_selection
    from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage

    if not isinstance(bound_package, TargetSpecBoundOfflineResponsePackage):
        return None
    if not isinstance(effective_scope, EffectiveScope):
        return None
    if not isinstance(doctor_catalog, TargetDoctorCatalog):
        return None

    spec = bound_package.spec
    if (
        spec.response_stage not in {"scoped_family_price", "concrete_service_price"}
        or not spec.scope_price_topic
    ):
        return None

    selection = run_target_scope_aware_selection(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=spec.scope_price_topic,
    )
    if selection.kind != "scoped_shortlist" or not selection.offers_by_service_id:
        return None

    service_lines: list[ServiceLevelOverviewLine] = []

    for service_id in selection.service_ids:
        offers = selection.offers_by_service_id.get(service_id, ())
        service = bundle.services.get(service_id)
        service_name = service.name if service is not None else service_id
        overview_line = build_service_level_overview_line(
            service_name=service_name,
            offers=offers,
        )
        if overview_line is not None:
            service_lines.append(overview_line)

    commerce_block = _build_service_overview_commerce_block(tuple(service_lines))
    if commerce_block is None:
        return None
    patient_block, entry_offers, amounts = commerce_block
    widget = _build_widget_offer_payload(
        presentation_mode="overview",
        ordered_offers=entry_offers,
        featured_offer_id=None,
        selected_exact_offer=None,
        entry_price_amount=min(amounts) if amounts else None,
        bundle=bundle,
    )
    return AuthoritativeCommerceResult(
        service_id=None,
        presentation_mode="overview",
        entry_price_amount=min(amounts) if amounts else None,
        entry_price_text=None,
        ordered_offers=entry_offers,
        featured_offer_id=None,
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


def _normalize_percent_value(raw: str) -> str:
    normalized = re.sub(r"[ \u00a0\u202f]", "", raw)
    normalized = normalized.replace(",", ".")
    if normalized.endswith("%"):
        normalized = normalized[:-1]
    try:
        value = float(normalized)
    except ValueError:
        return normalized
    if value == int(value):
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _percents_in_text(text: str) -> set[str]:
    percents: set[str] = set()
    for match in _PERCENT_LITERAL_RE.finditer(text):
        digits = re.search(
            r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?",
            match.group(0),
        )
        if digits is not None:
            percents.add(_normalize_percent_value(digits.group(0)))
    return percents


def _sentence_is_commercial_percent_claim(sentence: str) -> bool:
    if not _percents_in_text(sentence):
        return False
    return _COMMERCIAL_PERCENT_CLAIM_MARKER_RE.search(sentence) is not None


def _sentence_has_unauthorized_commercial_percent_claim(
    sentence: str,
    allowed_commercial_percents: frozenset[str],
) -> bool:
    if not _sentence_is_commercial_percent_claim(sentence):
        return False
    percents = _percents_in_text(sentence)
    if not allowed_commercial_percents:
        return True
    return not percents.issubset(allowed_commercial_percents)


def _remove_unauthorized_commercial_claim_sentences(
    text: str,
    *,
    allowed_amounts: frozenset[int],
    allowed_commercial_percents: frozenset[str],
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
            if _sentence_has_unauthorized_commercial_percent_claim(
                sentence,
                allowed_commercial_percents,
            ):
                continue
            kept_parts.append(sentence)
        if kept_parts:
            kept_paragraphs.append(" ".join(kept_parts))
    return "\n\n".join(kept_paragraphs).strip()


def sanitize_model_text_for_authoritative_marketing(
    text: str,
    *,
    allowed_amounts: frozenset[int],
    allowed_percents: frozenset[str],
) -> str:
    """Strip model commercial numeric claims not present in authoritative sources."""

    return _remove_unauthorized_commercial_claim_sentences(
        _strip_route_metadata(text),
        allowed_amounts=allowed_amounts,
        allowed_commercial_percents=allowed_percents,
    )


def collect_planned_render_commercial_allowlist(
    *,
    planned_commercial_fact_texts: tuple[str, ...],
    commerce: AuthoritativeCommerceResult | None,
    commercial_intent: str,
) -> tuple[frozenset[int], frozenset[str]]:
    """Build commercial allowlist only from planned promo/commerce render owners."""

    allowed_amounts: set[int] = set()
    allowed_percents: set[str] = set()
    if commerce is not None and commercial_intent == "price":
        allowed_amounts.update(commerce.authoritative_amounts)
        for amount in _amounts_in_text(commerce.patient_price_block or ""):
            allowed_amounts.add(amount)
    for text in planned_commercial_fact_texts:
        allowed_amounts.update(_amounts_in_text(text))
        allowed_percents.update(_percents_in_text(text))
    return frozenset(allowed_amounts), frozenset(allowed_percents)


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
