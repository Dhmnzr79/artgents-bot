from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

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
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import (
    TargetComposerExecutorError,
    TargetComposerInvocation,
    TargetComposerTone,
)
from core.target_composer_request import TargetComposerRequestError
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticVerification,
    TargetSemanticVerifierInvocation,
)
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)
from core.target_verified_response_pipeline import (
    run_target_offline_verified_response_pipeline,
)


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)
VALID_TEXT = (
    "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
    "Кузнецов Дмитрий Андреевич — врач со стажем 19 лет. "
    "Можно пройти бесплатную консультацию: врач посмотрит снимки и поможет "
    "подобрать подходящий протокол."
)


class RecordingComposerBackend:
    def __init__(self, text: str = VALID_TEXT) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.text


class FailingComposerBackend:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.calls += 1
        raise RuntimeError("composer provider detail")


class RecordingSemanticBackend:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticVerification(
            general_grounding_ok=self.accepted,
            strict_commercial_grounding_ok=self.accepted,
            topic_scope_ok=True,
            medical_boundary_ok=True,
            selected_facts_ok=True,
        )


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
        "cached_full_context": DEMO_FULL_CONTEXT,
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_demo_pipeline_crosses_s36_s37_s38_once_and_preserves_sidecars() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    inputs = _real_inputs()
    bound = inputs["bound_package"]
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()

    result = run_target_offline_verified_response_pipeline(
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )

    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert composer.invocations[0].primary_evidence_json == (
        semantic.invocations[0].primary_evidence_json
    )
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert composer.invocations[0].primary_evidence_json
    assert composer.invocations[0].response_directives_json not in (
        composer.invocations[0].cached_full_context
    )
    assert composer.invocations[0].primary_evidence_json not in (
        composer.invocations[0].cached_full_context
    )
    assert composer.invocations[0].user_message == inputs["user_message"]
    assert semantic.invocations[0].candidate_text is composer.text
    assert result.text is composer.text
    assert result.spec is bound.spec  # type: ignore[union-attr]
    assert result.selected_followups.source == "content"
    assert result.selected_cta_key == "plan"
    assert result.verification_status == "verified"
    assert {path: _sha256(path) for path in paths} == before


def test_real_s36_failure_reaches_neither_backend_and_propagates_exact_error() -> None:
    inputs = _real_inputs()
    inputs["bound_package"] = object()
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    with pytest.raises(TargetComposerRequestError) as caught:
        run_target_offline_verified_response_pipeline(
            **inputs,  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert caught.value.code == "composer_request_package_invalid"
    assert composer.invocations == []
    assert semantic.invocations == []


def test_real_s37_failure_calls_once_and_never_reaches_semantic_backend() -> None:
    composer = FailingComposerBackend()
    semantic = RecordingSemanticBackend()
    with pytest.raises(TargetComposerExecutorError) as caught:
        run_target_offline_verified_response_pipeline(
            **_real_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert (caught.value.code, caught.value.value, composer.calls) == (
        "composer_executor_backend_failed",
        "RuntimeError",
        1,
    )
    assert semantic.invocations == []


def test_real_s38_numeric_rejection_occurs_before_semantic_backend() -> None:
    composer = RecordingComposerBackend(
        "All-on-4 стоит 999 999 рублей. Можно пройти бесплатную консультацию."
    )
    semantic = RecordingSemanticBackend()
    with pytest.raises(TargetResponseVerificationError) as caught:
        run_target_offline_verified_response_pipeline(
            **_real_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert (caught.value.code, caught.value.value) == (
        "target_verifier_numeric_ungrounded",
        ("money", "999999"),
    )
    assert len(composer.invocations) == 1
    assert semantic.invocations == []


def test_real_semantic_rejection_returns_no_partial_verified_response() -> None:
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend(accepted=False)
    with pytest.raises(TargetResponseVerificationError) as caught:
        run_target_offline_verified_response_pipeline(
            **_real_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert (caught.value.code, caught.value.value) == (
        "target_verifier_semantic_rejected",
        ("general_grounding_ok", "strict_commercial_grounding_ok"),
    )
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
