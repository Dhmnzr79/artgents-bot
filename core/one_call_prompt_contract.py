"""Versioned ONE_CALL prompt contract markers (Stage 3A)."""

from __future__ import annotations

from config import SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_PROMPT_CONTRACT_VERSION = 1

ONE_CALL_MODEL_SNAPSHOT = SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS = """Return a control envelope before any patient narrative.
Closed fields (invalid value → safe handoff, no retry):
route: ANSWER | ADMIN | CLARIFY
service_id: active client pack id or null
extent: one_tooth | few_teeth | full_arch | null
jaw: upper | lower | both | null
stage: client-authored allowlist value or null
scenario: pain_fear | cost | time | doctor_trust | result_reliability | none
clarify_axis: service | extent | jaw | stage | null
clarify service options: up to 3 service_id from active pack
patient answer text: narrative without commercial amounts
JSON Schema / structured output support is not asserted until LIVE capability test.
Until then transport uses the legacy @ANSWER/@ADMIN line protocol in dynamic suffix only."""


def one_call_contract_header() -> str:
    return (
        f"=== ONE_CALL_PROMPT_CONTRACT v{ONE_CALL_PROMPT_CONTRACT_VERSION} ===\n"
        f"model_snapshot: {ONE_CALL_MODEL_SNAPSHOT}"
    )
