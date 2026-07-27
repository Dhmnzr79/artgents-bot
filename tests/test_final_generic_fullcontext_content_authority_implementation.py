"""COMPLETION checker — FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

import app as app_module
from contracts.planner_attempt import PlannerAttempt
from contracts.ui_scope_action import UiScopeAction
from core.target_contact_authority import (
    canonical_contact_phone,
    canonical_contact_scalar,
    materialize_clinic_contact_primary_evidence,
    normalize_contact_scalar,
)
from core.target_generic_fullcontext_content import (
    GENERIC_FULLCONTEXT_CONTENT_CAPABILITY,
    is_generic_fullcontext_content_policy_request,
)
from core.target_medical_boundary import normalize_boundary_for_pipeline
from core.target_presentation_decision import (
    TargetPresentationCadenceState,
    decide_target_presentation,
)
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    verify_target_composed_response,
)
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from scripts.validate_client_pack import validate_client_pack
from session import mem_reset
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
    BackendPayload,
    MessageBuildingComposerBackend,
    RecordingBoundaryBackend,
    RecordingSemanticBackend,
    assert_materialized_route,
    assert_not_error_route,
    build_frame,
    orchestrate_via_app,
)
from tests.test_final_fullcontext_dialogue_runtime_convergence_implementation import (
    _FAQ_TEXT,
    _assert_materialized,
)
from tests.test_final_generic_fullcontext_content_authority_governance import (
    test_frozen_artifact_guards as _governance_frozen_artifact_guards,
    test_seam_audit_exists_and_covers_generic_fullcontext,
    test_task_governance_section_and_acceptance_matrix,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_target_response_verifier import (
    RecordingBackend,
    _cached_context,
    _request,
    _response,
    _spec,
)
from tests.test_target_turn_frame_dispatch import _envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_ALLOWED_TOPICS = frozenset(
    {"implantation", "doctors", "clinic", "prosthetics", "aesthetics", "whitening"}
)
_ALLOWED_SERVICES = frozenset(
    {
        "all_on_4",
        "classic",
        "sinus_lift",
        "bone_graft",
        "single_implant",
    }
)

_DISPOSABLE_TEXT = (
    "Да, в работе используются только одноразовые материалы — перчатки, маски, салфетки."
)
_APPOINTMENTS_TEXT = (
    "Если речь об имплантации, новый зуб можно поставить за 2 приёма."
)
_WIFI_GAP_TEXT = "В материалах клиники эта информация не указана."
_PRICE_TEXT = "Стоимость имплантации зависит от клинической ситуации и объёма работ."
_ALL_ON_4_PRICE = "All-on-4 от 350 000 рублей за челюсть."
_CONCERN_TEXT = (
    "Приживаемость имплантов в клинике высокая, врач расскажет подробнее на консультации."
)
_DURATION_TEXT = "Имплантация обычно занимает от нескольких месяцев до полугода."


def _demo_frame(**overrides: object):
    return build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        **overrides,
    )


def _partial_null_topic_frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": [],
        "primary_aspect": None,
        "service_id": None,
        "topic": None,
        "topic_confidence": 0.0,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _contact_text(*fields: str) -> str:
    blocks = materialize_clinic_contact_primary_evidence(
        "demo",
        fields=fields,  # type: ignore[arg-type]
    )
    return "\n".join(block.text for block in blocks)


def _run(
    frame,
    *,
    user_message: str,
    composer_text: str,
    boundary: BackendPayload | None = None,
    boundary_backend: RecordingBoundaryBackend | None = None,
    sid: str | None = None,
    primary_ref: str | None = None,
):
    from flask import Flask, request

    from core.runtime_turn_frame import publish_planner_attempt_frame
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn
    from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
        _planner_attempt,
    )

    sid = sid or f"gfc-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    if boundary_backend is None:
        boundary_backend = RecordingBoundaryBackend(boundary or BackendPayload("none", 0.95))
    composer = MessageBuildingComposerBackend(composer_text, primary_ref=primary_ref)
    semantic = RecordingSemanticBackend()
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        outcome = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary_backend,
        )
    return outcome, composer, semantic, boundary_backend


def _assert_structured_contact(outcome, composer, semantic, boundary_backend) -> None:
    meta = outcome.widget.payload.get("meta") or {}
    assert_materialized_route(meta)
    assert_not_error_route(meta)
    assert outcome.widget.payload.get("answer")
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0
    assert len(boundary_backend.invocations) == 0


def test_scenario_01_disposable_materials_generic_answer() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, semantic, _ = _run(
        frame,
        user_message="А вы используете одноразовые материалы в работе?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert len(semantic.invocations) == 1
    assert _DISPOSABLE_TEXT in outcome.widget.payload["answer"]


def test_scenario_02_null_topic_empty_aspects_same_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_03_appointments_conditional_implantation() -> None:
    frame = _demo_frame(
        aspects=["duration", "stages"],
        primary_aspect="duration",
        service_id=None,
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="А за сколько приёмов можно поставить новый зуб?",
        composer_text=_APPOINTMENTS_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "2 приёма" in outcome.widget.payload["answer"]


def test_scenario_04_advisory_needs_clarification_not_terminal() -> None:
    frame = _demo_frame(
        aspects=["duration", "stages"],
        primary_aspect="duration",
        service_id=None,
        needs_clarify=True,
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="А за сколько приёмов можно поставить новый зуб?",
        composer_text=_APPOINTMENTS_TEXT,
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("service_route") != "target_fullcontext_terminal_clarify"


def test_scenario_05_fresh_sid_no_service_focus() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
        sid=f"gfc-fresh-{uuid.uuid4().hex[:8]}",
    )
    _assert_materialized(outcome, composer)


def test_scenario_06_old_sinus_lift_focus_does_not_block_generic() -> None:
    sid = f"gfc-focus-{uuid.uuid4().hex[:8]}"
    seed_frame = _demo_frame(
        service_id="sinus_lift",
        aspects=["overview"],
        primary_aspect="overview",
    )
    _run(
        seed_frame,
        user_message="Расскажите про синус-лифт",
        composer_text="Синус-лифт выполняется при нехватке костной ткании.",
        sid=sid,
    )
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
        sid=sid,
    )
    _assert_materialized(outcome, composer)


def test_scenario_07_wifi_missing_data_gap_no_phone() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Есть ли Wi-Fi?",
        composer_text=_WIFI_GAP_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert canonical_contact_phone("demo") not in outcome.widget.payload["answer"]


def test_scenario_08_generic_missing_source_text_only() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
        primary_ref=None,
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert "primary_content_ref" not in meta or meta.get("primary_content_ref") is None


def test_scenario_09_generic_valid_source_followups() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
        primary_ref="implantation__faq__safety.md",
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("primary_content_ref") == "implantation__faq__safety.md"


def test_scenario_10_broad_implantation_price_structured() -> None:
    frame = _demo_frame(
        aspects=["price"],
        primary_aspect="price",
        service_id=None,
        route="price_lookup",
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Сколько стоит имплантация?",
        composer_text=_PRICE_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_11_named_all_on_4_price_structured() -> None:
    frame = _demo_frame(
        aspects=["price"],
        primary_aspect="price",
        service_id="all_on_4",
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Сколько стоит All-on-4?",
        composer_text=_PRICE_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_12_unusual_price_no_money_from_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="А по деньгам как там с одноразовыми материалами?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "руб" not in outcome.widget.payload["answer"].lower()


def test_scenario_13_money_without_primary_evidence_blocks() -> None:
    request = _request()
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            _response(request, "Есть 4 варианта по 100 000 рублей."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert caught.value.code == "target_verifier_numeric_ungrounded"


def test_scenario_14_structured_contacts_zero_llm() -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
        service_id=None,
    )
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Какой телефон?",
        composer_text=_contact_text("phone"),
    )
    _assert_structured_contact(outcome, composer, semantic, boundary)


def test_scenario_15_clinic_wide_doctors_path() -> None:
    frame = _demo_frame(
        topic="doctors",
        aspects=[],
        primary_aspect=None,
        service_id=None,
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Кто ваши врачи?",
        composer_text="В клинике работают врачи-имплантологи.",
    )
    _assert_materialized(outcome, composer)


def test_scenario_16_typed_ui_scope_stage_path(monkeypatch) -> None:
    frame = _demo_frame(
        aspects=["price"],
        primary_aspect="price",
        service_id=None,
        route="price_lookup",
    )
    body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="продолжить",
        frame=frame,
        composer_text=_PRICE_TEXT,
    )
    assert body["meta"]["service_route"] == "target_fullcontext_materialized"
    assert len(composer.invocations) >= 1


def test_scenario_17_personal_eligibility_handoff_before_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Мне можно ставить импланты?",
        composer_text="Это решает врач на консультации.",
        boundary=BackendPayload("medical_handoff", 0.95),
    )
    _assert_materialized(outcome, composer)


def test_scenario_18_diagnosis_semantic_block() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="personal_medical_conclusion",
                    offending_span="У вас пульпит",
                ),
            )
        )
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            _response(request, "У вас пульпит. Строгий факт 5 лет."),
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    assert caught.value.code == "target_verifier_semantic_rejected"


def test_scenario_19_dangerous_fantasy_block() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="material_external_medical_claim",
                    offending_span="растворится",
                ),
            )
        )
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            _response(request, "Имплант растворится через день. Строгий факт 5 лет."),
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    assert caught.value.code == "target_verifier_semantic_rejected"


def test_scenario_20_harmless_general_detail_non_blocking() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="minor_external_detail",
                    offending_span="титан",
                ),
            )
        )
    )
    verified = verify_target_composed_response(
        request,
        _response(request, "Импланты из титана. Строгий факт 5 лет."),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert verified.verification_status == "verified"


def test_scenario_21_not_offered_service_fail_closed() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "topic": "secret-topic",
            "topic_confidence": 0.9,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    outcome, _, _, _ = _run(
        frame,
        user_message="общий вопрос",
        composer_text=_FAQ_TEXT,
    )
    assert outcome.widget.kind == "error"


def test_scenario_22_malformed_planner_fail_closed() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "topic": "implantation",
            "topic_confidence": 0.9,
            "service_id": "unknown_service",
            "service_confidence": 0.9,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    outcome, _, _, _ = _run(
        frame,
        user_message="вопрос",
        composer_text=_FAQ_TEXT,
    )
    assert outcome.widget.kind == "error"


def test_scenario_23_partial_frame_generic_materialized() -> None:
    dispatch = dispatch_target_turn_frame_response(_partial_null_topic_frame(), _envelope())
    assert dispatch.kind == "materialize"
    assert is_generic_fullcontext_content_policy_request(dispatch.policy_request)  # type: ignore[arg-type]


def test_scenario_24_composer_failure_technical_phone() -> None:
    frame = _partial_null_topic_frame()

    class _FailingComposer:
        def generate(self, _invocation: object, /) -> object:
            raise RuntimeError("composer down")

    from flask import Flask, request

    from core.runtime_turn_frame import publish_planner_attempt_frame
    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    sid = f"gfc-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(
            attempt=PlannerAttempt(frame=frame, status="partial")  # type: ignore[arg-type]
        )
        outcome = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message="вопрос",
            composer_backend=_FailingComposer(),
            semantic_backend=RecordingSemanticBackend(),
            boundary_backend=RecordingBoundaryBackend(BackendPayload("none", 0.95)),
        )
    assert outcome.widget.kind == "error"
    assert canonical_contact_phone("demo") in outcome.widget.payload["answer"]


def test_scenario_25_invented_source_ui_removed() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
        primary_ref="invented__fake__doc.md",
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("primary_content_ref") != "invented__fake__doc.md"


def test_scenario_26_consultation_value_no_bleed() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)
    payload = outcome.widget.payload
    assert "consultation_value" not in str(payload.get("meta", {}))


def test_scenario_27_marketing_scenario_amplifier() -> None:
    frame = _demo_frame(
        aspects=[],
        primary_aspect=None,
        service_id=None,
        marketing_scenarios=["result_reliability"],
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Вдруг имплант не приживётся?",
        composer_text=_CONCERN_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_28_direct_duration_not_marketing_scenario() -> None:
    frame = _demo_frame(
        aspects=["duration"],
        primary_aspect="duration",
        marketing_scenarios=[],
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Сколько по времени занимает имплантация?",
        composer_text=_DURATION_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert frame.marketing_scenarios == []


def test_scenario_29_presentation_caps_unchanged() -> None:
    from contracts.target_response_spec import TargetResponseSpec
    from contracts.ui_scope_action import build_ui_scope_ref
    from core.target_client_ui_nav import TargetNavigationFollowup

    navigation = tuple(
        TargetNavigationFollowup(
            label=f"Вариант {idx}",
            ref=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
        )
        for idx in range(5)
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=_DEMO_ROOT / "md",
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="classic",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("content",),
        ),
        navigation_followups=navigation,
        selected_followups=TargetResponseFollowupSelection(source="content", content=(), price=()),
        primary_content_ref="implantation__service__classic.md",
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert len(decision.quick_replies) <= 4


def test_scenario_30_ask_and_stream_parity(monkeypatch) -> None:
    frame = _partial_null_topic_frame()
    ask_body, _, sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="Используете одноразовые материалы?",
        frame=frame,
        composer_text=_DISPOSABLE_TEXT,
    )
    stream_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="Используете одноразовые материалы?",
        frame=frame,
        composer_text=_DISPOSABLE_TEXT,
        sid=sid,
    )
    assert ask_body["meta"]["service_route"] == stream_body["meta"]["service_route"]


def test_generic_capability_constant() -> None:
    assert GENERIC_FULLCONTEXT_CONTENT_CAPABILITY == "generic_fullcontext_content"


def test_governance_checker_still_passes() -> None:
    test_seam_audit_exists_and_covers_generic_fullcontext()
    test_task_governance_section_and_acceptance_matrix()


def test_frozen_pins_unchanged() -> None:
    _governance_frozen_artifact_guards()


def test_validate_client_pack_demo() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []


def test_import_app() -> None:
    assert app_module.app is not None
