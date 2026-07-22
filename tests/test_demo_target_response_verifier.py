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
from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_composer_request import materialize_target_composer_request
from core.target_response_policy import build_target_response_spec
from core.target_cached_full_context import build_target_cached_full_context
from core.target_response_verifier import (
    TargetSemanticVerification,
    TargetSemanticVerifierInvocation,
    verify_target_composed_response,
)
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"


class RecordingSemanticBackend:
    def __init__(self) -> None:
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticVerification(
            general_grounding_ok=True,
            strict_commercial_grounding_ok=True,
            topic_scope_ok=True,
            medical_boundary_ok=True,
            selected_facts_ok=True,
        )


def _real_request():
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
    return materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Расскажите про All-on-4, цену и врачей",
        md_root=MD_ROOT,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_demo_all_on_4_response_reaches_one_offline_semantic_assessment() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    request = _real_request()
    text = (
        "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
        "Кузнецов Дмитрий Андреевич — врач со стажем 19 лет. "
        "Можно пройти бесплатную консультацию: врач посмотрит снимки и поможет "
        "подобрать подходящий протокол."
    )
    unverified = TargetUnverifiedComposedResponse(
        text=text,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    backend = RecordingSemanticBackend()

    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=build_target_cached_full_context(MD_ROOT),
        semantic_backend=backend,
    )

    assert len(backend.invocations) == 1
    invocation = backend.invocations[0]
    assert invocation.candidate_text is text
    spec_payload = json.loads(invocation.response_spec_json)
    assert spec_payload == {
        "response_mode": "answer",
        "allowed_topics": ["implantation", "doctors"],
        "forbidden_topics": ["diagnosis", "personal_eligibility"],
        "required_fact_ids": ["free_implant_consult"],
    }
    evidence = json.loads(invocation.primary_evidence_json)
    assert [item["kind"] for item in evidence] == [
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
    assert any(item["ref"] == "fact:free_implant_consult" for item in evidence)
    assert result.text is text
    assert result.spec is request.spec
    assert result.selected_followups is request.selected_followups
    assert result.selected_cta_key is request.selected_cta_key
    assert result.verification_status == "verified"
    assert {path: _sha256(path) for path in paths} == before
