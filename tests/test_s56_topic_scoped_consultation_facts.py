from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.response_schema_loader import load_response_schema_bundle
from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_composer_request import materialize_target_composer_request
from core.target_marketing_selector import select_target_marketing
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    verify_target_composed_response,
)
from core.target_spec_offline_response_package import assemble_target_spec_offline_response_package
from core.target_topic_scoped_commercial_fact import select_topic_scoped_consultation_fact
from tests.test_target_fullcontext_content_response import (
    DEMO_FULL_CONTEXT,
    MD_ROOT,
    TARGET_ROOT,
    _content_only_policy,
    _pipeline_inputs,
)


TODAY = date(2026, 7, 22)


def _issue(kind: str, span: str) -> TargetSemanticIssue:
    return TargetSemanticIssue(kind=kind, offending_span=span)  # type: ignore[arg-type]


def _topic_fact(
    fact_id: str,
    *,
    topics: list[str],
    active: bool = True,
    active_until: str | None = "2026-12-31",
    services: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": fact_id,
        "kind": "promo",
        "catalog_label": f"Catalog topic for {fact_id}",
        "text_fact": f"Exact {fact_id}.",
        "render_mode": "natural",
        "active": active,
        "allowed_service_ids": services or [],
        "allowed_topics": topics,
        "incompatible_with": [],
        "active_until": active_until,
    }


def _prosthetics_only_bundle() -> ResponseSchemaBundle:
    demo = load_response_schema_bundle(TARGET_ROOT)
    facts = {fact_id: fact.model_dump() for fact_id, fact in demo.facts.items()}
    prosthetics_only = dict(facts["free_implant_consult"])
    prosthetics_only["allowed_topics"] = ["prosthetics"]
    facts["free_implant_consult"] = prosthetics_only
    payload = demo.model_dump()
    payload["facts"] = facts
    return ResponseSchemaBundle.model_validate(payload)


class FreeConsultSemanticBackend:
    def assess(self, invocation: object, /) -> TargetSemanticAssessment:
        payload = json.loads(invocation.primary_evidence_json)  # type: ignore[attr-defined]
        has_fact = any(item.get("kind") == "commercial_fact" for item in payload)
        text = invocation.candidate_text.lower()  # type: ignore[attr-defined]
        if "бесплат" in text and not has_fact:
            return TargetSemanticAssessment(
                issues=(_issue("unsupported_clinic_claim", "бесплатная"),)
            )
        return TargetSemanticAssessment()


def _assemble_fullcontext_request(
    *,
    bundle: ResponseSchemaBundle,
    turn_topic: str,
    allowed_topics: tuple[str, ...] = ("implantation",),
    include_consultation_close: bool = True,
) -> object:
    inputs = _pipeline_inputs(bundle=bundle)
    policy = _content_only_policy(allowed_topics=allowed_topics)
    spec = build_target_response_spec(policy)
    bound = assemble_target_spec_offline_response_package(
        bundle,
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        spec=spec,
        brand_term=None,
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context="service",
        today=TODAY,
        md_root=MD_ROOT,
        include_initial_block=False,
        include_consultation_close=include_consultation_close,
        include_cta=False,
        turn_topic=turn_topic,
    )
    return materialize_target_composer_request(
        bound,
        bundle,
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Нужна консультация.",
        md_root=MD_ROOT,
    )


def test_implantation_topic_includes_demo_free_consult_in_primary_evidence() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    request = _assemble_fullcontext_request(bundle=bundle, turn_topic="implantation")
    commercial = [
        block for block in request.evidence_blocks if block.kind == "commercial_fact"
    ]
    assert len(commercial) == 1
    assert commercial[0].ref == "fact:free_implant_consult"
    assert "бесплат" in commercial[0].text.lower()


def test_prosthetics_only_fact_not_selected_for_implantation_topic() -> None:
    bundle = _prosthetics_only_bundle()
    selected = select_topic_scoped_consultation_fact(
        bundle,
        turn_topic="implantation",
        today=TODAY,
    )
    assert selected is None
    request = _assemble_fullcontext_request(
        bundle=bundle,
        turn_topic="implantation",
        allowed_topics=("implantation",),
    )
    assert all(block.kind != "commercial_fact" for block in request.evidence_blocks)


