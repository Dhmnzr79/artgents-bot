"""Composer decision authority builder from current-client bundle material."""

from __future__ import annotations

from datetime import date

from contracts.answer_plan import AspectKind
from contracts.response_plan import all_allowed_route_mode_pairs
from contracts.response_plan_composer import (
    ComposerDecisionAuthority,
    RequestableFactDescriptor,
    ServiceDescriptor,
)
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.target_service_content_topic import parse_service_catalog_content_topic
from core.response_plan_fact_projection import (
    build_requestable_fact_descriptors,
    fact_active_as_of,
)


def collect_allowed_topic_ids(
    material: PostComposerMaterialAuthority,
) -> tuple[str, ...]:
    return _collect_allowed_topic_ids(material)


def _collect_allowed_topic_ids(
    material: PostComposerMaterialAuthority,
) -> tuple[str, ...]:
    topics: set[str] = set()
    bundle = material.bundle
    for service in bundle.services.values():
        if not service.active:
            continue
        topic = parse_service_catalog_content_topic(service.content_ref)
        if topic is not None:
            topics.add(topic)
    for fact in bundle.facts.values():
        if not fact.active:
            continue
        topics.update(fact.allowed_topics)
    return tuple(sorted(topics))


def _collect_known_inactive_service_ids(
    material: PostComposerMaterialAuthority,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            service_id
            for service_id, service in material.bundle.services.items()
            if not service.active
        )
    )


def _build_known_inactive_service_descriptors(
    material: PostComposerMaterialAuthority,
) -> tuple[ServiceDescriptor, ...]:
    descriptors: list[ServiceDescriptor] = []
    for service_id, service in sorted(material.bundle.services.items()):
        if service.active:
            continue
        descriptors.append(
            ServiceDescriptor(
                service_id=service_id,
                label=service.name,
                aliases=tuple(service.aliases),
                short_meaning=service.family,
            )
        )
    return tuple(descriptors)


def _build_service_descriptors(
    material: PostComposerMaterialAuthority,
) -> tuple[ServiceDescriptor, ...]:
    descriptors: list[ServiceDescriptor] = []
    for service_id, service in sorted(material.bundle.services.items()):
        if not service.active:
            continue
        descriptors.append(
            ServiceDescriptor(
                service_id=service_id,
                label=service.name,
                aliases=tuple(service.aliases),
                short_meaning=service.family,
            )
        )
    return tuple(descriptors)


def build_composer_decision_authority(
    material: PostComposerMaterialAuthority,
    *,
    allowed_source_refs: tuple[str, ...],
    history_turn_count: int,
    active_session_service_id: str | None,
    as_of: date,
) -> ComposerDecisionAuthority:
    if history_turn_count < 0:
        raise ValueError("history_turn_count_negative")

    allowed_aspect_ids: tuple[AspectKind, ...] = (
        "price",
        "payment",
        "warranty",
        "pain",
        "included",
        "duration",
        "comparison",
        "stages",
        "overview",
        "contacts",
        "contact_phone",
        "contact_address",
        "contact_parking",
        "contact_hours",
        "contact_whatsapp",
        "service_availability",
    )

    requestable_facts = build_requestable_fact_descriptors(
        material.bundle,
        as_of=as_of,
    )

    return ComposerDecisionAuthority(
        source_client_id=material.source_client_id,
        allowed_route_modes=all_allowed_route_mode_pairs(),
        allowed_topic_ids=_collect_allowed_topic_ids(material),
        service_descriptors=_build_service_descriptors(material),
        allowed_source_refs=allowed_source_refs,
        bypass=False,
        active_session_service_id=active_session_service_id,
        context_strategy="full_context",
        history_turn_count=history_turn_count,
        allowed_aspect_ids=allowed_aspect_ids,
        requestable_facts=requestable_facts,
        known_inactive_service_ids=_collect_known_inactive_service_ids(material),
        known_inactive_service_descriptors=_build_known_inactive_service_descriptors(material),
    )


def fact_descriptor_ids(
    descriptors: tuple[RequestableFactDescriptor, ...],
) -> frozenset[str]:
    return frozenset(descriptor.fact_id for descriptor in descriptors)


def active_fact_ids_as_of(
    material: PostComposerMaterialAuthority,
    *,
    as_of: date,
) -> frozenset[str]:
    active: set[str] = set()
    for fact_id, fact in material.bundle.facts.items():
        if fact_active_as_of(fact, as_of):
            active.add(fact_id)
    return frozenset(active)
