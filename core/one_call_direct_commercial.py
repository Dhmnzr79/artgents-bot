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
    for fact_id in direct_fact_ids:
        if not _fact_is_eligible(
            bundle=bundle,
            fact_id=fact_id,
            authoritative_service_id=authoritative_service_id,
            today=today,
        ):
            saw_ineligible = True
            continue
        fact = bundle.facts[fact_id]
        text = str(fact.text_fact).strip()
        if text and text not in eligible_texts:
            eligible_texts.append(text)

    eligible_tuple = tuple(eligible_texts)
    if eligible_tuple and saw_ineligible:
        rendered = "\n\n".join([*eligible_tuple, DIRECT_COMMERCIAL_INELIGIBLE_PHRASE])
    elif eligible_tuple:
        rendered = "\n\n".join(eligible_tuple)
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
    return f"{body}{separator}{'\n\n'.join(missing)}"