def test_prosthetics_only_fact_selected_for_prosthetics_topic() -> None:
    bundle = _prosthetics_only_bundle()
    selected = select_topic_scoped_consultation_fact(
        bundle,
        turn_topic="prosthetics",
        today=TODAY,
    )
    assert selected is not None
    assert selected.id == "free_implant_consult"
    request = _assemble_fullcontext_request(
        bundle=bundle,
        turn_topic="prosthetics",
        allowed_topics=("prosthetics",),
    )
    commercial = [
        block for block in request.evidence_blocks if block.kind == "commercial_fact"
    ]
    assert len(commercial) == 1
    assert commercial[0].ref == "fact:free_implant_consult"


@pytest.mark.parametrize(
    ("fact_id", "turn_topic", "today"),
    [
        ("inactive_topic_consult", "implantation", TODAY),
        ("expired_topic_consult", "implantation", TODAY),
        ("prosthetics_topic_consult", "implantation", TODAY),
    ],
)
def test_ineligible_topic_facts_are_not_selected(
    fact_id: str,
    turn_topic: str,
    today: date,
) -> None:
    bundle = _prosthetics_only_bundle()
    facts = {key: TargetCommercialFact.model_validate(value) for key, value in bundle.model_dump()["facts"].items()}
    facts[fact_id] = TargetCommercialFact.model_validate(
        _topic_fact(
            fact_id,
            topics=["prosthetics"] if fact_id == "prosthetics_topic_consult" else ["implantation"],
            active=fact_id != "inactive_topic_consult",
            active_until="2026-01-01" if fact_id == "expired_topic_consult" else "2026-12-31",
        )
    )
    payload = bundle.model_dump()
    payload["facts"] = {key: fact.model_dump() for key, fact in facts.items()}
    custom = ResponseSchemaBundle.model_validate(payload)
    assert (
        select_topic_scoped_consultation_fact(
            custom,
            turn_topic=turn_topic,
            today=today,
        )
        is None
    )


def test_free_consult_claim_without_structured_fact_is_rejected() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    request = _assemble_fullcontext_request(
        bundle=bundle,
        turn_topic="clinic",
        allowed_topics=("clinic",),
    )
    assert all(block.kind != "commercial_fact" for block in request.evidence_blocks)
    unverified = TargetUnverifiedComposedResponse(
        text="Сейчас можно пройти бесплатную консультацию.",
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError):
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=DEMO_FULL_CONTEXT,
            semantic_backend=FreeConsultSemanticBackend(),
        )


def test_topic_only_fact_is_not_selected_via_service_marketing_path() -> None:
    demo = load_response_schema_bundle(TARGET_ROOT)
    facts = {fact_id: fact.model_dump() for fact_id, fact in demo.facts.items()}
    facts["topic_only_consult"] = _topic_fact("topic_only_consult", topics=["prosthetics"])
    bundle = ResponseSchemaBundle.model_validate({**demo.model_dump(), "facts": facts})
    doctors = _pipeline_inputs(bundle=bundle)["doctor_catalog"]
    external = _pipeline_inputs(bundle=bundle)["external_index"]
    selection = select_target_marketing(
        bundle,
        doctors,  # type: ignore[arg-type]
        external,  # type: ignore[arg-type]
        semantic_context="service",
        service_id="all_on_4",
        today=TODAY,
        include_initial_block=True,
    )
    assert "fact:topic_only_consult" not in selection.selected_refs


def test_service_specific_marketing_path_still_selects_service_scoped_facts() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(
        TargetResponsePolicyRequest.model_validate(
            {
                "response_mode": "answer",
                "service_id": "all_on_4",
                "tone_key": "commercial_warm",
                "allowed_topics": ("implantation",),
                "forbidden_topics": ("diagnosis", "personal_eligibility"),
                "required_fact_ids": ("free_implant_consult",),
                "requested_components": ("content",),
                "primary_component": None,
                "allow_marketing_facts": True,
                "allow_consultation_close": True,
                "allow_cta": False,
            }
        )
    )
    bound = assemble_target_spec_offline_response_package(
        bundle,
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        spec=spec,
        brand_term=None,
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context="service",
        today=TODAY,
        md_root=MD_ROOT,
        include_initial_block=True,
        include_consultation_close=True,
        include_cta=False,
    )
    assert "free_implant_consult" in bound.package.plan.commercial_fact_ids
