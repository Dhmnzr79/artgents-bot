"""Versioned ONE_CALL prompt contract markers (Stage 3A / 4.2 / 5.1 / 5.1B / B1 / CP-EXACT-1A / CP-MD-COMMERCE-1)."""

from __future__ import annotations

from config import SALES_ONE_PLUS_FLASH_MODEL

ONE_CALL_PROMPT_CONTRACT_VERSION = 7
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
references.direct_fact_ids: JSON array (never null) of unique nonblank catalog fact_id strings from EXACT_COMMERCIAL_CATALOG; empty array when no direct commercial fact applies.

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

EXACT_COMMERCIAL_CATALOG is the canonical source of exact commercial data for the current client pack: facts, offers, prices, billing units, package labels/includes, payment stages, and active service links.
COMMERCIAL_AS_OF in the user prompt provides as_of_date and date_eligible_fact_ids for date-bound facts only. date_eligible_fact_ids is not an automatic-marketing allowlist and does not override service applicability or marketing.yaml rules.
Select direct_fact_ids only from EXACT_COMMERCIAL_CATALOG fact_id values. Do not invent IDs. Do not choose inactive catalog rows.
On CP-EXACT-1A you receive full exact commercial data for grounding, but patient_text must not contain code-owned exact values: price amounts, billing units, package amounts, payment-stage amounts, promotion percentages/conditions, or canonical fact texts copied verbatim for rendering.
Do not spontaneously insert service_value blocks, promos, amplifiers, warranty facts, or other commercial inserts into patient_text without a direct patient question. Automatic service_value, promos, and amplifiers are added later by deterministic code per marketing.yaml and CP-MKT-1.
Presence in EXACT_COMMERCIAL_CATALOG or date_eligible_fact_ids does not authorize automatic advertising of that fact.

Direct commercial intent rules (v6):
fact-only non-promo commercial question → commercial_intent=payment + non-empty direct_fact_ids.
general promotions question («Какие акции?») → commercial_intent=promotion + promotion_scope=general + direct_fact_ids=[].
specific authored promotion/discount question → commercial_intent=promotion + matching direct_fact_id.
price + fact → commercial_intent=price + direct_fact_ids.
included-package + fact → commercial_intent=included + direct_fact_ids.
mixed facts without price/included → promotion if all kind=promo, else payment.
ordinary MD answer without direct commercial fact → commercial_intent=none + direct_fact_ids=[].
CLARIFY/ADMIN → direct_fact_ids=[].

Cost scenario and general cost objection (v7):
General cost fear or worry without a direct price/payment/promotion question → route=ANSWER, scenario=cost, commercial_intent=none, promotion_scope=none, direct_fact_ids=[].
Do not choose ADMIN or CLARIFY only because no specific service was named or no exact price was requested.
Do not pick a personal treatment protocol or invent a price amount in patient_text unless the patient asked for a price.
Automatic service_value, promos, amplifiers, and CTA/UI are added later by code when marketing rules allow; patient_text should stay a useful grounded answer from MD (e.g. cost FAQ), not a spontaneous price quote.

Semantic examples:
«Я боюсь, что имплантация — это дорого» → route=ANSWER, scenario=cost, commercial_intent=none, service_reference_status=none, direct_fact_ids=[]
«Переживаю, что лечение окажется слишком дорогим» → route=ANSWER, scenario=cost, commercial_intent=none, service_reference_status=none, direct_fact_ids=[]
«Сколько стоит All-on-4?» → route=ANSWER, scenario=cost, commercial_intent=price, service_reference_status=resolved, requested_service_id=all_on_4, direct_fact_ids per authoritative price path
«Можно ли в рассрочку?» → route=ANSWER, commercial_intent=payment, direct_fact_ids include installment_12 when applicable

Classify all closed semantic controls in the JSON envelope: commercial_intent, promotion_scope, service_reference_status, requested_service_id, references.direct_fact_ids, route, scenario, and other closed fields.
Never compute or invent prices, payment terms, included-package amounts, or promotion percentages or conditions in patient_text.
Exact commercial values in the visible answer are still code-owned after the model response on CP-EXACT-1A.

commercial_intent=promotion requires promotion_scope=general|service|shown; other intents require promotion_scope=none.
promotion_scope=service classifies a service-specific promotion question; authoritative service_id may be null in envelope when governed UI supplies it later.
patient_text is the only model prose surface. Control fields must be separate JSON values, never embedded in patient_text.
PRE_MODEL_HINTS and COMMERCIAL_AS_OF are observability/context-only; envelope fields are authoritative for your response."""


def one_call_contract_header() -> str:
    return (
        f"=== ONE_CALL_PROMPT_CONTRACT v{ONE_CALL_PROMPT_CONTRACT_VERSION} ===\n"
        f"model_snapshot: {ONE_CALL_MODEL_SNAPSHOT}"
    )
