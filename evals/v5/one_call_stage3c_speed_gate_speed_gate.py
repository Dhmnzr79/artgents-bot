"""Speed Gate verdict logic (frozen thresholds, Stage 3C)."""

from __future__ import annotations

from statistics import median
from typing import Any, Literal

from evals.v5.one_call_stage3c_speed_gate_contract import (
    NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
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


def evaluate_speed_gate(
    *,
    warm_new_ttft_ms: list[int],
    warm_old_ttft_ms: list[int],
    warm_new_total_ms: list[int],
    warm_old_total_ms: list[int],
    new_provider_calls_ok: bool,
    quality_pass: bool,
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

    ttft_p50_pass = ttft_relative_ok or ttft_absolute_ok
    ttft_p95_pass = (
        new_p95 is not None
        and old_p95 is not None
        and new_p95 <= old_p95
    )
    total_p50_pass = (
        new_total_p50 is not None
        and old_total_p50 is not None
        and new_total_p50 <= old_total_p50
    )
    provider_budget_pass = new_provider_calls_ok
    quality_guard_pass = quality_pass

    speed_pass = (
        ttft_p50_pass
        and ttft_p95_pass
        and total_p50_pass
        and provider_budget_pass
        and quality_guard_pass
    )

    verdict: SpeedGateVerdict
    if not warm_new_ttft_ms or not warm_old_ttft_ms:
        verdict = "inconclusive"
    elif speed_pass:
        verdict = "pass"
    else:
        verdict = "fail"

    return {
        "speed_pass": speed_pass,
        "verdict": verdict,
        "thresholds": {
            "ttft_p50_min_relative_improvement": SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT,
            "ttft_p50_min_absolute_ms": SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS,
            "new_max_provider_calls_per_free_text": NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
        },
        "warm_ttft_p50": {"new": new_p50, "old": old_p50},
        "warm_ttft_p95": {"new": new_p95, "old": old_p95},
        "warm_total_p50": {"new": new_total_p50, "old": old_total_p50},
        "checks": {
            "ttft_p50_pass": ttft_p50_pass,
            "ttft_p95_pass": ttft_p95_pass,
            "total_p50_pass": total_p50_pass,
            "provider_budget_pass": provider_budget_pass,
            "quality_guard_pass": quality_guard_pass,
        },
    }
