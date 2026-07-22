# TASK — S35 Scoped Response Evidence

**Branch / baseline:** `codex/stage-a` / `1e106bf feat: bind response spec to offline package S34`

**Goal:** turn one exact S34 result into a closed, identity-only evidence view that
enforces the spec's topic scope and required structured facts. Offline/unwired; no
retrieval, prose composition, product routing, or authority.

## Owner laws

- S34 raw materials and follow-up candidates remain internal and never become payload.
- S35 does not add a retriever, ranking, fuzzy matching, topic inference, or fallback.
- A selected service's canonical topic comes from the exact `topic` field in the
  frontmatter of its owned service MD. Service-linked offers and selected commercial
  facts inherit that topic.
- A selected plan doctor and a selected external `doctor:` ref preserve two proven axes
  in this order: the selected service MD topic, then the linked doctor profile MD topic,
  deduplicated. This lets service questions use doctors without hiding a forbidden
  `doctors` topic.
- Selected external `kb:` refs use the exact topic of their own MD. A selected external
  `doctor:` ref is valid only when that doctor is linked to the selected service and has
  one valid owned profile MD ref.
- Every factual evidence item must intersect `spec.allowed_topics` and must not intersect
  `spec.forbidden_topics`. Missing/unreadable topic metadata fails closed.
- `required_fact_ids` are covered only by commercial facts actually present in the S34
  consumable plan. Merely existing in the bundle or in an offer's candidate `fact_refs`
  is not coverage.
- `medical_handoff` still requires the later Composer/Verifier no-diagnosis,
  no-differential, no-personal-eligibility and no-treatment-choice boundary. S35 checks
  evidence scope; it does not inspect or rewrite prose.

## Contract

Add `core/target_scoped_response_evidence.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetEvidenceScopeRecord:
    ref: str
    topics: tuple[str, ...]
    fact_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class TargetScopedResponseEvidence:
    spec: TargetResponseSpec
    service_id: str
    primary_content_ref: str | None
    offer_ids: tuple[str, ...]
    doctor_ids: tuple[str, ...]
    commercial_fact_ids: tuple[str, ...]
    external_source_refs: tuple[str, ...]
    consultation_content_ref: str | None
    selected_followups: TargetResponseFollowupSelection
    selected_cta_key: str | None
    scope_records: tuple[TargetEvidenceScopeRecord, ...]
    covered_fact_ids: tuple[str, ...]

def build_target_scoped_response_evidence(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    *,
    md_root: Path,
) -> TargetScopedResponseEvidence: ...
```

The output copies only the S34 consumable composition view. It does not expose
`TargetOfflineResponsePackage`, candidate materials, candidate follow-ups, or candidate
CTA.

Canonical scope refs, in composition order:

1. `content:{primary_content_ref}` when selected;
2. `offer:{offer_id}` for selected plan offers;
3. `doctor:{doctor_id}` for selected plan doctors;
4. `fact:{fact_id}` for selected plan commercial facts, with `fact_ids=(fact_id,)`;
5. each selected external source ref unchanged;
6. `consultation:{consultation_content_ref}` when selected.

Duplicate canonical refs are forbidden. `covered_fact_ids` is the first-seen ordered
union of record `fact_ids`; current S35 therefore equals selected commercial fact IDs.
Selected follow-ups and CTA are copied unchanged but are not factual scope records:
content follow-ups already originate from the selected content source, and price
follow-ups from selected offers.

One public `TargetScopedResponseEvidenceError(ValueError)` has `.code`, `.value`, and
exact message `f"{code}: {value!r}"`. Validation precedence:

1. exact S34 bound-package type → `scoped_evidence_package_invalid`;
2. `isinstance(md_root, Path)`, safely resolved existing directory →
   `scoped_evidence_md_root_invalid`; every selected MD ref must resolve inside it;
3. spec/package/plan identity mismatch or duplicate/missing selected identity →
   `scoped_evidence_package_inconsistent`;
4. any required component listed by the plan as unfulfilled →
   `scoped_evidence_component_unfulfilled`;
5. unsafe/unreadable/missing or invalid frontmatter topic/source →
   `scoped_evidence_source_invalid`;
6. first record intersecting forbidden topics → `scoped_evidence_topic_forbidden`;
7. first record with no allowed-topic intersection →
   `scoped_evidence_topic_not_allowed`;
8. missing required fact IDs → `scoped_evidence_required_fact_missing`.

Errors carry the smallest deterministic identifying value documented by tests. Downstream
objects are not mutated. No exception is converted into empty evidence or whole-base
fallback.

## Explicit safety boundary

S35 is the first closed evidence identity view suitable for the future Composer contract,
but it remains offline and unwired. It does not materialize MD text, render prices or
doctor prose, evaluate generated language, or authorize product use. Composer and
Verifier remain separate later checkpoints.

## Boundaries / allowlist

No TurnFrame/A9, patient scope, live/LLM, client data edits, old RAG/runtime/UI/session,
Composer/Verifier, authority, or full-suite run. Do not change S27–S34 contracts or tests.

- `TASK.md`
- `core/target_scoped_response_evidence.py`
- `tests/test_target_scoped_response_evidence.py`
- `tests/test_demo_target_scoped_response_evidence.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- exact frozen shapes/signature/error surface and precedence;
- closed output contains only plan-selected S34 identities;
- raw candidate offer/doctor/fact/CTA identities cannot leak;
- allowed service topic succeeds; forbidden or unrelated topic fails closed;
- an external KB source uses its own MD topic; service-linked external doctor is checked;
- selected commercial fact covers an exact required fact; candidate-only and unknown facts
  fail;
- unfulfilled required component fails before source reads;
- unsafe/missing/bad-topic MD refs fail without fallback;
- an evidence-bearing `medical_handoff` uses the same scope checks, preserves its exact
  spec/mode without downgrade, and fails on a forbidden doctor or service topic; this
  does not claim prose-level no-diagnosis verification;
- real demo All-on-4 content/price/doctors, one selected marketing fact, consultation,
  follow-ups and CTA; no client writes;
- import firewall, no skip/xfail/live.

Run only S35 target/demo plus S34 and S31 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern scoped response evidence S35` only to stage-a.
3. Implement only the allowlist and run minimal tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: enforce scoped response evidence S35`; final clean/synced.

Next checkpoint after S35: minimal Composer contract over this closed identity view; no
runtime wiring before a separate Verifier checkpoint.
