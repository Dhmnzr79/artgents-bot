"""Versioned ONE_CALL prompt contract markers (Stage 3A / 4.2 / 5.1)."""

from __future__ import annotations

from config import SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_PROMPT_CONTRACT_VERSION = 3

ONE_CALL_MODEL_SNAPSHOT = SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS = """Return exactly one JSON object and nothing else.
No markdown fences. No text before or after the JSON object.
Closed top-level keys only (missing or extra keys → invalid):
route: ANSWER | ADMIN | CLARIFY
service_id: active client pack service_id or null
extent: one_tooth | few_teeth | full_arch | null
jaw: upper | lower | both | null
stage: allowed patient stage from ACTIVE_SERVICE_CATALOG or null
scenario: pain_fear | cost | time | doctor_trust | result_reliability | none
commercial_intent: none | price | payment | included | promotion
promotion_scope: none | general | service | shown
clarify_axis: service | extent | jaw | stage | null
clarify_service_options: null or array of 2-3 active service_id values
patient_text: string or null
Route invariants:
ANSWER — nonblank patient_text; clarify_axis=null; clarify_service_options=null.
ADMIN — patient_text=null; clarify_axis=null; clarify_service_options=null; promotion_scope=none.
CLARIFY — nonblank patient_text; clarify_axis required; for clarify_axis=service use 2-3 unique active service_id values; for other axes clarify_service_options=null; promotion_scope=none.
commercial_intent=promotion requires promotion_scope=general|service|shown; other intents require promotion_scope=none.
promotion_scope=service classifies a service-specific promotion question; authoritative service_id may be null in envelope when governed UI supplies it later.
patient_text is the only model prose surface. Control fields must be separate JSON values, never embedded in patient_text.
PRE_MODEL_HINTS are observability-only; envelope fields are authoritative for your response.
Classify commercial_intent and promotion_scope only; never compute or invent prices, payment terms, included-package amounts, or promotion percentages or conditions.
Exact commercial values are code-owned after the model response."""


def one_call_contract_header() -> str:
    return (
        f"=== ONE_CALL_PROMPT_CONTRACT v{ONE_CALL_PROMPT_CONTRACT_VERSION} ===\n"
        f"model_snapshot: {ONE_CALL_MODEL_SNAPSHOT}"
    )
