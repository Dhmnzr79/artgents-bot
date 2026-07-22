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
from core.target_scoped_response_evidence import build_target_scoped_response_evidence
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"


def _real_bound_package():
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
    request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": "all_on_4",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation", "doctors"),
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": ("free_implant_consult",),
            "requested_components": ("content", "price", "doctors"),
            "primary_component": "content",
            "allow_marketing_facts": True,
            "allow_consultation_close": True,
            "allow_cta": True,
        }
    )
    spec = build_target_response_spec(request)
    bound = assemble_target_spec_offline_response_package(
        bundle,
        doctors,
        external_index,
        consultations,
        spec=spec,
        brand_term=None,
        strategy_context=TargetStrategyMatch(
            family="implantology",
            extent="full_arch",
        ),
        semantic_context="service",
        today=date(2026, 7, 22),
        md_root=MD_ROOT,
        include_initial_block=True,
        include_consultation_close=True,
        include_cta=True,
        shown_fact_ids=("installment_12", "implant_same_day_discount"),
    )
    return spec, bound


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_scope_is_closed_and_covers_selected_fact() -> None:
    spec, bound = _real_bound_package()
    result = build_target_scoped_response_evidence(bound, md_root=MD_ROOT)

    assert result.spec is spec
    assert result.service_id == "all_on_4"
    assert result.primary_content_ref == "implantation__service__all_on_4.md"
    assert result.offer_ids == (
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    )
    assert result.doctor_ids == (
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    )
    assert result.commercial_fact_ids == ("free_implant_consult",)
    assert result.covered_fact_ids == ("free_implant_consult",)
    assert result.consultation_content_ref == (
        "implantation__service__all_on_4.md"
    )
    assert result.selected_cta_key == "plan"
    assert result.selected_followups.source == "content"
    assert [item.id for item in result.selected_followups.content] == [
        "komu-podhodit-all-on-4",
        "kak-rabotaet-metod-all-on-4",
        "ogranicheniya-i-uhod",
    ]
    assert all(
        record.topics == ("implantation", "doctors")
        for record in result.scope_records
        if record.ref.startswith("doctor:")
    )
    assert not hasattr(result, "package")
    assert "installment_12" not in result.commercial_fact_ids
    assert "implant_same_day_discount" not in result.commercial_fact_ids


def test_real_scope_build_is_read_only_for_demo_client() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _spec, bound = _real_bound_package()
    build_target_scoped_response_evidence(bound, md_root=MD_ROOT)

    assert {path: _sha256(path) for path in paths} == before
