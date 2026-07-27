"""COMPLETION checker for MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH implementation."""

from __future__ import annotations

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
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.service_consultation_source import build_service_consultation_values
from core.target_cached_full_context import build_target_cached_full_context
from core.target_contact_authority import materialize_clinic_contact_primary_evidence
from core.target_composer_executor import TargetComposerInvocation, TargetComposerTone
from core.target_composer_output import composer_test_json
from core.target_response_verifier import (
    TargetSemanticAssessment,
    TargetSemanticVerifierInvocation,
)
from core.target_runtime_llm_messages import build_composer_sdk_messages
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from core.target_turn_frame_dispatch import TargetTurnFrameDispatchError
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_MD_ROOT = _DEMO_ROOT / "md"
_DEMO_FULL_CONTEXT = build_target_cached_full_context(_MD_ROOT)

_VALID_TEXT = (
    "All-on-4 в клинике стоит от 318 000 рублей за одну челюсть. "
    "Можно пройти бесплатную консультацию."
)
_BONE_GRAFT_TEXT = (
    "Костная пластика помогает восстановить объём кости для имплантации."
)
_DOCTORS_TEXT = "Орлов Никита Владимирович — врач-имплантолог."
_CONTACTS_TEXT = materialize_clinic_contact_primary_evidence("demo", aspect="contacts")[
    0
].text
_FAQ_TEXT = "Имплантация проходит поэтапно с контролем приживления."


class MessageBuildingComposerBackend:
    def __init__(self, text: str) -> None:
        self.text = text
        self.invocations: list[TargetComposerInvocation] = []
        self.sdk_messages: list[list[dict[str, str]]] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocations.append(invocation)
        self.sdk_messages.append(build_composer_sdk_messages(invocation))
        return composer_test_json(self.text)


class RecordingSemanticBackend:
    def __init__(self) -> None:
        self.invocations: list[TargetSemanticVerifierInvocation] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocations.append(invocation)
        return TargetSemanticAssessment()


def _envelope() -> TargetTurnFramePolicyEnvelope:
    return TargetTurnFramePolicyEnvelope.model_validate(
        {
            "boundary_decision": "none",
            "tone_key": "commercial_warm",
            "allowed_topics": ("implantation", "doctors", "clinic"),
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "allow_marketing_facts": True,
            "allow_consultation_close": True,
            "allow_cta": True,
            "min_topic_confidence": 0.5,
            "min_service_confidence": 0.0,
            "min_intent_confidence": 0.0,
        }
    )


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors", "clinic"}),
        allowed_service_ids=frozenset({"all_on_4", "bone_graft"}),
    )


def _pipeline_inputs(**overrides: object) -> dict[str, object]:
    bundle = load_response_schema_bundle(_TARGET_ROOT)
    doctors = load_doctor_catalog(_DEMO_ROOT / "doctor_catalog.json")
    kb_refs = build_response_schema_kb_refs(_MD_ROOT)
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
    consultations = build_service_consultation_values(_MD_ROOT)
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
        "today": date(2026, 7, 27),
        "md_root": _MD_ROOT,
        "cached_full_context": _DEMO_FULL_CONTEXT,
        "include_initial_block": False,
        "include_consultation_close": True,
        "include_cta": True,
        "shown_fact_ids": (),
        "tone": TargetComposerTone(
            key="commercial_warm",
            instruction="Отвечай доброжелательно и без давления.",
        ),
        "client_id": "demo",
    }
    payload.update(overrides)
    return payload


def _materialize(
    frame,
    *,
    user_message: str,
    composer_text: str,
) -> tuple[TargetTurnFrameBoundMaterializeResponse, MessageBuildingComposerBackend, RecordingSemanticBackend]:
    composer = MessageBuildingComposerBackend(composer_text)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(),
        user_message=user_message,
        composer_backend=composer,
        semantic_backend=semantic,
        **_pipeline_inputs(),  # type: ignore[arg-type]
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    return result, composer, semantic


def test_implementation_artifacts_present() -> None:
    assert (_REPO_ROOT / "tests/test_target_runtime_llm_messages.py").is_file()
    assert (_REPO_ROOT / "core/target_runtime_llm_messages.py").is_file()
    assert (_REPO_ROOT / "core/target_turn_frame_dispatch.py").is_file()


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_runtime_matrix_contacts_bone_graft_doctors_price_and_faq() -> None:
    cases = [
        (
            "contacts",
            _frame(
                topic="clinic",
                aspects=["contacts"],
                primary_aspect="contacts",
                service_id=None,
            ),
            "а где вы находитесь и есть ли парковка?",
            _CONTACTS_TEXT,
            ("content",),
        ),
        (
            "bone_graft_faq",
            _frame(
                topic="implantation",
                aspects=["overview"],
                primary_aspect="overview",
                service_id="bone_graft",
            ),
            "Что такое костная пластика?",
            _BONE_GRAFT_TEXT,
            ("content",),
        ),
        (
            "clinic_doctors",
            _frame(
                topic="doctors",
                aspects=[],
                primary_aspect=None,
                service_id=None,
            ),
            "Кто ваши врачи?",
            _DOCTORS_TEXT,
            ("doctors",),
        ),
        (
            "price",
            _frame(
                topic="implantation",
                aspects=["price"],
                primary_aspect="price",
                service_id="all_on_4",
            ),
            "Сколько стоит All-on-4?",
            _VALID_TEXT,
            ("price",),
        ),
        (
            "generic_faq",
            _frame(
                topic="implantation",
                aspects=["overview"],
                primary_aspect="overview",
                service_id=None,
            ),
            "Как проходит имплантация?",
            _FAQ_TEXT,
            ("content",),
        ),
    ]

    for _name, frame, user_message, composer_text, components in cases:
        result, composer, semantic = _materialize(
            frame,
            user_message=user_message,
            composer_text=composer_text,
        )
        assert result.dispatch.policy_request.requested_components == components
        assert len(composer.invocations) == 1
        assert len(semantic.invocations) == 1
        assert len(composer.sdk_messages) == 1
        user_content = composer.sdk_messages[0][1]["content"]
        assert '"answer":"<text>"' in user_content
        assert '"source_identity"' in user_content
        assert user_message in user_content
        assert result.verified.verification_status == "verified"
        assert result.verified.text


def test_non_doctors_empty_aspects_remains_fail_closed() -> None:
    composer = MessageBuildingComposerBackend(_FAQ_TEXT)
    semantic = RecordingSemanticBackend()
    try:
        run_target_offline_turn_frame_bound_response(
            _frame(
                topic="implantation",
                aspects=[],
                primary_aspect=None,
                service_id=None,
            ),
            _envelope(),
            user_message="Как проходит имплантация?",
            composer_backend=composer,
            semantic_backend=semantic,
            **_pipeline_inputs(),  # type: ignore[arg-type]
        )
    except TargetTurnFrameDispatchError as exc:
        assert exc.code == "dispatch_field_invalid"
        assert exc.value == "aspects"
    else:
        raise AssertionError("expected dispatch_field_invalid")

    assert composer.invocations == []
    assert semantic.invocations == []
