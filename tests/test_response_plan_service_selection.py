from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.effective_scope import EffectiveScope
from contracts.response_plan import SessionKey
from contracts.response_plan_dialogue_context import (
    ShownOptionsFreshnessPolicy,
    ShownServiceOptionsSnapshot,
)
from core.response_plan_dialogue_context import ValidatedShownOptionsSnapshot
from core.response_plan_service_selection import (
    adapter_reference_rejection,
    resolve_reference_service_status,
    resolve_service_selection,
)
from core.response_schema_loader import load_response_schema_bundle

TARGET_ROOT = Path("clients/demo/target_response")
SESSION = SessionKey(client_id="demo", sid="s1")


@pytest.fixture
def demo_bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def _scope(**overrides: object) -> EffectiveScope:
    payload = {"extent": "unknown", "jaw": "unknown", "topic": "implantation"}
    payload.update(overrides)
    return EffectiveScope(**payload)  # type: ignore[arg-type]


def _shown_snapshot(service_ids: tuple[str, ...]) -> ValidatedShownOptionsSnapshot:
    return ValidatedShownOptionsSnapshot(
        snapshot=ShownServiceOptionsSnapshot(
            session_key=SESSION,
            topic_id="implantation",
            service_ids=service_ids,
            shown_at_turn=1,
        ),
        age_turns=1,
        eligible_service_ids=service_ids,
    )


def test_exact_price_all_on_6_only_candidate(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id="all_on_6",
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.price_candidate_service_ids == ("all_on_6",)
    assert result.ranked_service_ids == ()
    assert result.selection_basis == "referenced_service"


def test_rejected_explicit_service_blocks_generic_price(demo_bundle) -> None:
    from contracts.response_plan_composer import ComposerDecisionDiagnostic

    rejected = adapter_reference_rejection(
        (ComposerDecisionDiagnostic(code="service_id_not_allowed", detail="all_on_6"),)
    )
    assert rejected == (True, "all_on_6")
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=True,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.price_candidate_service_ids == ()
    assert result.ranked_service_ids == ()


def test_generic_full_arch_price_candidates(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.price_candidate_service_ids[:2] == ("all_on_4", "all_on_6")
    assert result.selection_basis == "current_situation"


def test_shown_options_price_uses_snapshot_only(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=False,
        option_reference_kind="shown_options",
        validated_shown=_shown_snapshot(("all_on_4", "all_on_6")),
        requested_aspect_ids=("price", "comparison"),
    )
    assert result.price_candidate_service_ids == ("all_on_4", "all_on_6")
    assert result.comparison_service_ids == ("all_on_4", "all_on_6")
    assert result.selection_basis == "shown_options"
    assert "zygomatic_implants" not in result.price_candidate_service_ids


def test_shown_options_comparison_without_price(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=False,
        option_reference_kind="shown_options",
        validated_shown=_shown_snapshot(("all_on_4", "all_on_6")),
        requested_aspect_ids=("comparison",),
    )
    assert result.comparison_service_ids == ("all_on_4", "all_on_6")
    assert result.price_candidate_service_ids == ()


def test_unknown_stage_not_conflict(demo_bundle) -> None:
    status, _ = resolve_reference_service_status(
        demo_bundle,
        reference_service_id="one_stage",
        resolved_topic_id="implantation",
        patient=__import__(
            "core.target_strategy_context",
            fromlist=["selection_patient_context_from_inputs"],
        ).selection_patient_context_from_inputs(_scope(extent="one_tooth")),
    )
    assert status == "unknown"


def test_known_contradictory_stage_conflict(demo_bundle) -> None:
    status, diag = resolve_reference_service_status(
        demo_bundle,
        reference_service_id="one_stage",
        resolved_topic_id="implantation",
        patient=__import__(
            "core.target_strategy_context",
            fromlist=["selection_patient_context_from_inputs"],
        ).selection_patient_context_from_inputs(
            _scope(extent="one_tooth", stage="natural_tooth_present")
        ),
    )
    assert status == "conflict"
    assert diag


def test_catalog_reference_price_allowed_with_conflict_status(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="one_tooth", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id="all_on_4",
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.price_candidate_service_ids == ("all_on_4",)
    assert result.selection_basis == "referenced_service"
    assert result.reference_service_status in {"conflict", "unknown", "compatible"}


def test_situation_based_selection_does_not_use_catalog_reference_shortcut(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="one_tooth", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.selection_basis == "current_situation"
    assert result.price_candidate_service_ids
    assert "all_on_4" not in result.price_candidate_service_ids or result.price_candidate_service_ids[0] != "all_on_4"


def test_catalog_reference_conflict_keeps_only_reference_service(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="one_tooth", jaw="upper", stage="natural_tooth_present"),
        resolved_topic_id="implantation",
        reference_service_id="one_stage",
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("price",),
    )
    assert result.reference_service_status == "conflict"
    assert result.price_candidate_service_ids == ("one_stage",)


def test_overview_plans_visible_options(demo_bundle) -> None:
    result = resolve_service_selection(
        demo_bundle,
        source_client_id="demo",
        effective_scope=_scope(extent="full_arch", jaw="upper"),
        resolved_topic_id="implantation",
        reference_service_id=None,
        reference_rejected=False,
        option_reference_kind="none",
        validated_shown=None,
        requested_aspect_ids=("overview",),
    )
    assert result.visible_service_option_ids[:2] == ("all_on_4", "all_on_6")
    assert len(result.visible_service_option_ids) <= 3
