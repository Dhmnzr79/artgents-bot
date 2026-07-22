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
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_turn_frame_dispatch import TargetTurnFrameDispatchError
from core.target_response_verifier import (
    TargetSemanticVerification,
    TargetSemanticVerifierInvocation,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DEMO_FULL_CONTEXT = build_target_cached_full_context(MD_ROOT)
VALID_TEXT = (
    "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
    "Можно пройти бесплатную консультацию: врач посмотрит снимки и поможет "
    "подобрать подходящий протокол."
)
DOCTORS_TEXT = (
    "Кузнецов Дмитрий Андреевич — врач со стажем 19 лет."
)
MEDICAL_TEXT = (
    "Имплантация проходит поэтапно. На консультации врач составит понятный план лечения."
)


class RecordingComposerBackend:
    def __init__(self, text: str = VALID_TEXT) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.text


class RecordingSemanticBackend:
    def __init__(self) -> None:
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticVerification(
            grounded_in_primary_evidence=True,
            topic_scope_ok=True,
            medical_boundary_ok=True,
            selected_facts_ok=True,
        )


def _envelope(**overrides: object) -> TargetTurnFramePolicyEnvelope:
    payload: dict[str, object] = {
        "boundary_decision": "none",
        "tone_key": "commercial_warm",
        "allowed_topics": ("implantation", "doctors"),
        "forbidden_topics": ("diagnosis", "personal_eligibility"),
        "required_fact_ids": (),
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
        "aspects": ["overview", "price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def _pipeline_inputs() -> dict[str, object]:
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
        "cached_full_context": DEMO_FULL_CONTEXT,
        "include_initial_block": False,
        "include_consultation_close": True,
        "include_cta": True,
        "shown_fact_ids": (),
        "user_message": "Расскажите про All-on-4, цену и врачей",
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_materialize_path_crosses_dispatch_and_s40_once() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()

    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )

    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.response_mode == "answer"
    assert result.dispatch.policy_request.requested_components == ("content", "price")
    assert len(composer.invocations) == 1
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert len(semantic.invocations) == 1
    assert result.verified.verification_status == "verified"
    assert {path: _sha256(path) for path in paths} == before


def test_real_terminal_clarify_never_reaches_composer() -> None:
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(needs_clarify=True),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundTerminalResponse)
    assert result.dispatch.terminal_mode == "clarify"
    assert composer.invocations == []
    assert semantic.invocations == []


def test_real_doctors_only_materialize_requests_doctors_component() -> None:
    composer = RecordingComposerBackend(text=DOCTORS_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(
            topic="doctors",
            topic_confidence=0.95,
            aspects=["overview"],
            primary_aspect="overview",
        ),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.requested_components == ("doctors",)
    assert len(composer.invocations) == 1


def test_materializable_medical_handoff_crosses_s40_once() -> None:
    composer = RecordingComposerBackend(text=MEDICAL_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(aspects=["overview"], primary_aspect=None, route="content"),
        _envelope(boundary_decision="medical_handoff"),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.response_mode == "medical_handoff"
    assert result.dispatch.policy_request.requested_components == ("content",)
    assert len(composer.invocations) == 1
    assert len(semantic.invocations) == 1


class TurnAwareComposerBackend:
    def __init__(self, texts: tuple[str, ...]) -> None:
        self.texts = texts
        self.invocations: list[TargetComposerInvocation] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        return self.texts[len(self.invocations) - 1]


def test_prebuilt_full_context_is_identical_across_two_materialize_turns() -> None:
    composer = TurnAwareComposerBackend((VALID_TEXT, DOCTORS_TEXT))
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    first = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    second = run_target_offline_turn_frame_bound_response(
        _frame(
            topic="doctors",
            topic_confidence=0.95,
            aspects=["overview"],
            primary_aspect="overview",
        ),
        _envelope(),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(first, TargetTurnFrameBoundMaterializeResponse)
    assert isinstance(second, TargetTurnFrameBoundMaterializeResponse)
    assert len(composer.invocations) == 2
    assert composer.invocations[0].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert composer.invocations[1].cached_full_context == DEMO_FULL_CONTEXT.corpus_text
    assert (
        composer.invocations[0].cached_full_context
        == composer.invocations[1].cached_full_context
    )
    assert (
        composer.invocations[0].primary_evidence_json
        != composer.invocations[1].primary_evidence_json
    )


def test_real_incompatible_topic_raises_before_s40() -> None:
    composer = RecordingComposerBackend()
    semantic = RecordingSemanticBackend()
    with pytest.raises(TargetTurnFrameDispatchError) as caught:
        run_target_offline_turn_frame_bound_response(
            _frame(topic="doctors", topic_confidence=0.95, aspects=["overview"]),
            _envelope().model_copy(update={"allowed_topics": ("implantation",)}),
            **_pipeline_inputs(),  # type: ignore[arg-type]
            composer_backend=composer,
            semantic_backend=semantic,
        )
    assert caught.value.code == "dispatch_topic_scope_incompatible"
    assert composer.invocations == []
    assert semantic.invocations == []
