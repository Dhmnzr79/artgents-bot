from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_composer import (
    AdaptedComposerDecision,
    ComposerDecision,
    ComposerPatientSituation,
)
from contracts.response_plan_dialogue_context import (
    ShownServiceOptionsSnapshot,
    require_non_negative_int,
)
from contracts.response_plan_post_composer import (
    PostComposerMaterialAuthority,
    PostComposerOwnershipError,
    ResponseSituationDelta,
    ResponseSituationState,
    SituationContinuityPolicy,
)
from core.response_plan_post_composer import resolve_post_composer_selection
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
SESSION = SessionKey(client_id="demo", sid="s1")
AS_OF = date(2026, 8, 15)
POLICY = SituationContinuityPolicy(max_age_turns=3)


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle):
    return PostComposerMaterialAuthority(source_client_id="demo", bundle=demo_bundle)


def _situation(**overrides: object) -> ComposerPatientSituation:
    payload = {
        "extent": "unknown",
        "jaw": "unknown",
        "stage": "unknown",
        "modifiers": (),
    }
    payload.update(overrides)
    return ComposerPatientSituation(**payload)  # type: ignore[arg-type]


def _adapted(**overrides: object) -> AdaptedComposerDecision:
    decision_payload = {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "test",
        "service_reference_kind": "none",
        "option_reference_kind": "none",
        "topic_id": "implantation",
        "explicit_service_id": None,
        "requested_aspect_ids": ("overview",),
        "patient_situation": _situation(),
        "requested_fact_ids": (),
        "source_identity": None,
    }
    decision_payload.update(overrides)
    return AdaptedComposerDecision(
        decision=ComposerDecision(**decision_payload),  # type: ignore[arg-type]
        source_identity=None,
        warnings=(),
        diagnostics=(),
    )


def _resolve(
    adapted: AdaptedComposerDecision,
    material: PostComposerMaterialAuthority,
    *,
    prior: ResponseSituationState | None = None,
    turn: int = 1,
    active_session_service_id: str | None = None,
    shown_options_snapshot: ShownServiceOptionsSnapshot | None = None,
):
    return resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=material,
        active_session_service_id=active_session_service_id,
        prior_situation_state=prior,
        current_turn_index=turn,
        policy=POLICY,
        as_of=AS_OF,
        shown_options_snapshot=shown_options_snapshot,
    )


def test_foreign_client_mismatch_raises(demo_material) -> None:
    other_session = SessionKey(client_id="nikadent", sid="s1")
    with pytest.raises(PostComposerOwnershipError):
        resolve_post_composer_selection(
            session_key=other_session,
            adapted=_adapted(),
            material=demo_material,
            active_session_service_id=None,
            prior_situation_state=None,
            current_turn_index=1,
            policy=POLICY,
            as_of=AS_OF,
        )


def test_full_arch_follow_up_two_turn(demo_material) -> None:
    turn1 = _resolve(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("overview",),
        ),
        demo_material,
        turn=1,
    )
    assert turn1.selection_intent == "service_options"
    ranked = turn1.ranked_service_ids
    assert ranked[:2] == ("all_on_4", "all_on_6")
    assert len(turn1.visible_service_option_ids) >= 2
    confirmed_snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    assert turn1.situation_delta.action == "upsert"
    prior = turn1.situation_delta.state

    turn2 = _resolve(
        _adapted(
            service_reference_kind="none",
            option_reference_kind="shown_options",
            topic_id=None,
            patient_situation=_situation(),
            requested_aspect_ids=("price", "comparison"),
        ),
        demo_material,
        prior=prior,
        turn=2,
        shown_options_snapshot=confirmed_snapshot,
    )
    assert turn2.effective_scope.extent == "full_arch"
    assert turn2.effective_scope.jaw == "upper"
    assert turn2.resolved_topic_id == "implantation"
    assert turn2.response_scope == "topic"
    assert turn2.price_candidate_service_ids == ("all_on_4", "all_on_6")
    assert turn2.comparison_service_ids == ("all_on_4", "all_on_6")
    assert turn2.selection_basis == "shown_options"
    assert turn2.visible_service_option_ids == ()
    assert "zygomatic_implants" not in turn2.price_candidate_service_ids


