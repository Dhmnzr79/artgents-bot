from __future__ import annotations

import pytest

from core.target_composer_executor import TargetUnverifiedComposedResponse
from core.target_composer_request import materialize_target_composer_request
from core.target_fullcontext_content_package import assemble_target_fullcontext_content_bound_package
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import (
    TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
    TargetSemanticVerifierInvocation,
    verify_target_composed_response,
)
from tests.s59_semantic_policy_backend import S59SemanticPolicyBackend
from tests.test_target_fullcontext_content_response import (
    DIABETES_GROUNDED_TEXT,
    FC_MEDICAL_03_TEXT,
    FC_MISSING_01_TEXT,
    PAIN_GROUNDED_TEXT,
    _content_only_policy,
    _pipeline_inputs,
)
from tests.test_target_response_verifier import (
    RecordingBackend,
    _cached_context,
    _caught,
    _request,
    _response,
)

S58_MISSING_01_TEXT = (
    "В предоставленных материалах клиники нет информации о возможности установки "
    "имплантов при системной красной волчанке.\n\n"
    "Имплантация возможна не во всех случаях, и перед лечением врач обязательно "
    "оценивает состояние здоровья. К абсолютным противопоказаниям относятся "
    "тяжёлые заболевания иммунной системы."
)

S58_MEDICAL_02_TEXT = (
    "Беременность относится к относительным противопоказаниям для имплантации. "
    "Это не означает, что процедура запрещена навсегда, но обычно лечение "
    "переносят на период после родов и завершения грудного вскармливания.\n\n"
    "Такой подход связан с необходимостью обеспечить максимальную безопасность "
    "для мамы и малыша, а также с тем, что гормональные изменения могут "
    "влиять на процессы заживления тканей."
)

_BLOCKING_KINDS = frozenset(
    {
        "unsupported_clinic_claim",
        "personal_medical_conclusion",
        "material_external_medical_claim",
    }
)


def test_policy_text_describes_s59_lightweight_boundary() -> None:
    policy = TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY
    assert "BLOCKING ONLY" in policy
    assert "NON-BLOCKING" in policy
    assert "Absence of grounding alone is not a block reason" in policy
    assert "disclaimer that exact rules are unavailable" not in policy


def test_lupus_immune_general_mention_is_non_blocking() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(
        _invocation(
            "В материалах клиники нет информации по этой теме. "
            "Системная красная волчанка связана с иммунной системой. "
            "На консультации врач ответит на ваш вопрос."
        )
    )
    assert not _blocking(assessment)
    assert any(issue.kind == "minor_external_detail" for issue in assessment.issues)


def test_s58_missing_01_class_is_non_blocking_under_s59() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(_invocation(S58_MISSING_01_TEXT))
    assert not _blocking(assessment)


def test_s58_pregnancy_extension_class_is_non_blocking_under_s59() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(_invocation(S58_MEDICAL_02_TEXT))
    assert not _blocking(assessment)


@pytest.mark.parametrize(
    "text",
    [
        "У вас волчанка, поэтому вам нельзя ставить импланты.",
        "Вам точно подходит имплантация.",
        "Вам нужно выбрать имплант, а не мост.",
        "По симптомам у вас диагноз пulpit.",
    ],
)
def test_personal_diagnosis_and_treatment_choice_blocks(text: str) -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(_invocation(text))
    assert _blocking(assessment)
    assert any(
        issue.kind == "personal_medical_conclusion" for issue in assessment.issues
    )


def test_corpus_contradiction_blocks() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(
        _invocation(
            "Беременность не противопоказана для имплантации — можно смело планировать лечение."
        )
    )
    assert _blocking(assessment)
    assert any(
        issue.kind == "material_external_medical_claim" for issue in assessment.issues
    )


def test_absurd_medical_claim_blocks() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(
        _invocation("Имплантация на 100% безопасна и гарантированно без осложнений.")
    )
    assert any(
        issue.kind == "material_external_medical_claim" for issue in assessment.issues
    )


def test_invented_clinic_price_blocks_semantically() -> None:
    backend = S59SemanticPolicyBackend()
    assessment = backend.assess(
        _invocation("All-on-4 стоит от 999 999 рублей за одну челюсть.")
    )
    assert any(issue.kind == "unsupported_clinic_claim" for issue in assessment.issues)


def test_pain_diabetes_and_fc_missing_verify_with_s59_backend() -> None:
    inputs = _pipeline_inputs()
    request = _missing_base_request(inputs)
    backend = S59SemanticPolicyBackend()
    for text in (PAIN_GROUNDED_TEXT, DIABETES_GROUNDED_TEXT, FC_MISSING_01_TEXT):
        result = verify_target_composed_response(
            request,
            TargetUnverifiedComposedResponse(
                text=text,
                spec=request.spec,
                selected_followups=request.selected_followups,
                selected_cta_key=request.selected_cta_key,
            ),
            cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
            semantic_backend=backend,
        )
        assert result.verification_status == "verified"


def test_fc_medical_03_text_verifies_with_minor_issues() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Можно ли ставить имплант при беременности?",
        md_root=inputs["md_root"],  # type: ignore[arg-type]
    )
    backend = S59SemanticPolicyBackend()
    result = verify_target_composed_response(
        request,
        TargetUnverifiedComposedResponse(
            text=FC_MEDICAL_03_TEXT,
            spec=request.spec,
            selected_followups=request.selected_followups,
            selected_cta_key=request.selected_cta_key,
        ),
        cached_full_context=inputs["cached_full_context"],  # type: ignore[arg-type]
        semantic_backend=backend,
    )
    assert result.verification_status == "verified"
    assessment = backend.assess(
        TargetSemanticVerifierInvocation(
            system_policy=TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
            cached_full_context=str(inputs["cached_full_context"].corpus_text),  # type: ignore[attr-defined]
            response_spec_json="{}",
            primary_evidence_json="[]",
            candidate_text=FC_MEDICAL_03_TEXT,
        )
    )
    assert any(issue.kind == "minor_external_detail" for issue in assessment.issues)


def test_numeric_wrong_price_still_blocks_before_semantic() -> None:
    request = _request()
    error = _caught(
        lambda: verify_target_composed_response(
            request,
            _response(request, "All-on-4 стоит от 999 999 рублей."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    )
    assert error.code == "target_verifier_numeric_ungrounded"


def _invocation(text: str) -> TargetSemanticVerifierInvocation:
    return TargetSemanticVerifierInvocation(
        system_policy=TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
        cached_full_context="Клиника проводит имплантацию. Беременность — противопоказание.",
        response_spec_json="{}",
        primary_evidence_json="[]",
        candidate_text=text,
    )


def _blocking(assessment: object) -> bool:
    from core.target_response_verifier import TargetSemanticAssessment

    assert isinstance(assessment, TargetSemanticAssessment)
    return any(issue.kind in _BLOCKING_KINDS for issue in assessment.issues)


def _missing_base_request(inputs: dict[str, object]) -> object:
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    return materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=inputs["md_root"],  # type: ignore[arg-type]
    )
