"""Scoring for A9R2 patient-scope planner live harness."""

from __future__ import annotations

from typing import Any

from contracts.turn_frame import TurnFrame
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
    simulate_session_patient_facts_after_turn,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from evals.v5.a9r2_patient_scope_live_contract import (
    NEGATIVE_AMBIGUOUS_CATEGORIES,
    POSITIVE_CATEGORIES,
    PROPOSED_GATES,
    SCORABLE_AXES,
    AxisOutcome,
)

_MALFORMED_STATUSES = frozenset({"invalid", "missing", "defaulted"})


def _expected_axis_values(expected_scope: dict[str, Any]) -> dict[str, str | None]:
    modifiers = list(expected_scope.get("modifiers") or [])
    reported_context: str | None = None
    if "reported_bone_deficit" in modifiers:
        reported_context = "reported_bone_deficit"
    stage = expected_scope.get("stage")
    return {
        "extent": str(expected_scope.get("extent") or "unknown"),
        "jaw": str(expected_scope.get("jaw") or "unknown"),
        "stage": None if stage in (None, "unknown") else str(stage),
        "reported_context": reported_context,
    }


def _observed_axis_values(frame: TurnFrame) -> dict[str, dict[str, Any]]:
    projected = project_patient_scope_from_turn_frame(frame)
    meta = frame.field_meta.patient_scope
    return {
        "extent": {
            "value": projected.extent.value or "unknown",
            "usable": projected.extent.usable,
            "status": meta.extent.status,
        },
        "jaw": {
            "value": projected.jaw.value or "unknown",
            "usable": projected.jaw.usable,
            "status": meta.jaw.status,
        },
        "stage": {
            "value": projected.stage.value,
            "usable": projected.stage.usable,
            "status": meta.stage.status,
        },
        "reported_context": {
            "value": projected.reported_context.value,
            "usable": projected.reported_context.usable,
            "status": meta.modifiers.status,
        },
    }


def score_axis(
    *,
    axis: str,
    expected: str | None,
    observed: dict[str, Any],
    category: str,
) -> AxisOutcome:
    status = str(observed.get("status") or "")
    usable = bool(observed.get("usable"))
    value = observed.get("value")
    if status in _MALFORMED_STATUSES:
        return "malformed_invalid_defaulted_projection"

    negative_case = category in NEGATIVE_AMBIGUOUS_CATEGORIES
    expected_unknown = expected in (None, "unknown")
    observed_unknown = value in (None, "unknown") or not usable

    if negative_case:
        if usable and not observed_unknown:
            return "false_positive_axis"
        return "not_applicable"

    if expected_unknown:
        if usable and not observed_unknown:
            return "false_positive_axis"
        return "not_applicable"

    if observed_unknown:
        return "missing_expected_positive_axis"

    if str(value) == str(expected):
        return "correct_expected_axis"

    return "wrong_non_unknown_axis"


def score_planner_call(
    *,
    frame: TurnFrame | None,
    planner_status: str,
    call_spec: dict[str, Any],
    prior_session: object | None = None,
    session_turn_count: int = 1,
) -> dict[str, Any]:
    if planner_status != "ok" or frame is None:
        return {
            "transport_provider_error": True,
            "axis_outcomes": {},
            "composite_turn_exact": False,
            "malformed_projection_count": 0,
            "wrong_non_unknown_axis_count": 0,
            "false_positive_axis_count": 0,
            "missing_expected_positive_axis_count": 0,
            "correct_expected_axis_count": 0,
        }

    expected_axes = _expected_axis_values(call_spec["expected_scope"])
    observed_axes = _observed_axis_values(frame)
    axis_outcomes: dict[str, AxisOutcome] = {}
    counts = {
        "correct_expected_axis": 0,
        "missing_expected_positive_axis": 0,
        "wrong_non_unknown_axis": 0,
        "false_positive_axis": 0,
        "malformed_invalid_defaulted_projection": 0,
        "not_applicable": 0,
    }
    for axis in SCORABLE_AXES:
        outcome = score_axis(
            axis=axis,
            expected=expected_axes[axis],
            observed=observed_axes[axis],
            category=str(call_spec["category"]),
        )
        axis_outcomes[axis] = outcome
        counts[outcome] += 1

    projected = project_patient_scope_from_turn_frame(frame)
    merged = merge_effective_scope_axes(
        EffectiveScopeMergeInputs(
            current_topic=call_spec["topic"],
            session_turn_count=session_turn_count,
            session_facts=prior_session,
            projected_turn_scope=projected,
        )
    )
    correction_success: bool | None = None
    session_overwrite_safe: bool | None = None
    if call_spec.get("is_correction_turn"):
        correction_success = merged.extent == call_spec["expected_scope"].get("extent")
        must_not = call_spec.get("must_not_keep_prior") or {}
        if "extent" in must_not:
            session_overwrite_safe = merged.extent != must_not["extent"]
    elif call_spec["category"] in NEGATIVE_AMBIGUOUS_CATEGORIES and prior_session is not None:
        session_overwrite_safe = merged.extent == getattr(prior_session, "extent", None)

    sim = simulate_session_patient_facts_after_turn(
        merged=merged,
        prior=prior_session,
        current_topic=call_spec["topic"],
        session_turn_count=session_turn_count,
    )
    if call_spec["category"] in NEGATIVE_AMBIGUOUS_CATEGORIES:
        session_overwrite_safe = sim.wrote is False

    scorable = [
        outcome
        for axis, outcome in axis_outcomes.items()
        if outcome != "not_applicable"
    ]
    composite_turn_exact = bool(scorable) and all(
        outcome == "correct_expected_axis" for outcome in scorable
    )

    return {
        "transport_provider_error": False,
        "axis_outcomes": axis_outcomes,
        "observed_axes": {
            axis: observed_axes[axis]["value"] for axis in SCORABLE_AXES
        },
        "projected_usable": {
            axis: observed_axes[axis]["usable"] for axis in SCORABLE_AXES
        },
        "merged_extent": merged.extent,
        "merged_jaw": merged.jaw,
        "merged_stage": merged.stage,
        "merged_reported_context": merged.reported_context,
        "correction_success": correction_success,
        "session_overwrite_safe": session_overwrite_safe,
        "composite_turn_exact": composite_turn_exact,
        "malformed_projection_count": counts["malformed_invalid_defaulted_projection"],
        "wrong_non_unknown_axis_count": counts["wrong_non_unknown_axis"],
        "false_positive_axis_count": counts["false_positive_axis"],
        "missing_expected_positive_axis_count": counts["missing_expected_positive_axis"],
        "correct_expected_axis_count": counts["correct_expected_axis"],
        "simulated_session_wrote": sim.wrote,
    }


