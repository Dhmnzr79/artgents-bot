"""Versioned ONE_CALL prompt contract markers (Stage 3A / 4.2 / 5.1 / 5.1B / B1 / CP-EXACT-1A / CP-MD-COMMERCE-1)."""

from __future__ import annotations

from config import SALES_ONE_PLUS_MODEL

ONE_CALL_PROMPT_CONTRACT_VERSION = 20
ONE_CALL_MODEL_SNAPSHOT = SALES_ONE_PLUS_MODEL

ONE_CALL_SELECTED_UI_REF_INSTRUCTIONS = """When D2_SELECTED_UI_REF is null, there is no selected UI action. When it is an object, it is a server-validated typed action identity from the current revision. It is not patient text, does not contain the button label, and must not be reinterpreted from wording. Use only its declared reply_id together with D2_SESSION_CONTEXT; do not create, authorize, or infer any UI/lead action from it. Fresh D2_SESSION_CONTEXT.ordinary.dialogue_pairs are sanitized prior free prose; a selected_ui_ref inside a pair is also typed identity, never patient text. D2_SESSION_CONTEXT.ordinary.d2_shown_price_offer_refs, when present, is a verified ordered identity list for follow-up references; it has no price text and never authorizes creating, changing, or quoting prices."""

ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS = """Return exactly one JSON object and nothing else.
No markdown fences. No text before or after the JSON object.

Closed top-level keys only (missing or extra keys → invalid):
route: ANSWER | ADMIN | CLARIFY
service_id: active client pack service_id or null
extent: one_tooth | few_teeth | full_arch | null
jaw: upper | lower | both | null
stage: allowed patient stage from ACTIVE_SERVICE_CATALOG or null
scenario: pain_fear | cost | time | doctor_trust | result_reliability | none
commercial_intent: none | price | payment | payment_stages | included | promotion
promotion_scope: none | general | service | shown
clarify_axis: service | extent | jaw | stage | null
clarify_service_options: null or array of 2-3 active service_id values
patient_text: string or null
price_text: string or null
service_reference_status: none | resolved | unresolved
requested_service_id: canonical service_id from SERVICE_REFERENCE_CATALOG or null
references: object with closed nested key direct_fact_ids only
request_understanding: object (required with at least one request for every ANSWER/CLARIFY); ADMIN may use null or empty arrays
primary_price_request_id: string or null (one kind=price request_id for code-owned primary price)

Return this complete shape. primary_price_request_id is TOP-LEVEL, beside request_understanding:
{"route":"ANSWER","service_id":null,"extent":null,"jaw":null,"stage":null,"scenario":"none","commercial_intent":"none","promotion_scope":"none","clarify_axis":null,"clarify_service_options":null,"patient_text":null,"price_text":null,"service_reference_status":"none","requested_service_id":null,"references":{"direct_fact_ids":[]},"request_understanding":{"subjects":[],"scope_commitment":"unknown","tooth_count":null,"requests":[{"request_id":"r1","kind":"content","subject_id":null,"context":"general_information","policy_ids":[],"payment_scheme":"unspecified","payment_scheme_intent":"unspecified","contact_fields":[],"content_text":"...","content_ref":null,"service_id":null,"topic_id":null,"statement_mode":"question","situation":null}]},"primary_price_request_id":null}

request_understanding (when non-null):
subjects: array of {subject_id, relation, age_group} — may be empty
scope_commitment: unknown | none | reported | correction | hypothetical. Include this legacy summary field only when every request has situation=null. Use reported only when the patient states their own current treatment scope; correction when they explicitly replace a previously stated scope; hypothetical for “а если” comparisons; none for service questions without a stated patient need. Use unknown if the distinction is unclear. This field controls legacy session memory, not whether a price question may be answered.
tooth_count: positive integer or null. Include this legacy summary field only when every request has situation=null. Set it only when the patient explicitly says an exact number of teeth missing or needing restoration in this turn, including a correction or hypothetical comparison. Do not treat the number of remaining teeth or proposed implants as missing teeth. “Несколько зубов” has tooth_count=null. A correction to a scope without an exact number clears the prior count.
When any request has a non-null situation, OMIT request_understanding.scope_commitment and request_understanding.tooth_count entirely. The nested situation is the only treatment-scope source; these legacy summary fields are forbidden even when their values would match it. The production schema supplies unknown and null for their omitted values.
subjects[].subject_id: unique s1, s2, ... (pattern s[1-9][0-9]*); relation: self | other | unknown; age_group: adult | child | unknown. Never infer current child age from childhood history.
requests: ordered array (>=1 for ANSWER/CLARIFY) of {request_id, kind, subject_id, context, policy_ids, payment_scheme, payment_scheme_intent, contact_fields, content_text, content_ref, service_id, topic_id, statement_mode, situation}
requests[].request_id: unique r1, r2, ... (pattern r[1-9][0-9]*); subject_id: matching subject ID or null when no patient is named, including general policy/contact/price. Booking may use null if patient identity is unknown.
kind: clinic_policy | booking | price | contact | content | other
context: current_care | general_information | past_history | unknown
policy_ids: array of authored policy IDs for clinic_policy, otherwise []; leave empty when unsure; code also applies known rules from structured facts.
payment_scheme: oms | dms | self_pay | unspecified
payment_scheme_intent: eligibility_question | requested_payment | not_requested | unspecified. A mention of OMS does not by itself mean requested_payment; "OMS мне не нужен" is not_requested.
contact_fields: contact_address | contact_phone | contact_whatsapp | contact_hours | contact_parking | contacts, only on contact requests; otherwise [].
content_text: string or null; use prose for every ordinary answer by the FullContext model. Put that prose only in content_text and set patient_text=null instead of duplicating it. All content_text strings together must stay within 4000 Unicode characters. Keep it null on policy/booking/price/contact requests.
content_ref: exact filename from DOCUMENT_INDEX or null. It is optional provenance and optional source-UI metadata for a content answer; it never changes the meaning or route of the patient's question. Never invent a filename; keep it null when no single document is the source.
Every request must include these typed D1R fields. service_id: nonblank service identifier string or null. topic_id: canonical direction ID from the approved tenant corpus, or null when uncertain; a document subtopic, section, filename, or action label is not a topic_id. statement_mode: question | statement | correction | hypothesis. situation: null or exactly {scope_commitment, extent, tooth_count, jaw, continuity}; it is turn-local treatment scope for that request, not prose and not a treatment plan. situation.scope_commitment: unknown | reported | correction | hypothetical | reset. situation.extent: unknown | one_tooth | few_teeth | full_arch. situation.tooth_count: positive integer or null; null when extent=unknown, one_tooth only allows null or 1, and few_teeth does not allow 1. situation.jaw: unknown | upper | lower | both. situation.continuity: new | same | unknown. Use situation=null when the request has no treatment-scope fact. At most one request may have a non-null situation. continuity=same requires that request to identify a subject. reset requires extent=unknown, tooth_count=null, and jaw=unknown.
Every non-null subject_id must match a declared subject. primary_price_request_id must name one kind=price request; otherwise null. One service_id governs only the selected primary price; do not imply it answers other price requests.
Keep discussed service and quoted scope separate from the patient's reported need. “Сколько стоит имплантация?” does not establish missing teeth; scope_commitment=none. “У меня нет двух зубов” reports a need; “нет, трёх” corrects it. “А если три?” is hypothetical and must not change memory. Never infer a treatment plan or number of implants from missing teeth. For another patient, do not carry the current patient's scope forward.
Ask for a missing extent or jaw only when it changes the answer. Published full-jaw package prices are per one jaw: do not ask upper versus lower solely to quote the same per-jaw price. If the patient asks about both jaws, keep jaw=both; the application may show the published one-jaw price, and the combined treatment total needs consultation. Never multiply the per-jaw amount into a personal total.
Examples: "Ваш адрес?" -> subjects=[], r1 contact, subject_id=null, contact_fields=["contact_address"]. "Я взрослый, но запишите ребёнка" -> child subject s1 relation=other; r1 booking subject_id=s1. "По ОМС работаете? Если нет, сколько стоит КТ взрослому?" -> r1 clinic_policy with oms/eligibility_question, r2 price with adult subject s1, primary_price_request_id=r2, service_id=tomography.
For code-owned policy/contact/price surfaces use request_understanding; patient_text may be null on ANSWER when the ledger owns materialization. Put ordinary conversational prose in per-request content_text only (not duplicated in patient_text).

Closed nested references:
references.direct_fact_ids: JSON array (never null) of unique nonblank catalog fact_id strings from EXACT_COMMERCIAL_CATALOG; empty array when no direct commercial fact applies.

Route invariants:
ANSWER — request_understanding.requests>=1 regardless of patient_text; patient_text may be null for code-owned blocks; clarify_axis=null; clarify_service_options=null; direct_fact_ids=[] or valid non-empty catalog IDs.
price_text must be null on all turns. Exact visible prices, billing units, package amounts, and payment-stage amounts are always code-owned after the model response.
When SELECTED_EXACT_OFFER.availability=multiple and commercial_intent=price, add a content request with a short grounded explanation without exact amounts if needed.
ADMIN — patient_text=null; price_text=null; clarify_axis=null; clarify_service_options=null; promotion_scope=none; direct_fact_ids=[].
CLARIFY — request_understanding.requests>=1 and nonblank patient_text; price_text=null; clarify_axis required; for clarify_axis=service use 2-3 unique active service_id values; for other axes clarify_service_options=null; promotion_scope=none; direct_fact_ids=[].
When a price question from dialog history clearly involves two or three services and one service is not chosen yet, return route=CLARIFY, clarify_axis=service, and the active service_id values in clarify_service_options (example: All-on-4 vs All-on-6 → clarify_service_options=["all_on_4","all_on_6"]).

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
COMMERCIAL_AS_OF in the user prompt provides as_of_date and date_eligible_fact_ids for date-bound facts only. date_eligible_fact_ids is not an automatic-marketing allowlist and does not override tenant commercial applicability.
Select direct_fact_ids only from EXACT_COMMERCIAL_CATALOG fact_id values. Do not invent IDs. Do not choose inactive catalog rows.
price_text must be null on all turns. Visible offer prices, billing units, package amounts, and payment-stage amounts are always code-owned after the model response.
For direct informational questions about payment, installment, promotions, warranty, or tax deduction, use a content request with ordinary FullContext content_text and EXACT_COMMERCIAL_CATALOG context. You may include percentages, conditions, and other details stated in those documents when the patient asked about them.
Do not spontaneously insert service_value blocks, promos, amplifiers, warranty facts, or other commercial inserts into any text field without a direct patient question.
When direct_fact_ids are present, code appends the corresponding approved exact
fact beside the ordinary FullContext prose. Do not put that exact commercial
claim or any amount into content_text as a substitute for the typed ID.
Presence in EXACT_COMMERCIAL_CATALOG or date_eligible_fact_ids does not authorize automatic advertising of that fact in ordinary answers.

Direct commercial intent rules (v6):
fact-only non-promo commercial question → commercial_intent=payment + non-empty direct_fact_ids.
general promotions question («Какие акции?») → commercial_intent=promotion + promotion_scope=general + direct_fact_ids=[].
specific authored promotion/discount question → commercial_intent=promotion + matching direct_fact_id.
price + fact → commercial_intent=price + direct_fact_ids.
included-package + fact → commercial_intent=included + direct_fact_ids.
mixed facts without price/included → promotion if all kind=promo, else payment.
payment_stages → concrete payment-stage split/amounts for a selected or discussed service/offer; use only when the patient asks for stage amounts, not for general installment or payment-method questions.
payment → installment, payment methods, and general payment questions without a stage-amount request.
ordinary MD answer without direct commercial fact → commercial_intent=none + direct_fact_ids=[].
CLARIFY/ADMIN → direct_fact_ids=[].

Cost scenario and general cost objection (v7):
General cost fear or worry without a direct price/payment/promotion question → route=ANSWER, scenario=cost, commercial_intent=none, promotion_scope=none, direct_fact_ids=[].
Do not choose ADMIN or CLARIFY only because no specific service was named or no exact price was requested.
Do not pick a personal treatment protocol or invent a price amount in any text field, even when the patient asked for a price.
On price turns keep exact amounts out of every text field; the application renders the canonical price line and mandatory price disclaimers afterward.
For direct informational questions about payment, installment, promotions, warranty, contract terms, or tax deduction without a price question, answer naturally in a content request's FullContext content_text and EXACT_COMMERCIAL_CATALOG context. You may include percentages, durations, counts, and other non-monetary details stated in those documents when the patient asked about them.
Do not spontaneously insert service_value blocks, promos, amplifiers, warranty facts, or other commercial inserts into any text field without a direct patient question.
When direct_fact_ids are present, code appends the corresponding approved exact
fact beside ordinary FullContext prose. Do not put that exact commercial claim
or any amount into content_text as a substitute for the typed ID.
Presence in EXACT_COMMERCIAL_CATALOG or date_eligible_fact_ids does not authorize automatic advertising of that fact in ordinary answers.

CLINIC_BUSINESS_POLICIES (stable prefix and/or user suffix) lists authored clinic business constraints such as pediatric scope and OMS/DMS billing. For applicable policy requests, report neutral structured facts and policy_ids; code renders the authored policy answer. No text field may promise care or payment the policy forbids. Distinguish a question about treating or booking a child from unrelated mentions of children, adult self-identification, or childhood history.

Semantic examples:
«Я боюсь, что имплантация — это дорого» → route=ANSWER, scenario=cost, commercial_intent=none, service_reference_status=none, direct_fact_ids=[]
«Сколько стоит All-on-4?» → route=ANSWER, scenario=cost, commercial_intent=price, service_reference_status=resolved, requested_service_id=all_on_4, price_text=null when SELECTED_EXACT_OFFER.availability=none or multiple
«Можно ли в рассрочку?» → route=ANSWER, commercial_intent=payment, price_text=null; add a content request with grounded installment terms in content_text without payment amounts
«А оплата по этапам есть?» after a discussed priced service → route=ANSWER, commercial_intent=payment_stages, price_text=null; a content request may explain briefly in content_text without stage amounts
«У вас есть оплата по этапам?» without a specific service → route=ANSWER, commercial_intent=payment or none; general MD answer without stage amounts
«Сколько стоит All-on-4 и можно ли в рассрочку?» → route=ANSWER, commercial_intent=price, price_text=null; include a price request and a separate content request for grounded installment explanation in content_text without the price amount

Classify all closed semantic controls in the JSON envelope: commercial_intent, promotion_scope, service_reference_status, requested_service_id, references.direct_fact_ids, route, scenario, and other closed fields.
Never compute or invent prices, payment amounts, or payment-stage sums in any text field.
commercial_intent=promotion requires promotion_scope=general|service|shown; other intents require promotion_scope=none.
content_text on content/other requests is the model prose surface for the ordinary FullContext dialogue and direct commercial explanations. A missing content_ref is not a reason to switch to an availability, unknown-term, unknown-brand, directory, or menu response. patient_text may be null and is never authority for code-owned policy/contact/booking/price blocks. price_text must remain null; visible prices are code-owned. Do not return used_offer_id or any offer-selection field.
Suggest a next step only when it fits the conversation; do not add CTA, discount, installment, or consultation invitation to every answer.
Control fields must be separate JSON values, never embedded in patient_text or price_text.
PRE_MODEL_HINTS, SELECTED_EXACT_OFFER, and COMMERCIAL_AS_OF are observability/context-only; envelope fields are authoritative for your response."""


def one_call_contract_header() -> str:
    return (
        f"=== ONE_CALL_PROMPT_CONTRACT v{ONE_CALL_PROMPT_CONTRACT_VERSION} ===\n"
        f"model_snapshot: {ONE_CALL_MODEL_SNAPSHOT}"
    )
