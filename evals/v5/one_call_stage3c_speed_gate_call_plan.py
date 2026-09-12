"""Frozen provider call plan for Stage 3C Speed Gate."""

from __future__ import annotations

from dataclasses import dataclass

from evals.v5.one_call_stage3c_speed_gate_contract import (
    FROZEN_ADMIN_CASE_IDS,
    FROZEN_LATENCY_CASE_IDS,
    NEW_MAX_PROVIDER_CALLS_ADMIN,
    NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
    OLD_MAX_PROVIDER_CALLS_PER_TURN,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import FROZEN_SPEED_GATE_CASES


@dataclass(frozen=True, slots=True)
class FrozenCallPlan:
    old_max_per_turn: int
    new_max_per_free_text: int
    new_max_admin: int
    latency_case_count: int
    admin_case_count: int
    max_provider_calls_live: int
    derivation_notes: tuple[str, ...]


def build_frozen_call_plan() -> FrozenCallPlan:
    latency_count = len(FROZEN_LATENCY_CASE_IDS)
    admin_count = len(FROZEN_ADMIN_CASE_IDS)
    # Latency matrix: each case runs OLD + NEW arms (12 turns).
    # Admin matrix: NEW only (3 turns).
    max_live = (
        latency_count * OLD_MAX_PROVIDER_CALLS_PER_TURN
        + latency_count * NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT
        + admin_count * NEW_MAX_PROVIDER_CALLS_ADMIN
    )
    notes = (
        "OLD arm uses ingress+planner+target_fullcontext (boundary+composer+verifier).",
        "Ingress may be 0 (deterministic) or 1 (LLM); planner=1; boundary=0-1; composer=1; verifier=0-1.",
        f"Proved offline upper bound per OLD turn = {OLD_MAX_PROVIDER_CALLS_PER_TURN}.",
        f"NEW free-text arm = {NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT} sales_fast call.",
        f"NEW admin arm = {NEW_MAX_PROVIDER_CALLS_ADMIN} provider calls (local gate).",
        f"LIVE budget = {latency_count}*(OLD+NEW) + {admin_count}*NEW_admin = {max_live}.",
    )
    return FrozenCallPlan(
        old_max_per_turn=OLD_MAX_PROVIDER_CALLS_PER_TURN,
        new_max_per_free_text=NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT,
        new_max_admin=NEW_MAX_PROVIDER_CALLS_ADMIN,
        latency_case_count=latency_count,
        admin_case_count=admin_count,
        max_provider_calls_live=max_live,
        derivation_notes=notes,
    )


def assert_old_call_ceiling_observed(role_counts: dict[str, int]) -> bool:
    total = sum(int(role_counts.get(key, 0)) for key in role_counts)
    return total <= OLD_MAX_PROVIDER_CALLS_PER_TURN


def observed_old_roles_from_transport(calls: list[object]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for call in calls:
        source = str(getattr(call, "source", "unknown"))
        totals[source] = totals.get(source, 0) + 1
    return totals


def prove_old_max_for_matrix_cases(
    observed_per_case: dict[str, int],
) -> tuple[int, bool]:
    if not observed_per_case:
        return 0, False
    peak = max(observed_per_case.values())
    latency_ids = {case.case_id for case in FROZEN_SPEED_GATE_CASES if case.kind == "latency"}
    proved = peak <= OLD_MAX_PROVIDER_CALLS_PER_TURN and latency_ids == set(observed_per_case.keys())
    return peak, proved
