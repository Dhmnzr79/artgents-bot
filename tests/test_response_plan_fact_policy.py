from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from contracts.response_plan import CommercialFactCandidate
from contracts.response_plan_fact_policy import RequestedFactPolicyContext
from contracts.response_schema import RequestedDisplayPolicy, TargetCommercialFact
from core.response_plan_fact_policy import (
    evaluate_automatic_fact_display,
    evaluate_requested_fact_display,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from tests.test_response_plan_contract import compose, fact, make_plan


def _installment_fact() -> TargetCommercialFact:
    return TargetCommercialFact(
        id="installment_fixture",
        kind="payment",
        catalog_label="Рассрочка",
        text_fact="Рассрочка на 12 месяцев доступна для имплантации.",
        render_mode="strict",
        allowed_service_ids=["classic", "all_on_4"],
        requested_display_policy=RequestedDisplayPolicy(
            allow_clinic=True,
            allowed_topic_ids=("implantation",),
            canonical_text_is_scope_qualified=True,
        ),
    )


def _warranty_fact() -> TargetCommercialFact:
    return TargetCommercialFact(
        id="warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия",
        text_fact="Гарантия на имплантацию 1 год.",
        render_mode="strict",
        allowed_topics=["implantation"],
        requested_display_policy=RequestedDisplayPolicy(
            allow_clinic=False,
            allowed_topic_ids=("implantation",),
            canonical_text_is_scope_qualified=True,
        ),
    )


def test_clinic_installment_allowed_with_display_permission() -> None:
    outcome = evaluate_requested_fact_display(
        fact=_installment_fact(),
        context=RequestedFactPolicyContext(response_scope="clinic"),
    )
    assert outcome == "allowed"


def test_service_scoped_without_permission_blocked_at_clinic() -> None:
    fact_model = _installment_fact().model_copy(update={"requested_display_policy": None})
    outcome = evaluate_requested_fact_display(
        fact=fact_model,
        context=RequestedFactPolicyContext(response_scope="clinic"),
    )
    assert outcome == "missing_display_permission"


def test_topic_warranty_through_resolver_and_renderer() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_topic_id="implantation",
        selected_service_id=None,
        commercial_facts=(
            fact(
                "warranty_fixture",
                text="Гарантия на имплантацию 1 год.",
                roles=("requested_fact",),
                applicability="topic_scoped",
                allowed_topic_ids=("implantation",),
                explicit_only=True,
                requires_implant_scope=True,
                requested_display_policy=RequestedDisplayPolicy(
                    allow_clinic=False,
                    allowed_topic_ids=("implantation",),
                    canonical_text_is_scope_qualified=True,
                ),
            ),
        ),
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("warranty_fixture",), patient_text="А гарантия?"),
    )
    text = render_response_text(resolved)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("warranty_fixture",)
    assert "Гарантия на имплантацию 1 год." in text


def test_clinic_installment_through_resolver_and_renderer() -> None:
    plan = make_plan(
        response_scope="clinic",
        selected_service_id=None,
        selected_topic_id=None,
        commercial_facts=(
            fact(
                "installment_fixture",
                text="Рассрочка на 12 месяцев доступна для имплантации.",
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("classic", "all_on_4"),
                requested_display_policy=RequestedDisplayPolicy(
                    allow_clinic=True,
                    allowed_topic_ids=("implantation",),
                    canonical_text_is_scope_qualified=True,
                ),
            ),
        ),
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("installment_fixture",), patient_text="Есть рассрочка?"),
    )
    text = render_response_text(resolved)
    assert "Рассрочка на 12 месяцев" in text


def test_unrelated_explicit_service_blocks_scoped_fact() -> None:
    outcome = evaluate_requested_fact_display(
        fact=_installment_fact(),
        context=RequestedFactPolicyContext(
            response_scope="service",
            resolved_topic_id="implantation",
            reference_service_id="professional_whitening",
        ),
    )
    assert outcome == "restricted_scope"


def _service_scoped_implant_warranty_fact() -> TargetCommercialFact:
    return TargetCommercialFact(
        id="implant_warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия на имплантацию",
        text_fact="Гарантия на имплантацию 1 год.",
        render_mode="strict",
        allowed_service_ids=["all_on_4", "all_on_6"],
        requested_display_policy=RequestedDisplayPolicy(
            allow_clinic=False,
            allowed_topic_ids=("implantation",),
            canonical_text_is_scope_qualified=True,
        ),
    )


def test_service_scoped_warranty_without_display_permission_blocked_at_topic() -> None:
    fact_model = _service_scoped_implant_warranty_fact().model_copy(
        update={"requested_display_policy": None}
    )
    outcome = evaluate_requested_fact_display(
        fact=fact_model,
        context=RequestedFactPolicyContext(
            response_scope="topic",
            resolved_topic_id="implantation",
            implant_context_confirmed=True,
        ),
    )
    assert outcome == "missing_display_permission"


def test_service_scoped_warranty_with_display_permission_at_topic() -> None:
    outcome = evaluate_requested_fact_display(
        fact=_service_scoped_implant_warranty_fact(),
        context=RequestedFactPolicyContext(
            response_scope="topic",
            resolved_topic_id="implantation",
            implant_context_confirmed=True,
        ),
    )
    assert outcome == "allowed"


def test_service_scoped_warranty_through_resolver_and_renderer() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="implantation",
        commercial_facts=(
            fact(
                "implant_warranty_fixture",
                text="Гарантия на имплантацию 1 год.",
                roles=("requested_fact",),
                applicability="service_scoped",
                allowed_service_ids=("all_on_4", "all_on_6"),
                explicit_only=True,
                requires_implant_scope=True,
                requested_display_policy=RequestedDisplayPolicy(
                    allow_clinic=False,
                    allowed_topic_ids=("implantation",),
                    canonical_text_is_scope_qualified=True,
                ),
            ),
        ),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
        required_offer_conditions=(),
    )
    resolved = resolve_response_plan(
        plan,
        compose(
            requested_fact_ids=("implant_warranty_fixture",),
            patient_text="А гарантия?",
        ),
    )
    text = render_response_text(resolved)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("implant_warranty_fixture",)
    assert "Гарантия на имплантацию 1 год." in text


def test_automatic_promo_blocked_by_requested_display_permission_at_clinic() -> None:
    candidate = CommercialFactCandidate(
        fact_id="installment_fixture",
        display_text="Рассрочка на 12 месяцев доступна для имплантации.",
        allowed_roles=("promo",),
        applicability="service_scoped",
        allowed_service_ids=("classic", "all_on_4"),
        source_client_id="demo",
        requested_display_policy=RequestedDisplayPolicy(
            allow_clinic=True,
            allowed_topic_ids=("implantation",),
            canonical_text_is_scope_qualified=True,
        ),
    )
    outcome = evaluate_automatic_fact_display(
        fact=candidate,
        context=RequestedFactPolicyContext(response_scope="clinic"),
    )
    assert outcome == "missing_display_permission"
