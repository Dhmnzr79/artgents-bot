"""Read-only diagnostic recompute for frozen A9R2 live artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.turn_frame import TurnFrame
from core.target_effective_scope import SessionPatientFacts
from core.target_effective_scope_merge import (
    EffectiveScopeMergeInputs,
    merge_effective_scope_axes,
    simulate_session_patient_facts_after_turn,
)
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from evals.v5.a9r2_patient_scope_live_contract import (
    LIVE_DIAGNOSTIC_RECOMPUTE_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MATRIX_V2_BLOB,
    OFFICIAL_A9R2_LIVE_VERDICT,
    OFFICIAL_A9R2_STATUS,
    assert_frozen_a9r2_live_artifacts_unchanged,
    iter_live_planner_calls,
    load_frozen_matrix_v2,
)
from evals.v5.a9r2_patient_scope_live_scoring import (
    aggregate_call_results,
    evaluate_proposed_gates,
    score_planner_call,
)
from evals.v5.fullcontext_response_eval_contract import prepare_json_artifact_payload


def _frame_from_raw_turn_plan(raw_turn_plan: dict[str, Any] | None) -> TurnFrame | None:
    if not isinstance(raw_turn_plan, dict):
        return None
    return TurnFrame.model_validate(raw_turn_plan)


def _call_spec_by_id(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {call["call_id"]: call for call in iter_live_planner_calls(matrix)}


def recompute_frozen_a9r2_live_diagnostic() -> dict[str, Any]:
    """Re-score frozen raw with corrected scorer; does not mutate official live artifacts."""

    assert_frozen_a9r2_live_artifacts_unchanged()
    official = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    matrix = load_frozen_matrix_v2()
    specs = _call_spec_by_id(matrix)
    raw_by_id = {entry["call_id"]: entry for entry in raw.get("calls", [])}

    prior_session: SessionPatientFacts | None = None
    prev_case_id: str | None = None
    scored_calls: list[dict[str, Any]] = []

    for index, call_spec in enumerate(iter_live_planner_calls(matrix), start=1):
        call_id = call_spec["call_id"]
        raw_entry = raw_by_id.get(call_id)
        if raw_entry is None:
            raise ValueError(f"missing frozen raw entry for {call_id}")
        if call_spec["case_id"] != prev_case_id:
            prior_session = None
            prev_case_id = call_spec["case_id"]

        frame = _frame_from_raw_turn_plan(raw_entry.get("raw_turn_plan"))
        score = score_planner_call(
            frame=frame,
            planner_status=str(raw_entry.get("planner_status") or ""),
            call_spec=call_spec,
            prior_session=prior_session,
            session_turn_count=index,
        )
        row = {
            **call_spec,
            "planner_status": raw_entry.get("planner_status"),
            "score": score,
        }
        scored_calls.append(row)

        if (
            not score.get("transport_provider_error")
            and frame is not None
            and call_spec.get("session_write") in ("write_if_confident", "optional_if_confident")
        ):
            projected = project_patient_scope_from_turn_frame(frame)
            merged = merge_effective_scope_axes(
                EffectiveScopeMergeInputs(
                    current_topic=call_spec["topic"],
                    session_turn_count=index,
                    session_facts=prior_session,
                    projected_turn_scope=projected,
                )
            )
            sim = simulate_session_patient_facts_after_turn(
                merged=merged,
                prior=prior_session,
                current_topic=call_spec["topic"],
                session_turn_count=index,
            )
            if sim.wrote:
                prior_session = sim.facts

    summary = aggregate_call_results(scored_calls)
    summary["retry_count"] = 0
    proposed_gates = evaluate_proposed_gates(summary)

    neg_fps = []
    for row in scored_calls:
        if row.get("category") not in ("no_scope_from_service", "no_stage_inference", "ambiguous"):
            continue
        for axis, outcome in (row.get("score", {}).get("axis_outcomes") or {}).items():
            if outcome == "false_positive_axis":
                neg_fps.append(
                    {
                        "call_id": row["call_id"],
                        "axis": axis,
                        "observed": row["score"]["observed_axes"].get(axis),
                    }
                )

    return prepare_json_artifact_payload(
        {
            "measurement_id": "a9r2_patient_scope_live_diagnostic_recompute",
            "matrix_blob": MATRIX_V2_BLOB,
            "official_live_verdict": OFFICIAL_A9R2_LIVE_VERDICT,
            "official_live_verdict_unchanged": official.get("automated_verdict")
            == OFFICIAL_A9R2_LIVE_VERDICT,
            "official_status": OFFICIAL_A9R2_STATUS,
            "diagnostic_automated_verdict": (
                "AUTOMATED_PASS" if proposed_gates["all_passed"] else "AUTOMATED_FAIL"
            ),
            "no_retroactive_pass": True,
            "corrected_summary": summary,
            "corrected_proposed_gates": proposed_gates,
            "corrected_transport_provider_error_count": summary["transport_provider_error_count"],
            "corrected_correction_success_rate": summary["correction_success_rate"],
            "corrected_composite_exact_turn_rate": summary["composite_exact_turn_rate"],
            "remaining_false_positive_axes": [
                {
                    "call_id": row["call_id"],
                    "category": row["category"],
                    "axis": axis,
                    "outcome": outcome,
                }
                for row in scored_calls
                for axis, outcome in (row.get("score", {}).get("axis_outcomes") or {}).items()
                if outcome == "false_positive_axis"
            ],
            "remaining_negative_ambiguous_false_positives": neg_fps,
            "call_results": scored_calls,
        }
    )


def write_diagnostic_recompute_artifact(path: Path = LIVE_DIAGNOSTIC_RECOMPUTE_PATH) -> dict[str, Any]:
    payload = recompute_frozen_a9r2_live_diagnostic()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
