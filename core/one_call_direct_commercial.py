"""Deterministic direct-commercial fact materializer (Checkpoint B1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from contracts.response_schema import ResponseSchemaBundle

DIRECT_COMMERCIAL_INELIGIBLE_PHRASE = (
    "Сейчас не могу подтвердить актуальные условия по этому вопросу."
)


@dataclass(frozen=True, slots=True)
class DirectCommercialMaterialization:
    eligible_texts: tuple[str, ...]
    has_ineligible: bool
    rendered_text: str


def _fact_is_eligible(
    *,
    bundle: ResponseSchemaBundle,
    fact_id: str,
    authoritative_service_id: str | None,
    today: date,
) -> bool:
    fact = bundle.facts.get(fact_id)
    if fact is None:
        return False
    if not bool(fact.active):
        return False
    today_iso = today.isoformat()
    if fact.active_from is not None and today_iso < fact.active_from:
        return False
    if fact.active_until is not None and today_iso > fact.active_until:
        return False
    allowed = tuple(fact.allowed_service_ids)
    if authoritative_service_id is not None and allowed:
        return authoritative_service_id in allowed
    return True


def _direct_commercial_fact_is_eligible(
    *,
    bundle: ResponseSchemaBundle,
    fact_id: str,
    authoritative_service_id: str | None,
    today: date,
    selected_fact_ids: set[str],
) -> bool:
    from core.target_marketing_selector import _promo_fact_runtime_eligible

    if fact_id not in bundle.facts:
        return False
    return _promo_fact_runtime_eligible(
        bundle,
        f"fact:{fact_id}",
        service_id=authoritative_service_id,
        turn_topic=None,
        today_iso=today.isoformat(),
        selected_fact_ids=selected_fact_ids,
        apply_service_applicability=True,
        apply_topic_applicability=False,
    )


def direct_fact_ids_block_installment_context(
    bundle: ResponseSchemaBundle,
    direct_fact_ids: tuple[str, ...],
) -> bool:
    for fact_id in direct_fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is None:
            continue
        if "installment_12" in fact.incompatible_with:
            return True
    return False


def materialize_direct_commercial(
    *,
    bundle: ResponseSchemaBundle,
    direct_fact_ids: tuple[str, ...],
    authoritative_service_id: str | None,
    today: date,
) -> DirectCommercialMaterialization:
    """Render ordered exact eligible ``text_fact`` values or controlled ineligible phrase."""

    if not direct_fact_ids:
        return DirectCommercialMaterialization((), False, "")

    eligible_texts: list[str] = []
    saw_ineligible = False
    selected_fact_ids: set[str] = set()
    for fact_id in direct_fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is None:
            saw_ineligible = True
            continue
        if "installment_12" in fact.incompatible_with:
            saw_ineligible = True
            continue
        if not _direct_commercial_fact_is_eligible(
            bundle=bundle,
            fact_id=fact_id,
            authoritative_service_id=authoritative_service_id,
            today=today,
            selected_fact_ids=selected_fact_ids,
        ):
            saw_ineligible = True
            continue
        if str(fact.kind) == "service_value":
            saw_ineligible = True
            continue
        text = str(fact.text_fact).strip()
        if text and text not in eligible_texts:
            eligible_texts.append(text)
            selected_fact_ids.add(fact_id)

    eligible_tuple = tuple(eligible_texts)
    if eligible_tuple:
        rendered = "\n\n".join(eligible_tuple)
    elif not any(
        fact_id in bundle.facts
        and str(bundle.facts[fact_id].kind) != "service_value"
        for fact_id in direct_fact_ids
    ):
        rendered = ""
    else:
        rendered = DIRECT_COMMERCIAL_INELIGIBLE_PHRASE

    return DirectCommercialMaterialization(
        eligible_texts=eligible_tuple,
        has_ineligible=saw_ineligible,
        rendered_text=rendered,
    )


def materialize_direct_commercial_text(
    *,
    bundle: ResponseSchemaBundle,
    direct_fact_ids: tuple[str, ...],
    authoritative_service_id: str | None,
    today: date,
) -> str:
    return materialize_direct_commercial(
        bundle=bundle,
        direct_fact_ids=direct_fact_ids,
        authoritative_service_id=authoritative_service_id,
        today=today,
    ).rendered_text


def append_direct_commercial_without_duplicates(
    patient_text: str,
    direct_commercial_text: str,
) -> str:
    """Append deterministic direct blocks once when absent from existing text."""

    token = str(direct_commercial_text or "").strip()
    if not token:
        return patient_text
    body = str(patient_text or "").rstrip()
    blocks = [part.strip() for part in token.split("\n\n") if part.strip()]
    missing = [block for block in blocks if block not in body]
    if not missing:
        return patient_text
    separator = "\n\n" if body else ""
    missing_text = "\n\n".join(missing)
    return f"{body}{separator}{missing_text}"
