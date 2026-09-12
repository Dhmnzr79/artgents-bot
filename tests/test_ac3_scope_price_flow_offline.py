from __future__ import annotations

import hashlib
import re
from pathlib import Path

from contracts.effective_scope import EffectiveScope
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref, is_ui_stage_ref
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from tests.test_demo_target_turn_frame_bound_response import (
    RecordingComposerBackend,
    RecordingSemanticBackend,
    VALID_TEXT,
    _envelope,
    _frame,
    _pipeline_inputs,
)
from tests.test_w1_family_price_overview_offline import _family_overview_frame

TARGET_ROOT = Path("clients/demo/target_response")
_ARTIFACT_DIR = Path("docs/artifacts/w1b_wip_checkpoint_2026-07-24")


def _run_family_price(**overrides):
    composer = RecordingComposerBackend(text="Краткий обзор цен.")
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    frame_overrides = overrides.pop("frame_overrides", {})
    inputs.update(overrides)
    return run_target_offline_turn_frame_bound_response(
        _family_overview_frame(**frame_overrides),
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )


def test_broad_implantation_has_scope_nav_no_price_followups() -> None:
    result = _run_family_price(user_message="Сколько стоит имплантация?")
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "broad_family_price"
    assert len(result.verified.navigation_followups) == 2
    refs = {item.ref for item in result.verified.navigation_followups}
    assert refs == {
        "target:ui_scope/implantation/one_tooth",
        "target:ui_scope/implantation/full_arch",
    }
    assert result.verified.selected_followups.price == ()


