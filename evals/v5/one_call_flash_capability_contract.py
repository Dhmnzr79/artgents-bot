"""Frozen contract for ONE_CALL Flash capability eval (Stage 3A offline)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from config import SALES_ONE_PLUS_FLASH_MODEL

MEASUREMENT_ID = "one_call_flash_capability"
MODEL_SNAPSHOT = SALES_ONE_PLUS_FLASH_MODEL

# Proposed LIVE gate — not activated in Stage 3A offline.
LIVE_AUTHORIZED_ATTEMPT_ID: str | None = None
PROPOSED_LIVE_ATTEMPT_ID = "one_call_flash_capability_v1_2026-08-09"
MAX_CALLS = 6
ATTEMPT_MARKER_EXISTS_CODE = "ATTEMPT_MARKER_EXISTS"

# Stage 3B offline preflight closes wall-timeout and Windows process isolation gaps.
STAGE_3B_LIVE_GAPS: tuple[str, ...] = ()

ResponseFormatStrategy = Literal["json_mode", "legacy_line_protocol"]
CapabilityOutcome = Literal[
    "supported",
    "unsupported",
    "malformed",
    "model_mismatch",
    "transport_error",
    "cache_miss",
    "live_blocked",
    "skipped",
]

JSON_MODE_PROBE_USER = (
    "Deprecated alias — use evals.v5.one_call_flash_capability_probes."
    "JSON_MODE_CAPABILITY_PROBE_USER"
)


@dataclass(frozen=True, slots=True)
class CapabilityCaseSpec:
    case_id: str
    requested_model: str
    stream: bool
    response_format_strategy: ResponseFormatStrategy
    expect_cached_tokens_gt_zero: bool = False
    description: str = ""


FROZEN_CAPABILITY_CASES: tuple[CapabilityCaseSpec, ...] = (
    CapabilityCaseSpec(
        case_id="json_mode_blocking",
        requested_model=MODEL_SNAPSHOT,
        stream=False,
        response_format_strategy="json_mode",
        description="Blocking call with response_format json_object (JSON mode, not JSON Schema)",
    ),
    CapabilityCaseSpec(
        case_id="json_mode_streaming",
        requested_model=MODEL_SNAPSHOT,
        stream=True,
        response_format_strategy="json_mode",
        description="Streaming call with response_format json_object",
    ),
    CapabilityCaseSpec(
        case_id="legacy_blocking",
        requested_model=MODEL_SNAPSHOT,
        stream=False,
        response_format_strategy="legacy_line_protocol",
        description="Blocking legacy @ANSWER/@ADMIN line protocol",
    ),
    CapabilityCaseSpec(
        case_id="legacy_streaming",
        requested_model=MODEL_SNAPSHOT,
        stream=True,
        response_format_strategy="legacy_line_protocol",
        description="Streaming legacy line protocol",
    ),
    CapabilityCaseSpec(
        case_id="cache_cold",
        requested_model=MODEL_SNAPSHOT,
        stream=False,
        response_format_strategy="legacy_line_protocol",
        description="First identical-prefix call — cached_tokens 0/None",
    ),
    CapabilityCaseSpec(
        case_id="cache_repeat",
        requested_model=MODEL_SNAPSHOT,
        stream=False,
        response_format_strategy="legacy_line_protocol",
        expect_cached_tokens_gt_zero=True,
        description="Repeat identical-prefix call — cached_tokens>0 required for supported",
    ),
)


def frozen_case_ids() -> tuple[str, ...]:
    return tuple(case.case_id for case in FROZEN_CAPABILITY_CASES)


def case_by_id(case_id: str) -> CapabilityCaseSpec:
    for case in FROZEN_CAPABILITY_CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def build_attempt_marker_payload() -> dict[str, Any]:
    return {
        "measurement_id": MEASUREMENT_ID,
        "model_snapshot": MODEL_SNAPSHOT,
        "live_authorized_attempt_id": LIVE_AUTHORIZED_ATTEMPT_ID,
        "proposed_attempt_id": PROPOSED_LIVE_ATTEMPT_ID,
        "max_calls": MAX_CALLS,
        "case_ids": list(frozen_case_ids()),
        "stage_3b_gaps": list(STAGE_3B_LIVE_GAPS),
        "provider_json_mode_support_asserted": False,
        "offline_json_mode_validator_passed": False,
    }
