"""COMPLETION checker — FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest

import app as app_module
from contracts.planner_attempt import PlannerAttempt
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_contact_authority import (
    canonical_contact_phone,
    canonical_contact_scalar,
    materialize_clinic_contact_primary_evidence,
    normalize_contact_scalar,
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
from core.target_runtime_widget import materialize_boundary_uncertain_payload
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from orchestration.planner_turn import PlannerTurnOutcome
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
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_final_lightweight_response_gates_convergence_harness import run_runtime_turn
from tests.test_target_response_verifier import (
    RecordingBackend,
    _cached_context,
    _request,
    _response,
    _spec,
    _valid_text,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_BUNDLE = load_response_schema_bundle(_TARGET_ROOT)
_ALLOWED_SERVICES = frozenset(_BUNDLE.services.keys())
_ALLOWED_TOPICS = frozenset(
    {"implantation", "doctors", "clinic", "prosthetics", "aesthetics", "whitening"}
)
_CONCERN_TEXT = (
    "Приживаемость имплантов в клинике высокая, врач расскажет подробнее на консультации."
)
_DURATION_TEXT = "Имплантация обычно занимает от нескольких месяцев до полугода."
_WARRANTY_TEXT = "Гарантия на имплантацию оформляется по договору клиники."
_PRICE_TEXT = "Стоимость имплантации зависит от клинической ситуации и объёма работ."


def _demo_frame(**overrides: object):
    return build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        **overrides,
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
):
    sid = sid or f"lwg-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    if boundary_backend is None:
        boundary_backend = RecordingBoundaryBackend(boundary or BackendPayload("none", 0.95))
    from flask import Flask, request

    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    composer = MessageBuildingComposerBackend(composer_text)
    semantic = RecordingSemanticBackend()
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        from contracts.planner_attempt import turn_frame_has_invalid_or_missing

        status = "partial" if turn_frame_has_invalid_or_missing(frame) else "ok"
        publish_planner_attempt_frame(attempt=PlannerAttempt(frame=frame, status=status))  # type: ignore[arg-type]
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


def test_scenario_01_result_reliability_empty_aspects_materialized() -> None:
    frame = _demo_frame(
        aspects=[],
        primary_aspect=None,
        service_id=None,
        marketing_scenarios=["result_reliability"],
    )
    outcome, composer, semantic, _boundary = _run(
        frame,
        user_message="Вдруг имплант не приживётся?",
        composer_text=_CONCERN_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert len(semantic.invocations) == 1


def test_scenario_02_time_concern_partial_frame_materialized() -> None:
    frame = _demo_frame(
        aspects=[],
        primary_aspect=None,
        service_id=None,
        marketing_scenarios=["time"],
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Боюсь, что это долго",
        composer_text="Сроки лечения зависят от плана, врач подскажет на консультации.",
    )
    _assert_materialized(outcome, composer)


def test_scenario_03_direct_duration_no_marketing_scenario() -> None:
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


def test_scenario_04_direct_warranty_no_result_reliability() -> None:
    frame = _demo_frame(
        aspects=["warranty"],
        primary_aspect="warranty",
        marketing_scenarios=[],
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Какая гарантия на имплантацию?",
        composer_text=_WARRANTY_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "result_reliability" not in frame.marketing_scenarios


def test_scenario_05_generic_faq_missing_source_identity_text_only() -> None:
    frame = _demo_frame(service_id=None, aspects=["overview"], primary_aspect="overview")
    outcome, composer, _, _ = _run(
        frame,
        user_message="Что такое имплантация?",
        composer_text=_FAQ_TEXT,
        boundary=BackendPayload("none", 0.95),
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert "primary_content_ref" not in meta or meta.get("primary_content_ref") is None


@pytest.mark.parametrize(
    ("aspect", "message", "field"),
    [
        ("contact_address", "А где вы находитесь?", "address"),
        ("contact_parking", "Есть ли парковка?", "parking"),
        ("contact_phone", "Какой телефон?", "phone"),
        ("contact_hours", "Когда работаете?", "hours"),
    ],
)
def test_scenarios_06_09_structured_contacts(
    aspect: str,
    message: str,
    field: str,
) -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=[aspect],
        primary_aspect=aspect,
        service_id=None,
    )
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message=message,
        composer_text=_contact_text(field),
    )
    _assert_structured_contact(outcome, composer, semantic, boundary)
    scalar = canonical_contact_scalar(field, "demo")  # type: ignore[arg-type]
    assert scalar
    assert normalize_contact_scalar(scalar) in normalize_contact_scalar(
        outcome.widget.payload["answer"]
    )


def test_scenario_10_address_parking_structured() -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_address", "contact_parking"],
        primary_aspect="contact_address",
        service_id=None,
    )
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Адрес и парковка?",
        composer_text=_contact_text("address", "parking"),
    )
    _assert_structured_contact(outcome, composer, semantic, boundary)
    answer = outcome.widget.payload["answer"]
    assert "Адрес:" in answer
    assert "Парковка:" in answer


def test_scenario_11_clinic_wide_doctors_materialized() -> None:
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


def test_scenario_12_broad_implantation_price_materialized() -> None:
    frame = _demo_frame(
        aspects=["price"],
        primary_aspect="price",
        service_id=None,
        intent="price_lookup",
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Сколько стоит имплантация?",
        composer_text=_PRICE_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_14_malformed_topic_fail_closed() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["overview"],
            "primary_aspect": "overview",
            "topic": "secret-topic",
            "topic_confidence": 0.9,
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    outcome, _, _, _ = _run(
        frame,
        user_message="общий вопрос",
        composer_text=_FAQ_TEXT,
    )
    assert outcome.widget.kind == "error"
    assert outcome.widget.payload["meta"]["service_route"] == "target_fullcontext_error"


def test_scenario_15_boundary_low_confidence_materializes() -> None:
    frame = _demo_frame(aspects=["overview"], primary_aspect="overview")
    outcome, composer, _, _ = _run(
        frame,
        user_message="Расскажите про имплантацию",
        composer_text=_FAQ_TEXT,
        boundary=BackendPayload("none", 0.55),
    )
    _assert_materialized(outcome, composer)


def test_scenario_16_boundary_backend_failure_technical_phone() -> None:
    frame = _demo_frame(aspects=["overview"], primary_aspect="overview")

    class _ExplodingBoundary:
        def classify(self, _invocation: object, /) -> object:
            raise RuntimeError("backend down")

    outcome, _, _, _ = _run(
        frame,
        user_message="Расскажите про имплантацию",
        composer_text=_FAQ_TEXT,
        boundary_backend=_ExplodingBoundary(),  # type: ignore[arg-type]
    )
    assert outcome.widget.kind in {"error", "terminal"}
    assert canonical_contact_phone("demo") in outcome.widget.payload["answer"]


def test_scenario_17_numeric_distortion_blocks() -> None:
    request = _request()
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            _response(request, "Есть 4 варианта по 100 000 рублей."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert caught.value.code == "target_verifier_numeric_ungrounded"


def test_scenario_19_diagnosis_semantic_block() -> None:
    request = _request()
    backend = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="personal_medical_conclusion",
                    offending_span="Вам нельзя",
                ),
            )
        )
    )
    with pytest.raises(TargetResponseVerificationError) as caught:
        verify_target_composed_response(
            request,
            _response(
                request,
                "Вам нельзя имплантацию. Строгий факт 5 лет.",
            ),
            cached_full_context=_cached_context(),
            semantic_backend=backend,
        )
    assert caught.value.code == "target_verifier_semantic_rejected"


def test_scenario_21_harmless_general_detail_non_blocking() -> None:
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
        _response(
            request,
            "Импланты из титана. Строгий факт 5 лет.",
        ),
        cached_full_context=_cached_context(),
        semantic_backend=backend,
    )
    assert verified.verification_status == "verified"


def test_scenario_22_typed_ui_click_skips_planner(monkeypatch) -> None:
    from contracts.ui_scope_action import UiScopeAction

    frame = _demo_frame(
        aspects=["price"],
        primary_aspect="price",
        service_id=None,
        intent="price_lookup",
    )
    publish_calls: list[str] = []

    def _fake_planner(**_kwargs: object) -> PlannerTurnOutcome:
        publish_calls.append("called")
        return PlannerTurnOutcome("content", None)

    monkeypatch.setattr(app_module, "run_planner_turn", _fake_planner)
    body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="продолжить",
        frame=frame,
        composer_text=_PRICE_TEXT,
    )
    assert body["meta"]["service_route"] == "target_fullcontext_materialized"
    assert publish_calls == []


def test_scenario_23_composer_failure_technical_phone() -> None:
    frame = _demo_frame(aspects=["overview"], primary_aspect="overview")

    class _FailingComposer:
        def generate(self, _invocation: object, /) -> object:
            raise RuntimeError("composer down")

    from flask import Flask, request

    from core.target_runtime_turn import run_target_fullcontext_runtime_turn

    sid = f"lwg-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(
            attempt=PlannerAttempt(frame=frame, status="ok")  # type: ignore[arg-type]
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


def test_scenario_25_leadflow_date_time_forbidden() -> None:
    from core.booking_date_defer import should_defer_booking_date_at_entry

    assert should_defer_booking_date_at_entry(
        q="Можно записаться на завтра в 15:00?",
        client_id="demo",
    )


def test_scenario_26_presentation_caps_unchanged() -> None:
    from contracts.ui_scope_action import build_ui_scope_ref
    from contracts.target_response_spec import TargetResponseSpec
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


def test_scenario_27_ask_and_stream_parity(monkeypatch) -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
        service_id=None,
    )
    ask_body, _, sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="телефон?",
        frame=frame,
        composer_text=_contact_text("phone"),
    )
    stream_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="телефон?",
        frame=frame,
        composer_text=_contact_text("phone"),
        sid=sid,
    )
    assert ask_body["meta"]["service_route"] == stream_body["meta"]["service_route"]


def test_scenario_28_verifier_uses_runtime_client_id() -> None:
    from core.target_composer_request import TargetComposerEvidenceBlock

    alt_phone = "+7 (999) 000-00-00"
    facts_path = "core.target_contact_authority.load_clinic_contact_facts"

    class _AltFacts:
        phone_display = alt_phone
        whatsapp_display = None
        address_display = None
        hours_display = None
        parking_display = None

    block = TargetComposerEvidenceBlock(
        kind="clinic_contact",
        ref="clinic_contact:phone",
        topics=("clinic",),
        fact_ids=(),
        text=f"Телефон: {alt_phone}",
        must_preserve_exact=True,
    )
    from core.target_contact_authority import load_clinic_contact_facts

    def _load_facts(client_id: str | None):
        if client_id == "alt-client":
            return _AltFacts()
        return load_clinic_contact_facts(client_id)

    request = _request(
        spec=_spec(required_fact_ids=(), required_components=("content",)),
        blocks=(block,),
    )
    with patch(facts_path, side_effect=_load_facts):
        verify_target_composed_response(
            request,
            _response(request, f"Позвоните: {alt_phone}"),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
            client_id="alt-client",
        )
    with patch(facts_path, side_effect=_load_facts):
        with pytest.raises(TargetResponseVerificationError):
            verify_target_composed_response(
                request,
                _response(
                    request,
                    f"Позвоните: {canonical_contact_scalar('phone', 'demo')}",
                ),
                cached_full_context=_cached_context(),
                semantic_backend=RecordingBackend(),
                client_id="alt-client",
            )


def test_boundary_uncertain_terminal_includes_phone() -> None:
    payload = materialize_boundary_uncertain_payload(client_id="demo", sid="s1")
    assert canonical_contact_phone("demo") in payload.payload["answer"]


def test_normalize_boundary_low_confidence_degrades_to_none() -> None:
    from contracts.target_medical_boundary import TargetMedicalBoundaryResult

    uncertain = TargetMedicalBoundaryResult(
        decision="uncertain",
        confidence=0.0,
        reason_code="boundary_uncertain_low_confidence",
        source="fail_closed",
    )
    normalized = normalize_boundary_for_pipeline(uncertain)
    assert normalized.decision == "none"


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_validate_client_pack_demo() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []


def test_import_app() -> None:
    assert app_module.app is not None


def test_governance_checker_still_passes() -> None:
    from tests.test_final_lightweight_response_gates_convergence_governance import (
        test_seam_audit_exists_and_covers_lightweight_gates,
        test_task_governance_section_and_acceptance_matrix,
    )

    test_seam_audit_exists_and_covers_lightweight_gates()
    test_task_governance_section_and_acceptance_matrix()