def test_scoped_one_tooth_has_no_scope_nav() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="implantation",
        source="session",
        provenance=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
    )
    result = _run_family_price(
        user_message="продолжить",
        effective_scope=scope,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage in {
        "scoped_family_price",
        "concrete_service_price",
    }
    assert result.verified.navigation_followups == ()


def test_named_service_all_on_4_unchanged() -> None:
    composer = RecordingComposerBackend(text=VALID_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id == "all_on_4"
    assert result.dispatch.policy_request.response_stage is None


def test_broad_prosthetics_same_mechanism() -> None:
    frame = _family_overview_frame(topic="prosthetics")
    composer = RecordingComposerBackend(text="Обзор протезирования.")
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = "Сколько стоит протезирование?"
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "broad_family_price"
    assert result.verified.spec.scope_price_topic == "prosthetics"


def test_broad_prosthetics_materializes_when_planner_needs_clarify() -> None:
    frame = _family_overview_frame(topic="prosthetics", needs_clarify=True)
    composer = RecordingComposerBackend(text="Обзор протезирования.")
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = "Сколько стоит протезирование?"
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "broad_family_price"
    assert len(result.verified.navigation_followups) == 3
    refs = {item.ref for item in result.verified.navigation_followups}
    assert refs == {
        "target:ui_scope/prosthetics/one_tooth",
        "target:ui_scope/prosthetics/few_teeth",
        "target:ui_scope/prosthetics/full_arch",
    }


def test_full_arch_scoped_has_no_scope_nav() -> None:
    scope = EffectiveScope(
        extent="full_arch",
        topic="implantation",
        source="session",
        provenance=build_ui_scope_ref(topic="implantation", extent="full_arch"),
    )
    result = _run_family_price(effective_scope=scope, user_message="продолжить")
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.navigation_followups == ()


def test_topic_change_clears_scope_and_restores_broad_nav() -> None:
    import uuid

    from contracts.ui_scope_action import UiScopeAction
    from core.target_runtime_session import (
        read_target_runtime_session,
        sync_session_patient_facts_topic,
        write_session_patient_facts_from_ui_action,
    )
    from session import mem_reset

    sid = f"s-ac3-topic-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    write_session_patient_facts_from_ui_action(
        sid,
        UiScopeAction(
            extent="one_tooth",
            topic="implantation",
            ref=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
        ),
    )
    assert read_target_runtime_session(sid).patient_facts is not None
    sync_session_patient_facts_topic(sid, current_topic="prosthetics")
    assert read_target_runtime_session(sid).patient_facts is None

    result = _run_family_price(
        user_message="Сколько стоит протезирование?",
        frame_overrides={"topic": "prosthetics"},
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "broad_family_price"
    assert len(result.verified.navigation_followups) == 3
    refs = {item.ref for item in result.verified.navigation_followups}
    assert refs == {
        "target:ui_scope/prosthetics/one_tooth",
        "target:ui_scope/prosthetics/few_teeth",
        "target:ui_scope/prosthetics/full_arch",
    }


def test_broad_answer_has_no_price_followups() -> None:
    result = _run_family_price(user_message="Сколько стоит имплантация?")
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.selected_followups.price == ()
    assert result.verified.selected_followups.content == ()


def test_data_gap_returns_empty_offers_without_invented_price() -> None:
    from core.target_scope_aware_price_package import assemble_scope_aware_price_package
    from contracts.target_response_spec import TargetResponseSpec
    from core.target_strategy_context import strategy_match_from_effective_scope

    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(Path("clients/demo/doctor_catalog.json"))
    inputs = _pipeline_inputs()
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance="test",
    )
    spec = TargetResponseSpec.model_validate(
        {
            "response_mode": "answer",
            "response_stage": "data_gap",
            "scope_price_topic": "prosthetics",
            "tone_key": "commercial_warm",
            "allowed_topics": ("prosthetics",),
            "required_components": ("price",),
            "allow_marketing_facts": False,
            "allow_cta": False,
        }
    )
    package = assemble_scope_aware_price_package(
        bundle,
        doctors,
        inputs["external_index"],  # type: ignore[arg-type]
        inputs["consultation_values"],  # type: ignore[arg-type]
        spec=spec,
        effective_scope=scope,
        strategy_context=strategy_match_from_effective_scope(scope),
        client_id="demo",
        md_root=inputs["md_root"],  # type: ignore[arg-type]
        semantic_context="prosthetics",
        today=inputs["today"],  # type: ignore[arg-type]
        include_initial_block=False,
        include_cta=False,
    )
    assert package.materials.offers == ()
    assert package.navigation_followups == ()


def test_prosthetics_one_tooth_stage_clarify_buttons() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance=build_ui_scope_ref(topic="prosthetics", extent="one_tooth"),
    )
    result = _run_family_price(
        effective_scope=scope,
        user_message="продолжить",
        frame_overrides={"topic": "prosthetics"},
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "stage_clarify"
    assert len(result.verified.navigation_followups) == 2
    assert all(is_ui_stage_ref(item.ref) for item in result.verified.navigation_followups)
    assert result.verified.selected_followups.price == ()
    assert result.verified.selected_cta_key is None


def test_prosthetics_stage_click_then_scoped_services() -> None:
    scope = EffectiveScope(
        extent="one_tooth",
        topic="prosthetics",
        source="session",
        provenance=build_ui_stage_ref(topic="prosthetics", stage="natural_tooth_present"),
        stage="natural_tooth_present",
    )
    frame = _family_overview_frame(topic="prosthetics")
    composer = RecordingComposerBackend(text="Цены на коронки.")
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = "продолжить"
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        effective_scope=scope,
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "concrete_service_price"
    assert result.verified.navigation_followups == ()


def test_concrete_all_on_4_has_payment_price_followup() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": "all_on_4",
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )
    composer = RecordingComposerBackend(text=VALID_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        frame,
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    refs = [item.ref for item in result.verified.selected_followups.price]
    assert "price:all_on_4/stages" in refs


def test_broad_implantation_marketing_limited() -> None:
    composer = RecordingComposerBackend(text="Краткий обзор цен.")
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["include_initial_block"] = True
    inputs["user_message"] = "Сколько стоит имплантация?"
    result = run_target_offline_turn_frame_bound_response(
        _family_overview_frame(),
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
        client_id="demo",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.verified.spec.response_stage == "broad_family_price"
    assert result.verified.spec.allow_marketing_facts
    import json

    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    fact_blocks = [block for block in evidence if block.get("kind") == "commercial_fact"]
    assert len(fact_blocks) <= 1


def test_w1b_snapshot_checksums_unchanged() -> None:
    checksums = (_ARTIFACT_DIR / "checksums.sha256").read_text(encoding="utf-8")
    expected = dict(re.findall(r"^([A-Z_]+)=([A-F0-9]+)", checksums, re.M))
    files = {
        "TRACKED_PATCH": _ARTIFACT_DIR / "w1b_tracked.patch",
        "DIFF_STAT": _ARTIFACT_DIR / "diff_stat.txt",
    }
    for key, path in files.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        assert digest == expected[key]
