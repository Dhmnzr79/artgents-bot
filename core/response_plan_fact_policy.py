"""Pure requested-fact display policy evaluation."""

from __future__ import annotations

from typing import Literal

from contracts.response_plan import CommercialFactCandidate, FactApplicability
from contracts.response_plan_fact_policy import (
    RequestedDisplayPolicy,
    RequestedFactDisplayOutcome,
    RequestedFactPolicyContext,
)
from contracts.response_schema import TargetCommercialFact
from contracts.target_service_content_topic import parse_service_catalog_content_topic
from contracts.response_schema import ResponseSchemaBundle

FactEvaluationPurpose = Literal["requested", "automatic"]


def requested_display_policy_from_fact(
    fact: TargetCommercialFact,
) -> RequestedDisplayPolicy | None:
    raw = getattr(fact, "requested_display_policy", None)
    if raw is None:
        return None
    if isinstance(raw, RequestedDisplayPolicy):
        return raw
    return RequestedDisplayPolicy.model_validate(raw)


def commercial_candidate_display_policy(
    candidate: CommercialFactCandidate,
) -> RequestedDisplayPolicy | None:
    if candidate.requested_display_policy is None:
        return None
    return candidate.requested_display_policy


def evaluate_requested_fact_display(
    *,
    fact: TargetCommercialFact | CommercialFactCandidate,
    context: RequestedFactPolicyContext,
    bundle: ResponseSchemaBundle | None = None,
    evaluation_purpose: FactEvaluationPurpose = "requested",
) -> RequestedFactDisplayOutcome:
    _ = bundle
    if isinstance(fact, CommercialFactCandidate):
        explicit_only = fact.explicit_only
        applicability = fact.applicability
        allowed_topic_ids = fact.allowed_topic_ids
        allowed_service_ids = fact.allowed_service_ids
        requires_implant_scope = fact.requires_implant_scope
        display_policy = commercial_candidate_display_policy(fact)
        active = True
    else:
        explicit_only = fact.kind == "warranty"
        applicability = _schema_applicability(fact)
        allowed_topic_ids = tuple(fact.allowed_topics)
        allowed_service_ids = tuple(fact.allowed_service_ids)
        requires_implant_scope = _requires_implant_scope(fact, bundle)
        display_policy = requested_display_policy_from_fact(fact)
        active = bool(fact.active)

    _ = explicit_only
    _ = applicability

    if not active:
        return "inactive"

    if requires_implant_scope and not context.implant_context_confirmed:
        return "missing_implant_scope"

    has_topic_restriction = bool(allowed_topic_ids)
    has_service_restriction = bool(allowed_service_ids)

    if context.reference_service_id is not None:
        if has_service_restriction and context.reference_service_id not in allowed_service_ids:
            return "restricted_scope"
        if has_topic_restriction:
            if context.resolved_topic_id is None:
                return "restricted_scope"
            if context.resolved_topic_id not in allowed_topic_ids:
                return "restricted_scope"

    if context.response_scope == "service":
        if context.reference_service_id is None:
            return "restricted_scope"
        if has_service_restriction and context.reference_service_id not in allowed_service_ids:
            return "restricted_scope"
        if has_topic_restriction:
            if context.resolved_topic_id is None:
                return "restricted_scope"
            if context.resolved_topic_id not in allowed_topic_ids:
                return "restricted_scope"
        return "allowed"

    if context.response_scope == "topic":
        if has_topic_restriction:
            if context.resolved_topic_id is None:
                return "restricted_scope"
            if context.resolved_topic_id not in allowed_topic_ids:
                return "restricted_scope"
        if has_service_restriction:
            return _extended_display_outcome(
                context=context,
                display_policy=display_policy,
                evaluation_purpose=evaluation_purpose,
            )
        return "allowed"

    if has_topic_restriction or has_service_restriction:
        return _extended_display_outcome(
            context=context,
            display_policy=display_policy,
            evaluation_purpose=evaluation_purpose,
        )

    return "allowed"


def evaluate_automatic_fact_display(
    *,
    fact: CommercialFactCandidate,
    context: RequestedFactPolicyContext,
) -> RequestedFactDisplayOutcome:
    return evaluate_requested_fact_display(
        fact=fact,
        context=context,
        bundle=None,
        evaluation_purpose="automatic",
    )


def _extended_display_outcome(
    *,
    context: RequestedFactPolicyContext,
    display_policy: RequestedDisplayPolicy | None,
    evaluation_purpose: FactEvaluationPurpose,
) -> RequestedFactDisplayOutcome:
    if evaluation_purpose == "automatic":
        return "missing_display_permission"
    if display_policy is None:
        return "missing_display_permission"
    if context.response_scope == "clinic":
        if display_policy.allow_clinic:
            return "allowed"
        if context.resolved_topic_id is not None:
            if context.resolved_topic_id in display_policy.allowed_topic_ids:
                return "allowed"
        return "missing_display_permission"
    if context.resolved_topic_id is not None:
        if context.resolved_topic_id in display_policy.allowed_topic_ids:
            return "allowed"
    return "missing_display_permission"


def _schema_applicability(fact: TargetCommercialFact) -> FactApplicability:
    if fact.allowed_topics and fact.allowed_service_ids:
        return "service_scoped"
    if fact.allowed_topics:
        return "topic_scoped"
    if fact.allowed_service_ids:
        return "service_scoped"
    return "clinic_wide"


def _requires_implant_scope(
    fact: TargetCommercialFact,
    bundle: ResponseSchemaBundle | None,
) -> bool:
    if fact.kind != "warranty":
        return False
    if fact.allowed_topics:
        return len(fact.allowed_topics) == 1 and fact.allowed_topics[0] == "implantation"
    if not fact.allowed_service_ids or bundle is None:
        return False
    topics: set[str] = set()
    for service_id in fact.allowed_service_ids:
        service = bundle.services.get(service_id)
        if service is None:
            continue
        topic = parse_service_catalog_content_topic(service.content_ref)
        if topic is not None:
            topics.add(topic)
    return topics == {"implantation"}


def implant_context_confirmed(context: RequestedFactPolicyContext) -> bool:
    return context.implant_context_confirmed
