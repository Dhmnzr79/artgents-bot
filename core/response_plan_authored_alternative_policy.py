"""Response-plan authored-alternative policy resolution (demo policy parity)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.response_schema import ResponseSchemaBundle
from contracts.target_service_content_topic import parse_service_catalog_content_topic
from core.clinic_policies_loader import load_authored_service_alternatives

_MAX_AUTHORED_ALTERNATIVES = 2


@dataclass(frozen=True, slots=True)
class AuthoredAlternativePolicyResult:
    requested_service_id: str
    original_alternative_service_ids: tuple[str, ...]
    validated_alternative_service_ids: tuple[str, ...]
    unavailable_text: str
    group_approved_text: str | None
    unambiguous_topic_id: str | None


def _service_display_name(bundle: ResponseSchemaBundle, service_id: str) -> str:
    service = bundle.services.get(service_id)
    if service is None:
        return service_id
    return str(service.name or service_id).strip() or service_id


def _validate_alternative_ids(
    bundle: ResponseSchemaBundle,
    alternative_service_ids: tuple[str, ...],
) -> tuple[str, ...]:
    kept: list[str] = []
    for alt_id in alternative_service_ids:
        if alt_id in kept:
            continue
        service = bundle.services.get(alt_id)
        if service is None or not service.active:
            continue
        kept.append(alt_id)
        if len(kept) >= _MAX_AUTHORED_ALTERNATIVES:
            break
    return tuple(kept)


def unambiguous_topic_for_service_ids(
    bundle: ResponseSchemaBundle,
    service_ids: tuple[str, ...],
) -> str | None:
    topics: list[str] = []
    for service_id in service_ids:
        service = bundle.services.get(service_id)
        if service is None or not service.active:
            return None
        topic = parse_service_catalog_content_topic(service.content_ref)
        if topic is None:
            return None
        topics.append(topic)
    if not topics:
        return None
    unique = set(topics)
    if len(unique) != 1:
        return None
    return topics[0]


def resolve_authored_alternative_policy(
    *,
    source_client_id: str,
    requested_service_id: str,
    bundle: ResponseSchemaBundle,
) -> AuthoredAlternativePolicyResult | None:
    token = str(requested_service_id or "").strip()
    if not token:
        return None

    matched = None
    for row in load_authored_service_alternatives(source_client_id):
        if row.requested_service_id == token:
            matched = row
            break
    if matched is None:
        return None

    original_ids = tuple(matched.alternative_service_ids)
    validated_ids = _validate_alternative_ids(bundle, original_ids)
    unavailable_text = (
        f"Сейчас услуга «{_service_display_name(bundle, token)}» в клинике не оказывается."
    )
    group_approved_text: str | None = None
    if validated_ids and validated_ids == original_ids:
        approved = matched.approved_text.strip()
        if approved:
            group_approved_text = approved

    return AuthoredAlternativePolicyResult(
        requested_service_id=token,
        original_alternative_service_ids=original_ids,
        validated_alternative_service_ids=validated_ids,
        unavailable_text=unavailable_text,
        group_approved_text=group_approved_text,
        unambiguous_topic_id=unambiguous_topic_for_service_ids(bundle, validated_ids),
    )
