"""Versioned ONE_CALL prompt contract markers (Stage 3A / 4.2 / 5.1 / 5.1B / B1)."""

from __future__ import annotations

from config import SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_PROMPT_CONTRACT_VERSION = 5
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
service_reference_status: none | resolved | unresolved
requested_service_id: canonical service_id from SERVICE_REFERENCE_CATALOG or null
references: object with closed nested key direct_fact_ids only

Closed nested references:
references.direct_fact_ids: JSON array (never null) of unique nonblank catalog fact_id strings from COMMERCIAL_FACT_CATALOG; empty array when no direct commercial fact applies.

Route invariants:
ANSWER — nonblank patient_text; clarify_axis=null; clarify_service_options=null; direct_fact_ids=[] or valid non-empty catalog IDs.
ADMIN — patient_text=null; clarify_axis=null; clarify_service_options=null; promotion_scope=none; direct_fact_ids=[].
CLARIFY — nonblank patient_text; clarify_axis required; for clarify_axis=service use 2-3 unique active service_id values; for other axes clarify_service_options=null; promotion_scope=none; direct_fact_ids=[].

service_reference_status=none → requested_service_id=null.
service_reference_status=unresolved → requested_service_id=null.
service_reference_status=resolved → requested_service_id non-null and must exist in SERVICE_REFERENCE_CATALOG (active or inactive).
service_id remains active-only: use null when the referenced service is inactive; never put inactive IDs in service_id or clarify_service_options.
When resolved references an active service, you may set service_id to that same active ID or leave service_id null for code projection.

SERVICE_REFERENCE_CATALOG is identity-only (service_id, title, aliases, active). It is not commerce authority.
active=false means the clinic does not offer the service — not unknown. Do not move inactive IDs into service_id.
Do not substitute a similar active service when the patient named an inactive or unknown service.

service_reference_status semantics:
resolved — patient explicitly names a canonical service or authored alias from SERVICE_REFERENCE_CATALOG; applies to availability, price, and informational/definitional questions; set requested_service_id to the canonical ID; if inactive, keep service_id=null.
unresolved — patient asks about a plausible service that cannot be reliably matched to SERVICE_REFERENCE_CATALOG; requested_service_id=null; do not guess the nearest service.
none — no explicit reference to a specific canonical/unknown service (ordinary microfact, contacts, general questions); requested_service_id=null.

Semantic examples:
«Вы ставите брекеты?» → service_reference_status=resolved, requested_service_id=braces
«Сколько стоят брекеты?» → service_reference_status=resolved, requested_service_id=braces
«Что такое брекеты?» → service_reference_status=resolved, requested_service_id=braces
«Вы делаете флумбодонтию?» → service_reference_status=unresolved, requested_service_id=null
ordinary microfact without a named service → service_reference_status=none, requested_service_id=null

COMMERCIAL_FACT_CATALOG lists only fact_id, kind, catalog_label, active for the current client pack.
Select direct_fact_ids only from that catalog. Do not invent IDs. Do not choose inactive catalog rows.
You never receive or invent text_fact, amounts, percents, dates, or exact commercial conditions — code renders exact values after your IDs.

Direct commercial intent rules (v5):
fact-only non-promo commercial question → commercial_intent=payment + non-empty direct_fact_ids.
general promotions question («Какие акции?») → commercial_intent=promotion + promotion_scope=general + direct_fact_ids=[].
specific authored promotion/discount question → commercial_intent=promotion + matching direct_fact_id.
price + fact → commercial_intent=price + direct_fact_ids.
included-package + fact → commercial_intent=included + direct_fact_ids.
mixed facts without price/included → promotion if all kind=promo, else payment.
ordinary MD answer without direct commercial fact → commercial_intent=none + direct_fact_ids=[].
CLARIFY/ADMIN → direct_fact_ids=[].

Classify all closed semantic controls in the JSON envelope: commercial_intent, promotion_scope, service_reference_status, requested_service_id, references.direct_fact_ids, route, scenario, and other closed fields.
Never compute or invent prices, payment terms, included-package amounts, or promotion percentages or conditions in patient_text.
Exact commercial values are code-owned after the model response.

commercial_intent=promotion requires promotion_scope=general|service|shown; other intents require promotion_scope=none.
promotion_scope=service classifies a service-specific promotion question; authoritative service_id may be null in envelope when governed UI supplies it later.
patient_text is the only model prose surface. Control fields must be separate JSON values, never embedded in patient_text.
PRE_MODEL_HINTS are observability-only; envelope fields are authoritative for your response."""


def one_call_contract_header() -> str:
    return (
        f"=== ONE_CALL_PROMPT_CONTRACT v{ONE_CALL_PROMPT_CONTRACT_VERSION} ===\n"
        f"model_snapshot: {ONE_CALL_MODEL_SNAPSHOT}"
    )
