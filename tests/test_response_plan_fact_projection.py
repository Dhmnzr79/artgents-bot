from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan_fact_policy import RequestedDisplayPolicy
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_schema import TargetCommercialFact
from core.response_plan_composer_authority import build_composer_decision_authority
from core.response_plan_composer_contract import build_composer_policy_sidecar
from core.response_plan_fact_projection import (
    build_requestable_fact_descriptors,
    resolve_requested_fact_candidates,
)
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
AS_OF = date(2026, 8, 15)


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def test_general_installment_requires_display_permission(demo_bundle) -> None:
    candidates, diagnostics = resolve_requested_fact_candidates(
        demo_bundle,
        source_client_id="demo",
        requested_fact_ids=("installment_12",),
        response_scope="clinic",
        resolved_topic_id=None,
        reference_service_id=None,
        as_of=AS_OF,
    )
    assert candidates == ()
    assert any(d.code == "requested_fact_inapplicable" for d in diagnostics)


def test_installment_with_synthetic_display_permission(demo_bundle) -> None:
    bundle = demo_bundle.model_copy(deep=True)
    bundle.facts["installment_fixture"] = TargetCommercialFact(
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
    candidates, diagnostics = resolve_requested_fact_candidates(
        bundle,
        source_client_id="demo",
        requested_fact_ids=("installment_fixture",),
        response_scope="clinic",
        resolved_topic_id=None,
        reference_service_id=None,
        as_of=AS_OF,
    )
    assert diagnostics == ()
    assert len(candidates) == 1


def test_implant_warranty_without_display_permission_blocked_at_topic(demo_bundle) -> None:
    candidates, diagnostics = resolve_requested_fact_candidates(
        demo_bundle,
        source_client_id="demo",
        requested_fact_ids=("implant_warranty",),
        response_scope="topic",
        resolved_topic_id="implantation",
        reference_service_id=None,
        effective_scope=__import__(
            "contracts.effective_scope", fromlist=["EffectiveScope"]
        ).EffectiveScope(topic="implantation", extent="unknown"),
        as_of=AS_OF,
    )
    assert candidates == ()
    assert any(d.code == "requested_fact_inapplicable" for d in diagnostics)


def test_implant_warranty_with_approved_display_policy_at_topic(demo_bundle) -> None:
    bundle = demo_bundle.model_copy(deep=True)
    original = bundle.facts["implant_warranty"]
    bundle.facts["implant_warranty"] = original.model_copy(
        update={
            "requested_display_policy": RequestedDisplayPolicy(
                allow_clinic=False,
                allowed_topic_ids=("implantation",),
                canonical_text_is_scope_qualified=True,
            )
        }
    )
    candidates, diagnostics = resolve_requested_fact_candidates(
        bundle,
        source_client_id="demo",
        requested_fact_ids=("implant_warranty",),
        response_scope="topic",
        resolved_topic_id="implantation",
        reference_service_id=None,
        as_of=AS_OF,
    )
    assert diagnostics == ()
    assert candidates[0].fact_id == "implant_warranty"


def test_warranty_suppressed_for_unrelated_explicit_service(demo_bundle) -> None:
    candidates, diagnostics = resolve_requested_fact_candidates(
        demo_bundle,
        source_client_id="demo",
        requested_fact_ids=("implant_warranty",),
        response_scope="service",
        resolved_topic_id="caries",
        reference_service_id="caries",
        as_of=AS_OF,
    )
    assert candidates == ()
    assert any(d.code == "requested_fact_inapplicable" for d in diagnostics)


def test_clinic_wide_fact_descriptor_sidecar_and_authority(demo_bundle) -> None:
    bundle = demo_bundle.model_copy(deep=True)
    bundle.facts["clinic_wide_fixture"] = TargetCommercialFact(
        id="clinic_wide_fixture",
        kind="payment",
        catalog_label="Общая информация",
        text_fact="Оплата картой доступна в клинике.",
        render_mode="strict",
    )
    descriptors = build_requestable_fact_descriptors(bundle, as_of=AS_OF)
    descriptor = next(item for item in descriptors if item.fact_id == "clinic_wide_fixture")
    assert descriptor.applicability == "clinic_wide"
    assert descriptor.requires_implant_scope is False
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    authority = build_composer_decision_authority(
        material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=AS_OF,
    )
    sidecar = build_composer_policy_sidecar(authority)
    sidecar_descriptor = next(
        item for item in sidecar.requestable_facts if item.fact_id == "clinic_wide_fixture"
    )
    assert sidecar_descriptor.applicability == "clinic_wide"
    assert sidecar_descriptor.requested_display_policy is None


def test_projection_candidate_through_resolver_and_renderer(demo_bundle) -> None:
    from core.response_plan_resolver import resolve_response_plan
    from core.response_text_renderer import render_response_text
    from tests.test_response_plan_contract import compose, make_plan

    bundle = demo_bundle.model_copy(deep=True)
    original = bundle.facts["implant_warranty"]
    bundle.facts["implant_warranty"] = original.model_copy(
        update={
            "requested_display_policy": RequestedDisplayPolicy(
                allow_clinic=False,
                allowed_topic_ids=("implantation",),
                canonical_text_is_scope_qualified=True,
            )
        }
    )
    candidates, diagnostics = resolve_requested_fact_candidates(
        bundle,
        source_client_id="demo",
        requested_fact_ids=("implant_warranty",),
        response_scope="topic",
        resolved_topic_id="implantation",
        reference_service_id=None,
        as_of=AS_OF,
    )
    assert diagnostics == ()
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="implantation",
        commercial_facts=candidates,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
        required_offer_conditions=(),
    )
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("implant_warranty",), patient_text="А гарантия?"),
    )
    text = render_response_text(resolved)
    assert resolved.finalized_commercial_ids.requested_fact_ids == ("implant_warranty",)
    assert text


def test_arbitrary_warranty_id_descriptor_is_explicit_only(demo_bundle) -> None:
    bundle = demo_bundle.model_copy(deep=True)
    bundle.facts["custom_warranty_fixture"] = TargetCommercialFact(
        id="custom_warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия",
        text_fact="Гарантия 1 год по договору.",
        render_mode="strict",
        allowed_service_ids=["all_on_4"],
    )
    descriptors = build_requestable_fact_descriptors(bundle, as_of=AS_OF)
    descriptor = next(item for item in descriptors if item.fact_id == "custom_warranty_fixture")
    assert descriptor.explicit_only is True


def test_arbitrary_warranty_projected_candidate_is_explicit_only(demo_bundle) -> None:
    from core.response_plan_fact_projection import project_commercial_fact_candidate

    bundle = demo_bundle.model_copy(deep=True)
    bundle.facts["custom_warranty_fixture"] = TargetCommercialFact(
        id="custom_warranty_fixture",
        kind="warranty",
        catalog_label="Гарантия",
        text_fact="Гарантия 1 год по договору.",
        render_mode="strict",
        allowed_service_ids=["all_on_4"],
    )
    fact = bundle.facts["custom_warranty_fixture"]
    candidate = project_commercial_fact_candidate(
        bundle,
        fact,
        source_client_id="demo",
        allowed_roles=("requested_fact",),
    )
    assert candidate.explicit_only is True
