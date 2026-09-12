"""Resolve optional service_value facts from canonical catalog refs."""

from __future__ import annotations

from contracts.response_schema import ResponseSchemaBundle

_SERVICE_VALUE_KIND = "service_value"


def resolve_service_value_ref(
    bundle: ResponseSchemaBundle,
    *,
    service_id: str | None,
    shown_service_value_ids: frozenset[str],
    bypass_service_value_id: str | None = None,
) -> str | None:
    """Return ``fact:<id>`` when service metadata points at an eligible service_value fact."""

    if not service_id:
        return None
    service = bundle.services.get(service_id)
    if service is None:
        return None
    raw_ref = service.service_value_ref
    if not raw_ref or not str(raw_ref).startswith("fact:"):
        return None
    fact_id = str(raw_ref).removeprefix("fact:")
    if fact_id in shown_service_value_ids and fact_id != bypass_service_value_id:
        return None
    fact = bundle.facts.get(fact_id)
    if fact is None or str(fact.kind) != _SERVICE_VALUE_KIND or not fact.active:
        return None
    if fact.allowed_service_ids and service_id not in fact.allowed_service_ids:
        return None
    return f"fact:{fact_id}"


def service_value_text_for_ref(
    bundle: ResponseSchemaBundle,
    service_value_ref: str | None,
) -> str:
    if not service_value_ref or not service_value_ref.startswith("fact:"):
        return ""
    fact = bundle.facts.get(service_value_ref.removeprefix("fact:"))
    if fact is None:
        return ""
    return str(fact.text_fact).strip()
