"""COMPLETION checker — FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

import app as app_module
import ingress_gate
from contracts.response_schema import TargetService, TargetServiceSelection
from core.target_client_data import load_target_client_data
from core.target_structured_service_availability import (
    ATTRIBUTION_KIND,
    PROVENANCE,
    build_structured_service_availability_answer,
    materialize_structured_service_availability_answer_text,
)
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response
from core.turn_frame_from_raw import build_turn_frame_from_raw, service_availability_requested
from ingress_gate import IngressRouteResult, classify_ingress
from scripts.validate_client_pack import validate_client_pack
from session import mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_generic_fullcontext_content_authority_implementation import (
    _assert_materialized,
    _partial_null_topic_frame,
    _run as _generic_run,
)
from tests.test_final_service_availability_and_clinic_capability_routing_governance import (
    test_frozen_artifact_guards as _governance_frozen_artifact_guards,
    test_seam_audit_exists_and_covers_service_availability,
    test_task_governance_section_and_acceptance_matrix,
)
from tests.test_final_service_availability_and_clinic_capability_routing_harness import (
    BackendPayload,
    MessageBuildingComposerBackend,
    RecordingBoundaryBackend,
    RecordingSemanticBackend,
    assert_materialized_route,
    assert_not_error_route,
    build_frame,
    orchestrate_via_app,
    run_runtime_turn,
)
from tests.test_final_client_pack_data_convergence_sparse_pack import (
    test_sparse_pack_passes_offline_validator,
)
from tests.test_target_turn_frame_dispatch import _envelope

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_CATALOG_PATH = _DEMO_ROOT / "target_response" / "service_catalog.json"
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
        "tomography",
        "professional_whitening",
        "braces_fixture",
    }
)

_QUARTZ_TEXT = "Кварцевание воздуха — уничтожение микробов в помещении."
_DISPOSABLE_TEXT = (
    "Да, в работе используются только одноразовые материалы — перчатки, маски, салфетки."
)
_APRF_TEXT = (
    "Технология APRF (биоматериал из собственной крови): ускоряет заживление, "
    "снижает отёк после операции, поддерживает восстановление тканей."
)
_LAB_TEXT = (
    "Собственная зуботехническая лаборатория: коронки и протезы за 1–3 дня."
)
_GAP_TEXT = "В материалах клиники эта информация не указана."
_UNKNOWN_SERVICE_TEXT = (
    "В материалах клиники такая услуга или возможность не указана."
)
_ALL_ON_4_CONTENT = (
    "All-on-4 — это метод имплантации, при котором на четырех имплантах "
    "фиксируется полный несъёмный протез."
)
_KT_PRICE_TEXT = "КТ (компьютерная томография) — 3 000 рублей за одно исследование."
_KT_INFO_TEXT = (
    "КТ (компьютерная томография) — это 3D-снимок челюсти для точного планирования лечения."
)


def _availability_frame(service_id: str, **overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["service_availability"],
        "primary_aspect": "service_availability",
        "service_id": service_id,
        "service_confidence": 0.95,
        "topic": "clinic",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _run(
    frame,
    *,
    user_message: str,
    composer_text: str = "",
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

    sid = sid or f"svc-avail-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    if boundary_backend is None:
        boundary_backend = RecordingBoundaryBackend(boundary or BackendPayload("none", 0.95))
    composer = MessageBuildingComposerBackend(composer_text or "stub", primary_ref=primary_ref)
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


def _assert_structured_availability(
    outcome,
    composer,
    semantic,
    boundary,
    *,
    active: bool = True,
    service_name: str | None = None,
) -> None:
    meta = outcome.widget.payload.get("meta") or {}
    assert_materialized_route(meta)
    assert_not_error_route(meta)
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0
    assert len(boundary.invocations) == 0
    answer = outcome.widget.payload["answer"]
    if active:
        assert "оказывает услугу" in answer
    else:
        assert "не оказывается" in answer
    if service_name:
        assert service_name in answer


def test_scenario_01_all_on_4_active_yes() -> None:
    frame = _availability_frame("all_on_4", topic="implantation")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Делаете All-on-4?",
    )
    _assert_structured_availability(
        outcome,
        composer,
        semantic,
        boundary,
        service_name="All-on-4",
    )


def test_scenario_02_whitening_active_yes() -> None:
    frame = _availability_frame("professional_whitening", topic="whitening")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="У вас есть отбеливание?",
    )
    _assert_structured_availability(
        outcome,
        composer,
        semantic,
        boundary,
        service_name="отбеливание",
    )


def test_scenario_03_tomography_active_without_content_ref() -> None:
    frame = _availability_frame("tomography")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Проводите КТ?",
    )
    _assert_structured_availability(
        outcome,
        composer,
        semantic,
        boundary,
        service_name="КТ",
    )
    service = load_target_client_data("demo").bundle.services["tomography"]
    assert service.content_ref == "diagnostics__service__tomography.md"


def test_scenario_04_3d_diagnostics_no_technical_error() -> None:
    frame = _availability_frame("tomography")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Делаете 3D-диагностику?",
    )
    _assert_structured_availability(outcome, composer, semantic, boundary)
    assert outcome.widget.kind == "materialized"


def test_scenario_05_active_availability_zero_boundary_composer_semantic() -> None:
    frame = _availability_frame("tomography")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Делаете КТ?",
    )
    _assert_structured_availability(outcome, composer, semantic, boundary)


def test_scenario_06_inactive_service_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    inactive = TargetService(
        name="Брекеты",
        aliases=["брекеты"],
        family="orthodontics",
        roles=[],
        active=False,
        content_ref=None,
        selection=TargetServiceSelection(mode="direct"),
        options=[],
    )

    def _lookup(client_id: str, service_id: str):
        if service_id == "braces_fixture":
            return inactive
        return load_target_client_data(client_id).bundle.services.get(service_id)

    monkeypatch.setattr(
        "core.target_structured_service_availability.lookup_catalog_service",
        _lookup,
    )
    frame = _availability_frame("braces_fixture")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Делаете брекеты?",
    )
    _assert_structured_availability(
        outcome,
        composer,
        semantic,
        boundary,
        active=False,
        service_name="Брекеты",
    )


def test_scenario_07_unknown_dental_service_generic_gap() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Делаете гемисекцию корня?",
        composer_text=_UNKNOWN_SERVICE_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "не указана" in outcome.widget.payload["answer"]


def test_scenario_08_unknown_record_ingress_not_categorical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ingress_gate,
        "_call_ingress_llm",
        lambda *_args, **_kwargs: IngressRouteResult(
            route="service_not_offered",
            confidence=0.95,
            reason="llm",
            policy_key=None,
            requested_service="гемисекция",
            source="llm",
            is_urgent=False,
        ),
    )
    result = classify_ingress(
        "Делаете гемисекцию корня?",
        client_id="demo",
        sid="ingress-unknown",
    )
    assert result.route == "normal"
    assert result.reason == "catalog_miss_availability_routing"


def test_scenario_09_quartz_generic_fullcontext() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Проводите кварцевание воздуха?",
        composer_text=_QUARTZ_TEXT,
        primary_ref="implantation__faq__safety.md",
    )
    _assert_materialized(outcome, composer)
    assert _QUARTZ_TEXT in outcome.widget.payload["answer"]


def test_scenario_10_quartz_not_in_service_catalog() -> None:
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    blob = json.dumps(catalog, ensure_ascii=False).lower()
    assert "кварцев" not in blob


def test_scenario_11_disposable_materials_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert _DISPOSABLE_TEXT in outcome.widget.payload["answer"]


def test_scenario_12_aprf_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете APRF?",
        composer_text=_APRF_TEXT,
        primary_ref="clinic__info__technology.md",
    )
    _assert_materialized(outcome, composer)
    assert "APRF" in outcome.widget.payload["answer"]


def test_scenario_13_own_lab_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Есть своя лаборатория?",
        composer_text=_LAB_TEXT,
        primary_ref="clinic__info__technology.md",
    )
    _assert_materialized(outcome, composer)
    assert "лаборатор" in outcome.widget.payload["answer"].lower()


def test_scenario_14_microscope_missing_information_gap() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете микроскоп?",
        composer_text=_GAP_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "не указана" in outcome.widget.payload["answer"]


def test_scenario_15_what_is_ct_informational_not_only_yes() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Что такое КТ?",
        composer_text=_KT_INFO_TEXT,
        primary_ref="implantation__service__classic.md",
    )
    _assert_materialized(outcome, composer)
    assert "оказывает услугу" not in outcome.widget.payload["answer"]
    assert len(composer.invocations) == 1


def test_scenario_16_all_on_4_concrete_content_route() -> None:
    frame = build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        service_id="all_on_4",
        aspects=["stages"],
        primary_aspect="stages",
        topic="implantation",
    )
    outcome, composer, _, _ = _run(
        frame,
        user_message="Как проходит All-on-4?",
        composer_text=_ALL_ON_4_CONTENT,
        primary_ref="implantation__service__all_on_4.md",
    )
    _assert_materialized(outcome, composer)
    assert len(composer.invocations) == 1


def test_scenario_17_tomography_structured_price_route() -> None:
    frame = build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        service_id="tomography",
        aspects=["price"],
        primary_aspect="price",
        topic="implantation",
        route="price_lookup",
    )
    dispatch = dispatch_target_turn_frame_response(
        frame,
        _envelope(allowed_topics=("implantation", "doctors", "clinic")),
    )
    assert dispatch.kind == "materialize"
    assert dispatch.policy_request.service_id == "tomography"  # type: ignore[union-attr]
    assert dispatch.policy_request.requested_components == ("price",)  # type: ignore[union-attr]


def test_scenario_18_personal_eligibility_not_availability() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Подходит ли КТ именно мне?",
        composer_text="На консультации врач оценит показания к КТ.",
        boundary=BackendPayload("medical_handoff", 0.95),
    )
    assert len(boundary.invocations) == 1
    assert outcome.widget.kind == "materialized"
    assert "оказывает услугу" not in (outcome.widget.payload.get("answer") or "")


def test_scenario_19_heart_transplant_hard_non_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ingress_gate,
        "_call_ingress_llm",
        lambda *_args, **_kwargs: IngressRouteResult(
            route="hard_stop_non_target",
            confidence=0.95,
            reason="llm",
            policy_key=None,
            requested_service=None,
            source="llm",
            is_urgent=False,
        ),
    )
    result = classify_ingress(
        "Делаете пересадку сердца?",
        client_id="demo",
        sid="ingress-heart",
    )
    assert result.route == "hard_stop_non_target"


@pytest.mark.parametrize(
    "user_message",
    [
        "Делаете КТ?",
        "Оказываете КТ?",
        "Проводите КТ?",
        "Есть ли у вас КТ?",
    ],
)
def test_scenario_20_availability_phrase_variants(user_message: str) -> None:
    frame = _availability_frame("tomography")
    outcome, composer, semantic, boundary = _run(frame, user_message=user_message)
    _assert_structured_availability(outcome, composer, semantic, boundary)


def test_scenario_21_old_session_full_arch_no_distortion() -> None:
    sid = f"svc-session-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="all_on_4",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    frame = _availability_frame("tomography")
    outcome, composer, semantic, boundary = _run(
        frame,
        user_message="Делаете КТ?",
        sid=sid,
    )
    _assert_structured_availability(outcome, composer, semantic, boundary, service_name="КТ")
    assert "All-on-4" not in outcome.widget.payload["answer"]


def test_scenario_22_unknown_capability_no_neighbor_service_bleed() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете микроскоп?",
        composer_text=_GAP_TEXT,
    )
    _assert_materialized(outcome, composer)
    answer = outcome.widget.payload["answer"].lower()
    assert "all-on-4" not in answer
    assert "350 000" not in answer


def test_scenario_23_service_catalog_unchanged() -> None:
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    assert "tomography" in catalog
    assert catalog["tomography"]["active"] is True
    assert "all_on_4" in catalog


def test_scenario_24_prices_offers_unchanged() -> None:
    price_path = _DEMO_ROOT / "target_response" / "pricebook" / "services" / "tomography.default.json"
    payload = json.loads(price_path.read_text(encoding="utf-8"))
    assert payload["price"]["amount"] == 3000


def test_scenario_25_doctors_catalog_unchanged() -> None:
    doctors_path = _DEMO_ROOT / "doctor_catalog.json"
    doctors = json.loads(doctors_path.read_text(encoding="utf-8"))
    assert doctors.get("doctors")


def test_scenario_26_generic_does_not_declare_new_service() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Проводите кварцевание воздуха?",
        composer_text=_QUARTZ_TEXT,
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload.get("meta") or {}
    assert meta.get("service_id") in (None, "")


def test_scenario_27_generic_no_price_without_primary_evidence() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете одноразовые материалы?",
        composer_text=_DISPOSABLE_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert "руб" not in outcome.widget.payload["answer"].lower()


def test_scenario_28_source_identity_unchanged_for_generic() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете APRF?",
        composer_text=_APRF_TEXT,
        primary_ref="clinic__info__technology.md",
    )
    _assert_materialized(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("primary_content_ref") == "clinic__info__technology.md"


def test_scenario_29_ask_and_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _availability_frame("tomography")
    ask_body, _, sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="Делаете КТ?",
        frame=frame,
        composer_text="unused",
    )
    stream_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="Делаете КТ?",
        frame=frame,
        composer_text="unused",
        sid=sid,
    )
    assert ask_body["meta"]["service_route"] == stream_body["meta"]["service_route"]
    assert "оказывает услугу" in ask_body["answer"]
    assert "оказывает услугу" in stream_body["answer"]


def test_scenario_30_sparse_new_client_fixture(tmp_path: Path) -> None:
    test_sparse_pack_passes_offline_validator(tmp_path)


def test_structured_availability_contract() -> None:
    answer = build_structured_service_availability_answer(
        client_id="demo",
        service_id="tomography",
    )
    assert answer.provenance == PROVENANCE
    assert answer.attribution_kind == ATTRIBUTION_KIND
    assert answer.active is True
    text = materialize_structured_service_availability_answer_text(answer)
    assert "КТ" in text


def test_service_availability_requested_rejects_mixed_aspects() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["service_availability", "overview"],
            "primary_aspect": "service_availability",
            "service_id": "tomography",
            "service_confidence": 0.95,
            "topic": "clinic",
            "topic_confidence": 0.9,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    assert service_availability_requested(frame) is False


def test_dispatch_service_availability_materialize() -> None:
    frame = _availability_frame("tomography")
    dispatch = dispatch_target_turn_frame_response(frame, _envelope())
    assert dispatch.kind == "materialize"
    assert dispatch.policy_request.service_id == "tomography"  # type: ignore[union-attr]


def test_governance_checker_still_passes() -> None:
    test_seam_audit_exists_and_covers_service_availability()
    test_task_governance_section_and_acceptance_matrix()


def test_frozen_pins_unchanged() -> None:
    _governance_frozen_artifact_guards()
    test_w1b_snapshot_checksums_unchanged()


def test_validate_client_pack_demo() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []
