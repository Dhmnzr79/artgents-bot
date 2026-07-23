"""Read-only recomputation of frozen S62 live verdict with corrected gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.s62_target_runtime_live_contract import (
    LIVE_RESULT_ARTIFACT_PATH,
    MAX_HTTP_TURNS,
)
from evals.v5.s62_target_runtime_live_harness import _evaluate_summary
from evals.v5.s62_target_runtime_live_provider_audit import ProviderAuditState


def load_frozen_live_result(path: Path = LIVE_RESULT_ARTIFACT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("frozen live result must be object")
    return payload


def build_audit_state_from_frozen_result(payload: dict[str, Any]) -> ProviderAuditState:
    summary = payload.get("summary") or {}
    provider = summary.get("provider") or {}
    role_totals = dict(provider.get("role_totals") or {})
    state = ProviderAuditState()
    state.total_started = int(provider.get("total_calls") or 0)
    for role, count in role_totals.items():
        if role in state.role_totals:
            state.role_totals[role] = int(count)
    return state


def recompute_frozen_live_verdict(
    path: Path = LIVE_RESULT_ARTIFACT_PATH,
) -> dict[str, Any]:
    """Apply corrected harness gates to frozen live capture without rewriting it."""

    payload = load_frozen_live_result(path)
    turn_results = list(payload.get("turn_results") or [])
    audit = build_audit_state_from_frozen_result(payload)
    corrected = _evaluate_summary(turn_results, audit)
    frozen_verdict = str((payload.get("summary") or {}).get("automated_verdict") or "")
    return {
        "frozen_automated_verdict": frozen_verdict,
        "corrected_automated_verdict": corrected["automated_verdict"],
        "corrected_summary": corrected,
        "turn_count": len(turn_results),
        "expected_turn_count": MAX_HTTP_TURNS,
        "frozen_bytes_unchanged": True,
    }
