# TASK — S38 Minimal Target Runtime Verifier

**Branch / baseline:** `codex/stage-a` / `ab78724 feat: execute target composer request S37`

**Goal:** add a fail-closed target Verifier that accepts only the exact S36 request and its
exact S37 unverified response, deterministically checks numeric provenance and selected
strict facts, invokes one provider-neutral semantic backend exactly once, and
returns an immutable verified response. Offline tests only; no product/live/LLM wiring.

## Owner laws

- S38 never edits, softens, removes sentences from, repairs, retries, or replaces Composer
  text. It either returns the exact text unchanged or raises a typed blocking error.
- The legacy `numeric_fact_gate` and legacy `VerifierVerdict` are not reused: they depend on
  old runtime/config and do not provide this target fail-closed contract.
- Every digit-form numeric claim in the candidate must have a same-kind normalized value in
  the exact selected primary evidence. Missing whitelist is rejection, never pass/fail-open.
  Numeric claims written as words are checked semantically; S38 does not pretend the digit
  extractor proves their provenance.
- Every selected commercial fact is intended response material. A selected strict fact
  must occur verbatim; a selected natural fact must retain its meaning under semantic
  verification. Omission is not silently allowed merely because the fact is not listed in
  `required_fact_ids`.
- Semantic verification is mandatory for every response. This owner decision prioritizes
  accuracy for the initial target architecture over one-call latency; later sampling or a
  narrower trigger requires a separate evidence-backed governance decision.
- Semantic verification checks grounding, allowed/forbidden topic scope, required facts and
  the medical boundary. It never rewrites source-owned wording and is not a forbidden
  phrase blocklist/claim gate.
- The mandatory semantic backend is called exactly once. Failure, malformed output or any
  false assessment blocks the response. No retry, fallback, second model or side effect.
- S38 does not prove model quality offline. Recording backends prove only orchestration.
  Actual semantic quality still requires owner-authorized live evaluation.
- Successful S38 output is a target contract only. Runtime/UI/product authority remains
  forbidden until a later end-to-end checkpoint and explicit authority decision.

## Contract

Add `core/target_response_verifier.py`:

```python
TargetNumericKind = Literal["money", "percent", "day", "month", "year", "generic"]

@dataclass(frozen=True, slots=True)
class TargetNumericClaim:
    kind: TargetNumericKind
    value: str

@dataclass(frozen=True, slots=True)
class TargetSemanticVerifierInvocation:
    system_policy: str
    response_spec_json: str
    primary_evidence_json: str
    candidate_text: str

@dataclass(frozen=True, slots=True)
class TargetSemanticVerification:
    grounded_in_primary_evidence: bool
    topic_scope_ok: bool
    medical_boundary_ok: bool
    selected_facts_ok: bool

class TargetSemanticVerifierBackend(Protocol):
    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object: ...

@dataclass(frozen=True, slots=True)
class TargetVerifiedComposedResponse:
    text: str
    spec: TargetResponseSpec
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None
    verification_status: Literal["verified"] = "verified"

def verify_target_composed_response(
    request: TargetComposerRequest,
    response: TargetUnverifiedComposedResponse,
    *,
    semantic_backend: TargetSemanticVerifierBackend,
) -> TargetVerifiedComposedResponse: ...
```

The result preserves exact `text`, `spec`, `selected_followups` and `selected_cta_key`
identities from S37. It never exposes a modified answer.

## Exact input boundary

Validation is total/fail-closed for every field S38 reads:

1. exact `TargetComposerRequest` and exact `TargetUnverifiedComposedResponse`;
2. exact `TargetResponseSpec`; exact mode `answer|medical_handoff`; `allowed_topics` is an
   exact nonempty tuple of unique canonical strings; `forbidden_topics` and
   `required_fact_ids` are exact tuples of unique canonical strings; allowed/forbidden are
   disjoint; exact trimmed nonempty response text; exact
   `verification_status == "unverified"`;
3. response `spec`, follow-up selection and CTA are the same objects (`is`) as request
   sidecars; this is the direct S37 adjacency contract;
4. request evidence is a nonempty exact tuple of exact `TargetComposerEvidenceBlock`;
   every block has an allowed exact kind, canonical nonempty ref/text, exact tuple of
   canonical topics/fact IDs and exact bool preservation marker; refs are unique;
