"""Speed Gate verdict logic (absolute NEW latency contract, Stage 3C)."""

from __future__ import annotations

from typing import Any, Literal

from evals.v5.one_call_stage3c_speed_gate_contract import (
    NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
    SPEED_GATE_NEW_CASE_TOTAL_MAX_MS,
    SPEED_GATE_NEW_WARM_TOTAL_P50_MAX_MS,
    SPEED_GATE_NEW_WARM_TTFT_P95_MAX_MS,
    SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS,
    SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT,
    SpeedGateVerdict,
)


def _p50(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _p95(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, int(round(0.95 * (len(ordered) - 1))))
    return float(ordered[index])


def _valid_total_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def warm_latency_ttft_ready(latency_runs: list[dict[str, Any]]) -> bool:
    warm_rows = [
        row
        for row in latency_runs
        if row.get("kind") == "latency" or row.get("latency_category") is not None
    ]
    warm_rows = [row for row in warm_rows if row.get("latency_category") == "warm"]
    if not warm_rows:
        return False
    return all(
        bool(row.get("ttft_measurement_valid"))
        and row.get("patient_ttft_ms") is not None
        for row in warm_rows
    )


def compute_speed_gate_quality_pass(
    latency_runs: list[dict[str, Any]],
    admin_runs: list[dict[str, Any]],
) -> bool:
    for row in admin_runs:
        if not (row.get("quality") or {}).get("pass"):
            return False
    for row in latency_runs:
        if row.get("arm") == "NEW" and not (row.get("quality") or {}).get("pass"):
            return False
    return True


def _new_latency_rows(latency_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in latency_runs
        if row.get("arm") == "NEW" and row.get("kind") == "latency"
    ]


def _new_warm_latency_rows(latency_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in _new_latency_rows(latency_runs)
        if row.get("latency_category") == "warm"
    ]


def evaluate_speed_gate(
    *,
    warm_new_ttft_ms: list[int],
    warm_old_ttft_ms: list[int],
    warm_new_total_ms: list[int],
    warm_old_total_ms: list[int],
    new_provider_calls_ok: bool,
    quality_pass: bool,
    ttft_measurement_ready: bool = True,
    new_latency_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    new_p50 = _p50(warm_new_ttft_ms)
    old_p50 = _p50(warm_old_ttft_ms)
    new_p95 = _p95(warm_new_ttft_ms)
    old_p95 = _p95(warm_old_ttft_ms)
    new_total_p50 = _p50(warm_new_total_ms)
    old_total_p50 = _p50(warm_old_total_ms)

    ttft_relative_ok = False
    ttft_absolute_ok = False
    if new_p50 is not None and old_p50 is not None and old_p50 > 0:
        improvement = (old_p50 - new_p50) / old_p50
        ttft_relative_ok = improvement >= SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT
        ttft_absolute_ok = (old_p50 - new_p50) >= SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS

    latency_rows = list(new_latency_runs or [])
    totals_valid = True
    case_totals: list[int] = []
    for row in latency_rows:
        total = _valid_total_ms(row.get("total_ms"))
        if total is None:
            totals_valid = False
            continue
        case_totals.append(total)

    case_total_pass = totals_valid and all(
        total <= SPEED_GATE_NEW_CASE_TOTAL_MAX_MS for total in case_totals
    )
    new_total_p50_pass = (
        new_total_p50 is not None
        and new_total_p50 <= SPEED_GATE_NEW_WARM_TOTAL_P50_MAX_MS
    )
    new_ttft_p95_pass = (
        new_p95 is not None and new_p95 <= SPEED_GATE_NEW_WARM_TTFT_P95_MAX_MS
    )
    provider_budget_pass = new_provider_calls_ok
    quality_guard_pass = quality_pass
    ttft_measurement_pass = ttft_measurement_ready
    new_latency_present = bool(latency_rows)

    speed_pass = (
        new_latency_present
        and totals_valid
        and ttft_measurement_pass
        and new_total_p50_pass
        and case_total_pass
        and new_ttft_p95_pass
        and provider_budget_pass
        and quality_guard_pass
    )

    verdict: SpeedGateVerdict
    if (
        not new_latency_present
        or not totals_valid
        or not ttft_measurement_ready
        or not warm_new_ttft_ms
    ):
        verdict = "inconclusive"
    elif speed_pass:
        verdict = "pass"
    else:
        verdict = "fail"

    return {
        "speed_pass": speed_pass,
        "verdict": verdict,
        "thresholds": {
            "new_warm_total_p50_max_ms": SPEED_GATE_NEW_WARM_TOTAL_P50_MAX_MS,
            "new_case_total_max_ms": SPEED_GATE_NEW_CASE_TOTAL_MAX_MS,
            "new_warm_ttft_p95_max_ms": SPEED_GATE_NEW_WARM_TTFT_P95_MAX_MS,
            "new_max_provider_calls_per_free_text": NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
            "diagnostic_ttft_p50_min_relative_improvement": (
                SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT
            ),
            "diagnostic_ttft_p50_min_absolute_ms": SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS,
        },
        "warm_ttft_p50": {"new": new_p50, "old": old_p50},
        "warm_ttft_p95": {"new": new_p95, "old": old_p95},
        "warm_total_p50": {"new": new_total_p50, "old": old_total_p50},
        "diagnostic_ttft_p50_relative_ok": ttft_relative_ok,
        "diagnostic_ttft_p50_absolute_ok": ttft_absolute_ok,
        "checks": {
            "ttft_measurement_pass": ttft_measurement_pass,
            "new_latency_present": new_latency_present,
            "new_totals_valid": totals_valid,
            "new_total_p50_pass": new_total_p50_pass,
            "new_case_total_pass": case_total_pass,
            "new_ttft_p95_pass": new_ttft_p95_pass,
            "provider_budget_pass": provider_budget_pass,
            "quality_guard_pass": quality_guard_pass,
        },
    }
