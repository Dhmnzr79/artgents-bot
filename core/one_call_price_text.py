"""Isolated price_text validation and canonical fallback (CP-EXACT-1B-SINGLE / MULTI-V1)."""

from __future__ import annotations

import re

from contracts.one_call_envelope import OneCallCommercialIntent
from contracts.precomposer_selected_offer import (
    PrecomposerSelectedOfferResult,
    PriceTextDiagnostic,
    ResolvedPriceText,
)
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from core.one_call_multi_offer_price_block import build_canonical_multi_offer_price_block
from core.sales_fast_authoritative_commerce import (
    _amounts_in_text,
    build_canonical_exact_offer_price_line,
)

_PACKAGE_ANCHOR_RE = re.compile(r"[\wа-яё\-]+", re.IGNORECASE | re.UNICODE)


def _normalize_package_anchor(label: str) -> str:
    tokens = _PACKAGE_ANCHOR_RE.findall(label.casefold())
    return " ".join(tokens)


def _expected_amount(offer: TargetOffer) -> int | None:
    if offer.price.mode != "fixed" or offer.price.amount is None:
        return None
    return int(offer.price.amount)


def _currency_tokens(currency: str) -> tuple[str, ...]:
    token = currency.strip().upper()
    if token == "RUB":
        return ("₽", "руб", "rub")
    return (token.casefold(),)


def _billing_unit_tokens(billing_unit: str) -> tuple[str, ...]:
    unit = billing_unit.strip().casefold()
    mapping = {
        "procedure": ("процедур", "исследован", "услуг"),
        "tooth": ("зуб",),
        "jaw": ("челюст",),
        "unit": ("единиц",),
        "course": ("курс", "лечен"),
    }
    return mapping.get(unit, (unit,))


def _contains_currency(text: str, currency: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in _currency_tokens(currency))


def _contains_billing_unit(text: str, billing_unit: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in _billing_unit_tokens(billing_unit))


def _contains_package_anchor(text: str, package_label: str) -> bool:
    anchor = _normalize_package_anchor(package_label)
    if not anchor:
        return True
    return anchor in _normalize_package_anchor(text)


def validate_model_price_text(
    price_text: str | None,
    *,
    offer: TargetOffer,
    bundle: ResponseSchemaBundle,
) -> PriceTextDiagnostic | None:
    canonical_amount = _expected_amount(offer)
    if canonical_amount is None:
        return "wrong_amount"
    if price_text is None or not str(price_text).strip():
        return "missing"

    text = str(price_text).strip()
    amounts = _amounts_in_text(text)
    if canonical_amount not in amounts:
        return "wrong_amount"
    if len(amounts) > 1:
        return "extra_amount"
    if not _contains_currency(text, str(offer.price.currency or "RUB")):
        return "wrong_amount"
    if not _contains_billing_unit(text, str(offer.price.billing_unit or "")):
        return "wrong_unit"
    package_label = str(offer.package.label or "").strip()
    if package_label and not _contains_package_anchor(text, package_label):
        return "wrong_scope"
    if offer.service_id not in bundle.services:
        return "wrong_scope"
    return None


def resolve_price_text_for_turn(
    *,
    price_text: str | None,
    commercial_intent: OneCallCommercialIntent,
    selection: PrecomposerSelectedOfferResult,
    bundle: ResponseSchemaBundle,
) -> ResolvedPriceText:
    if commercial_intent != "price":
        if price_text is not None and str(price_text).strip():
            return ResolvedPriceText(
                line="",
                owner="none",
                diagnostic="unexpected_nonprice",
            )
        return ResolvedPriceText(line="", owner="none")

    if selection.availability == "multiple":
        diagnostic: PriceTextDiagnostic | None = None
        if price_text is not None and str(price_text).strip():
            diagnostic = "unexpected_multi_price_text"
        multi = build_canonical_multi_offer_price_block(
            bundle=bundle,
            selection=selection,
        )
        if multi.block:
            return ResolvedPriceText(
                line=multi.block,
                owner="canonical_multi",
                diagnostic=diagnostic,
                multi_offer_ids=multi.offer_ids,
            )
        return ResolvedPriceText(
            line="",
            owner="none",
            diagnostic=diagnostic or multi.diagnostic,  # type: ignore[arg-type]
            multi_offer_ids=multi.offer_ids,
        )

    canonical = build_canonical_exact_offer_price_line(offer=selection.offer, bundle=bundle) if (
        selection.availability == "selected" and selection.offer is not None
    ) else ""

    if selection.availability != "selected" or selection.offer is None:
        if price_text is not None and str(price_text).strip():
            return ResolvedPriceText(
                line="",
                owner="none",
                diagnostic="unexpected_nonprice",
            )
        return ResolvedPriceText(line="", owner="none")

    offer = selection.offer
    failure = validate_model_price_text(price_text, offer=offer, bundle=bundle)
    if failure is None and price_text is not None:
        return ResolvedPriceText(
            line=str(price_text).strip(),
            owner="model_price_text",
            selected_offer_id=offer.offer_id,
        )
    single_diagnostic: PriceTextDiagnostic = failure or "canonical_fallback_used"
    if failure is None:
        single_diagnostic = "canonical_fallback_used"
    return ResolvedPriceText(
        line=canonical,
        owner="canonical_fallback",
        diagnostic=single_diagnostic,
        selected_offer_id=offer.offer_id,
    )


def patient_text_contains_duplicate_amount(
    patient_text: str,
    *,
    offer: TargetOffer,
) -> bool:
    amount = _expected_amount(offer)
    if amount is None:
        return False
    return amount in _amounts_in_text(patient_text)


def patient_text_contains_monetary_amount(patient_text: str) -> bool:
    return bool(_amounts_in_text(patient_text))


def assemble_price_turn_visible_text(
    *,
    price_line: str,
    patient_text: str,
    marketing_suffix: str,
) -> str:
    parts: list[str] = []
    if price_line.strip():
        parts.append(price_line.strip())
    if patient_text:
        parts.append(patient_text)
    if marketing_suffix.strip():
        parts.append(marketing_suffix.strip())
    return "\n\n".join(parts)
