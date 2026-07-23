from __future__ import annotations

import json
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
from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import build_target_cached_full_context
from core.target_composer_executor import (
    TargetComposerInvocation,
    TargetComposerTone,
)
from core.target_composer_request import materialize_target_composer_request
from core.target_fullcontext_content_package import assemble_target_fullcontext_content_bound_package
from core.target_response_policy import build_target_response_spec
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
    verify_target_composed_response,
)
from core.target_spec_offline_response_package import assemble_target_spec_offline_response_package
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_verified_response_pipeline import run_target_offline_verified_response_pipeline
from core.turn_frame_from_raw import build_turn_frame_from_raw
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.target_composer_executor import TargetUnverifiedComposedResponse


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)

PAIN_GROUNDED_TEXT = (
    "Страх боли при имплантации — нормальная реакция. "
    "Во время операции используется современная прицельная анестезия: "
    "она эффективно убирает боль. "
    "Максимальные ощущения — лёгкий дискомфорт, сопоставимый с лечением кариеса. "
    "На консультации заранее обсудят, какой вариант обезболивания подходит."
)

DIABETES_GROUNDED_TEXT = (
    "При компенсированном диабете имплантация возможна — под контролем врача. "
    "При неконтролируемом — противопоказана из-за высокого риска осложнений. "
    "Решение принимается после диагностики совместно с эндокринологом. "
    "На консультации врач оценит ваш случай и подскажет дальнейшие шаги."
)

DIABETES_PERSONAL_TEXT = (
    "Вам можно ставить импланты при диабете — имплантация вам подходит без ограничений."
)

MISSING_TOPIC_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "На консультации врач ответит на ваш вопрос и подскажет, что актуально именно для вас."
)

EXTERNAL_MEDICAL_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "Системный красный волчанок — аутоиммунное заболевание соединительной ткани."
)

UNGROUNDED_EXTENSION_TEXT = (
    "При компенсированном диабете имплантация возможна — под контролем врача. "
    "Обычно полное заживление занимает около трёх месяцев."
)

FC_MISSING_01_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "При компенсированном диабете имплантация возможна под контролем врача. "
    "Системная красная волчанка относится к аутоиммунным заболеваниям."
)

FC_MISSING_02_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "Псориаз относится к аутоиммунным заболеваниям."
)

FC_MEDICAL_03_TEXT = (
    "При беременности имплантация противопоказана. "
    "В период лактации гормональный фон замедляет заживление, поэтому лучше подождать."
)

MINOR_CLASSIFICATION_TEXT = (
    "В материалах клиники нет информации по этой теме. "
    "Системная красная волчанка относится к аутоиммунным заболеваниям. "
    "На консультации врач ответит на ваш вопрос."
)

CTA_FROM_CORPUS_TEXT = (
    "Страх боли при имплантации — нормальная реакция. "
    "Запишитесь по телефону +7 (495) 128-47-60."
)


class RecordingComposerBackend:
    def __init__(self, text: str) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.text


class RecordingSemanticBackend:
    def __init__(self, assessment: TargetSemanticAssessment | None = None) -> None:
        self.assessment = assessment or TargetSemanticAssessment()
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.assessment


def _issue(kind: str, span: str) -> TargetSemanticIssue:
    return TargetSemanticIssue(kind=kind, offending_span=span)  # type: ignore[arg-type]


from tests.s59_semantic_policy_backend import S59SemanticPolicyBackend