def test_topic_switch_to_clinic_clears_implantation(demo_material) -> None:
    turn1 = _resolve(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
        ),
        demo_material,
        turn=1,
    )
    prior = turn1.situation_delta.state
    turn2 = _resolve(
        _adapted(
            topic_id=None,
            service_reference_kind="none",
            patient_situation=_situation(),
            requested_aspect_ids=(),
        ),
        demo_material,
        prior=prior,
        turn=2,
    )
    assert turn2.response_scope == "clinic"
    assert turn2.selection_intent == "none"
    assert turn2.ranked_service_ids == ()
    assert turn2.effective_scope.extent == "unknown"


def test_explicit_conflict_preserves_reference_without_recommendation(demo_material) -> None:
    plan = _resolve(
        _adapted(
            service_reference_kind="explicit_current",
            explicit_service_id="all_on_4",
            patient_situation=_situation(extent="one_tooth"),
        ),
        demo_material,
    )
    assert plan.reference_service_id == "all_on_4"
    assert plan.reference_service_status == "conflict"
    assert "all_on_4" not in plan.visible_service_option_ids
    assert any(d.code == "explicit_service_situation_conflict" for d in plan.diagnostics)


def test_missing_fact_preserves_patient_text_and_adds_diagnostic(demo_material) -> None:
    patient_text = "Есть гарантия?"
    plan = _resolve(
        _adapted(
            patient_text=patient_text,
            requested_fact_ids=("missing_fact",),
        ),
        demo_material,
    )
    assert plan.decision.patient_text == patient_text
    assert plan.requested_fact_candidates == ()
    assert any(d.code == "requested_fact_unavailable" for d in plan.diagnostics)


def test_terminal_admin_has_no_services_or_facts(demo_material) -> None:
    plan = _resolve(
        _adapted(route="ADMIN", mode="standard", patient_text=None),
        demo_material,
    )
    assert plan.ranked_service_ids == ()
    assert plan.requested_fact_candidates == ()
    assert plan.selection_intent == "none"


def test_shown_options_topic_mismatch_excludes_snapshot_from_selection(demo_material) -> None:
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    plan = _resolve(
        _adapted(
            option_reference_kind="shown_options",
            topic_id="whitening",
            requested_aspect_ids=("price",),
        ),
        demo_material,
        turn=2,
        shown_options_snapshot=snapshot,
    )
    assert any(d.code == "shown_options_topic_mismatch" for d in plan.diagnostics)
    assert plan.price_candidate_service_ids == ()
    assert plan.selection_basis == "none"


def test_shown_options_one_unavailable_service_keeps_subset(demo_material) -> None:
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "missing_service", "all_on_6"),
        shown_at_turn=1,
    )
    plan = _resolve(
        _adapted(
            option_reference_kind="shown_options",
            topic_id="implantation",
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("comparison",),
        ),
        demo_material,
        turn=2,
        shown_options_snapshot=snapshot,
    )
    assert plan.comparison_service_ids == ("all_on_4", "all_on_6")
    assert any(
        d.code == "shown_options_snapshot_unavailable" and d.detail == "missing_service"
        for d in plan.diagnostics
    )


def test_post_composer_reference_unavailable_blocks_generic_price(demo_material) -> None:
    plan = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=AdaptedComposerDecision(
            decision=ComposerDecision(
                route="ANSWER",
                mode="standard",
                patient_text="test",
                service_reference_kind="explicit_current",
                option_reference_kind="none",
                topic_id="implantation",
                explicit_service_id="nonexistent_service",
                requested_aspect_ids=("price",),
                patient_situation=_situation(extent="full_arch", jaw="upper"),
                requested_fact_ids=(),
                source_identity=None,
            ),
            source_identity=None,
            warnings=(),
            diagnostics=(),
        ),
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=1,
        policy=POLICY,
        as_of=AS_OF,
    )
    assert plan.price_candidate_service_ids == ()
    assert any(d.code == "reference_service_rejected" for d in plan.diagnostics)
    assert any(
        d.code in {"reference_service_unavailable", "post_composer_active_service_unavailable"}
        for d in plan.diagnostics
    )


