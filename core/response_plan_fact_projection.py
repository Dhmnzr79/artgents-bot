"""Requestable fact descriptors and post-Composer fact projection."""

from __future__ import annotations

from datetime import date

from contracts.effective_scope import EffectiveScope
from contracts.response_plan import CommercialFactCandidate, FactApplicability
from contracts.response_plan_composer import RequestableFactDescriptor
from contracts.response_plan_fact_policy import RequestedFactPolicyContext
from contracts.response_plan_post_composer import PostComposerDiagnostic
from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact
from contracts.target_service_content_topic import parse_service_catalog_content_topic
from core.response_plan_fact_policy import (
    evaluate_requested_fact_display,
    requested_display_policy_from_fact,
)


def fact_active_as_of(fact: TargetCommercialFact, as_of: date) -> bool:
    if not fact.active:
        return False
    as_of_iso = as_of.isoformat()
    if fact.active_from is not None and as_of_iso < fact.active_from:
        return False
    if fact.active_until is not None and as_of_iso > fact.active_until:
        return False
    return True


def _fact_applicability(fact: TargetCommercialFact) -> FactApplicability:
    if fact.allowed_topics and fact.allowed_service_ids:
        return "service_scoped"
    if fact.allowed_topics:
        return "topic_scoped"
    if fact.allowed_service_ids:
        return "service_scoped"
    return "clinic_wide"


def _topics_from_service_ids(
    bundle: ResponseSchemaBundle,
    service_ids: tuple[str, ...],
) -> frozenset[str]:
    topics: set[str] = set()
    for service_id in service_ids:
        service = bundle.services.get(service_id)
        if service is None:
            continue
        topic = parse_service_catalog_content_topic(service.content_ref)
        if topic is not None:
            topics.add(topic)
    return frozenset(topics)


def _requires_implant_scope(
    bundle: ResponseSchemaBundle,
    fact: TargetCommercialFact,
) -> bool:
    if fact.kind != "warranty":
        return False
    if fact.allowed_topics:
        return len(fact.allowed_topics) == 1 and fact.allowed_topics[0] == "implantation"
    if not fact.allowed_service_ids:
        return False
    topics = _topics_from_service_ids(bundle, tuple(fact.allowed_service_ids))
    return topics == frozenset({"implantation"})


def build_requestable_fact_descriptors(
    bundle: ResponseSchemaBundle,
    *,
    as_of: date,
) -> tuple[RequestableFactDescriptor, ...]:
    descriptors: list[RequestableFactDescriptor] = []
    for fact_id, fact in sorted(bundle.facts.items()):
        if not fact_active_as_of(fact, as_of):
            continue
        applicability = _fact_applicability(fact)
        display_policy = requested_display_policy_from_fact(fact)
        requires_implant_scope = (
            False
            if applicability == "clinic_wide"
            else _requires_implant_scope(bundle, fact)
        )
        common = {
            "fact_id": fact_id,
            "meaning": fact.catalog_label,
            "explicit_only": fact.kind == "warranty",
            "applicability": applicability,
            "requires_implant_scope": requires_implant_scope,
            "requested_display_policy": display_policy,
        }
        if applicability == "topic_scoped":
            descriptors.append(
                RequestableFactDescriptor(
                    **common,
                    allowed_service_ids=(),
                    allowed_topic_ids=tuple(fact.allowed_topics),
                )
            )
        elif applicability == "service_scoped":
            descriptors.append(
                RequestableFactDescriptor(
                    **common,
                    allowed_service_ids=tuple(fact.allowed_service_ids),
                    allowed_topic_ids=tuple(fact.allowed_topics),
                )
            )
        else:
            descriptors.append(
                RequestableFactDescriptor(
                    **common,
                    allowed_service_ids=(),
                    allowed_topic_ids=(),
                )
            )
    return tuple(descriptors)


def _policy_context(
    *,
    response_scope: str,
    resolved_topic_id: str | None,
    reference_service_id: str | None,
    effective_scope: EffectiveScope | None,
) -> RequestedFactPolicyContext:
    _ = effective_scope
    implant_confirmed = resolved_topic_id == "implantation"
    return RequestedFactPolicyContext(
        response_scope=response_scope,  # type: ignore[arg-type]
        resolved_topic_id=resolved_topic_id,
        reference_service_id=reference_service_id,
        implant_context_confirmed=implant_confirmed,
    )


def resolve_requested_fact_candidates(
    bundle: ResponseSchemaBundle,
    *,
    source_client_id: str,
    requested_fact_ids: tuple[str, ...],
    response_scope: str,
    resolved_topic_id: str | None,
    reference_service_id: str | None,
    effective_scope: EffectiveScope | None = None,
    as_of: date,
) -> tuple[tuple[CommercialFactCandidate, ...], tuple[PostComposerDiagnostic, ...]]:
    candidates: list[CommercialFactCandidate] = []
    diagnostics: list[PostComposerDiagnostic] = []
    accepted_fact_ids: set[str] = set()
    policy_context = _policy_context(
        response_scope=response_scope,
        resolved_topic_id=resolved_topic_id,
        reference_service_id=reference_service_id,
        effective_scope=effective_scope,
    )

    for fact_id in requested_fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is None:
            diagnostics.append(
                PostComposerDiagnostic(code="requested_fact_unavailable", detail=fact_id)
            )
            continue
        if not fact.active:
            diagnostics.append(
                PostComposerDiagnostic(code="requested_fact_unavailable", detail=fact_id)
            )
            continue
        if not fact_active_as_of(fact, as_of):
            diagnostics.append(
                PostComposerDiagnostic(code="requested_fact_expired", detail=fact_id)
            )
            continue
        blocked = False
        for accepted_id in accepted_fact_ids:
            accepted_fact = bundle.facts[accepted_id]
            if (
                fact_id in accepted_fact.incompatible_with
                or accepted_id in fact.incompatible_with
            ):
                blocked = True
                break
        if blocked:
            diagnostics.append(
                PostComposerDiagnostic(code="requested_fact_incompatible", detail=fact_id)
            )
            continue

        outcome = evaluate_requested_fact_display(
            fact=fact,
            context=policy_context,
            bundle=bundle,
            evaluation_purpose="requested",
        )
        if outcome != "allowed":
            diagnostics.append(
                PostComposerDiagnostic(code="requested_fact_inapplicable", detail=fact_id)
            )
            continue

        candidates.append(
            CommercialFactCandidate(
                fact_id=fact_id,
                display_text=fact.text_fact,
                explicit_only=fact.kind == "warranty",
                allowed_roles=("requested_fact",),
                applicability=_fact_applicability(fact),
                allowed_topic_ids=tuple(fact.allowed_topics),
                allowed_service_ids=tuple(fact.allowed_service_ids),
                source_client_id=source_client_id,
                requires_implant_scope=_requires_implant_scope(bundle, fact),
                requested_display_policy=requested_display_policy_from_fact(fact),
            )
        )
        accepted_fact_ids.add(fact_id)

    return tuple(candidates), tuple(diagnostics)