5. each required fact ID maps to exactly one `commercial_fact` block with exact
   `fact_ids == (id,)` and `ref == f"fact:{id}"`; every selected commercial-fact block has
   exactly one matching fact ID/ref.

S38 trusts S37/S36 as the authenticity boundary and does not reopen MD/JSON sources. It
does not claim authenticity for a caller fabricating a structurally valid adjacent pair.

## Deterministic numeric verification

Digit-form numeric claims are extracted in appearance order from candidate text and
source-owned text with Unicode-aware, case-insensitive rules. Normalize Unicode NFKC, remove grouping spaces
(`space`, NBSP, narrow NBSP), convert decimal comma to dot, and canonicalize leading/trailing
decimal zeroes without rounding. A sign is not inferred from the hyphen in names such as
`All-on-4`.

A digit inside one contiguous Latin alphanumeric/hyphenated lexical name containing at
least one Latin letter and one digit (for example `All-on-4`/`All-on-6`) is not a standalone
numeric claim. The entire name is delegated to the mandatory semantic grounding check.
This exception does not cover standalone ranges or Russian unit forms such as `1–3 дня` or
`15-летний`: their digits remain claims. A price-only request therefore does not need to
scan excluded `service_id=all_on_4` merely to authorize the lexical name.

Kind is determined by an immediately associated unit:

- `money`: case-insensitive prefix or postfix currency association with optional spacing;
  postfix `₽`, `руб`, `руб.`, `рубль`, `рубля`, `рублей`, `р.`, `RUB`; prefix `₽` or
  `RUB` (for example `368 000 рублей`, `368000 рубля`, `368000 RUB`, `₽ 368000`);
- `percent`: `%` or Russian percent word;
- `day`, `month`, `year`: Russian day/month/year forms;
- otherwise `generic`.

Ranges retain both endpoints with the associated unit (`1–3 дня` → day `1`, day `3`).
Duplicates are allowed. Candidate claim passes only when the exact `(kind, value)` occurs
in the evidence whitelist.

Evidence whitelist is built only from selected blocks. Structured JSON must have the exact
S36 keys/types below; malformed/extra/missing fields are input-invalid:

- `offer` root keys are exactly `offer_id`, `service_id`, `option_id`, `brand_id`, `price`,
  `package`, `payment_stages`; `offer_id` and `service_id` are non-null canonical strings;
  only `option_id` and `brand_id` may be null, otherwise they are canonical strings;
  `price` keys are
  exactly the fields of its mode (`fixed: mode,amount,currency,billing_unit`;
  `from: mode,min_amount,currency,billing_unit`;
  `range: mode,min_amount,max_amount,currency,billing_unit`;
  `no_public_price: mode,approved_text`); amounts are exact nonnegative integers; range
  additionally requires `min_amount <= max_amount`; currency/billing unit are
  canonical strings;
- `package` keys are exactly `label,includes`, with canonical label and exact unique list of
  canonical strings; `payment_stages` is null or a nonempty list whose objects have exactly
  `label,amount,currency`, canonical text and exact nonnegative integer amount; stage labels
  are unique;
- for valid offers, fixed `amount`, from `min_amount`, range `min_amount|max_amount` and
  every `payment_stages[].amount` become `money`; scan `no_public_price.approved_text`,
  `package.label`, every `package.includes` item and payment-stage labels by the same typed
  text rules; validate but do not scan offer/service/option/brand IDs, currency, mode or
  billing unit;
- `doctor|external_doctor` root keys are exactly `doctor_id`, `name`, `position`,
  `experience_years`, `profile_text`; ID/name/position/profile are canonical strings and
  experience is an exact nonnegative integer. Experience becomes `year`; scan exact name,
  position and profile text by the same typed text rules; do not scan `doctor_id`;
- `content|commercial_fact|external_kb|consultation`: scan exact block text by the same
  typed rules.

Malformed structured JSON/schema blocks are input-invalid, not an empty whitelist. First
unsupported candidate claim blocks deterministically with its exact `(kind, value)`.

## Selected facts and semantic verification

For each selected commercial-fact block:

- `must_preserve_exact=True` → exact block text must be a substring of candidate text;
- `must_preserve_exact=False` → its meaning and presence are checked by semantic assessment.

Semantic verification is mandatory for every response and the backend is called exactly
once after deterministic numeric and strict-fact checks pass.

`TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` is one stable constant requiring an assessment
only (no rewrite) of these fields in order:

1. all factual claims, including numbers written with digits or words and their units and
   context, grounded in `PRIMARY_EVIDENCE`;
2. answer stays inside allowed topics and outside forbidden topics;
3. in `medical_handoff`, no diagnosis, differential, personal eligibility or treatment
   choice; for ordinary answer this field must still be true;
4. every selected commercial fact is present; natural facts retain meaning and strict facts
   remain verbatim;
5. return only the four-field structured assessment; never repair the answer.

`selected_facts_ok` explicitly means all selected commercial facts, not only
`spec.required_fact_ids`.

Invocation JSON uses compact UTF-8 serialization with stable field order. `response_spec_json`
fields: `response_mode`, `allowed_topics`, `forbidden_topics`, `required_fact_ids`.
`primary_evidence_json` objects: `kind`, `ref`, `topics`, `fact_ids`, `text`,
`must_preserve_exact`. Candidate text is separate and exact.

Backend output must be exact `TargetSemanticVerification`, all four fields exact bool, and
all must be true. A false assessment rejects with the ordered tuple of failed field names.

## Errors and precedence

One public `TargetResponseVerificationError(ValueError)` has `.code`, `.value`, exact
message `f"{code}: {value!r}"`. Precedence:

1. invalid/mismatched adjacent input → `target_verifier_input_invalid` with first marker
   `request`, `response`, `spec`, `identity`, `evidence`, `required_facts`;
2. first unsupported numeric claim → `target_verifier_numeric_ungrounded`, value exact
   `(kind, value)`;
3. first missing selected strict fact → `target_verifier_strict_fact_missing`, value ID;
4. backend lacks callable `assess` → `target_verifier_backend_invalid`, value
   `semantic_assess`;
5. backend exception → `target_verifier_backend_failed`, value exact exception class name,
   original chained;
6. malformed semantic output → `target_verifier_semantic_output_invalid`, original value;
7. false semantic fields → `target_verifier_semantic_rejected`, ordered failed field names.

Exactly seven S38 error-code strings exist. There is no fallback or partial verified result.

## Boundaries / allowlist

No live/LLM/provider SDK, client data, A9/TurnFrame/patient scope, legacy verifier/numeric
gate import, runtime/routes/session/cache, UI/product authority, repair/fallback, or full
suite. Do not edit S27–S37 contracts/tests.

- `TASK.md`
- `core/target_response_verifier.py`
- `tests/test_target_response_verifier.py`
- `tests/test_demo_target_response_verifier.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- exact frozen shapes/signature/constant/seven errors and precedence;
- hostile nested inputs produce typed failures before extraction/backend;
- exact adjacent identity and unverified input status enforced;
- typed digit numeric extraction covers prices/grouping/decimals/percent/ranges/time,
  currency prefix/postfix and inflections, lexical-name `All-on-4` exclusion, and structured
  fixed/from/range/no-public offer/doctor fields;
- price-only All-on-4 may use its lexical service name while a standalone unsupported `4`
  still blocks before semantic verification;
- package/includes/payment-stage labels and doctor name/position/profile contribute typed
  numeric source facts while structured IDs never do;
- unsupported first number blocks; absent whitelist never passes; no text removal/repair;
- every selected strict fact requires exact presence; every natural selected fact is covered
  by semantic assessment;
- every answer, including ordinary and medical_handoff, makes exactly one semantic call with
  exact spec/evidence/text; number words are explicitly in semantic policy;
- backend missing/failure/malformed/false fields fail without retry/fallback;
- `selected_facts_ok=False` rejects all-selected-fact coverage, including optional natural;
- successful result preserves exact text/spec/follow-up/CTA and says verified;
- real demo All-on-4 price/doctor/natural-fact response verifies offline through one positive
  recording semantic assessment without client writes or a model-quality claim;
- import firewall proves no provider/live/legacy/runtime/cache/search and no skip/xfail.

Run only S38 target/demo plus S37 and S36 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern target runtime verifier S38` only to stage-a.
3. Implement only the allowlist and run minimal offline tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: verify target composed response S38`; final clean/synced.

Next checkpoint after S38: one minimal offline end-to-end target response pipeline. It may
use recording Composer/semantic backends only to prove orchestration, never answer quality.
