"""Frozen contract for ONE_CALL Stage 3C Speed Gate (offline + future LIVE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from config import SALES_ONE_PLUS_FLASH_MODEL

MEASUREMENT_ID = "one_call_stage3c_speed_gate"
MODEL_SNAPSHOT = SALES_ONE_PLUS_FLASH_MODEL
CLIENT_ID = "demo"

# LIVE gate — default closed; dry-run and offline tests keep None.
LIVE_AUTHORIZED_ATTEMPT_ID: str | None = None
PROPOSED_LIVE_ATTEMPT_ID = "one_call_stage3c_speed_gate_v1_2026-08-10-01"
PROPOSED_LIVE_ATTEMPT_ID_V2 = "one_call_stage3c_speed_gate_v2_2026-08-11-01"
ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"
MAX_RETRIES = 0

# Governance: accepted Stage 3C OFFLINE foundation (ancestry pin, not exact LIVE HEAD).
STAGE3C_OFFLINE_BASELINE_COMMIT = "4fe14658ebe8a454be6c4cb017c3670c7ea2f4c0"

# Relative path allowed to carry temporary LIVE gate authorization edits.
STAGE3C_GATE_CONTRACT_REL_PATH = "evals/v5/one_call_stage3c_speed_gate_contract.py"

ArmLabel = Literal["OLD", "NEW"]
SpeedGateVerdict = Literal["pass", "fail", "inconclusive"]
LatencyCategory = Literal["cold", "warm"]
CaseKind = Literal["latency", "admin"]

# Speed Gate thresholds — owner product contract (Stage 3C v2 post-LIVE).
SPEED_GATE_NEW_WARM_TOTAL_P50_MAX_MS = 8000
SPEED_GATE_NEW_CASE_TOTAL_MAX_MS = 10000
SPEED_GATE_NEW_WARM_TTFT_P95_MAX_MS = 6000

# Diagnostic-only relative comparison vs OLD (not blocking).
SPEED_GATE_TTFT_P50_MIN_RELATIVE_IMPROVEMENT = 0.30
SPEED_GATE_TTFT_P50_MIN_ABSOLUTE_MS = 2000
SPEED_GATE_ENDPOINT = (
    "https://ws-yk9n49fhzg4hebx9.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)

# Provider call ceilings per HTTP turn (proved offline in call_plan module).
OLD_MAX_PROVIDER_CALLS_PER_TURN = 5
NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT = 1
NEW_MAX_PROVIDER_CALLS_ADMIN = 0


@dataclass(frozen=True, slots=True)
class SpeedGateQualitySpec:
    expected_route: str
    critical_required_all: tuple[str, ...] = ()
    noncritical_review_any: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    forbidden_price_tokens: tuple[str, ...] = ()
    max_provider_calls: int = 1
    execution_layer: str = "model"


@dataclass(frozen=True, slots=True)
class SpeedGateCaseSpec:
    case_id: str
    user_message: str
    kind: CaseKind
    quality: SpeedGateQualitySpec
    stage2_ref: str | None = None
    source_refs: tuple[str, ...] = ()


FROZEN_LATENCY_CASE_IDS: tuple[str, ...] = (
    "s01_microfact",
    "s02_service",
    "s03_exact_price",
    "s04_both_jaws",
    "s05_doctor_trust",
    "s06_pain_fear",
)

FROZEN_ADMIN_CASE_IDS: tuple[str, ...] = (
    "a01",
    "a02",
    "a03",
)

FROZEN_ALL_CASE_IDS: tuple[str, ...] = FROZEN_LATENCY_CASE_IDS + FROZEN_ADMIN_CASE_IDS

# Global provider-call ceiling for one LIVE measurement (frozen call plan).
MAX_PROVIDER_CALLS_LIVE = (
    len(FROZEN_LATENCY_CASE_IDS) * OLD_MAX_PROVIDER_CALLS_PER_TURN
    + len(FROZEN_LATENCY_CASE_IDS) * NEW_MAX_PROVIDER_CALLS_PER_FREE_TEXT
    + len(FROZEN_ADMIN_CASE_IDS) * NEW_MAX_PROVIDER_CALLS_ADMIN
)


def build_attempt_marker_payload(
    *,
    attempt_id: str,
    frozen_matrix_sha256: str,
    stage3c_offline_baseline_commit: str,
    expected_live_head: str,
    observed_live_head: str,
) -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "model_snapshot": MODEL_SNAPSHOT,
        "live_authorized_attempt_id": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "frozen_matrix_sha256": frozen_matrix_sha256,
        "stage3c_offline_baseline_commit": stage3c_offline_baseline_commit,
        "expected_live_head": expected_live_head,
        "observed_live_head": observed_live_head,
        "latency_case_ids": list(FROZEN_LATENCY_CASE_IDS),
        "admin_case_ids": list(FROZEN_ADMIN_CASE_IDS),
        "max_retries_configured": MAX_RETRIES,
        "status": "attempt_started",
    }
