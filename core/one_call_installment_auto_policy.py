"""Deterministic installment_12 auto-append on code-owned price turns."""

from __future__ import annotations

from datetime import date

from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from core.one_call_direct_commercial import _fact_is_eligible

INSTALLMENT_12_FACT_ID = "installment_12"
INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT = (
    "Для этой услуги рассрочка в прайсе клиники не указана. "
    "Администратор уточнит доступные варианты оплаты при записи."
)


def _installment_fact(bundle: ResponseSchemaBundle):
    return bundle.facts.get(INSTALLMENT_12_FACT_ID)


def installment_microfact_text(bundle: ResponseSchemaBundle) -> str:
    fact = _installment_fact(bundle)
    if fact is None:
        return ""
    micro = getattr(fact, "microfact_text", None)
    return str(micro or "").strip()


def installment_positive_context_text(bundle: ResponseSchemaBundle) -> str:
    fact = _installment_fact(bundle)
    if fact is None:
        return ""
    text_fact = str(fact.text_fact or "").strip()
    if text_fact:
        return text_fact
    return installment_microfact_text(bundle)


def resolve_installment_excluded_scope_text(
    bundle: ResponseSchemaBundle,
    service_id: str | None,
) -> str | None:
    if not service_id:
        return None
    fact = _installment_fact(bundle)
    if fact is None:
        return None
    excluded_ids = tuple(str(item).strip() for item in (fact.excluded_service_ids or ()))
    if service_id not in excluded_ids:
        return None
    token = str(fact.excluded_scope_text or "").strip()
    return token or None


def offer_supports_installment_12(
    *,
    bundle: ResponseSchemaBundle,
    offer: TargetOffer,
    today: date,
) -> bool:
    refs = tuple(str(ref).strip() for ref in (offer.fact_refs or ()))
    if INSTALLMENT_12_FACT_ID not in refs:
        return False
    service_id = str(offer.service_id or "").strip()
    if not service_id:
        return False
    return _fact_is_eligible(
        bundle=bundle,
        fact_id=INSTALLMENT_12_FACT_ID,
        authoritative_service_id=service_id,
        today=today,
    )


def all_displayed_offers_support_installment_12(
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    today: date,
) -> bool:
    if not displayed_offers:
        return False
    return all(
        offer_supports_installment_12(bundle=bundle, offer=offer, today=today)
        for offer in displayed_offers
    )


def installment_auto_append_allowed_on_price_turn(
    *,
    semantic: SalesOnePlusSemanticFrame,
    materialized_public_price: bool,
) -> bool:
    return semantic.commercial_intent == "price" and materialized_public_price


def payment_installment_context_materialization_allowed(
    semantic: SalesOnePlusSemanticFrame,
) -> bool:
    return (
        semantic.commercial_intent == "payment"
        and INSTALLMENT_12_FACT_ID in semantic.direct_fact_ids
    )


def resolve_shared_installment_suffix_for_price_turn(
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    today: date,
) -> str | None:
    if not all_displayed_offers_support_installment_12(
        bundle=bundle,
        displayed_offers=displayed_offers,
        today=today,
    ):
        return None
    suffix = installment_microfact_text(bundle)
    return suffix or None


def _context_service_id(
    *,
    displayed_offers: tuple[TargetOffer, ...],
    service_id: str | None,
) -> str | None:
    if displayed_offers:
        service_ids = {
            str(offer.service_id).strip()
            for offer in displayed_offers
            if str(offer.service_id or "").strip()
        }
        if len(service_ids) > 1:
            return None
        if service_ids:
            return next(iter(service_ids))
    return str(service_id or "").strip() or None


def _authored_offers_for_service(
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> tuple[TargetOffer, ...]:
    token = str(service_id or "").strip()
    if not token:
        return ()
    return tuple(
        offer
        for offer in bundle.offers
        if str(offer.service_id or "").strip() == token and bool(offer.active)
    )


def resolve_contextual_payment_installment_text(
    *,
    bundle: ResponseSchemaBundle,
    displayed_offers: tuple[TargetOffer, ...],
    service_id: str | None,
    today: date,
) -> str | None:
    """Code-owned installment answer when payment intent has service/offer context."""

    context_service_id = _context_service_id(
        displayed_offers=displayed_offers,
        service_id=service_id,
    )
    if context_service_id is None and not displayed_offers and not service_id:
        return None
    if context_service_id is None and displayed_offers:
        return INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT

    resolved_service_id = context_service_id or str(service_id or "").strip() or None
    if not resolved_service_id:
        return None

    excluded = resolve_installment_excluded_scope_text(bundle, resolved_service_id)
    if excluded:
        return excluded

    if displayed_offers:
        if all_displayed_offers_support_installment_12(
            bundle=bundle,
            displayed_offers=displayed_offers,
            today=today,
        ):
            positive = installment_positive_context_text(bundle)
            return positive or None
        return INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT

    service_offers = _authored_offers_for_service(bundle, resolved_service_id)
    if not service_offers:
        return INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT
    if all_displayed_offers_support_installment_12(
        bundle=bundle,
        displayed_offers=service_offers,
        today=today,
    ):
        positive = installment_positive_context_text(bundle)
        return positive or None
    return INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT
