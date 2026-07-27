"""COMPLETION checker — FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_contact_authority import (
    canonical_contact_scalar,
    load_clinic_contact_facts,
    materialize_clinic_contact_primary_evidence,
    normalize_contact_scalar,
)
from core.target_marketing_selector import select_target_marketing
from core.target_presentation_turn_projection import (
    resolve_bound_marketing_flags,
    should_include_initial_marketing_block,
)
from core.target_response_verifier import (
    TargetResponseVerificationError,
    verify_target_composed_response,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from core.target_runtime_session import read_target_runtime_session
from session import mem_get, mem_reset
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_contact_value_verification_and_marketing_scenario_activation_harness import (
    BackendPayload,
    MessageBuildingComposerBackend,
    build_frame,
    orchestrate_via_app,
    pipeline_result_materialized,
    run_runtime_turn,
)
from tests.test_final_fullcontext_dialogue_runtime_convergence_implementation import (
    _assert_materialized,
)
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_target_boundary_enforced_fullcontext_response import PAIN_GROUNDED_TEXT
from tests.test_target_response_verifier import (
    RecordingBackend,
    _cached_context,
    _request,
    _response,
    _spec,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_BUNDLE = load_response_schema_bundle(_TARGET_ROOT)
_DOCTOR_CATALOG = load_doctor_catalog(_DEMO_ROOT / "doctor_catalog.json")
_ALLOWED_SERVICES = frozenset(_BUNDLE.services.keys())
_ALLOWED_TOPICS = frozenset(
    {"implantation", "doctors", "clinic", "prosthetics", "aesthetics", "whitening"}
)
_TODAY = __import__("datetime").date(2026, 7, 15)
from contracts.doctor_schema_refs import build_doctor_source_refs
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from core.response_schema_kb_index import build_response_schema_kb_refs

_EXTERNAL_INDEX = ResponseSchemaExternalIndex(
    kb_refs=build_response_schema_kb_refs(_DEMO_ROOT / "md"),
    doctor_refs=build_doctor_source_refs(_DOCTOR_CATALOG),
)


def _demo_frame(**overrides: object):
    return build_frame(
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
        **overrides,
    )


def _contact_blocks(*fields: str):
    return materialize_clinic_contact_primary_evidence(
        "demo",
        fields=fields,  # type: ignore[arg-type]
    )


def _natural_wrapper(field: str) -> str:
    scalar = canonical_contact_scalar(field, "demo")  # type: ignore[arg-type]
    assert scalar
    wrappers = {
        "phone": f"Позвоните нам: {scalar}",
        "address": f"Мы находимся по адресу {scalar}",
        "parking": f"Для пациентов доступна парковка: {scalar}",
        "hours": f"Мы работаем {scalar}",
        "whatsapp": f"Напишите нам в WhatsApp: {scalar}",
    }
    return wrappers[field]


def _verify_contact_natural(field: str, answer: str) -> None:
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks(field),
    )
    result = verify_target_composed_response(
        request,
        _response(request, answer),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"


def _run_marketing(
    frame,
    *,
    user_message: str,
    composer_text: str,
    sid: str | None = None,
):
    return run_runtime_turn(
        sid=sid or f"mkt-{uuid.uuid4().hex[:8]}",
        user_message=user_message,
        composer_text=composer_text,
        frame=frame,
    )


def _amplifier_refs_from_composer(composer: MessageBuildingComposerBackend) -> list[str]:
    assert composer.invocations
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    return [block["ref"] for block in evidence]


def _materialized_amplifiers(outcome) -> tuple[str, ...]:
    materialized = pipeline_result_materialized(outcome)
    assert materialized is not None
    selection = materialized.session_selection
    assert selection is not None
    return selection.shown_amplifier_refs


@pytest.mark.parametrize(
    "field",
    ["phone", "address", "parking", "hours", "whatsapp"],
)
def test_contact_natural_wrapper_passes(field: str) -> None:
    _verify_contact_natural(field, _natural_wrapper(field))


def test_contact_address_parking_mixed_passes() -> None:
    facts = load_clinic_contact_facts("demo")
    assert facts.address_display and facts.parking_display
    answer = (
        f"Мы находимся по адресу {facts.address_display}. "
        f"Парковка: {facts.parking_display}"
    )
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks("address", "parking"),
    )
    result = verify_target_composed_response(
        request,
        _response(request, answer),
        cached_full_context=_cached_context(),
        semantic_backend=RecordingBackend(),
    )
    assert result.verification_status == "verified"


def test_contact_changed_address_blocks() -> None:
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks("address"),
    )
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            request,
            _response(request, "Мы находимся по адресу ул. Неверная, 1"),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert exc.value.code == "target_verifier_clinic_contact_missing"


def test_contact_changed_phone_blocks() -> None:
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks("phone"),
    )
    with pytest.raises(TargetResponseVerificationError) as exc:
        verify_target_composed_response(
            request,
            _response(request, "Позвоните: +7 (000) 000-00-00"),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )
    assert exc.value.code == "target_verifier_clinic_contact_missing"


def test_contact_omitted_requested_field_blocks() -> None:
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=_contact_blocks("address"),
    )
    with pytest.raises(TargetResponseVerificationError):
        verify_target_composed_response(
            request,
            _response(request, "Добро пожаловать в нашу клинику."),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
        )


def test_contact_unrequested_fields_not_required() -> None:
    _verify_contact_natural("address", _natural_wrapper("address"))


@pytest.mark.parametrize("endpoint", ["/ask", "/ask/stream"])
def test_contact_http_parity(monkeypatch, endpoint: str) -> None:
    import app as app_module

    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_address"],
        primary_aspect="contact_address",
    )
    body, composer, _sid = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint=endpoint,
        q="Где вы находитесь?",
        frame=frame,
        composer_text=_natural_wrapper("address"),
    )
    assert body["meta"]["service_route"] == "target_fullcontext_materialized"
    assert "Тверская" in body["answer"]
    assert composer.sdk_messages


@pytest.mark.parametrize(
    ("scenario", "user_message", "composer_text"),
    [
        ("pain_fear", "Боюсь боли при имплантации", PAIN_GROUNDED_TEXT),
        (
            "result_reliability",
            "Боюсь, что имплант не приживётся",
            "Приживление зависит от индивидуальных факторов и контроля.",
        ),
        (
            "cost",
            "Переживаю, что имплантация дорогая",
            "Стоимость можно обсудить на консультации.",
        ),
        (
            "time",
            "Кажется, лечение слишком долгое",
            "Сроки зависят от клинической ситуации.",
        ),
        (
            "doctor_trust",
            "Боюсь, что врач неопытный",
            "Врачи клиники проходят строгий отбор.",
        ),
    ],
)
def test_marketing_concern_runtime_evidence_and_session(
    scenario: str,
    user_message: str,
    composer_text: str,
) -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id="all_on_4",
        marketing_scenarios=[scenario],
    )
    sid = f"concern-{scenario}"
    mem_reset(sid)
    outcome, composer, _semantic = _run_marketing(
        frame,
        user_message=user_message,
        composer_text=composer_text,
        sid=sid,
    )
    _assert_materialized(outcome, composer)
    refs = _amplifier_refs_from_composer(composer)
    assert any(ref.startswith(("kb:", "fact:", "doctor:")) for ref in refs)
    assert _materialized_amplifiers(outcome)
    session = read_target_runtime_session(sid)
    assert session.shown_amplifier_refs


def test_marketing_topic_only_service_id_none_selects_amplifier() -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id=None,
        marketing_scenarios=["pain_fear"],
    )
    outcome, composer, _semantic = _run_marketing(
        frame,
        user_message="Боюсь боли",
        composer_text=PAIN_GROUNDED_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert any(
        "pain" in ref for ref in _amplifier_refs_from_composer(composer)
    )


def test_marketing_unrelated_topic_no_implantation_amplifier() -> None:
    selection = select_target_marketing(
        _BUNDLE,
        _DOCTOR_CATALOG,
        _EXTERNAL_INDEX,
        semantic_context="default",
        service_id=None,
        today=_TODAY,
        include_initial_block=False,
        marketing_scenarios=["pain_fear"],
        turn_topic="whitening",
    )
    assert selection.amplifier_refs == ()


def test_marketing_initial_block_off_scenario_on() -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id=None,
        marketing_scenarios=["pain_fear"],
    )
    from core.target_presentation_turn_projection import provisional_spec_from_turn_frame

    spec = provisional_spec_from_turn_frame(
        frame,
        allowed_topics=tuple(_ALLOWED_TOPICS),
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
    assert scenarios == ("pain_fear",)
    assert brand is None


def test_marketing_initial_block_on_without_scenario() -> None:
    frame = _demo_frame(
        topic="implantation",
        aspects=["overview"],
        primary_aspect="overview",
        service_id="all_on_4",
        marketing_scenarios=[],
    )
    spec = _spec(
        service_id="all_on_4",
        required_components=("content",),
        required_fact_ids=(),
        allow_marketing_facts=True,
    )
    include, scenarios, _brand = resolve_bound_marketing_flags(
        frame,
        spec,
        boundary_allows_marketing=True,
        brand_term="demo",
        marketing_scenarios=[],
    )
    assert include is True
    assert scenarios == ()


def test_marketing_contacts_suppress_scenarios() -> None:
    frame = _demo_frame(
        topic="clinic",
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
        marketing_scenarios=["pain_fear"],
    )
    from core.target_presentation_turn_projection import provisional_spec_from_turn_frame

    spec = provisional_spec_from_turn_frame(
        frame,
        allowed_topics=tuple(_ALLOWED_TOPICS),
    )
    _include, scenarios, _brand = resolve_bound_marketing_flags(
        frame,
        spec,
        boundary_allows_marketing=True,
        brand_term="demo",
        marketing_scenarios=["pain_fear"],
    )
    assert scenarios == ()


def test_marketing_no_repeat_shown_amplifier() -> None:
    shown_ref = "kb:implantation__faq__pain.md#korotko"
    frame = _demo_frame(
        topic="implantation",
        service_id="all_on_4",
        marketing_scenarios=["pain_fear"],
    )
    sid = "mkt-repeat"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        shown_fact_ids=[],
        shown_amplifier_refs=[shown_ref],
        shown_consultation_value_refs=[],
        shown_video_ids=[],
        shown_content_followup_refs=[],
        shown_price_followup_refs=[],
        situation_offered=False,
    )
    outcome, composer, _semantic = _run_marketing(
        frame,
        user_message="Снова боюсь боли",
        composer_text=PAIN_GROUNDED_TEXT,
        sid=sid,
    )
    _assert_materialized(outcome, composer)
    refs = _amplifier_refs_from_composer(composer)
    assert shown_ref not in refs


def test_marketing_no_eligible_amplifier_leaves_answer() -> None:
    frame = _demo_frame(
        topic="implantation",
        service_id="all_on_4",
        marketing_scenarios=["pain_fear"],
    )
    sid = "mkt-all-shown"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        shown_fact_ids=[],
        shown_amplifier_refs=[
            "kb:implantation__faq__pain.md#korotko",
            "kb:implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut",
        ],
        shown_consultation_value_refs=[],
        shown_video_ids=[],
        shown_content_followup_refs=[],
        shown_price_followup_refs=[],
        situation_offered=False,
    )
    outcome, composer, _semantic = _run_marketing(
        frame,
        user_message="Боюсь боли",
        composer_text=PAIN_GROUNDED_TEXT,
        sid=sid,
    )
    _assert_materialized(outcome, composer)
    refs = _amplifier_refs_from_composer(composer)
    assert not any("implantation__faq__pain" in ref for ref in refs)


def test_runtime_sdk_message_builder_invoked() -> None:
    frame = _demo_frame(
        topic="implantation",
        service_id="all_on_4",
        marketing_scenarios=["pain_fear"],
    )
    outcome, composer, _semantic = _run_marketing(
        frame,
        user_message="Боюсь боли",
        composer_text=PAIN_GROUNDED_TEXT,
    )
    _assert_materialized(outcome, composer)
    assert composer.sdk_messages
    assert composer.invocations


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_turn_topic_reaches_selector_signature() -> None:
    import inspect

    from core.target_marketing_selector import select_target_marketing

    assert "turn_topic" in inspect.signature(select_target_marketing).parameters


def test_contact_scalar_normalization() -> None:
    raw = "г.  Москва,\nул. Тверская"
    assert normalize_contact_scalar(raw) == "г. Москва, ул. Тверская"
