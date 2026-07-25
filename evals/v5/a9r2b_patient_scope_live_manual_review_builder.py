"""Build full manual review artifact from A9R2b live result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.a9r2_patient_scope_live_scoring import AC2_MATERIAL_AXES
from evals.v5.a9r2b_patient_scope_live_contract import (
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MEASUREMENT_ID,
    NEGATIVE_AMBIGUOUS_CATEGORIES,
)
from evals.v5.fullcontext_response_eval_contract import prepare_json_artifact_payload


def build_manual_review_from_result(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") or {}
    call_results = result.get("call_results") or []
    automated_verdict = str(result.get("automated_verdict") or "")

    misses: list[dict[str, Any]] = []
    wrong_concrete: list[dict[str, Any]] = []
    material_false_positives: list[dict[str, Any]] = []
    diagnostic_reported_context: list[dict[str, Any]] = []
    transport_errors: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []

    for index, row in enumerate(call_results, start=1):
        score = row.get("score") or {}
        axis_outcomes = score.get("axis_outcomes") or {}
        observed = score.get("observed_axes") or {}
        expected = row.get("expected_scope") or {}

        if score.get("transport_provider_error"):
            transport_errors.append(
                {
                    "call_id": row.get("call_id"),
                    "planner_status": row.get("planner_status"),
                }
            )

        for axis, outcome in axis_outcomes.items():
            if outcome == "missing_expected_positive_axis":
                misses.append(
                    {
                        "call_id": row.get("call_id"),
                        "axis": axis,
                        "expected": expected.get(axis if axis != "reported_context" else "modifiers"),
                    }
                )
            elif outcome == "wrong_non_unknown_axis":
                wrong_concrete.append(
                    {
                        "call_id": row.get("call_id"),
                        "axis": axis,
                        "expected": expected.get(axis if axis != "reported_context" else "modifiers"),
                        "observed": observed.get(axis),
                    }
                )
            elif outcome == "false_positive_axis":
                entry = {
                    "call_id": row.get("call_id"),
                    "axis": axis,
                    "observed": observed.get(axis),
                    "category": row.get("category"),
                    "outcome": outcome,
                }
                if axis in AC2_MATERIAL_AXES:
                    material_false_positives.append(entry)
                elif axis == "reported_context":
                    diagnostic_reported_context.append(entry)

        turns.append(
            {
                "turn": index,
                "call_id": row.get("call_id"),
                "question": row.get("question"),
                "expected_scope": expected,
                "observed_scope": observed,
                "axis_classification": axis_outcomes,
                "session_effect": {
                    "simulated_session_wrote": score.get("simulated_session_wrote"),
                    "session_overwrite_safe": score.get("session_overwrite_safe"),
                    "correction_success": score.get("correction_success"),
                    "merged_extent": score.get("merged_extent"),
                    "merged_jaw": score.get("merged_jaw"),
                    "merged_stage": score.get("merged_stage"),
                },
                "planner_status": row.get("planner_status"),
                "composite_turn_exact": score.get("composite_turn_exact"),
                "transport_error": score.get("transport_provider_error"),
                "material_false_positive_axis_count": score.get("material_false_positive_axis_count"),
                "diagnostic_false_positive_axis_count": score.get(
                    "diagnostic_false_positive_axis_count"
                ),
            }
        )

    neg_amb_material = [
        fp
        for fp in material_false_positives
        if fp.get("category") in NEGATIVE_AMBIGUOUS_CATEGORIES
    ]

    gates_passed = automated_verdict == "AUTOMATED_PASS"
    manual_complete = True
    final_verdict = (
        "PASS"
        if gates_passed and manual_complete and not transport_errors
        else "FAIL" if not gates_passed else "PENDING_MANUAL_REVIEW"
    )

    return prepare_json_artifact_payload(
        {
            "measurement_id": MEASUREMENT_ID,
            "automated_verdict": automated_verdict,
            "final_verdict": final_verdict,
            "manual_review_completed": manual_complete,
            "manual_review_required": True,
            "authority_enabled": False,
            "planner_calls_actual": summary.get("planner_calls"),
            "owner_note": (
                "Single owner-approved A9R2b live attempt. "
                "reported_context is diagnostic-only per owner ruling. "
                "No rerun without new owner approval."
            ),
            "reported_context_ruling": "diagnostic_only_not_authority_candidate",
            "misses": misses,
            "wrong_concrete_values": wrong_concrete,
            "material_false_positives": material_false_positives,
            "negative_ambiguous_material_false_positives": neg_amb_material,
            "diagnostic_reported_context_false_positives": diagnostic_reported_context,
            "transport_errors": transport_errors,
            "turns": turns,
            "summary": summary,
            "proposed_gates": result.get("proposed_gates"),
        }
    )


def write_manual_review_artifact(
    *,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    output_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    payload = build_manual_review_from_result(result)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
