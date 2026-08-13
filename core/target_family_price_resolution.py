"""Deterministic family-level price resolution and broad mode selection."""

from __future__ import annotations

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetFamilyPrice,
    TargetFixedPrice,
    TargetFromPrice,
    TargetOffer,
    TargetPricePackage,
    TargetRangePrice,
)
from contracts.target_scope_aware_selection import TargetScopeAwareSelectionResult
from contracts.target_service_content_topic import service_catalog_content_topic_matches
from core.service_data_context import build_service_data_context
from core.target_offer_projection import project_target_service_offers
from core.target_strategy_context import (
    SelectionPatientContext,
    strategy_match_from_effective_scope,
)

FAMILY_ONLY_BROAD_EXCLUSION = "family_only_broad"
PROTOCOL_PRICE_UNCONFIRMED_PREFIX = "protocol_price_unconfirmed:"

_BROAD_ANCHOR_EXTENTS = ("one_tooth", "full_arch", "few_teeth")


def list_family_prices_for_topic(
    bundle: ResponseSchemaBundle,
    topic: str,
) -> tuple[TargetFamilyPrice, ...]:
    return tuple(
        record
        for record in bundle.family_prices.records
        if record.topic == topic
    )


def family_price_applies_to_service(
    family_price: TargetFamilyPrice,
    service_id: str,
) -> bool:
    return service_id in family_price.applies_to_service_ids


def is_family_only_broad_mode(selection: TargetScopeAwareSelectionResult) -> bool:
    return FAMILY_ONLY_BROAD_EXCLUSION in selection.exclusions


def is_protocol_price_unconfirmed(
    selection: TargetScopeAwareSelectionResult,
    service_id: str,
) -> bool:
    marker = f"{PROTOCOL_PRICE_UNCONFIRMED_PREFIX}{service_id}"
    return marker in selection.exclusions


def _numeric_offer_available(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    service_id: str,
    strategy_context,
) -> bool:
    context = build_service_data_context(bundle, doctor_catalog, service_id)
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_context,
    )
    for offer in projection.offers:
        if offer.price.mode in {"fixed", "from", "range"}:
            return True
    return False


def has_scope_specific_broad_anchors(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    base_patient: SelectionPatientContext,
    stage: str | None,
    jaw: str | None,
    reported_context: str | None,
) -> bool:
    """True when mode A applies: at least one extent anchor has a numeric service offer."""

    for extent in _BROAD_ANCHOR_EXTENTS:
        scoped_scope = effective_scope.model_copy(update={"extent": extent})
        patient = SelectionPatientContext(
            extent=extent,
            stage=base_patient.stage,
            jaw=base_patient.jaw,
            reported_context=base_patient.reported_context,
        )
        scoped_strategy = strategy_match_from_effective_scope(
            scoped_scope,
            stage=stage,  # type: ignore[arg-type]
            jaw=jaw,  # type: ignore[arg-type]
            reported_context=reported_context,  # type: ignore[arg-type]
        )
        from core.target_service_applicability import filter_applicable_services
        from core.response_strategy import resolve_target_strategy

        applicable = filter_applicable_services(
            bundle,
            topic=topic,
            strategy_context=scoped_strategy,
            patient=patient,
        )
        if not applicable:
            continue
        resolution = resolve_target_strategy(
            bundle.strategy,
            scoped_strategy,
            service_ids=tuple(item.service_id for item in applicable),
        )
        if not resolution.service_ids:
            continue
        if _numeric_offer_available(
            bundle,
            doctor_catalog,
            service_id=resolution.service_ids[0],
            strategy_context=scoped_strategy,
        ):
            return True
    return False


def _pick_family_anchor_service_id(
    bundle: ResponseSchemaBundle,
    family_price: TargetFamilyPrice,
    *,
    topic: str,
) -> str | None:
    for service_id in family_price.applies_to_service_ids:
        service = bundle.services.get(service_id)
        if service is None or not service.active:
            continue
        if service.content_ref is not None and not service_catalog_content_topic_matches(
            service.content_ref,
            topic,
        ):
            continue
        return service_id
    for service_id, service in bundle.services.items():
        if not service.active:
            continue
        if service_id not in family_price.applies_to_service_ids:
            continue
        return service_id
    return None


def transient_offer_from_family_price(
    bundle: ResponseSchemaBundle,
    family_price: TargetFamilyPrice,
    *,
    anchor_service_id: str,
) -> TargetOffer:
    service = bundle.services[anchor_service_id]
    return TargetOffer(
        offer_id=f"family_price:{family_price.family_price_id}",
        service_id=anchor_service_id,
        active=True,
        price=family_price.price,
        package=TargetPricePackage(
            label=service.name,
            includes=[family_price.approved_context],
        ),
        fact_refs=(),
        followups=(),
    )