def test_active_session_missing_at_post_composer_boundary_blocks_generic(demo_material) -> None:
    plan = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=AdaptedComposerDecision(
            decision=ComposerDecision(
                route="ANSWER",
                mode="standard",
                patient_text="Сколько стоит?",
                service_reference_kind="active_session",
                option_reference_kind="none",
                topic_id="implantation",
                explicit_service_id=None,
                requested_aspect_ids=("price",),
                patient_situation=_situation(extent="full_arch", jaw="upper"),
                requested_fact_ids=(),
                source_identity=None,
            ),
            source_identity=None,
            warnings=(),
            diagnostics=(),
        ),
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=2,
        policy=POLICY,
        as_of=AS_OF,
    )
    assert plan.price_candidate_service_ids == ()
    assert any(
        d.code == "post_composer_active_service_unavailable" for d in plan.diagnostics
    )
    assert any(d.code == "reference_service_rejected" for d in plan.diagnostics)


def test_runtime_validation_rejects_bool_shown_at_turn() -> None:
    from contracts.response_plan_dialogue_context import ShownOptionsSnapshotError

    with pytest.raises(ShownOptionsSnapshotError, match="shown_at_turn_bool_forbidden"):
        ShownServiceOptionsSnapshot(
            session_key=SESSION,
            topic_id="implantation",
            service_ids=("all_on_4",),
            shown_at_turn=True,  # type: ignore[arg-type]
        )


def test_runtime_validation_rejects_nan_current_turn_index() -> None:
    from contracts.response_plan_dialogue_context import ShownOptionsSnapshotError

    with pytest.raises(ShownOptionsSnapshotError, match="current_turn_index_nan_forbidden"):
        require_non_negative_int("current_turn_index", float("nan"))


def test_runtime_validation_rejects_invalid_situation_extent() -> None:
    from contracts.response_plan_post_composer import ResponseSituationState

    with pytest.raises(ValueError, match="situation_extent_invalid"):
        ResponseSituationState(
            session_key=SESSION,
            topic_id="implantation",
            extent="invalid_extent",  # type: ignore[arg-type]
            jaw="unknown",
            stage="unknown",
            modifiers=(),
            set_at_turn=1,
        )


def test_runtime_validation_rejects_bool_set_at_turn() -> None:
    from contracts.response_plan_post_composer import ResponseSituationState

    with pytest.raises(ValueError, match="set_at_turn_bool_forbidden"):
        ResponseSituationState(
            session_key=SESSION,
            topic_id="implantation",
            extent="unknown",
            jaw="unknown",
            stage="unknown",
            modifiers=(),
            set_at_turn=True,  # type: ignore[arg-type]
        )


def test_runtime_validation_rejects_float_max_age_turns() -> None:
    from contracts.response_plan_dialogue_context import ShownOptionsSnapshotError

    with pytest.raises(ShownOptionsSnapshotError, match="max_age_turns_float_forbidden"):
        SituationContinuityPolicy(max_age_turns=1.5)  # type: ignore[arg-type]


def test_runtime_validation_rejects_invalid_selection_basis() -> None:
    from contracts.response_plan_post_composer import PostComposerSelectionError, PostComposerSelectionPlan
    from contracts.effective_scope import EffectiveScope
    from contracts.response_plan_composer import ComposerDecision

    with pytest.raises(PostComposerSelectionError, match="selection_basis_invalid"):
        PostComposerSelectionPlan(
            session_key=SESSION,
            source_client_id="demo",
            decision=ComposerDecision(
                route="ANSWER",
                mode="standard",
                patient_text="test",
                service_reference_kind="none",
                option_reference_kind="none",
                topic_id="implantation",
                explicit_service_id=None,
                requested_aspect_ids=("overview",),
                patient_situation=_situation(),
                requested_fact_ids=(),
                source_identity=None,
            ),
            resolved_topic_id="implantation",
            response_scope="topic",
            reference_service_id=None,
            reference_service_status="none",
            effective_scope=EffectiveScope(),
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=(),
            comparison_service_ids=(),
            selection_basis="invalid_basis",  # type: ignore[arg-type]
            selection_intent="none",
            requested_fact_candidates=(),
            situation_delta=ResponseSituationDelta(action="keep"),
            adapter_diagnostics=(),
            diagnostics=(),
        )


