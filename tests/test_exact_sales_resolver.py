"""Focused offline contract tests for Exact Sales Resolver."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from contracts.patient_scope_projection import ProjectedPatientScope, ProjectedScopeAxis
from contracts.response_schema import TargetService
from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref
from contracts.ui_stage_action import UiStageAction, build_ui_stage_ref
from core.exact_sales_resolver import (
    ExactSalesResolverInputError,
    ExactSalesResolutionConflictError,
    ExactSalesResolverInputs,
    resolve_exact_sales_inputs,
)
from core.target_effective_scope import SessionPatientFacts
from core.target_service_resolver import TargetServiceResolutionError


def _service(name: str, aliases: list[str], *, active: bool = True) -> TargetService:
    return TargetService.model_validate(
        {
            "name": name,
            "aliases": aliases,
            "family": "implantology",
            "roles": ["protocol"],
            "active": active,
            "content_ref": "implantation__service__sample.md",
            "selection": {"mode": "scope", "extent": ["full_arch"]},
        }
    )


def _catalog() -> dict[str, TargetService]:
    return {
        "all_on_4": _service("All-on-4", ["all on four"]),
        "inactive": _service("Inactive", ["inactive exact"], active=False),
    }


def _projected(*, extent: str | None = None, jaw: str | None = None, stage: str | None = None) -> ProjectedPatientScope:
    def axis(value: str | None) -> ProjectedScopeAxis:
        return ProjectedScopeAxis(
            value=value,
            provenance="turn_plan.raw.patient_scope",
            usable=value is not None,
        )

    return ProjectedPatientScope(
        extent=axis(extent),
        jaw=axis(jaw),
        stage=axis(stage),
        reported_context=axis(None),
    )


def _session(*, extent: str = "full_arch", jaw: str | None = "lower", stage: str | None = "implant_placed") -> SessionPatientFacts:
    return SessionPatientFacts(
        extent=extent,  # type: ignore[arg-type]
        topic="implantation",
        provenance="test-session",
        ref="test:session",
        set_at_turn=1,
        jaw=jaw,  # type: ignore[arg-type]
        stage=stage,  # type: ignore[arg-type]
    )


def test_governed_ui_overrides_exact_turn_scope_and_records_conflict() -> None:
    ui = UiScopeAction(
        extent="few_teeth",
        topic="implantation",
        ref=build_ui_scope_ref(topic="implantation", extent="few_teeth"),
    )
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=2,
            current_ui_scope_action=ui,
            projected_turn_scope=_projected(extent="one_tooth"),
        )
    )

    assert result.extent == "few_teeth"
    assert result.extent_authority.authority == "governed_ui"
    assert result.extent_authority.provenance == ui.ref
    assert len(result.conflicts) == 1
    assert result.conflicts[0].field == "extent"
    assert result.conflicts[0].rejected_value == "one_tooth"


def test_exact_active_service_alias_and_aspect_are_preserved() -> None:
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=1,
            exact_service_term="  ALL ON FOUR ",
            exact_aspect="price",
        )
    )

    assert result.service_id == "all_on_4"
    assert result.service_id_authority.authority == "exact_turn"
    assert result.aspect == "price"
    assert result.aspect_authority.provenance == "exact_aspect"


@pytest.mark.parametrize("term", ["not a service", "inactive exact"])
def test_missing_or_inactive_exact_service_never_gets_a_match(term: str) -> None:
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=1,
            exact_service_term=term,
        )
    )

    assert result.service_id is None
    assert result.service_id_authority.authority == "unknown"


def test_valid_prior_session_is_only_scope_fallback() -> None:
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=2,
            session_facts=_session(),
        )
    )

    assert (result.extent, result.jaw, result.stage) == (
        "full_arch",
        "lower",
        "implant_placed",
    )
    assert result.extent_authority.authority == "valid_session"
    assert result.service_id is None


def test_exact_turn_scope_overrides_distinct_valid_session_and_records_conflict() -> None:
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=2,
            projected_turn_scope=_projected(extent="one_tooth"),
            session_facts=_session(extent="full_arch"),
        )
    )

    assert result.extent == "one_tooth"
    assert result.extent_authority.authority == "exact_turn"
    assert result.conflicts == (
        result.conflicts[0],
    )
    assert result.conflicts[0].rejected_authority == "valid_session"
    assert result.conflicts[0].rejected_value == "full_arch"


def test_governed_ui_topic_blocks_cross_topic_session_merge() -> None:
    stage_ui = UiStageAction(
        stage="implant_placed",
        topic="prosthetics",
        ref=build_ui_stage_ref(topic="prosthetics", stage="implant_placed"),
    )
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=2,
            current_ui_stage_action=stage_ui,
            session_facts=_session(),
        )
    )

    assert result.stage == "implant_placed"
    assert result.stage_authority.authority == "governed_ui"
    assert result.extent is None
    assert result.jaw is None


def test_current_exact_stage_beats_session_even_with_scope_click() -> None:
    scope_ui = UiScopeAction(
        extent="few_teeth",
        topic="implantation",
        ref=build_ui_scope_ref(topic="implantation", extent="few_teeth"),
    )
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="implantation",
            session_turn_count=2,
            current_ui_scope_action=scope_ui,
            projected_turn_scope=_projected(stage="natural_tooth_present"),
            session_facts=_session(stage="implant_placed"),
        )
    )

    assert result.stage == "natural_tooth_present"
    assert result.stage_authority.authority == "exact_turn"
    stage_conflict = next(item for item in result.conflicts if item.field == "stage")
    assert stage_conflict.rejected_authority == "valid_session"


@pytest.mark.parametrize("turn_count", [-1, True, "1"])
def test_invalid_session_turn_count_is_rejected(turn_count: object) -> None:
    with pytest.raises(ExactSalesResolverInputError) as exc_info:
        resolve_exact_sales_inputs(
            ExactSalesResolverInputs(
                services=_catalog(),
                current_topic="implantation",
                session_turn_count=turn_count,  # type: ignore[arg-type]
            )
        )

    assert exc_info.value.code == "exact_sales_resolution_session_turn_count_invalid"


@pytest.mark.parametrize("topic", ["", "  ", 7])
def test_invalid_current_topic_is_rejected(topic: object) -> None:
    with pytest.raises(ExactSalesResolverInputError) as exc_info:
        resolve_exact_sales_inputs(
            ExactSalesResolverInputs(
                services=_catalog(),
                current_topic=topic,  # type: ignore[arg-type]
                session_turn_count=1,
            )
        )

    assert exc_info.value.code == "exact_sales_resolution_current_topic_invalid"


def test_unknown_and_stale_session_remain_unknown() -> None:
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=_catalog(),
            current_topic="prosthetics",
            session_turn_count=99,
            session_facts=_session(),
        )
    )

    assert result.extent is None
    assert result.jaw is None
    assert result.stage is None
    assert result.conflicts == ()


def test_incompatible_governed_ui_topics_raise_explicit_conflict() -> None:
    with pytest.raises(ExactSalesResolutionConflictError) as exc_info:
        resolve_exact_sales_inputs(
            ExactSalesResolverInputs(
                services=_catalog(),
                current_topic="implantation",
                session_turn_count=1,
                current_ui_scope_action=UiScopeAction(
                    extent="one_tooth",
                    topic="implantation",
                    ref=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
                ),
                current_ui_stage_action=UiStageAction(
                    stage="implant_placed",
                    topic="prosthetics",
                    ref=build_ui_stage_ref(topic="prosthetics", stage="implant_placed"),
                ),
            )
        )

    assert exc_info.value.code == "exact_sales_resolution_ui_topic_conflict"


def test_ambiguous_service_alias_propagates_existing_typed_error() -> None:
    catalog = {
        "one": _service("One", ["shared"]),
        "two": _service("Two", ["shared"]),
    }
    with pytest.raises(TargetServiceResolutionError) as exc_info:
        resolve_exact_sales_inputs(
            ExactSalesResolverInputs(
                services=catalog,
                current_topic="implantation",
                session_turn_count=1,
                exact_service_term="shared",
            )
        )

    assert exc_info.value.code == "service_resolution_ambiguous"


def test_both_jaws_is_scope_only_and_result_is_immutable() -> None:
    catalog = _catalog()
    before = {key: service.model_dump() for key, service in catalog.items()}
    result = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=catalog,
            current_topic="implantation",
            session_turn_count=1,
            projected_turn_scope=_projected(jaw="both"),
        )
    )

    assert result.jaw == "both"
    assert result.service_id is None
    assert not hasattr(result, "price")
    assert not hasattr(result, "offer")
    with pytest.raises(FrozenInstanceError):
        result.jaw = "upper"  # type: ignore[misc]
    assert {key: service.model_dump() for key, service in catalog.items()} == before