class RuleBasedSemanticBackend:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        text = invocation.candidate_text.lower()
        corpus = invocation.cached_full_context.lower()
        if self.mode == "pain":
            grounded = (
                "анестез" in text
                and "анестез" in corpus
                and ("дискомфорт" in text or "боль" in text)
            )
            personal_promise = any(
                phrase in text
                for phrase in (
                    "вам не будет больно",
                    "вы точно не почувствуете",
                    "гарантируем отсутствие боли",
                )
            )
            issues: tuple[TargetSemanticIssue, ...] = ()
            if not grounded:
                issues += (_issue("unsupported_clinic_claim", "боль"),)
            if personal_promise:
                issues += (_issue("personal_medical_conclusion", "вам не будет больно"),)
            return TargetSemanticAssessment(issues=issues)
        if self.mode == "diabetes_ok":
            grounded = "компенсирован" in text and "компенсирован" in corpus
            return TargetSemanticAssessment(
                issues=()
                if grounded
                else (_issue("material_external_medical_claim", "компенсирован"),)
            )
        if self.mode == "diabetes_reject":
            return TargetSemanticAssessment(
                issues=(_issue("personal_medical_conclusion", "Вам можно"),)
            )
        if self.mode == "missing_ok":
            mentions_gap = "материал" in text and "нет" in text
            issues: tuple[TargetSemanticIssue, ...] = ()
            if not mentions_gap:
                issues += (_issue("unsupported_clinic_claim", "материал"),)
            assessment = S59SemanticPolicyBackend().assess(invocation)
            blocking = tuple(
                issue for issue in assessment.issues if issue.kind != "minor_external_detail"
            )
            return TargetSemanticAssessment(issues=issues + blocking)
        if self.mode == "missing_reject":
            return S59SemanticPolicyBackend().assess(invocation)
        if self.mode == "missing_minor":
            return S59SemanticPolicyBackend().assess(invocation)
        if self.mode in {"fc_missing_01", "fc_medical_03", "fc_missing_02", "s59"}:
            return S59SemanticPolicyBackend().assess(invocation)
        if self.mode == "ungrounded_extension":
            grounded_core = "компенсирован" in text and "компенсирован" in corpus
            issues: tuple[TargetSemanticIssue, ...] = ()
            if not grounded_core:
                issues += (_issue("material_external_medical_claim", "компенсирован"),)
            if "трёх месяц" in text or "заживл" in text:
                issues += (_issue("minor_external_detail", "заживл"),)
            return TargetSemanticAssessment(issues=issues)
        if self.mode == "cta_reject":
            has_contact = "+7" in text or "whatsapp" in text
            spec = json.loads(invocation.response_spec_json)
            allowed = spec.get("allow_cta", True)
            if has_contact and not allowed:
                return TargetSemanticAssessment(
                    issues=(_issue("unsupported_clinic_claim", "+7"),)
                )
            return TargetSemanticAssessment()
        raise AssertionError(f"unknown mode: {self.mode}")


def _envelope(**overrides: object) -> TargetTurnFramePolicyEnvelope:
    payload: dict[str, object] = {
        "boundary_decision": "none",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": ("free_implant_consult",),
        "allow_marketing_facts": True,
        "allow_consultation_close": True,
        "allow_cta": True,
        "min_topic_confidence": 0.5,
        "min_service_confidence": 0.0,
        "min_intent_confidence": 0.0,
    }
    payload.update(overrides)
    return TargetTurnFramePolicyEnvelope.model_validate(payload)


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["pain"],
        "primary_aspect": None,
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def _pipeline_inputs(**overrides: object) -> dict[str, object]:
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
    payload: dict[str, object] = {
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
        "cached_full_context": DEMO_FULL_CONTEXT,
        "include_initial_block": False,
        "include_consultation_close": True,
        "include_cta": False,
        "shown_fact_ids": (),
        "user_message": "Больно ли ставить имплант?",
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }
    payload.update(overrides)
    return payload


def _content_only_policy(**overrides: object) -> TargetResponsePolicyRequest:
    payload: dict[str, object] = {
        "response_mode": "answer",
        "service_id": None,
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation",),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": (),
        "requested_components": ("content",),
        "primary_component": None,
        "allow_marketing_facts": False,
        "allow_consultation_close": True,
        "allow_cta": False,
    }
    payload.update(overrides)
    return TargetResponsePolicyRequest.model_validate(payload)


def test_general_service_less_content_materializes_with_single_composer_and_verifier() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id is None
    assert result.dispatch.policy_request.requested_components == ("content",)
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert semantic.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    directives = json.loads(composer.invocations[0].response_directives_json)
    spec_payload = json.loads(semantic.invocations[0].response_spec_json)
    assert directives["allow_cta"] is False
    assert directives["allow_consultation_close"] is True
    assert spec_payload["allow_cta"] is False
    assert spec_payload["allow_consultation_close"] is True
    assert result.verified.verification_status == "verified"


def test_pain_reassurance_is_verified_without_personal_promise() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RuleBasedSemanticBackend(mode="pain")
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(boundary_decision="medical_handoff"),
        **_pipeline_inputs(user_message="Больно ли ставить имплант?"),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.response_mode == "medical_handoff"
    assert result.verified.verification_status == "verified"
    assert "консультац" in result.verified.text.lower()
    assert "вам не будет больно" not in result.verified.text.lower()


def test_known_diabetes_topic_passes_grounded_medical_answer() -> None:
    composer = RecordingComposerBackend(DIABETES_GROUNDED_TEXT)
    semantic = RuleBasedSemanticBackend(mode="diabetes_ok")
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], route="content"),
        _envelope(
            boundary_decision="medical_handoff",
            required_fact_ids=(),
            allow_marketing_facts=False,
        ),
        **_pipeline_inputs(user_message="Можно ли ставить импланты при диабете?"),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"
    assert "компенсирован" in result.verified.text.lower()


