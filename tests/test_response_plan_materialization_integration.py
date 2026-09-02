from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope
from contracts.response_plan import SessionKey
from contracts.response_plan_composer import AdaptedComposerDecision, ComposerDecisionDiagnostic
from contracts.response_plan_composer_input import ComposerInputContext
from contracts.response_plan_dialogue_context import (
    ShownOptionsFreshnessPolicy,
    ShownServiceOptionsSnapshot,
)
from contracts.response_plan_materialization import OfferConditionEvidence, ResponsePlanMaterializationSources
from contracts.response_plan_post_composer import PostComposerMaterialAuthority, SituationContinuityPolicy
from core.response_plan_composer_executor import execute_composer_decision
from core.response_plan_materialization import resolve_materialized_response
from core.response_plan_post_composer import resolve_post_composer_selection
from core.response_schema_loader import load_response_schema_bundle
from tests.test_response_plan_composer_executor import RecordingBackend
from tests.test_response_plan_composer_input import _authority, _demo_corpus, _input_context, _session_context
from tests.test_response_plan_materialization import (
    AS_OF,
    SESSION,
    _adapted,
    _complete_empty_evidence,
    _complete_with_conditions,
    _selection_from_post_composer,
    _situation,
    _sources,
    _terminal_authorities,
)

TARGET_ROOT = Path("clients/demo/target_response")


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


@pytest.fixture
def demo_material(demo_bundle):
    return PostComposerMaterialAuthority(source_client_id="demo", bundle=demo_bundle)


def _all_on_4_evidence() -> dict[str, OfferConditionEvidence]:
    return _complete_empty_evidence(
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )


def _resolve_full(adapted, material, **kwargs):
    selection = _selection_from_post_composer(adapted, material, **kwargs)
    return resolve_materialized_response(
        selection,
        adapted,
        _sources(material, condition_evidence_by_offer=_all_on_4_evidence()),
        as_of=AS_OF,
    )


def test_two_turn_overview_then_price_without_duplicate_options(demo_material) -> None:
    turn1_adapted = _adapted(
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        requested_aspect_ids=("overview",),
    )
    turn1 = _resolve_full(turn1_adapted, demo_material)
    assert turn1.resolved.service_options_block is not None
    assert turn1.resolved.price_block is None
    shown_ids = tuple(item.service_id for item in turn1.resolved.service_options_block.options)
    assert shown_ids[:2] == ("all_on_4", "all_on_6")

    from contracts.response_plan_dialogue_context import ShownServiceOptionsSnapshot

    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=shown_ids,
        shown_at_turn=1,
    )
    turn2_adapted = _adapted(
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        patient_situation=_situation(),
        requested_aspect_ids=("price",),
    )
    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=turn2_adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=turn1.situation_delta.state,
        current_turn_index=2,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=snapshot,
    )
    outcome = resolve_materialized_response(
        selection,
        turn2_adapted,
        _sources(demo_material, condition_evidence_by_offer=_all_on_4_evidence()),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert outcome.resolved.service_options_block is None
    assert set(selection.price_candidate_service_ids) == set(shown_ids)


def test_comparison_without_price_has_no_price_or_options(demo_material) -> None:
    turn1 = _selection_from_post_composer(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("overview",),
        ),
        demo_material,
    )
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    adapted = _adapted(
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        patient_situation=_situation(),
        requested_aspect_ids=("comparison",),
    )
    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=turn1.situation_delta.state,
        current_turn_index=2,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=snapshot,
    )
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is None
    assert outcome.resolved.service_options_block is None
    assert selection.comparison_service_ids == ("all_on_4", "all_on_6")


