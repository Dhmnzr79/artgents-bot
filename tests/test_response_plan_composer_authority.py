from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.target_service_content_topic import parse_service_catalog_content_topic
from core.response_plan_composer_authority import (
    active_fact_ids_as_of,
    build_composer_decision_authority,
    fact_descriptor_ids,
)
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
AS_OF = date(2026, 8, 15)


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle):
    return PostComposerMaterialAuthority(
        source_client_id="demo",
        bundle=demo_bundle,
    )


def test_authority_includes_known_inactive_service_ids(demo_material) -> None:
    bundle = demo_material.bundle.model_copy(deep=True)
    bundle.services["all_on_6"] = bundle.services["all_on_6"].model_copy(update={"active": False})
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    authority = build_composer_decision_authority(
        material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    assert "all_on_6" in authority.known_inactive_service_ids
    assert "all_on_4" not in authority.known_inactive_service_ids


def test_service_descriptors_cover_all_active_services(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=("clinic__info__contacts.md",),
        history_turn_count=1,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    active_service_ids = {
        service_id
        for service_id, service in demo_material.bundle.services.items()
        if service.active
    }
    descriptor_ids = {descriptor.service_id for descriptor in authority.service_descriptors}
    assert descriptor_ids == active_service_ids
    for descriptor in authority.service_descriptors:
        service = demo_material.bundle.services[descriptor.service_id]
        assert descriptor.label == service.name
        assert descriptor.aliases == tuple(service.aliases)
        assert descriptor.short_meaning == service.family


def test_topic_ids_from_services_and_facts(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    expected_topics: set[str] = set()
    for service in demo_material.bundle.services.values():
        if not service.active:
            continue
        topic = parse_service_catalog_content_topic(service.content_ref)
        if topic is not None:
            expected_topics.add(topic)
    for fact in demo_material.bundle.facts.values():
        expected_topics.update(fact.allowed_topics)
    assert frozenset(authority.allowed_topic_ids) == expected_topics
    assert "implantation" in authority.allowed_topic_ids


def test_no_default_implantation_topic(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    assert authority.allowed_topic_ids == tuple(sorted(set(authority.allowed_topic_ids)))


def test_requestable_facts_use_catalog_label_not_text_fact(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    assert authority.requestable_facts
    for descriptor in authority.requestable_facts:
        fact = demo_material.bundle.facts[descriptor.fact_id]
        assert descriptor.meaning == fact.catalog_label
        assert descriptor.meaning != fact.text_fact


def test_inactive_and_expired_facts_excluded(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=date(2027, 1, 1),
    )
    ids = fact_descriptor_ids(authority.requestable_facts)
    assert "free_implant_consult" not in ids


def test_warranty_explicit_only_without_hardcoded_id(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    warranty = next(
        descriptor
        for descriptor in authority.requestable_facts
        if demo_material.bundle.facts[descriptor.fact_id].kind == "warranty"
    )
    assert warranty.explicit_only is True
    assert warranty.requires_implant_scope is True


def test_nested_current_client_source_refs(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(
            "clinic__info__contacts.md",
            "implantation__service__classic.md",
        ),
        history_turn_count=2,
        active_session_service_id="classic",
        as_of=AS_OF,
    )
    assert authority.allowed_source_refs == (
        "clinic__info__contacts.md",
        "implantation__service__classic.md",
    )
    assert authority.active_session_service_id == "classic"


def test_injected_as_of_controls_eligibility(demo_material) -> None:
    fresh = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    expired = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=date(2027, 1, 1),
    )
    assert "free_implant_consult" in fact_descriptor_ids(fresh.requestable_facts)
    assert "free_implant_consult" not in fact_descriptor_ids(expired.requestable_facts)


def test_active_fact_ids_as_of_matches_descriptors(demo_material) -> None:
    authority = build_composer_decision_authority(
        demo_material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    assert fact_descriptor_ids(authority.requestable_facts) == active_fact_ids_as_of(
        demo_material,
        as_of=AS_OF,
    )