def test_personal_eligibility_answer_is_rejected() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Можно ли ставить импланты при диабете?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=DIABETES_PERSONAL_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=DEMO_FULL_CONTEXT,
            semantic_backend=RuleBasedSemanticBackend(mode="diabetes_reject"),
        )
    assert caught.value.code == "target_verifier_semantic_rejected"
    assert caught.value.value[0][0] == "personal_medical_conclusion"


def test_missing_topic_synthetic_passes_controlled_no_information(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=md_root,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=MISSING_TOPIC_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached,
        semantic_backend=RuleBasedSemanticBackend(mode="missing_ok"),
    )
    assert result.verification_status == "verified"


def test_missing_topic_allows_general_external_medical_context(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=md_root,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=EXTERNAL_MEDICAL_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached,
        semantic_backend=RuleBasedSemanticBackend(mode="missing_reject"),
    )
    assert result.verification_status == "verified"


def test_missing_topic_personal_conclusion_still_rejected(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=md_root,
    )
    personal_text = "У вас волчанка, поэтому вам нельзя ставить импланты."
    unverified = TargetUnverifiedComposedResponse(
        text=personal_text,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=cached,
            semantic_backend=RuleBasedSemanticBackend(mode="missing_reject"),
        )
    assert caught.value.code == "target_verifier_semantic_rejected"


def test_ungrounded_medical_extension_timeline_is_non_blocking() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Можно ли ставить импланты при диабете?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=UNGROUNDED_EXTENSION_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=DEMO_FULL_CONTEXT,
        semantic_backend=RuleBasedSemanticBackend(mode="ungrounded_extension"),
    )
    assert result.verification_status == "verified"


def test_cta_prose_from_corpus_rejected_when_allow_cta_false() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(
        _content_only_policy(response_mode="medical_handoff", allow_cta=False)
    )
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Больно ли ставить имплант?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=CTA_FROM_CORPUS_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=DEMO_FULL_CONTEXT,
            semantic_backend=RuleBasedSemanticBackend(mode="cta_reject"),
        )
    assert caught.value.code == "target_verifier_semantic_rejected"
    assert caught.value.value[0][0] == "unsupported_clinic_claim"


def test_consultation_close_without_contacts_stays_allowed() -> None:
    composer = RecordingComposerBackend(MISSING_TOPIC_TEXT)
    semantic = RuleBasedSemanticBackend(mode="missing_ok")
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], route="content"),
        _envelope(
            boundary_decision="medical_handoff",
            required_fact_ids=(),
            allow_marketing_facts=False,
            allow_cta=False,
            allow_consultation_close=True,
        ),
        **_pipeline_inputs(
            user_message="Можно ли делать имплантацию при системной красной волчанке?",
            include_cta=False,
        ),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"
    assert "консультац" in result.verified.text.lower()
    assert "+7" not in result.verified.text
    assert "whatsapp" not in result.verified.text.lower()


def test_price_without_structured_evidence_is_rejected() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(_content_only_policy())
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Сколько стоит имплант?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text="Имплантация стоит от 318 000 рублей за одну челюсть.",
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=DEMO_FULL_CONTEXT,
            semantic_backend=RecordingSemanticBackend(),
        )
    assert caught.value.code == "target_verifier_numeric_ungrounded"
    assert caught.value.value[0] == "money"


def test_service_specific_price_path_stays_green() -> None:
    composer = RecordingComposerBackend(
        "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
        "Можно пройти бесплатную консультацию."
    )
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(
            service_id="all_on_4",
            aspects=["price"],
            primary_aspect="price",
        ),
        _envelope(required_fact_ids=()),
        **_pipeline_inputs(
            user_message="Сколько стоит All-on-4?",
            include_consultation_close=True,
            include_cta=True,
        ),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.verification_status == "verified"


