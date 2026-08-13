"""Availability, authored alternatives and price coverage presentation (Stage 5.1B)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.authored_service_alternative import AuthoredServiceAlternative
from contracts.doctor_schema import TargetDoctorCatalog
from contracts.one_call_presentation_result import PresentationQuickReply
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetStrategyMatch
from contracts.service_reference import AvailabilityStatus, PriceCoverageKind
from contracts.ui_service_action import build_ui_service_ref
from core.clinic_policies_loader import load_authored_service_alternatives
from core.service_data_context import ServiceDataContextError, build_service_data_context
from core.target_family_price_resolution import (
    family_price_applies_to_service,
    resolve_family_price_context_for_service,
)
from core.target_offer_projection import project_target_service_offers

FAMILY_CONTEXT_DISCLAIMER = (
    "Это ориентир по направлению, а не цена конкретной услуги."
)

_MAX_AUTHORED_ALTERNATIVES = 2

_UNRESOLVED_OVERLAY_TEXT = (
    "Не вижу такой услуги в перечне клиники. "
    "Возможно, она называется иначе — уточните название."
)


@dataclass(frozen=True, slots=True)
class AvailabilityOverlay:
    not_offered_text: str | None = None
    unresolved_text: str | None = None
    alternative_texts: tuple[str, ...] = ()


def load_authored_alternatives(
    client_id: str,
    *,
    requested_service_id: str,
    bundle: ResponseSchemaBundle,
) -> tuple[AuthoredServiceAlternative, ...]:
    """Return validated authored alternatives for one inactive requested service."""

    token = str(requested_service_id or "").strip()
    if not token:
        return ()
    rows = load_authored_service_alternatives(client_id)
    matched: AuthoredServiceAlternative | None = None
    for row in rows:
        if row.requested_service_id == token:
            matched = row
            break
    if matched is None:
        return ()

    validated_ids: list[str] = []
    for alt_id in matched.alternative_service_ids:
        if alt_id in validated_ids:
            continue
        service = bundle.services.get(alt_id)
        if service is None or not service.active:
            continue
        validated_ids.append(alt_id)
        if len(validated_ids) >= _MAX_AUTHORED_ALTERNATIVES:
            break
    if not validated_ids:
        return ()
    return (
        AuthoredServiceAlternative(
            requested_service_id=matched.requested_service_id,
            alternative_service_ids=tuple(validated_ids),
            approved_text=matched.approved_text,
        ),
    )


def _active_offers_for_service(
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> tuple[TargetOffer, ...]:
    return tuple(
        offer
        for offer in bundle.offers
        if offer.service_id == service_id and offer.active
    )


def _projected_offers_for_service(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    service_id: str,
    strategy_context: TargetStrategyMatch | None,
) -> tuple[TargetOffer, ...]:
    try:
        context = build_service_data_context(bundle, doctor_catalog, service_id)
    except ServiceDataContextError:
        return ()
    strategy_match = strategy_context or TargetStrategyMatch(family=None, extent=None)
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_match,
    )
    return projection.offers


def resolve_price_coverage_kind(
    bundle: ResponseSchemaBundle,
    *,
    service_id: str,
    doctor_catalog: TargetDoctorCatalog | None = None,
    strategy_context: TargetStrategyMatch | None = None,
) -> PriceCoverageKind:
    """Apply price precedence: exact numeric > no_public_price > family_context > data_gap."""

    token = str(service_id or "").strip()
    if not token:
        return "none"
    service = bundle.services.get(token)
    if service is None or not service.active:
        return "none"

    offers = (
        _projected_offers_for_service(
            bundle,
            doctor_catalog,
            service_id=token,
            strategy_context=strategy_context,
        )
        if doctor_catalog is not None
        else _active_offers_for_service(bundle, token)
    )
    if any(offer.price.mode in {"fixed", "from", "range"} for offer in offers):
        return "exact_numeric"
    if any(offer.price.mode == "no_public_price" for offer in offers):
        return "no_public_price"
    for record in bundle.family_prices.records:
        if family_price_applies_to_service(record, token):
            return "family_context"
    return "data_gap"


def _service_display_name(bundle: ResponseSchemaBundle, service_id: str) -> str:
    service = bundle.services.get(service_id)
    if service is None:
        return service_id
    return str(service.name or service_id).strip() or service_id


def _not_offered_text(bundle: ResponseSchemaBundle, requested_service_id: str) -> str:
    name = _service_display_name(bundle, requested_service_id)
    return f"Сейчас услуга «{name}» в клинике не оказывается."


def build_availability_overlay(
    *,
    client_id: str,
    availability_status: AvailabilityStatus,
    requested_service_id: str | None,
    bundle: ResponseSchemaBundle,
) -> AvailabilityOverlay | None:
    """Build availability overlay for known_not_offered/unresolved; none returns None."""

    if availability_status == "none":
        return None
    if availability_status == "unresolved":
        return AvailabilityOverlay(unresolved_text=_UNRESOLVED_OVERLAY_TEXT)
    if availability_status != "known_not_offered":
        return None

    token = str(requested_service_id or "").strip()
    if not token:
        return None

    authored = load_authored_alternatives(
        client_id,
        requested_service_id=token,
        bundle=bundle,
    )
    alternative_texts = tuple(
        row.approved_text.strip()
        for row in authored
        if row.approved_text.strip()
    )
    if alternative_texts:
        return AvailabilityOverlay(
            not_offered_text=None,
            alternative_texts=alternative_texts,
        )
    return AvailabilityOverlay(
        not_offered_text=_not_offered_text(bundle, token),
        alternative_texts=(),
    )


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", "\u00a0") + " ₽"


def _offer_price_value(offer: TargetOffer) -> str | None:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        value = _rubles(int(price.amount))
    elif price.mode == "from" and price.min_amount is not None:
        value = "от " + _rubles(int(price.min_amount))
    elif (
        price.mode == "range"
        and price.min_amount is not None
        and price.max_amount is not None
    ):
        value = (
            f"{_rubles(int(price.min_amount))}–{_rubles(int(price.max_amount))}"
        )
    elif price.mode == "no_public_price":
        return str(price.approved_text).strip() or None
    else:
        return None

    package_label = str(offer.package.label or "").strip()
    if package_label:
        return f"{value} {package_label}"
    return value


def _alternative_price_line(
    bundle: ResponseSchemaBundle,
    *,
    alternative_service_id: str,
    doctor_catalog: TargetDoctorCatalog,
    strategy_context: TargetStrategyMatch | None,
) -> str | None:
    service = bundle.services.get(alternative_service_id)
    if service is None or not service.active:
        return None
    coverage = resolve_price_coverage_kind(
        bundle,
        service_id=alternative_service_id,
        doctor_catalog=doctor_catalog,
        strategy_context=strategy_context,
    )
    if coverage not in {"exact_numeric", "no_public_price"}:
        return None

    offers = _projected_offers_for_service(
        bundle,
        doctor_catalog,
        service_id=alternative_service_id,
        strategy_context=strategy_context,
    )
    if not offers:
        return None

    selected: TargetOffer | None = None
    for offer in offers:
        if offer.price.mode in {"fixed", "from", "range"}:
            selected = offer
            break
    if selected is None:
        for offer in offers:
            if offer.price.mode == "no_public_price":
                selected = offer
                break
    if selected is None:
        return None

    price_value = _offer_price_value(selected)
    if not price_value:
        return None
    service_name = _service_display_name(bundle, alternative_service_id)
    if selected.price.mode == "no_public_price":
        return f"По услуге «{service_name}»: {price_value}"
    return f"Стоимость услуги «{service_name}» — {price_value}."


def build_alternative_price_lines(
    bundle: ResponseSchemaBundle,
    *,
    alternative_service_ids: tuple[str, ...],
    doctor_catalog: TargetDoctorCatalog,
    strategy_context: TargetStrategyMatch | None = None,
) -> tuple[str, ...]:
    """Labelled alternative price lines for unavailable-service price requests."""

    lines: list[str] = []
    for alt_id in alternative_service_ids:
        line = _alternative_price_line(
            bundle,
            alternative_service_id=alt_id,
            doctor_catalog=doctor_catalog,
            strategy_context=strategy_context,
        )
        if line:
            lines.append(line)
    return tuple(lines)


def build_alternative_secondary_slots(
    bundle: ResponseSchemaBundle,
    *,
    alternative_service_ids: tuple[str, ...],
) -> tuple[PresentationQuickReply, ...]:
    """Build governed target:ui_service/{id} secondary slots for authored alternatives."""

    slots: list[PresentationQuickReply] = []
    for alt_id in alternative_service_ids:
        if len(slots) >= _MAX_AUTHORED_ALTERNATIVES:
            break
        service = bundle.services.get(alt_id)
        if service is None or not service.active:
            continue
        label = str(service.name or alt_id).strip() or alt_id
        slots.append(
            PresentationQuickReply(
                label=label,
                ref=build_ui_service_ref(service_id=alt_id),
            )
        )
    return tuple(slots)


def append_family_context_disclaimer(text: str) -> str:
    body = str(text or "").strip()
    if not body:
        return FAMILY_CONTEXT_DISCLAIMER
    if body.endswith(FAMILY_CONTEXT_DISCLAIMER):
        return body
    return f"{body} {FAMILY_CONTEXT_DISCLAIMER}"


def resolve_family_price_context_with_disclaimer(
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> str | None:
    context = resolve_family_price_context_for_service(bundle, service_id)
    if context is None:
        return None
    return append_family_context_disclaimer(context)