def test_exact_service_price_not_replaced_by_cheaper_alternative(demo_material) -> None:
    adapted = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_6",
        requested_aspect_ids=("price",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    assert selection.price_candidate_service_ids == ("all_on_6",)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(
            demo_material,
            condition_evidence_by_offer=_complete_empty_evidence(
                "all_on_6.jaw.implantium",
                "all_on_6.jaw.impro",
                "all_on_6.jaw.nobel",
            ),
        ),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert all(offer_id.startswith("all_on_6") for offer_id in outcome.resolved.price_block.offer_ids)
    assert not any(offer_id.startswith("all_on_4") for offer_id in outcome.resolved.price_block.offer_ids)


def test_rejected_reference_has_no_price_candidates(demo_material) -> None:
    base = _adapted(
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_6",
        requested_aspect_ids=("price",),
    )
    adapted = AdaptedComposerDecision(
        decision=base.decision,
        source_identity=None,
        warnings=(),
        diagnostics=(
            ComposerDecisionDiagnostic(code="service_id_not_allowed", detail="all_on_6"),
        ),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    assert selection.price_candidate_service_ids == ()
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is None


def test_finalized_ids_match_frozen_blocks(demo_material) -> None:
    adapted = _adapted(
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        requested_aspect_ids=("overview",),
    )
    outcome = _resolve_full(adapted, demo_material)
    block = outcome.resolved.service_options_block
    assert block is not None
    option_ids = tuple(item.service_id for item in block.options)
    assert outcome.resolved.finalized_commercial_ids.shown_service_option_ids == option_ids
    assert outcome.resolved.session_delta.shown_service_option_ids == option_ids
    assert outcome.ui_projection.projected_commercial_ids.shown_service_option_ids == option_ids


def test_blocking_and_streaming_share_same_render_path(demo_material) -> None:
    adapted = _adapted(
        patient_situation=_situation(extent="full_arch", jaw="upper"),
        requested_aspect_ids=("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    blocking = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, transport_kind="blocking"),
        as_of=AS_OF,
    )
    streaming = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, transport_kind="streaming"),
        as_of=AS_OF,
    )
    assert blocking.rendered_text == streaming.rendered_text
    assert blocking.resolved.model_dump(exclude={"transport_kind"}) == streaming.resolved.model_dump(
        exclude={"transport_kind"}
    )


@pytest.mark.parametrize(
    "route,mode,patient_text",
    [
        ("ANSWER", "standard", "Ответ."),
        ("ANSWER", "contacts", None),
        ("ADMIN", "standard", None),
        ("ADMIN", "medical_terminal", None),
        ("CLARIFY", "standard", "Уточните."),
    ],
)
def test_all_route_mode_pairs_materialize(
    demo_material,
    route: str,
    mode: str,
    patient_text: str | None,
) -> None:
    adapted = _adapted(
        route=route,
        mode=mode,
        patient_text=patient_text,
        topic_id=None if route != "ANSWER" or mode == "contacts" else "implantation",
        requested_aspect_ids=() if route != "ANSWER" or mode != "standard" else ("overview",),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert outcome.resolved.route == route
    assert outcome.resolved.mode == mode
    if route in {"ADMIN", "CLARIFY"} or (route == "ANSWER" and mode == "contacts"):
        assert outcome.resolved.price_block is None
        assert outcome.resolved.service_options_block is None


def _answer_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "route": "ANSWER",
        "mode": "standard",
        "patient_text": "All-on-4 стоит столько-то.",
        "service_reference_kind": "explicit_current",
        "option_reference_kind": "none",
        "topic_id": "implantation",
        "explicit_service_id": "all_on_4",
        "requested_aspect_ids": ["price"],
        "patient_situation": {
            "extent": "one_tooth",
            "jaw": "upper",
            "stage": "unknown",
            "modifiers": [],
        },
        "requested_fact_ids": [],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_executor_to_materialization_single_backend_call(demo_material) -> None:
    backend = RecordingBackend(_answer_json())
    context = _input_context(current_user_message="Сколько стоит All-on-4?")
    executor_result = execute_composer_decision(context, backend)
    assert len(backend.calls) == 1

    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=executor_result.adapted_decision,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=None,
        current_turn_index=1,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
    )
    outcome = resolve_materialized_response(
        selection,
        executor_result.adapted_decision,
        _sources(demo_material, condition_evidence_by_offer=_all_on_4_evidence()),
        as_of=AS_OF,
    )
    assert outcome.resolved.patient_text == executor_result.adapted_decision.decision.patient_text
    assert selection.price_candidate_service_ids == ("all_on_4",)


def test_two_offers_same_condition_id_preserve_offer_linkage(demo_material) -> None:
    turn1 = _selection_from_post_composer(
        _adapted(
            patient_situation=_situation(extent="full_arch", jaw="upper"),
            requested_aspect_ids=("overview",),
        ),
        demo_material,
    )
    adapted = _adapted(
        service_reference_kind="none",
        option_reference_kind="shown_options",
        topic_id=None,
        patient_situation=_situation(),
        requested_aspect_ids=("price",),
    )
    snapshot = ShownServiceOptionsSnapshot(
        session_key=SESSION,
        topic_id="implantation",
        service_ids=("all_on_4", "all_on_6"),
        shown_at_turn=1,
    )
    selection = resolve_post_composer_selection(
        session_key=SESSION,
        adapted=adapted,
        material=demo_material,
        active_session_service_id=None,
        prior_situation_state=turn1.situation_delta.state,
        current_turn_index=2,
        policy=SituationContinuityPolicy(max_age_turns=3),
        as_of=AS_OF,
        shown_options_snapshot=snapshot,
    )
    evidence = {
        "all_on_4.jaw.implantium": _complete_with_conditions(
            "all_on_4.jaw.implantium",
            text="Пакет All-on-4",
        ),
        "all_on_6.jaw.implantium": _complete_with_conditions(
            "all_on_6.jaw.implantium",
            text="Пакет All-on-6",
        ),
    }
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material, condition_evidence_by_offer=evidence),
        as_of=AS_OF,
    )
    assert outcome.resolved.price_block is not None
    assert outcome.resolved.price_block.owner == "canonical_multi"
    entries = outcome.resolved.required_offer_conditions[0].entries
    texts = {entry.offer_id: entry.display_text for entry in entries}
    assert texts["all_on_4.jaw.implantium"] == "Пакет All-on-4"
    assert texts["all_on_6.jaw.implantium"] == "Пакет All-on-6"
    assert "Пакет All-on-4" in outcome.rendered_text
    assert "Пакет All-on-6" in outcome.rendered_text


def test_clarify_with_service_reference_preserves_scope(demo_material) -> None:
    adapted = _adapted(
        route="CLARIFY",
        mode="standard",
        patient_text="Уточните детали.",
        service_reference_kind="explicit_current",
        explicit_service_id="all_on_4",
        topic_id="implantation",
        requested_aspect_ids=(),
    )
    selection = _selection_from_post_composer(adapted, demo_material)
    assert selection.response_scope == "service"
    assert selection.reference_service_id == "all_on_4"
    outcome = resolve_materialized_response(
        selection,
        adapted,
        _sources(demo_material),
        as_of=AS_OF,
    )
    assert outcome.resolved.route == "CLARIFY"
    assert outcome.resolved.response_scope == "service"
    assert outcome.resolved.price_block is None
    assert outcome.resolved.service_options_block is None
    assert outcome.resolved.session_delta.active_service_id == "all_on_4"
