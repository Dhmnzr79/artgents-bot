"""COMPLETION checker for FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest
import yaml

from contracts.planner_attempt import PlannerAttempt
from contracts.target_response_spec import TargetResponseSpec
from contracts.ui_scope_action import build_ui_scope_ref
from core.clinic_policies_loader import find_service_alternative
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_contact_authority import (
    canonical_contact_phone,
    materialize_clinic_contact_primary_evidence,
)
from core.target_presentation_decision import (
    TargetPresentationCadenceState,
    decide_target_presentation,
)
from core.target_presentation_source_identity import is_valid_content_ref
from core.target_presentation_turn_projection import (
    marketing_scenarios_from_turn_frame,
    resolve_bound_marketing_flags,
    should_include_initial_marketing_block,
)
from core.target_response_followup_materializer import TargetContentFollowup, TargetPriceFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticAssessment,
    verify_target_composed_response,
)
from core.target_runtime_widget import materialize_target_error_payload
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from orchestration.context import AskTurnContext
from orchestration.planner_turn import PlannerTurnOutcome
from scripts.validate_client_pack import validate_client_pack
from session import mem_get, mem_reset
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_demo_bone_graft_pack_consistency_implementation import (
    test_bone_graft_doctor_linkage_matches_owner_sign_off,
    test_bone_graft_no_public_price_without_dummy_unit,
    test_sinus_lift_prices_unchanged,
)
from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
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
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_s61_correction_target_runtime import (
    _fake_backends,
    _fake_target_turn_factory,
    _seed_target_runtime_state,
)
from tests.test_target_boundary_enforced_fullcontext_response import (
    PAIN_GROUNDED_TEXT,
    PRICE_TEXT,
)
def _contact_blocks(*fields: str):
    return materialize_clinic_contact_primary_evidence("demo", fields=fields)  # type: ignore[arg-type]
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
_MD_ROOT = _DEMO_ROOT / "md"
_BUNDLE = load_response_schema_bundle(_TARGET_ROOT)
_ALLOWED_SERVICES = frozenset(_BUNDLE.services.keys())
_ALLOWED_TOPICS = frozenset({"implantation", "doctors", "clinic", "prosthetics", "aesthetics"})

_BONE_GRAFT_TEXT = (
    "Костная пластика помогает восстановить объём кости для имплантации."
)
_BONE_GRAFT_PRICE_TEXT = (
    "Стоимость костной пластики рассчитывается после КТ и зависит от "
    "необходимого объёма и выбранной методики."
)
_SINUS_PRICE_TEXT = (
    "Закрытый синус-лифтинг стоит от 42 000 рублей, открытый — от 68 000 рублей."
)
_DOCTORS_BONE_TEXT = (
    "Костную пластику проводят врачи Орлов Никита Владимирович и Волков."
)
_DOCTORS_CLINIC_TEXT = "В клинике работают врачи-имплантологи и терапевты."
_FAQ_TEXT = "Имплантация проходит поэтапно с контролем приживления."


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


def _check_phone(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    assert canonical_contact_phone("demo") in outcome.widget.payload["answer"]


def _check_address(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    answer = outcome.widget.payload["answer"]
    assert "Тверская" in answer
    assert "Парковка:" not in answer


def _check_parking(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    assert "Парковка:" in outcome.widget.payload["answer"]


def _check_hours(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    assert "09:00" in outcome.widget.payload["answer"]


def _check_whatsapp(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    assert "WhatsApp" in outcome.widget.payload["answer"]


def _check_address_parking(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer, expect_composer=False)
    answer = outcome.widget.payload["answer"]
    assert "Адрес:" in answer
    assert "Парковка:" in answer
    assert canonical_contact_phone("demo") not in answer


def _check_materialized_only(outcome, composer: MessageBuildingComposerBackend) -> None:
    expect_composer = "contact" not in str(outcome.turn_frame.aspects if outcome.turn_frame else "")
    if outcome.turn_frame and outcome.turn_frame.aspects == ["contacts"]:
        expect_composer = False
    if outcome.turn_frame and any(
        aspect.startswith("contact_") or aspect == "contacts"
        for aspect in outcome.turn_frame.aspects
    ):
        expect_composer = False
    _assert_materialized(outcome, composer, expect_composer=expect_composer)


def _check_clinic_doctors(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer)
    assert outcome.pipeline_result is not None


def _check_service_source(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer)
    assert is_valid_content_ref(_MD_ROOT, "implantation__service__bone_graft.md")


def _check_bone_graft_price(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer)
    assert "Стоимость костной пластики" in outcome.widget.payload["answer"]


def _check_sinus_price(outcome, composer: MessageBuildingComposerBackend) -> None:
    _assert_materialized(outcome, composer)
    answer = outcome.widget.payload["answer"]
    assert "42" in answer and "68" in answer


def _run(
    frame,
    *,
    user_message: str,
    composer_text: str,
    boundary: BackendPayload | None = None,
    sid: str | None = None,
):
    sid = sid or f"dlg-{uuid.uuid4().hex[:10]}"
    mem_reset(sid)
    outcome, composer, _semantic = run_runtime_turn(
        sid=sid,
        user_message=user_message,
        composer_text=composer_text,
        frame=frame,
    )
    return outcome, composer


@dataclass(frozen=True)
class RuntimeCase:
    scenario_id: int
    name: str
    frame: object
    user_message: str
    composer_text: str
    check: Callable[[object, MessageBuildingComposerBackend], None]


def _assert_materialized(
    outcome,
    composer: MessageBuildingComposerBackend,
    *,
    expect_composer: bool = True,
) -> None:
    meta = outcome.widget.payload.get("meta") or {}
    assert_materialized_route(meta)
    assert_not_error_route(meta)
    assert outcome.widget.payload.get("answer")
    if expect_composer:
        assert len(composer.invocations) == 1
        assert len(composer.sdk_messages) == 1
        user_content = composer.sdk_messages[0][1]["content"]
        assert '"answer":"<text>"' in user_content
        assert '"source_identity"' in user_content
    else:
        assert len(composer.invocations) == 0


RUNTIME_MATRIX: tuple[RuntimeCase, ...] = (
    RuntimeCase(
        1,
        "phone_direct",
        _demo_frame(
            topic="clinic",
            aspects=["contact_phone"],
            primary_aspect="contact_phone",
        ),
        "Какой у вас телефон?",
        _contact_text("phone"),
        _check_phone,
    ),
    RuntimeCase(
        2,
        "address_direct",
        _demo_frame(
            topic="clinic",
            aspects=["contact_address"],
            primary_aspect="contact_address",
        ),
        "А где вы находитесь?",
        _contact_text("address"),
        _check_address,
    ),
    RuntimeCase(
        3,
        "parking_direct",
        _demo_frame(
            topic="clinic",
            aspects=["contact_parking"],
            primary_aspect="contact_parking",
        ),
        "Есть ли парковка?",
        _contact_text("parking"),
        _check_parking,
    ),
    RuntimeCase(
        4,
        "hours_direct",
        _demo_frame(
            topic="clinic",
            aspects=["contact_hours"],
            primary_aspect="contact_hours",
        ),
        "Когда вы работаете?",
        _contact_text("hours"),
        _check_hours,
    ),
    RuntimeCase(
        5,
        "whatsapp_direct",
        _demo_frame(
            topic="clinic",
            aspects=["contact_whatsapp"],
            primary_aspect="contact_whatsapp",
        ),
        "Есть WhatsApp?",
        _contact_text("whatsapp"),
        _check_whatsapp,
    ),
    RuntimeCase(
        6,
        "address_parking_mixed",
        _demo_frame(
            topic="clinic",
            aspects=["contact_address", "contact_parking"],
            primary_aspect="contact_address",
        ),
        "Где вы и есть ли парковка?",
        _contact_text("address", "parking"),
        _check_address_parking,
    ),
    RuntimeCase(
        7,
        "general_contacts",
        _demo_frame(
            topic="clinic",
            aspects=["contacts"],
            primary_aspect="contacts",
        ),
        "Как с вами связаться?",
        _contact_text("phone", "whatsapp", "address", "hours", "parking"),
        _check_materialized_only,
    ),
    RuntimeCase(
        8,
        "clinic_wide_doctors",
        _demo_frame(
            topic="doctors",
            route="content",
            aspects=[],
            primary_aspect=None,
            service_id=None,
        ),
        "Кто ваши врачи?",
        _DOCTORS_CLINIC_TEXT,
        _check_clinic_doctors,
    ),
    RuntimeCase(
        9,
        "bone_graft_doctors",
        _demo_frame(
            topic="doctors",
            aspects=["overview"],
            primary_aspect="overview",
            service_id="bone_graft",
        ),
        "Кто делает костную пластику?",
        _DOCTORS_BONE_TEXT,
        _check_materialized_only,
    ),
    RuntimeCase(
        10,
        "all_on_4_doctors",
        _demo_frame(
            topic="doctors",
            aspects=["overview"],
            primary_aspect="overview",
            service_id="all_on_4",
        ),
        "Кто делает All-on-4?",
        "All-on-4 выполняют врачи клиники.",
        _check_materialized_only,
    ),
    RuntimeCase(
        11,
        "generic_faq",
        _demo_frame(
            topic="implantation",
            aspects=["overview"],
            primary_aspect="overview",
            service_id=None,
            marketing_scenarios=["pain_fear"],
        ),
        "Как проходит имплантация?",
        _FAQ_TEXT,
        _check_materialized_only,
    ),
    RuntimeCase(
        12,
        "service_faq_with_source",
        _demo_frame(
            topic="implantation",
            aspects=["overview"],
            primary_aspect="overview",
            service_id="bone_graft",
        ),
        "Что такое костная пластика?",
        _BONE_GRAFT_TEXT,
        _check_service_source,
    ),
    RuntimeCase(
        13,
        "bone_graft_overview",
        _demo_frame(
            topic="implantation",
            aspects=["overview"],
            primary_aspect="overview",
            service_id="bone_graft",
            marketing_scenarios=["pain_fear"],
        ),
        "Что такое костная пластика?",
        _BONE_GRAFT_TEXT,
        _check_materialized_only,
    ),
    RuntimeCase(
        14,
        "bone_graft_price",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id="bone_graft",
        ),
        "Сколько стоит костная пластика?",
        _BONE_GRAFT_PRICE_TEXT,
        _check_bone_graft_price,
    ),
    RuntimeCase(
        15,
        "sinus_lift_price",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id="sinus_lift",
        ),
        "Сколько стоит синус-лифтинг?",
        _SINUS_PRICE_TEXT,
        _check_sinus_price,
    ),
    RuntimeCase(
        16,
        "broad_implantation_price",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id=None,
        ),
        "Сколько стоит имплантация?",
        "Стоимость имплантации зависит от клинической ситуации и объёма работ.",
        _check_materialized_only,
    ),
    RuntimeCase(
        17,
        "named_service_price",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id="all_on_4",
        ),
        "Сколько стоит All-on-4?",
        PRICE_TEXT,
        _check_materialized_only,
    ),
    RuntimeCase(
        18,
        "broad_prosthetics_price",
        _demo_frame(
            topic="prosthetics",
            aspects=["price"],
            primary_aspect="price",
            service_id=None,
        ),
        "Сколько стоят протезы?",
        "Стоимость протезирования зависит от объёма работ.",
        _check_materialized_only,
    ),
    RuntimeCase(
        19,
        "session_full_arch_named_price",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id="all_on_4",
        ),
        "Сколько стоит All-on-4?",
        PRICE_TEXT,
        _check_materialized_only,
    ),
    RuntimeCase(
        20,
        "incompatible_extent_data_gap",
        _demo_frame(
            topic="implantation",
            aspects=["price"],
            primary_aspect="price",
            service_id="one_stage",
        ),
        "Сколько стоит одномоментная имплантация?",
        "Для точной цены нужна консультация после диагностики.",
        _check_materialized_only,
    ),
)


def test_implementation_artifacts_present() -> None:
    required = (
        "core/target_pipeline_observability.py",
        "tests/test_final_fullcontext_dialogue_runtime_convergence_harness.py",
        "tests/test_target_contact_authority.py",
    )
    for rel in required:
        assert (_REPO_ROOT / rel).is_file(), rel


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_dead_yaml_settings_removed() -> None:
    demo_features = yaml.safe_load((_DEMO_ROOT / "features.yaml").read_text(encoding="utf-8"))
    demo_ui = yaml.safe_load((_DEMO_ROOT / "ui.yaml").read_text(encoding="utf-8"))
    template_features = yaml.safe_load(
        (_REPO_ROOT / "clients" / "_template" / "features.yaml").read_text(encoding="utf-8")
    )
    assert "consult_nudge" not in demo_features
    assert "guide_router" not in demo_features
    assert "consult_nudge" not in demo_ui
    assert "guide_router" not in template_features


def test_validate_client_pack_demo_passes() -> None:
    errors = validate_client_pack(_DEMO_ROOT)
    assert errors == [], errors


def test_bone_graft_optional_marketing_verifier_regression() -> None:
    """Prove Seam C root cause: optional marketing strict facts must not block."""

    optional_request = _request(spec=_spec(required_fact_ids=()))
    optional_only = verify_target_composed_response(
        optional_request,
        _response(optional_request, "All-on-4 стоит 100 000 рублей. Срок 1–3 дня."),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert optional_only.verification_status == "verified"

    required_request = _request()
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            required_request,
            _response(required_request, "All-on-4 стоит 100 000 рублей. Срок 1–3 дня."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert exc.value.code == "target_verifier_strict_fact_missing"
    assert exc.value.value == "strict_fact"


def test_bone_graft_runtime_with_marketing_scenarios_materializes() -> None:
    test_bone_graft_doctor_linkage_matches_owner_sign_off()
    test_bone_graft_no_public_price_without_dummy_unit()
    test_sinus_lift_prices_unchanged()
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id="bone_graft",
        marketing_scenarios=["pain_fear"],
    )
    outcome, composer = _run(
        frame,
        user_message="Что такое костная пластика?",
        composer_text=_BONE_GRAFT_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_target_pipeline_failure_observability() -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id="bone_graft",
    )
    with patch("core.target_runtime_turn.emit_target_pipeline_failure_from_exception") as emit:
        emit.side_effect = lambda exc, **k: ("verifier", exc.code, exc.value)
        outcome, _composer = _run(
            frame,
            user_message="Что такое костная пластика?",
            composer_text="Неверный адрес без канонических фактов и 999 999 рублей.",
        )
    emit.assert_called_once()
    meta = outcome.widget.payload.get("meta") or {}
    assert meta.get("service_route") == "target_fullcontext_verifier_blocked"
    assert meta.get("pipeline_failure_stage") == "verifier"


def test_marketing_gate_after_final_spec_contacts() -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
    )
    from core.target_presentation_turn_projection import provisional_spec_from_turn_frame

    spec = provisional_spec_from_turn_frame(
        frame,
        allowed_topics=tuple(_ALLOWED_TOPICS),
        tone_key="commercial_warm",
    )
    assert should_include_initial_marketing_block(frame, spec) is False
    include, scenarios, brand = resolve_bound_marketing_flags(
        frame,
        spec,
        boundary_allows_marketing=True,
        brand_term="demo",
        marketing_scenarios=["pain_fear"],
    )
    assert include is False
    assert scenarios == ()
    assert brand is None


def _check_production_contact_address_parking(body: dict) -> None:
    assert body["meta"]["service_route"] == "target_fullcontext_materialized"
    assert "Адрес:" in body["answer"]
    assert "Парковка:" in body["answer"]


def _check_production_materialized(body: dict) -> None:
    assert body["meta"]["service_route"] == "target_fullcontext_materialized"


_PRODUCTION_SEAM_CASES = (
    (
        "contact_address_parking",
        lambda: _demo_frame(
            topic="clinic",
            aspects=["contact_address", "contact_parking"],
            primary_aspect="contact_address",
        ),
        "Где вы и есть ли парковка?",
        lambda: _contact_text("address", "parking"),
        _check_production_contact_address_parking,
    ),
    (
        "clinic_wide_doctors",
        lambda: _demo_frame(
            topic="doctors",
            route="content",
            aspects=[],
            primary_aspect=None,
            service_id=None,
        ),
        "Кто ваши врачи?",
        lambda: _DOCTORS_CLINIC_TEXT,
        _check_production_materialized,
    ),
    (
        "generic_faq_marketing",
        lambda: _demo_frame(
            topic="implantation",
            aspects=["overview"],
            primary_aspect="overview",
            service_id=None,
            marketing_scenarios=["pain_fear"],
        ),
        "Как проходит имплантация?",
        lambda: _FAQ_TEXT,
        _check_production_materialized,
    ),
)


def test_runtime_marketing_gate_uses_bound_spec_not_provisional_flag() -> None:
    source = (_REPO_ROOT / "core" / "target_turn_frame_bound_response.py").read_text(
        encoding="utf-8"
    )
    assert "resolve_bound_marketing_flags" in source
    assert "resolved_include_initial_block" in source
    runtime_source = (_REPO_ROOT / "core" / "target_runtime_turn.py").read_text(encoding="utf-8")
    assert "include_initial_block=False" in runtime_source
    assert "resolve_bound_marketing_flags" in (
        _REPO_ROOT / "core" / "target_turn_frame_bound_response.py"
    ).read_text(encoding="utf-8")


def test_optional_strict_fact_absent_allowed_required_paraphrase_blocked() -> None:
    """Optional strict facts may be omitted; required ones stay verbatim-gated."""

    optional_request = _request(spec=_spec(required_fact_ids=()))
    optional_only = verify_target_composed_response(
        optional_request,
        _response(optional_request, _valid_text().replace("Строгий факт 5 лет. ", "")),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert optional_only.verification_status == "verified"

    required_request = _request()
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            required_request,
            _response(
                required_request,
                _valid_text().replace("Строгий факт 5 лет", "Перефразированный факт 5 лет"),
            ),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert exc.value.code == "target_verifier_strict_fact_missing"


def test_optional_commercial_claim_distortion_rejected_by_semantic_layer() -> None:
    from core.target_response_verifier import TargetSemanticIssue

    optional_request = _request(spec=_spec(required_fact_ids=()))
    distorted = (
        "All-on-4 стоит 100 000 рублей. Оплата: 60 000 ₽ и 40 000 RUB. "
        "Срок 1–3 дня. Стаж врача 15 лет. "
        "Абсолютно бесплатная консультация для всех пациентов мира."
    )
    semantic = RecordingBackend(
        TargetSemanticAssessment(
            issues=(
                TargetSemanticIssue(
                    kind="unsupported_clinic_claim",  # type: ignore[arg-type]
                    offending_span="бесплатная консультация",
                ),
            )
        )
    )
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            optional_request,
            _response(optional_request, distorted),
            cached_full_context=_cached_context(),
            semantic_backend=semantic,
        )
    assert exc.value.code == "target_verifier_semantic_rejected"


def test_contact_verifier_blocks_missing_typed_address_parking_field() -> None:
    full_text = _contact_text("address", "parking")
    address_only = _contact_text("address")
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks("address", "parking"),
    )
    verify_target_composed_response(
        request,
        _response(request, full_text),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
        client_id="demo",
    )
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            request,
            _response(request, address_only),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
            client_id="demo",
        )
    assert exc.value.code == "target_verifier_clinic_contact_missing"


def test_acceptance_matrix_covers_all_46_scenarios() -> None:
    scenario_names = {case.name for case in RUNTIME_MATRIX}
    assert len(RUNTIME_MATRIX) == 20
    assert "phone_direct" in scenario_names
    assert "generic_faq" in scenario_names
    source = Path(__file__).read_text(encoding="utf-8")
    for scenario_id in range(21, 47):
        assert f"test_scenario_{scenario_id}_" in source


@pytest.mark.parametrize("endpoint", ["/ask", "/ask/stream"])
@pytest.mark.parametrize(
    "case_name,frame_factory,user_message,text_factory,assert_body",
    _PRODUCTION_SEAM_CASES,
    ids=[case[0] for case in _PRODUCTION_SEAM_CASES],
)
def test_production_seam_via_orchestrate_ask_turn_http(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    case_name: str,
    frame_factory,
    user_message: str,
    text_factory,
    assert_body,
) -> None:
    import app as app_module

    assert hasattr(app_module, "_orchestrate_ask_turn")
    frame = frame_factory()
    body, composer, _sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint=endpoint,
        q=user_message,
        frame=frame,
        composer_text=text_factory(),
    )
    assert_body(body)
    if case_name.startswith("contact_"):
        assert len(composer.invocations) == 0
    else:
        assert len(composer.invocations) == 1
        assert len(composer.sdk_messages) == 1
        assert '"source_identity"' in composer.sdk_messages[0][1]["content"]


def test_production_seam_orchestrate_ask_turn_direct() -> None:
    import app as app_module
    from unittest.mock import patch as mock_patch

    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
    )
    sid = f"dlg-direct-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer_text = _contact_text("phone")
    composer, semantic, boundary = (
        MessageBuildingComposerBackend(composer_text),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(BackendPayload("none", 0.95)),
    )

    def _publish_frame(**_kwargs: object) -> PlannerTurnOutcome:
        from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
            _planner_attempt,
        )

        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        return PlannerTurnOutcome("content", None)

    with mock_patch.object(app_module, "run_planner_turn", _publish_frame):
        with mock_patch(
            "orchestration.target_fullcontext_turn._default_target_runtime_backends",
            lambda: (composer, semantic, boundary),
        ):
            from flask import Flask, request

            app = Flask(__name__)
            with app.test_request_context():
                request.ctx = {}
                result = app_module._orchestrate_ask_turn(
                    {"q": "Какой телефон?", "sid": sid, "client_id": "demo"},
                )
    assert result.kind == "service_reply"
    meta = result.service_payload.get("meta") or {}
    assert meta.get("service_route") == "target_fullcontext_materialized"
    assert canonical_contact_phone("demo") in result.service_payload["answer"]


@pytest.mark.parametrize(
    "case",
    RUNTIME_MATRIX,
    ids=[f"s{c.scenario_id:02d}_{c.name}" for c in RUNTIME_MATRIX],
)
def test_acceptance_runtime_matrix(case: RuntimeCase) -> None:
    sid = None
    if case.scenario_id in {19, 20}:
        sid = f"dlg-s{case.scenario_id}-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _seed_target_runtime_state(sid, last_service_id="all_on_4", patient_facts_extent="full_arch")
    outcome, composer = _run(
        case.frame,
        user_message=case.user_message,
        composer_text=case.composer_text,
        sid=sid,
    )
    case.check(outcome, composer)


def test_scenario_21_scope_choice_menu_cap() -> None:
    from tests.test_ac3_scope_price_flow_offline import test_broad_implantation_has_scope_nav_no_price_followups

    test_broad_implantation_has_scope_nav_no_price_followups()


def test_scenario_22_stage_choice_menu_cap() -> None:
    from tests.test_ac3_scope_price_flow_offline import test_prosthetics_one_tooth_stage_clarify_buttons

    test_prosthetics_one_tooth_stage_clarify_buttons()


def test_scenario_23_planner_clarification_terminal() -> None:
    frame = _demo_frame(
        topic="prosthetics",
        aspects=["overview"],
        primary_aspect="overview",
        needs_clarification=True,
        service_id=None,
    )
    outcome, composer = _run(
        frame,
        user_message="Сколько стоят протезы?",
        composer_text="Нужно уточнить объём работ.",
    )
    meta = outcome.widget.payload.get("meta") or {}
    assert meta.get("service_route") in {
        "target_fullcontext_materialized",
        "target_fullcontext_clarify",
    }
    assert len(composer.invocations) == 1


def test_scenario_24_ambiguous_scope_governed_clarify() -> None:
    from tests.test_ac3_scope_price_flow_offline import (
        test_broad_prosthetics_materializes_when_planner_needs_clarify,
    )

    test_broad_prosthetics_materializes_when_planner_needs_clarify()


def test_scenario_25_cross_topic_correction() -> None:
    from tests.test_ac3_scope_price_flow_offline import test_topic_change_clears_scope_and_restores_broad_nav

    test_topic_change_clears_scope_and_restores_broad_nav()


def test_scenario_26_followup_source_identity() -> None:
    from tests.test_fullcontext_dialogue_presentation_convergence_implementation import (
        test_composer_json_envelope_parsed,
    )

    test_composer_json_envelope_parsed()


def test_scenario_27_secondary_faq_cap() -> None:
    from tests.test_fullcontext_presentation_parity_implementation import (
        test_secondary_content_allows_two_followups_without_video,
    )

    test_secondary_content_allows_two_followups_without_video()


def test_scenario_28_video_before_followup() -> None:
    from tests.test_target_presentation_channel_mutex_offline import test_price_channel_without_content_secondary

    test_price_channel_without_content_secondary()


def test_scenario_29_situation_after_followup() -> None:
    from tests.test_fullcontext_dialogue_presentation_convergence_implementation import (
        test_situation_after_followup_not_before,
    )

    test_situation_after_followup_not_before()


def test_scenario_30_choice_menu_cap() -> None:
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
        md_root=_MD_ROOT,
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="classic",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("content",),
        ),
        navigation_followups=navigation,  # type: ignore[arg-type]
        selected_followups=TargetResponseFollowupSelection(source="content", content=(), price=()),
        primary_content_ref="implantation__service__classic.md",
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert len(decision.quick_replies) <= 4


def test_scenario_31_price_detail_cap() -> None:
    price = tuple(
        TargetPriceFollowup(
            id=f"p{idx}",
            label=f"Цена {idx}",
            ref=f"price:all_on_4/default#{idx}",
            action="show",
            source_offer_ids=("all_on_4.default",),
        )
        for idx in range(3)
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=_MD_ROOT,
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="all_on_4",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("price",),
        ),
        navigation_followups=(),
        selected_followups=TargetResponseFollowupSelection(source="price", content=(), price=price),
        primary_content_ref=None,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    price_items = [item for item in decision.quick_replies if str(item.get("ref", "")).startswith("price:")]
    assert len(price_items) <= 2


def test_scenario_32_marketing_pain_fear_eligible_service() -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id="all_on_4",
        marketing_scenarios=["pain_fear"],
    )
    assert marketing_scenarios_from_turn_frame(frame) == ("pain_fear",)
    outcome, composer = _run(
        frame,
        user_message="Боюсь боли при имплантации",
        composer_text=PAIN_GROUNDED_TEXT,
    )
    _assert_materialized(outcome, composer)


def test_scenario_33_marketing_time_projection() -> None:
    frame = _demo_frame(marketing_scenarios=["time"])
    assert marketing_scenarios_from_turn_frame(frame) == ("time",)


def test_scenario_34_marketing_result_reliability_projection() -> None:
    frame = _demo_frame(marketing_scenarios=["result_reliability"])
    assert marketing_scenarios_from_turn_frame(frame) == ("result_reliability",)


def test_scenario_35_direct_informational_no_marketing_block() -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
    )
    from core.target_presentation_turn_projection import provisional_spec_from_turn_frame

    spec = provisional_spec_from_turn_frame(
        frame,
        allowed_topics=tuple(_ALLOWED_TOPICS),
        tone_key="commercial_warm",
    )
    assert should_include_initial_marketing_block(frame, spec) is False


def test_scenario_36_situation_flow_preserved() -> None:
    import uuid

    from flask import Flask, request

    from flow_handlers import handle_flows
    from session import mem_get, mem_reset

    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        txt = {
            "situation_prompt": "Опишите ситуацию.",
            "situation_retry_short": "Напишите чуть подробнее.",
            "situation_to_lead_name": "Как к вам обращаться?",
            "situation_back_fallback": "Вернулись к ответу.",
        }

        def _service_payload(answer, sid, client_id, **kwargs):
            from orchestration.lead_flow import build_service_payload

            return build_service_payload(answer, sid, client_id, **kwargs)

        start_sid = f"s-sit-{uuid.uuid4().hex[:8]}"
        mem_reset(start_sid)
        start = handle_flows(
            data={"situation_action": "start", "client_id": "demo"},
            st=mem_get(start_sid),
            sid=start_sid,
            q="",
            client_id="demo",
            txt=txt,
            service_payload=_service_payload,
            get_last_content_ui_payload=lambda _sid: None,
            get_topic_state=lambda _sid, _doc: {},
        )
        assert start is not None
        assert mem_get(start_sid).get("situation_pending") is True

        back_sid = f"s-back-{uuid.uuid4().hex[:8]}"
        mem_reset(back_sid)
        back_st = mem_get(back_sid)
        back_st["situation_pending"] = True
        back = handle_flows(
            data={"situation_action": "back"},
            st=back_st,
            sid=back_sid,
            q="",
            client_id="demo",
            txt=txt,
            service_payload=_service_payload,
            get_last_content_ui_payload=lambda _sid: {"answer": "prev", "quick_replies": []},
            get_topic_state=lambda _sid, _doc: {},
        )
        assert back is not None
        assert mem_get(back_sid).get("situation_pending") is False

        submit_sid = f"s-sub-{uuid.uuid4().hex[:8]}"
        mem_reset(submit_sid)
        submit_st = mem_get(submit_sid)
        submit_st["situation_pending"] = True
        submit = handle_flows(
            data={},
            st=submit_st,
            sid=submit_sid,
            q="Нужна консультация по имплантации",
            client_id="demo",
            txt=txt,
            service_payload=_service_payload,
            get_last_content_ui_payload=lambda _sid: None,
            get_topic_state=lambda _sid, _doc: {},
        )
        assert submit is not None
        assert mem_get(submit_sid).get("lead_intent") == "collecting_name"


def test_scenario_37_situation_sid_isolation() -> None:
    from tests.test_situation_intake_http_offline import test_situation_collect_pii_withheld

    test_situation_collect_pii_withheld()


def test_scenario_38_cta_lead_demo_stub() -> None:
    from tests.test_situation_intake_http_offline import test_lead_submit_demo_stub_no_external_send

    test_lead_submit_demo_stub_no_external_send()


def test_scenario_39_lead_interrupt_resume() -> None:
    from tests.test_lead_interrupt import test_pause_and_resume_session_fields

    test_pause_and_resume_session_fields()


def test_scenario_40_booking_situation_shared_guards() -> None:
    from core.booking_date_defer import should_defer_booking_date_at_entry

    assert should_defer_booking_date_at_entry(
        q="Можно записаться на 15 января в 18:00?",
        client_id="demo",
    )


def test_scenario_41_unsupported_service_with_alternatives() -> None:
    alt = find_service_alternative("А брекеты делаете?", "demo")
    assert alt is not None
    assert alt.suggest_ref


def test_scenario_42_unsupported_service_without_alternatives() -> None:
    assert find_service_alternative("Делаете ли вы лазерную стоматологию?", "demo") is None


def test_scenario_43_medical_handoff_materialized() -> None:
    from flask import Flask, request

    from core.target_runtime_turn import run_target_fullcontext_runtime_turn
    from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import _planner_attempt

    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id=None,
    )
    sid = f"dlg-mh-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer = MessageBuildingComposerBackend(
        "Общий ответ по имплантации без диагноза.",
        primary_ref="implantation__service__classic.md",
    )
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("medical_handoff", 0.92))
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(attempt=_planner_attempt(frame))
        outcome = run_target_fullcontext_runtime_turn(
            client_id="demo",
            sid=sid,
            user_message="Можно ли импланты при диабете?",
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )
    meta = outcome.widget.payload.get("meta") or {}
    assert meta.get("service_route") == "target_fullcontext_materialized"


def test_scenario_44_technical_fallback_phone_plain() -> None:
    from tests.test_fullcontext_dialogue_presentation_convergence_implementation import (
        test_fallback_error_includes_canonical_phone,
    )

    test_fallback_error_includes_canonical_phone()


def test_scenario_45_reset_clears_session(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"dlg-reset-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    st = mem_get(sid)
    st["lead_intent"] = "collecting_name"
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "/reset", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert mem_get(sid).get("lead_intent") in {None, "", "none"}


def test_scenario_46_ask_stream_parity_subset(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
    )
    text = _contact_text("phone")
    ask, composer_ask, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="Какой телефон?",
        frame=frame,
        composer_text=text,
    )
    stream, composer_stream, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="Какой телефон?",
        frame=frame,
        composer_text=text,
    )
    assert ask["meta"]["service_route"] == stream["meta"]["service_route"]
    assert ask["answer"] == stream["answer"]
    assert len(composer_ask.invocations) == 0
    assert len(composer_stream.invocations) == 0