def test_runtime_validation_rejects_situation_state_foreign_session() -> None:
    from contracts.response_plan_post_composer import PostComposerSelectionError, PostComposerSelectionPlan
    from contracts.effective_scope import EffectiveScope
    from contracts.response_plan_composer import ComposerDecision
    from contracts.response_plan_post_composer import ResponseSituationDelta

    foreign_state = ResponseSituationState(
        session_key=SessionKey(client_id="demo", sid="other"),
        topic_id="implantation",
        extent="unknown",
        jaw="unknown",
        stage="unknown",
        modifiers=(),
        set_at_turn=1,
    )
    with pytest.raises(PostComposerSelectionError, match="situation_state_session_mismatch"):
        PostComposerSelectionPlan(
            session_key=SESSION,
            source_client_id="demo",
            decision=ComposerDecision(
                route="ANSWER",
                mode="standard",
                patient_text="test",
                service_reference_kind="none",
                option_reference_kind="none",
                topic_id="implantation",
                explicit_service_id=None,
                requested_aspect_ids=("overview",),
                patient_situation=_situation(),
                requested_fact_ids=(),
                source_identity=None,
            ),
            resolved_topic_id="implantation",
            response_scope="topic",
            reference_service_id=None,
            reference_service_status="none",
            effective_scope=EffectiveScope(),
            ranked_service_ids=(),
            visible_service_option_ids=(),
            price_candidate_service_ids=(),
            comparison_service_ids=(),
            selection_basis="none",
            selection_intent="none",
            requested_fact_candidates=(),
            situation_delta=ResponseSituationDelta(action="upsert", state=foreign_state),
            adapter_diagnostics=(),
            diagnostics=(),
        )


def test_known_inactive_snapshot_service_excluded_after_composer(demo_bundle) -> None:
    bundle = demo_bundle.model_copy(deep=True)
    bundle.services["all_on_6"] = bundle.services["all_on_6"].model_copy(update={"active": False})
    material = PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle)
    prior = ResponseSituationState(
        session_key=SESSION,
        topic_id="implantation",
        extent="full_arch",
        jaw="upper",
        stage="unknown",
        modifiers=(),
        set_at_turn=1,
    )
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    plan = _resolve(
        _adapted(
            option_reference_kind="shown_options",
            topic_id=None,
            patient_situation=_situation(),
            requested_aspect_ids=("price", "comparison"),
        ),
        material,
        prior=prior,
        turn=2,
        shown_options_snapshot=snapshot,
    )
    assert plan.price_candidate_service_ids == ("all_on_4",)
    assert plan.comparison_service_ids == ("all_on_4",)
    assert any(d.code == "shown_options_snapshot_unavailable" for d in plan.diagnostics)


def test_adapter_active_session_rejection_blocks_generic_selection(demo_material) -> None:
    from contracts.response_plan_composer import ComposerDecisionDiagnostic

    adapted = AdaptedComposerDecision(
        decision=ComposerDecision(
            route="ANSWER",
            mode="standard",
            patient_text="Сколько стоит?",
            service_reference_kind="none",
            option_reference_kind="none",
            topic_id="implantation",
            explicit_service_id=None,
            requested_aspect_ids=("price",),
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_fact_ids=(),
            source_identity=None,
        ),
        source_identity=None,
        warnings=(),
        diagnostics=(
            ComposerDecisionDiagnostic(code="active_session_service_unavailable"),
        ),
    )
    plan = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=1,
        policy=POLICY,
        as_of=AS_OF,
    )
    assert plan.price_candidate_service_ids == ()
    assert any(d.code == "reference_service_rejected" for d in plan.diagnostics)
