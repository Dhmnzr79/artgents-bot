from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    build_doctor_source_refs,
    validate_doctor_catalog_external_refs,
)
from contracts.response_schema import TargetStrategyMatch
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.service_consultation import validate_service_consultation_refs
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_response_policy import build_target_response_spec
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"


def _real_inputs() -> dict[str, object]:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    doctor_index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    assert validate_doctor_catalog_external_refs(doctors, doctor_index) is None
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    assert validate_response_schema_external_refs(bundle, external_index) is None
    consultations = build_service_consultation_values(MD_ROOT)
    assert validate_service_consultation_refs(consultations, bundle.services) is None
    return {
        "bundle": bundle,
        "doctor_catalog": doctors,
        "external_index": external_index,
        "consultation_values": consultations,
        "brand_term": None,
        "strategy_context": TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        "semantic_context": "service",
        "today": date(2026, 7, 22),
        "md_root": MD_ROOT,
        "include_initial_block": False,
        "include_consultation_close": False,
        "include_cta": False,
    }


def _spec(
    components: tuple[str, ...],
    *,
    primary: str | None,
    allow_marketing: bool = False,
    allow_consultation: bool = False,
    allow_cta: bool = False,
    required_fact_ids: tuple[str, ...] = (),
):
    request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": "all_on_4",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation",),
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": required_fact_ids,
            "requested_components": components,
            "primary_component": primary,
            "allow_marketing_facts": allow_marketing,
            "allow_consultation_close": allow_consultation,
            "allow_cta": allow_cta,
        }
    )
    return build_target_response_spec(request)


def _assemble(spec, **overrides: object):
    inputs = _real_inputs()
    inputs["spec"] = spec
    inputs.update(overrides)
    return assemble_target_spec_offline_response_package(**inputs)  # type: ignore[arg-type]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_content_only_plan_closes_price_and_doctors_candidates() -> None:
    result = _assemble(_spec(("content",), primary=None))
    assert result.package.materials.offers
    assert result.package.materials.doctors
    assert result.package.plan.primary_content_ref == (
        "implantation__service__all_on_4.md"
    )
    assert result.package.plan.offer_ids == ()
    assert result.package.plan.doctor_ids == ()
    assert result.package.selected_followups.source == "content"
    assert result.package.selected_followups.content
    assert result.package.selected_followups.price == ()


def test_real_price_and_doctor_plans_are_separately_closed() -> None:
    price = _assemble(_spec(("price",), primary=None))
    assert price.package.materials.selected_content_ref is not None
    assert price.package.materials.doctors
    assert price.package.plan.primary_content_ref is None
    assert price.package.plan.offer_ids
    assert price.package.plan.doctor_ids == ()
    assert price.package.selected_followups.source == "price"

    doctors = _assemble(_spec(("doctors",), primary=None))
    assert doctors.package.materials.offers
    assert doctors.package.materials.selected_content_ref is not None
    assert doctors.package.plan.primary_content_ref is None
    assert doctors.package.plan.offer_ids == ()
    assert doctors.package.plan.doctor_ids
    assert doctors.package.selected_followups.source is None


def test_real_permissions_gate_marketing_consultation_and_selected_cta() -> None:
    spec = _spec(
        ("content", "price", "doctors"),
        primary="content",
        allow_marketing=True,
        allow_consultation=True,
        allow_cta=True,
    )
    result = _assemble(
        spec,
        include_initial_block=True,
        include_consultation_close=True,
        include_cta=True,
    )
    assert result.package.plan.commercial_fact_ids
    assert result.package.plan.consultation_content_ref is None
    assert result.selected_cta_key == result.package.plan.cta_key

    consultation = _assemble(
        _spec(
            ("content",),
            primary=None,
            allow_consultation=True,
        ),
        include_consultation_close=True,
    )
    assert consultation.package.plan.consultation_content_ref == (
        "implantation__service__all_on_4.md"
    )

    narrow = _assemble(spec)
    assert narrow.package.plan.commercial_fact_ids == ()
    assert narrow.package.plan.external_source_refs == ()
    assert narrow.package.plan.consultation_content_ref is None
    assert narrow.selected_cta_key is None
    assert narrow.package.plan.cta_key


def test_topic_and_required_fact_scope_is_carried_but_not_claimed_enforced() -> None:
    spec = _spec(
        ("content",),
        primary=None,
        required_fact_ids=("future_fact_coverage",),
    )
    result = _assemble(spec)
    assert result.spec is spec
    assert result.spec.allowed_topics == ("implantation",)
    assert result.spec.forbidden_topics == ("diagnosis", "personal_eligibility")
    assert result.spec.required_fact_ids == ("future_fact_coverage",)
    assert "future_fact_coverage" not in result.package.plan.commercial_fact_ids


def test_real_integration_does_not_write_demo_files() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    _assemble(_spec(("content",), primary=None))
    assert {path: _sha256(path) for path in paths} == before
