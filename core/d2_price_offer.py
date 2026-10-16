"""Pure canonical offer projection shared by dialogue and future catalog readers.

No selection, filesystem access, model calls, history, revision or effects.
"""
from __future__ import annotations

from contracts.response_plan import D2FrozenPriceRow
from contracts.response_plan_materialization import (
    D2PublishedOfferTerms, MaterializationContractError, MaterializationOwnershipError,
)
from contracts.response_schema import (
    ResponseDataCatalog, TargetOffer, TargetFixedPrice, TargetFromPrice,
    TargetRangePrice, TargetNoPublicPrice,
)
from core.d2_published_offer_terms import build_d2_published_offer_terms


def build_d2_price_offer_row(
    offer: TargetOffer,
    *,
    bundle: ResponseDataCatalog,
    client_id: str,
    terms: D2PublishedOfferTerms,
) -> D2FrozenPriceRow:
    canonical = next((item for item in bundle.offers if item.offer_id == offer.offer_id), None)
    if canonical != offer or not offer.active:
        raise MaterializationOwnershipError("d2_price_offer_unavailable")
    if terms.source_client_id != client_id or terms.offer_id != offer.offer_id:
        raise MaterializationOwnershipError("materialization_foreign_material")
    if terms != build_d2_published_offer_terms(offer=offer, source_client_id=client_id):
        raise MaterializationContractError("d2_published_terms_mismatch")
    service = bundle.services.get(offer.service_id)
    if service is None or not service.active:
        raise MaterializationOwnershipError("materialization_foreign_material")
    if offer.option_id is not None and not any(
        item.option_id == offer.option_id and item.active is not False
        for item in service.options
    ):
        raise MaterializationOwnershipError("d2_price_option_unavailable")
    detail_fields = dict(includes=tuple(offer.package.includes),
                         excludes=tuple(offer.package.excludes),
                         stages=d2_payment_stage_texts(offer))
    variant = d2_offer_variant_label(bundle, offer)
    service_name = f"{service.name} — {variant}" if variant else service.name
    price = offer.price
    if isinstance(price, TargetFixedPrice):
        body = f"{_format_d2_amount(price.amount)}\u00a0{_d2_currency(price.currency)}"
        mode = "fixed"
    elif isinstance(price, TargetFromPrice):
        body = f"от {_format_d2_amount(price.min_amount)}\u00a0{_d2_currency(price.currency)}"
        mode = "from"
    elif isinstance(price, TargetRangePrice):
        body = (
            f"{_format_d2_amount(price.min_amount)}–{_format_d2_amount(price.max_amount)}\u00a0"
            f"{_d2_currency(price.currency)}"
        )
        mode = "range"
    elif isinstance(price, TargetNoPublicPrice):
        return D2FrozenPriceRow(
            **detail_fields,
            source_client_id=client_id,
            offer_id=offer.offer_id,
            service_id=offer.service_id,
            mode="no_public_price",
            display_text=f"{service_name} — {price.approved_text}",
            service_name=service.name,
            variant_label=variant,
            price_display_text=price.approved_text,
            scope_text=None,
            approved_text=price.approved_text,
            condition_texts=_d2_brief_price_conditions(
                # The first label clause is the billing scope. Without a
                # numeric price it is not a separate patient-facing condition.
                # Keep subsequent authored clauses and mandatory caveats.
                offer, package_label=terms.package_label.partition(";")[2],
                already_shown=price.approved_text,
            ),
        )
    else:  # pragma: no cover - TargetPrice is a discriminated union.
        raise MaterializationContractError("d2_price_mode_invalid")
    package_scope = terms.package_label.strip()
    scope_text = package_scope.split(";", 1)[0].strip()
    return D2FrozenPriceRow(
        **detail_fields,
        source_client_id=client_id,
        offer_id=offer.offer_id,
        service_id=offer.service_id,
        mode=mode,
        display_text=f"{service_name} — {body} {scope_text}".strip(),
        service_name=service.name,
        variant_label=variant,
        price_display_text=body,
        scope_text=scope_text or None,
        amount=price.amount if isinstance(price, TargetFixedPrice) else None,
        min_amount=(
            price.min_amount
            if isinstance(price, (TargetFromPrice, TargetRangePrice))
            else None
        ),
        max_amount=price.max_amount if isinstance(price, TargetRangePrice) else None,
        currency=price.currency,
        billing_unit=price.billing_unit,
        condition_texts=_d2_brief_price_conditions(
            offer, package_label=package_scope, already_shown=scope_text,
        ),
    )


def d2_payment_stage_texts(offer: TargetOffer) -> tuple[str, ...]:
    """One formatter for frozen card details and written detail responses."""
    return tuple(
        f"{stage.label} — {_format_d2_amount(stage.amount)}\u00a0{_d2_currency(stage.currency)}"
        + (f". {stage.timing_text}" if stage.timing_text else "")
        for stage in (offer.payment_stages or ())
    )


def _d2_brief_price_conditions(
    offer: TargetOffer, *, package_label: str, already_shown: str,
) -> tuple[str, ...]:
    """Keep authored scope and mandatory caveats, not package contents or payment stages."""
    # The authored package label carries the precise billing scope. When it is
    # present, the generic billing-unit phrase is not rendered a second time.
    # Semicolon-separated clauses are authored data, not inferred from prose.
    clauses = tuple(part.strip() for part in package_label.split(";") if part.strip())
    conditions = (item.display_text for item in (
        offer.required_conditions_metadata.conditions
        if offer.required_conditions_metadata is not None else ()
    ))
    return tuple(dict.fromkeys(
        item for item in (*clauses, *conditions) if item and item != already_shown
    ))


def _format_d2_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", "\u00a0")


def _d2_currency(currency: str) -> str:
    if currency == "RUB":
        return "₽"
    return currency


def d2_offer_variant_label(bundle: ResponseDataCatalog, offer: TargetOffer) -> str | None:
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