def build_family_only_broad_selection(
    bundle: ResponseSchemaBundle,
    *,
    family_price: TargetFamilyPrice,
    topic: str,
    effective_scope: EffectiveScope,
    strategy_context,
    matched_rule_id: str | None,
) -> TargetScopeAwareSelectionResult:
    anchor_service_id = _pick_family_anchor_service_id(
        bundle,
        family_price,
        topic=topic,
    )
    if anchor_service_id is None:
        return TargetScopeAwareSelectionResult(
            topic=topic,
            effective_scope=effective_scope,
            kind="broad_anchors",
            strategy_context=strategy_context,
            matched_rule_id=matched_rule_id,
            service_ids=(),
            offers_by_service_id={},
            anchors=(),
            exclusions=("family_price_no_anchor_service",),
        )
    offer = transient_offer_from_family_price(
        bundle,
        family_price,
        anchor_service_id=anchor_service_id,
    )
    return TargetScopeAwareSelectionResult(
        topic=topic,
        effective_scope=effective_scope,
        kind="broad_anchors",
        strategy_context=strategy_context,
        matched_rule_id=matched_rule_id,
        service_ids=(anchor_service_id,),
        offers_by_service_id={anchor_service_id: (offer,)},
        anchors=(),
        exclusions=(FAMILY_ONLY_BROAD_EXCLUSION,),
    )


def resolve_explicit_service_price_stage(
    bundle: ResponseSchemaBundle,
    *,
    explicit_service_id: str,
    topic: str,
    selection: TargetScopeAwareSelectionResult | None,
) -> str | None:
    """Return data_gap when a named service exists but must not inherit family price."""

    if selection is None:
        return None
    offers = selection.offers_by_service_id.get(explicit_service_id, ())
    if offers:
        return None
    service = bundle.services.get(explicit_service_id)
    if service is None or not service.active:
        return "data_gap"
    if is_protocol_price_unconfirmed(selection, explicit_service_id):
        return "data_gap"
    if list_family_prices_for_topic(bundle, topic):
        return "data_gap"
    if not offers:
        return "data_gap"
    return None


def service_offer_precedence(
    offers: tuple[TargetOffer, ...],
    *,
    family_price: TargetFamilyPrice | None,
) -> tuple[TargetOffer, ...] | None:
    """Apply price precedence for one service: specific > no_public_price > family > gap."""

    if not offers:
        return None
    numeric = tuple(
        offer for offer in offers if offer.price.mode in {"fixed", "from", "range"}
    )
    if numeric:
        return numeric
    no_public = tuple(
        offer for offer in offers if offer.price.mode == "no_public_price"
    )
    if no_public:
        return no_public
    if family_price is not None:
        return None
    return None


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", "\u00a0") + " ₽"


_BILLING_UNIT_PATIENT_LABELS: dict[str, str] = {
    "tooth": "за один зуб",
    "implant": "за один имплант",
    "tooth_package": "за лечение одного зуба под ключ",
    "jaw": "за одну челюсть",
    "both_jaws": "за обе челюсти",
    "procedure": "за одну процедуру",
    "unit": "за одну единицу",
    "course": "за курс лечения",
}


def _format_billing_unit(billing_unit: str) -> str:
    label = _BILLING_UNIT_PATIENT_LABELS.get(str(billing_unit or "").strip())
    if label is None:
        raise ValueError("family_price_billing_unit_invalid")
    return label


def _format_family_level_price(
    price: TargetFixedPrice | TargetFromPrice | TargetRangePrice,
) -> str:
    unit = _format_billing_unit(price.billing_unit)
    if price.mode == "fixed":
        return f"{_rubles(int(price.amount))} {unit}"
    if price.mode == "from":
        return f"от {_rubles(int(price.min_amount))} {unit}"
    if price.mode == "range":
        return (
            f"от {_rubles(int(price.min_amount))} "
            f"до {_rubles(int(price.max_amount))} {unit}"
        )
    raise ValueError("family_price_mode_invalid")


def resolve_family_price_context_for_service(
    bundle: ResponseSchemaBundle,
    service_id: str,
) -> str | None:
    """Return labeled family context text only when explicit applies_to_service_ids match."""

    token = str(service_id or "").strip()
    if not token:
        return None
    for record in bundle.family_prices.records:
        if not family_price_applies_to_service(record, token):
            continue
        amount_text = _format_family_level_price(record.price)
        context = str(record.approved_context).strip()
        if not context:
            continue
        return f"{context} {amount_text}."
    return None
