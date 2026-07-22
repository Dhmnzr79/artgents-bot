from __future__ import annotations

import hashlib
import json
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
from core.target_composer_request import materialize_target_composer_request
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
    spec = build_target_response_spec(
        TargetResponsePolicyRequest.model_validate(
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
    )
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
    return {
        "bound_package": bound,
        "bundle": bundle,
        "doctor_catalog": doctors,
        "consultation_values": consultations,
        "user_message": "Расскажите про All-on-4, цену и врачей",
        "md_root": MD_ROOT,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_composer_request_materializes_exact_selected_sources() -> None:
    inputs = _real_inputs()
    bound = inputs["bound_package"]
    result = materialize_target_composer_request(**inputs)  # type: ignore[arg-type]

    assert result.spec is bound.spec  # type: ignore[union-attr]
    assert result.user_message == "Расскажите про All-on-4, цену и врачей"
    assert [block.kind for block in result.evidence_blocks] == [
        "content",
        "offer",
        "offer",
        "offer",
        "doctor",
        "doctor",
        "doctor",
        "commercial_fact",
        "consultation",
    ]
    assert not result.evidence_blocks[0].text.startswith("---")
    assert "topic: implantation" not in result.evidence_blocks[0].text

    offer_payloads = [
        json.loads(block.text)
        for block in result.evidence_blocks
        if block.kind == "offer"
    ]
    assert [payload["offer_id"] for payload in offer_payloads] == [
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    ]
    assert [payload["price"]["amount"] for payload in offer_payloads] == [
        368000,
        318000,
        428000,
    ]
    assert all(len(payload["payment_stages"]) == 2 for payload in offer_payloads)
    assert all("fact_refs" not in payload for payload in offer_payloads)
    assert all("followups" not in payload for payload in offer_payloads)

    doctor_payloads = [
        json.loads(block.text)
        for block in result.evidence_blocks
        if block.kind == "doctor"
    ]
    assert [payload["doctor_id"] for payload in doctor_payloads] == [
        "doctors__doctor__kuznetsov",
        "doctors__doctor__orlov",
        "doctors__doctor__volkov",
    ]
    assert all(
        list(payload) == [
            "doctor_id",
            "name",
            "position",
            "experience_years",
            "profile_text",
        ]
        for payload in doctor_payloads
    )
    assert all(payload["profile_text"] for payload in doctor_payloads)

    fact = next(
        block for block in result.evidence_blocks if block.kind == "commercial_fact"
    )
    assert fact.ref == "fact:free_implant_consult"
    assert fact.text == inputs["bundle"].facts["free_implant_consult"].text_fact  # type: ignore[union-attr]
    consultation = next(
        block for block in result.evidence_blocks if block.kind == "consultation"
    )
    assert consultation.ref == "consultation:implantation__service__all_on_4.md"
    assert consultation.must_preserve_exact is False
    assert result.selected_followups.source == "content"
    assert result.selected_cta_key == "plan"
    assert not hasattr(result, "package")


def test_real_composer_request_is_read_only_for_demo_client() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    materialize_target_composer_request(**_real_inputs())  # type: ignore[arg-type]
    assert {path: _sha256(path) for path in paths} == before
