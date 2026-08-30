"""Production parity documentation and eval-only boundary helpers (CP-ARCH-COMPARE-REPORT-PARITY-V1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.v5.arch_compare.arch_compare_live_boundary import (
    ArchCompareBoundaryCapture,
    capture_provider_turn_boundary,
)
from evals.v5.arch_compare.arch_compare_matrix import ArchCompareScenarioSpec, ArchCompareTurnSpec
from evals.v5.arch_compare.arch_compare_live_schedule import scenario_for_id


@dataclass(frozen=True, slots=True)
class ProductionCallGraphStep:
    layer: str
    module: str
    symbol: str


WIDGET_PRODUCTION_CALL_GRAPH: tuple[ProductionCallGraphStep, ...] = (
    ProductionCallGraphStep("entry", "core.sales_fast_widget_runtime", "run_sales_fast_widget_turn"),
    ProductionCallGraphStep("orchestration", "core.sales_one_plus_turn", "run_sales_one_plus_candidate"),
    ProductionCallGraphStep("envelope", "core.one_call_envelope_protocol", "parse_production_envelope_json"),
    ProductionCallGraphStep("semantic", "core.sales_one_plus_semantic_authority", "bind_semantic_frame"),
    ProductionCallGraphStep("turn_frame", "core.sales_fast_turn_frame", "build_turn_frame_from_semantic_frame"),
    ProductionCallGraphStep("scope", "core.sales_fast_strict_evidence", "effective_scope_from_semantic_frame"),
    ProductionCallGraphStep("strategy", "core.target_strategy_context", "strategy_match_from_effective_scope"),
    ProductionCallGraphStep("bound_package", "core.sales_fast_strict_evidence", "resolve_sales_fast_bound_package"),
    ProductionCallGraphStep("precomposer", "core.resolve_precomposer_selected_offer", "resolve_precomposer_selected_offer"),
    ProductionCallGraphStep("price_resolution", "core.one_call_price_text", "resolve_price_text_for_turn"),
    ProductionCallGraphStep("presentation", "core.one_call_presentation_pass", "build_one_call_presentation_result"),
    ProductionCallGraphStep("visible_answer", "contracts.one_call_presentation_result", "OneCallPresentationResult.final_patient_text"),
)

ARCH_COMPARE_CAPTURE_CALL_GRAPH: tuple[ProductionCallGraphStep, ...] = (
    ProductionCallGraphStep("eval_transport", "evals.v5.arch_compare.arch_compare_live_transport", "ArchCompareLiveTransport.chat_completions_create"),
    ProductionCallGraphStep("envelope", "core.one_call_envelope_protocol", "parse_production_envelope_json"),
    ProductionCallGraphStep("boundary", "evals.v5.arch_compare.arch_compare_live_boundary", "capture_provider_turn_boundary"),
    ProductionCallGraphStep("semantic", "core.sales_one_plus_semantic_authority", "bind_semantic_frame"),
    ProductionCallGraphStep("turn_frame", "core.sales_fast_turn_frame", "build_turn_frame_from_semantic_frame"),
    ProductionCallGraphStep("scope", "core.sales_fast_strict_evidence", "effective_scope_from_semantic_frame"),
    ProductionCallGraphStep("strategy", "core.target_strategy_context", "strategy_match_from_effective_scope"),
    ProductionCallGraphStep("bound_package", "core.sales_fast_strict_evidence", "resolve_sales_fast_bound_package"),
    ProductionCallGraphStep("precomposer", "evals.v5.arch_compare.arch_compare_prompt_build", "resolve_precomposer_for_turn"),
    ProductionCallGraphStep("price_resolution", "core.one_call_price_text", "resolve_price_text_for_turn"),
    ProductionCallGraphStep("presentation", "core.one_call_presentation_pass", "build_one_call_presentation_result"),
    ProductionCallGraphStep("visible_answer", "evals.v5.arch_compare.arch_compare_live_boundary", "ArchCompareBoundaryCapture.visible_answer"),
)


def format_call_graph_markdown(
    *,
    title: str,
    steps: tuple[ProductionCallGraphStep, ...],
) -> str:
    lines = [f"### {title}", ""]
    for idx, step in enumerate(steps, start=1):
        lines.append(f"{idx}. `{step.module}` → `{step.symbol}` ({step.layer})")
    return "\n".join(lines)


def capture_arch_compare_price_turn(
    *,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    envelope_json: str,
    patient_text: str,
    session_id: str = "arch-compare-parity-offline",
) -> ArchCompareBoundaryCapture:
    """Run production boundary capture for arch-compare (provider mocked upstream)."""

    return capture_provider_turn_boundary(
        envelope_json=envelope_json,
        scenario=scenario,
        turn=turn,
        patient_text=patient_text,
        session_id=session_id,
    )


def scenario_turn_or_raise(*, scenario_id: str, turn_id: str) -> tuple[ArchCompareScenarioSpec, ArchCompareTurnSpec]:
    scenario = scenario_for_id(scenario_id)
    turn = next((row for row in scenario.turns if row.turn_id == turn_id), None)
    if turn is None:
        raise KeyError(f"turn_not_found:{scenario_id}:{turn_id}")
    return scenario, turn


def call_graph_comparison_markdown() -> str:
    widget = format_call_graph_markdown(title="Widget/API production path", steps=WIDGET_PRODUCTION_CALL_GRAPH)
    arch = format_call_graph_markdown(
        title="Arch-compare LIVE capture path (post-provider)",
        steps=ARCH_COMPARE_CAPTURE_CALL_GRAPH,
    )
    shared = (
        "Shared production functions after envelope parse: "
        "`bind_semantic_frame` → `build_turn_frame_from_semantic_frame` → "
        "`resolve_sales_fast_bound_package` / stage51b → `build_one_call_presentation_result`."
    )
    return "\n\n".join([widget, "", arch, "", shared])