def aggregate_call_results(call_results: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "planner_calls": len(call_results),
        "transport_provider_error_count": 0,
        "malformed_projection_count": 0,
        "wrong_non_unknown_axis_count": 0,
        "false_positive_axis_count": 0,
        "missing_expected_positive_axis_count": 0,
        "correct_expected_axis_count": 0,
        "composite_exact_turns": 0,
        "composite_scored_turns": 0,
        "positive_axis_expected": 0,
        "positive_axis_correct": 0,
        "correction_turns": 0,
        "correction_successes": 0,
    }
    for row in call_results:
        score = row.get("score") or {}
        if score.get("transport_provider_error"):
            totals["transport_provider_error_count"] += 1
            continue
        totals["malformed_projection_count"] += int(score.get("malformed_projection_count") or 0)
        totals["wrong_non_unknown_axis_count"] += int(
            score.get("wrong_non_unknown_axis_count") or 0
        )
        totals["false_positive_axis_count"] += int(score.get("false_positive_axis_count") or 0)
        totals["missing_expected_positive_axis_count"] += int(
            score.get("missing_expected_positive_axis_count") or 0
        )
        totals["correct_expected_axis_count"] += int(
            score.get("correct_expected_axis_count") or 0
        )
        if score.get("composite_turn_exact"):
            totals["composite_exact_turns"] += 1
        if any(
            outcome not in ("not_applicable",)
            for outcome in (score.get("axis_outcomes") or {}).values()
        ):
            totals["composite_scored_turns"] += 1

        category = str(row.get("category") or "")
        if category in POSITIVE_CATEGORIES:
            for outcome in (score.get("axis_outcomes") or {}).values():
                if outcome in (
                    "correct_expected_axis",
                    "missing_expected_positive_axis",
                    "wrong_non_unknown_axis",
                ):
                    totals["positive_axis_expected"] += 1
                    if outcome == "correct_expected_axis":
                        totals["positive_axis_correct"] += 1

        if row.get("is_correction_turn"):
            totals["correction_turns"] += 1
            if score.get("correction_success") is True:
                totals["correction_successes"] += 1

    totals["positive_axis_recall"] = (
        totals["positive_axis_correct"] / totals["positive_axis_expected"]
        if totals["positive_axis_expected"]
        else 1.0
    )
    totals["composite_exact_turn_rate"] = (
        totals["composite_exact_turns"] / totals["composite_scored_turns"]
        if totals["composite_scored_turns"]
        else 1.0
    )
    totals["correction_success_rate"] = (
        totals["correction_successes"] / totals["correction_turns"]
        if totals["correction_turns"]
        else 1.0
    )
    return totals


def evaluate_proposed_gates(summary: dict[str, Any]) -> dict[str, Any]:
    gates: dict[str, Any] = {}
    for name, rule in PROPOSED_GATES.items():
        actual = summary.get(name)
        if actual is None and name == "retry_count":
            actual = 0
        passed = True
        if "max" in rule and actual is not None:
            passed = float(actual) <= float(rule["max"])
        if "min" in rule and actual is not None:
            passed = float(actual) >= float(rule["min"])
        gates[name] = {
            "rule": rule,
            "actual": actual,
            "passed": passed,
        }
    gates["all_passed"] = all(item["passed"] for item in gates.values())
    return gates


def evaluate_automated_verdict(summary: dict[str, Any]) -> str:
    gates = evaluate_proposed_gates(summary)
    return "AUTOMATED_PASS" if gates["all_passed"] else "AUTOMATED_FAIL"


def map_automated_to_final_verdict(automated_verdict: str) -> str:
    if automated_verdict == "AUTOMATED_FAIL":
        return "FAIL"
    return "PENDING_MANUAL_REVIEW"