def test_prebuilt_full_context_is_shared_without_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []

    def fail_build(md_root: Path):
        calls.append(md_root)
        raise AssertionError("build_target_cached_full_context must not run inside pipeline")

    monkeypatch.setattr(
        "core.target_cached_full_context.build_target_cached_full_context",
        fail_build,
    )
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    run_target_offline_verified_response_pipeline(
        assemble_target_spec_offline_response_package(
            inputs["bundle"],  # type: ignore[arg-type]
            inputs["doctor_catalog"],  # type: ignore[arg-type]
            inputs["external_index"],  # type: ignore[arg-type]
            inputs["consultation_values"],  # type: ignore[arg-type]
            spec=build_target_response_spec(_content_only_policy()),
            brand_term=None,
            strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
            semantic_context="service",
            today=date(2026, 7, 22),
            md_root=MD_ROOT,
            include_initial_block=False,
            include_consultation_close=True,
            include_cta=False,
        ),
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Больно ли ставить имплант?",
        md_root=MD_ROOT,
        cached_full_context=DEMO_FULL_CONTEXT,
        tone=inputs["tone"],  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert calls == []
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert semantic.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text


def test_uncertain_boundary_stays_terminal_defer() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(service_id=None, aspects=["price"], primary_aspect="price"),
        _envelope(required_fact_ids=()),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundTerminalResponse)
    assert result.dispatch.terminal_mode == "defer"
    assert composer.invocations == []
    assert semantic.invocations == []


def test_structured_price_wins_over_conflicting_fullcontext_corpus() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(
        TargetResponsePolicyRequest.model_validate(
            {
                "response_mode": "answer",
                "service_id": "all_on_4",
                "tone_key": "commercial_warm",
                "allowed_topics": ("implantation",),
                "forbidden_topics": ("diagnosis", "personal_eligibility"),
                "required_fact_ids": (),
                "requested_components": ("content", "price"),
                "primary_component": "price",
                "allow_marketing_facts": False,
                "allow_consultation_close": True,
                "allow_cta": False,
            }
        )
    )
    bound = assemble_target_spec_offline_response_package(
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        spec=spec,
        brand_term=None,
        strategy_context=inputs["strategy_context"],  # type: ignore[arg-type]
        semantic_context="service",
        today=date(2026, 7, 22),
        md_root=MD_ROOT,
        include_initial_block=False,
        include_consultation_close=True,
        include_cta=False,
    )
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Сколько стоит All-on-4?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text="All-on-4 в клинике стоит от 100 000 рублей за одну челюсть.",
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            unverified,
            cached_full_context=DEMO_FULL_CONTEXT,
            semantic_backend=RecordingSemanticBackend(),
        )
    assert caught.value.code == "target_verifier_numeric_ungrounded"
    assert caught.value.value[0] == "money"


def test_confident_medical_handoff_materializes_without_service_id() -> None:
    composer = RecordingComposerBackend(PAIN_GROUNDED_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(service_id=None, aspects=["pain"]),
        _envelope(boundary_decision="medical_handoff"),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id is None
    assert result.dispatch.policy_request.response_mode == "medical_handoff"


def test_fc_missing_01_class_allows_general_external_context(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=md_root,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=FC_MISSING_01_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached,
        semantic_backend=RuleBasedSemanticBackend(mode="fc_missing_01"),
    )
    assert result.verification_status == "verified"


def test_fc_missing_02_class_allows_external_psoriasis_classification(
    tmp_path: Path,
) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при псориазе?",
        md_root=md_root,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=FC_MISSING_02_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached,
        semantic_backend=RuleBasedSemanticBackend(mode="fc_missing_02"),
    )
    assert result.verification_status == "verified"


def test_fc_medical_03_class_allows_lactation_healing_context() -> None:
    inputs = _pipeline_inputs()
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        inputs["bundle"],  # type: ignore[arg-type]
        inputs["doctor_catalog"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        user_message="Можно ли ставить имплант при беременности?",
        md_root=MD_ROOT,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=FC_MEDICAL_03_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=DEMO_FULL_CONTEXT,
        semantic_backend=RuleBasedSemanticBackend(mode="fc_medical_03"),
    )
    assert result.verification_status == "verified"


def test_minor_external_classification_is_warning_only(tmp_path: Path) -> None:
    md_root = tmp_path / "md"
    md_root.mkdir()
    (md_root / "general.md").write_text(
        "---\ndoc_id: general\ntopic: implantation\n---\n\n## Общее\nКлиника проводит имплантацию.\n",
        encoding="utf-8",
    )
    cached = build_target_cached_full_context(md_root)
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    consultations = build_service_consultation_values(MD_ROOT)
    spec = build_target_response_spec(_content_only_policy(response_mode="medical_handoff"))
    bound = assemble_target_fullcontext_content_bound_package(spec)
    request = materialize_target_composer_request(
        bound,
        bundle,
        doctors,
        consultations,
        user_message="Можно ли делать имплантацию при системной красной волчанке?",
        md_root=md_root,
    )
    unverified = TargetUnverifiedComposedResponse(
        text=MINOR_CLASSIFICATION_TEXT,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
    )
    result = verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached,
        semantic_backend=RuleBasedSemanticBackend(mode="missing_minor"),
    )
    assert result.verification_status == "verified"
