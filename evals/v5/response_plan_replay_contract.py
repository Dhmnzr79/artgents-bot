"""Frozen replay contract types for RESPONSE-REPLAY-1."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CaptureProvenance = Literal[
    "captured_exact",
    "derived_from_captured_structure",
    "frozen_baseline_lookup",
    "not_captured",
]
ReplayFidelity = Literal["full", "partial", "not_replayable"]
ReplayDeltaClass = Literal[
    "no_material_change",
    "expected_contract_change",
    "unexplained_visible_delta",
    "capture_gap",
    "model_output_issue",
    "response_plan_violation",
    "adapter_error",
    "fatal_replay_error",
]

ExpectedContractChangeReason = Literal[
    "legacy_direct_facts_not_promoted",
    "automatic_warranty_suppressed",
    "combined_multi_price_block",
]

EXPECTED_STRUCTURED_TURNS_SHA256 = (
    "98D5F672F2B54B64A3A4624BE06853D2419A3C85E7A8E9B32959557248327357"
)
EXPECTED_RAW_TURNS_SHA256 = "6EAF6E3B38D05709772A6E5CCC0FE9305304A1527577E33B580F636F945BA3A8"
EXPECTED_MANIFEST_SHA256 = "CD25D244D67B08D42B9826AF7ECD4A1EE7AEEC7FB59351B0C77A07BF0270851C"
EXPECTED_FACTS_SHA256 = "F2DB17BEE7A2E54ADB46A3A1431A000A2401B475C7D7E55B9C08C1827B094CBD"

EXPECTED_RECORD_COUNT = 76
EXPECTED_PROVIDER_TURN_COUNT = 68
EXPECTED_CODE_ONLY_TURN_COUNT = 8

CONFIG_TO_CONTEXT_STRATEGY: dict[str, str] = {
    "flash_full": "full_context",
    "plus_full": "full_context",
    "flash_curated": "hybrid",
    "plus_curated": "hybrid",
}

OVERALL_VERDICT = Literal["PASS", "PARTIAL_CAPTURE", "FAIL"]


class ReplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceKey(ReplayModel):
    scenario_id: str
    turn_id: str
    config_id: str
    session_id: str


class SourceHashes(ReplayModel):
    structured_turns: str
    raw_turns: str
    manifest: str
    facts: str


class ReplayManifest(ReplayModel):
    replay_id: str
    source_attempt_id: str
    source_root: str
    source_hashes: SourceHashes
    head_sha: str
    record_count: int = EXPECTED_RECORD_COUNT


class LegacySourceMetadata(ReplayModel):
    route: str | None = None
    patient_text: str | None = None
    visible_answer: str | None = None
    direct_fact_ids: tuple[str, ...] = ()
    promo_fact_ids: tuple[str, ...] = ()
    amplifier_fact_ids: tuple[str, ...] = ()
    service_value_id: str | None = None
    selected_offer_ids: tuple[str, ...] = ()
    canonical_price_block: str | None = None
    provider_turn: bool = False
    turn_error: str | None = None
    error_code: str | None = None


class TargetInputSummary(ReplayModel):
    context_strategy: str | None = None
    response_scope: str | None = None
    selected_service_id: str | None = None
    execution_kind: str | None = None
    route: str | None = None
    mode: str | None = None
    requested_fact_ids: tuple[str, ...] = ()
    promo_candidate_ids: tuple[str, ...] = ()
    amplifier_candidate_ids: tuple[str, ...] = ()


class TargetOutputSummary(ReplayModel):
    resolved: bool = False
    rendered_text: str | None = None
    patient_text: str | None = None
    terminal_text: str | None = None
    price_block_count: int = 0
    finalized_commercial_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    adapter_error: str | None = None
    response_plan_error: str | None = None
    contract_violations: tuple[str, ...] = ()


class ReplayComparison(ReplayModel):
    exact_text_match: bool | None = None
    patient_text_preserved: bool | None = None
    legacy_visible_answer: str | None = None
    target_visible_answer: str | None = None
    legacy_price_block_present: bool | None = None
    target_price_block_present: bool | None = None


class ReplayRecordResult(ReplayModel):
    source_key: SourceKey
    source_hashes: SourceHashes
    provider_turn: bool
    context_strategy: str | None = None
    capture_fidelity: ReplayFidelity
    capture_gaps: tuple[str, ...] = ()
    field_provenance: dict[str, CaptureProvenance] = Field(default_factory=dict)
    legacy_source: LegacySourceMetadata
    target_input_summary: TargetInputSummary
    target_output: TargetOutputSummary
    delta: ReplayComparison
    delta_classes: tuple[ReplayDeltaClass, ...] = ()
    contract_violations: tuple[str, ...] = ()
    captured_commercial_intent: str | None = None
    false_price_insertion: bool = False
    fabricated_findings: tuple[str, ...] = ()
    provenance_findings: tuple[str, ...] = ()
    expected_contract_change_reasons: tuple[ExpectedContractChangeReason, ...] = ()
    unexplained_visible_delta: bool = False
    price_intent_unresolved: bool = False


class ReplayMetrics(ReplayModel):
    source_count: int
    provider_turn_count: int
    code_only_turn_count: int
    full_count: int
    partial_count: int
    not_replayable_count: int
    resolved_count: int
    rendered_count: int
    adapter_error_count: int
    response_plan_violation_count: int
    patient_text_preserved_count: int
    exact_text_match_count: int
    expected_contract_change_count: int
    capture_gap_counts: dict[str, int] = Field(default_factory=dict)
    legacy_direct_ids_not_promoted_count: int = 0
    legacy_warranty_appearances: int = 0
    target_requested_warranty_count: int = 0
    target_automatic_warranty_count: int = 0
    single_price_count: int = 0
    multi_price_count: int = 0
    no_price_count: int = 0
    missing_required_conditions_count: int = 0
    terminal_not_replayable_count: int = 0
    scope_not_replayable_count: int = 0
    client_isolation_violations: int = 0
    provider_network_calls: int = 0
    safety_violation_count: int = 0
    unclassified_count: int = 0
    fabricated_field_count: int = 0
    false_price_insertion_count: int = 0
    expected_change_reason_counts: dict[str, int] = Field(default_factory=dict)
    unexplained_visible_delta_count: int = 0
    provenance_finding_count: int = 0
    price_intent_without_price_count: int = 0
    fatal_replay_error_count: int = 0
    unresolved_count: int = 0


class ReplayResult(ReplayModel):
    replay_id: str
    overall_verdict: OVERALL_VERDICT
    metrics: ReplayMetrics
    records: tuple[ReplayRecordResult, ...]

    @model_validator(mode="after")
    def _validate_record_count(self) -> Self:
        if len(self.records) != EXPECTED_RECORD_COUNT:
            raise ValueError("record_count_mismatch")
        return self


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
