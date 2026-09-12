# PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT — FINAL_LOCAL_EVIDENCE_PACKAGE_OFFLINE_EVAL / PERF-7C

**Baseline:** `codex/stage-a` @ `75ce5f9` (PERF-7B implementation complete). Corrected at
`codex/stage-a` @ `596a4b3` (the original, incorrect `PERF7C_OFFLINE_PACKAGE_EVAL_PASS` commit).
**NO COMPOSER / NO VERIFIER / NO BOUNDARY / NO PLANNER / NO INGRESS / NO RUNTIME WIRING / NO WIDGET
/ NO SERVER / NO LIVE / NO LLM / NO PROVIDER / NO NETWORK / NO EMBEDDINGS / NO FTS5 /
NO FEATURE FLAGS / NO CONTEXT_GROUPS / NO ANSWER CACHE / NO TOKEN STREAMING /
NO CLIENTS/\*\* CHANGE.**

## CORRECTION NOTICE — supersedes the original `PERF7C_OFFLINE_PACKAGE_EVAL_PASS` verdict

**This document has been corrected. The original PASS verdict was wrong and is withdrawn.**

The first version of this evaluation (commit `596a4b3`) contained a **circular-evaluation defect**:
for 10 scenarios, the expected "correct" lexical target document was set to whatever
`search_target_lexical_paragraph_index` actually returned, rather than to what a question's real
meaning and canonical demo-pack authority independently require. That let the eval grade the
algorithm against its own output — a topically irrelevant confident match (e.g. a question about
reviewing a treatment plan from another clinic resolving to `clinic__info__technology.md`, a page
about 3D/AI diagnostic technology) was recorded as the "expected" answer and therefore scored as a
pass. This is exactly the mistake a source/package evaluation exists to catch, and it was caught
only after independent review, not by this evaluation's own original design.

**Verdict: `PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND`.** `critical_false_narrow_count = 10` (previously
misreported as `0`). All ten are relevance defects in the **evaluation's own original
expectations**, not in `core/target_evidence_package_builder.py` or
`core/target_lexical_paragraph_index.py` — neither file was touched by this correction, per the
owner's explicit instruction. **No speedup exists yet anywhere** — this remains true, and remains
the least important fact about this document; the important fact is that PERF-7C did not actually
pass and must not be represented as having passed.

## 0. Scope and method (unchanged)

This is a source/package evaluation, not an answer-quality evaluation. No Composer or Verifier is
called anywhere in this milestone — there is no generated text to grade at all, only whether
`build_target_evidence_package` (PERF-7B, unmodified by this correction) selects the right MD refs
and structured IDs, correctly refuses to guess when uncertain, and correctly isolates session
projection.

118 synthetic, purpose-authored scenarios across the 18 required classes were run once through the
real `build_target_evidence_package`, against the real demo pack's lexical index
(`core/target_lexical_paragraph_index.py`, unmodified) and cached FullContext
(`core/target_cached_full_context.py`, unmodified), then run a second, independent time to prove
determinism. `clients/demo/**` was never written to, before or after this correction.

## 1. Governance correction (restated from TASK.md/seam audit — unaffected by this correction)

Synthetic eval question fixtures may be committed (the matrix's `synthetic_query` field) — this is a
test fixture the same way every other eval matrix already committed in this repository holds its
own `question`/`case` text. What remains forbidden, unchanged: real user data, a *generated*
Composer/Verifier answer (none exists — no Composer/Verifier call happens anywhere in PERF-7C), a
session id, PII, or a contact value. The result artifact
(`docs/evidence/performance/perf7c_local_evidence_package_eval_result.json`) holds neither the
matrix's query text nor any contact display value — verified directly (§ 9).

## 2. Matrix correction #1 (arithmetic, disclosed — unaffected by this correction)

The PERF-7 Phase 1 seam audit's own per-class table claimed its 18 counts summed to "~118" / "= 118"
(`10+8+8+6+4+4+6+6+6+8+6+8+8+8+8+8+6+8`). Recomputing that exact expression gives **126, not 118** —
a genuine arithmetic error in that Phase 1 document, found while freezing this matrix, not hidden.
The frozen matrix uses corrected per-class counts that actually sum to 118. Both the seam audit and
TASK.md carry a note recording this correction; the Phase 1 table itself is left as historical
record, not rewritten.

## 3. Matrix correction #2 — the circular-evaluation defect (this document's main subject)

### 3.1 What went wrong

For 10 scenarios spanning 3 classes, the original matrix set `lexical_target_options` to the
document `search_target_lexical_paragraph_index` actually returned for that exact query, discovered
by running the search **before** freezing the matrix — described at the time as "verification," but
in these 10 cases the "verification" produced a topically wrong document, and that wrong document
was accepted as the expectation anyway because it was a *unique, confident* top score. A unique
confident score proves the ranking function had no tie to resolve — it says nothing about whether
the returned document actually answers the question. Conflating the two is exactly the circularity
this correction fixes.

### 3.2 The 10 affected scenarios, corrected

Independent relevance was re-derived from **question meaning and canonical demo-pack authority
only** — never from search output. `allowed_retrieval_md_refs` names the document(s) a real, correct
answer could legitimately draw on for that exact frozen query; an empty list means no document in
the corpus is genuinely relevant, so the only acceptable outcome is `fullcontext_fallback`. Query
wording was **not** changed anywhere in this correction, per the owner's explicit instruction.

| Scenario | Class | Query (meaning) | Document the Builder actually, confidently selected | Why it is irrelevant | Independently-derived allowed target(s) |
|---|---|---|---|---|---|
| `s051` | treatment_plan_other_clinic | "another clinic gave me a plan, want to check it here" | `clinic__info__technology.md` | That page is about 3D/AI diagnostic technology, not plan review | `clinic__info__consultation.md` |
| `s053` | treatment_plan_other_clinic | "want a second opinion on a plan from another doctor" | `orthodontics__service__aligners.md` | An aligners service page has nothing to do with second opinions | `clinic__info__consultation.md` |
| `s054` | treatment_plan_other_clinic | "got scans elsewhere, worth re-checking the plan?" | `clinic__info__technology.md` | Same as `s051` | `clinic__info__consultation.md`, `diagnostics__service__tomography.md` |
| `s055` | treatment_plan_other_clinic | "I'll bring documents from another clinic, please review the plan" | `clinic__info__technology.md` | Same as `s051` | `clinic__info__consultation.md` |
| `s056` | treatment_plan_other_clinic | "is a consultation on someone else's plan possible here?" | `orthodontics__service__aligners.md` | Query literally says "консультация" (consultation); aligners page is unrelated | `clinic__info__consultation.md` |
| `s083` | cross_topic | "need an orthodontist AND a dentist consultation for different questions at once" | `orthodontics__service__aligners.md` | Covers only one of the two specialties the question asks about; deliberately cross-topic by design | none — `fullcontext_fallback` only |
| `s084` | cross_topic | "what's the difference between therapy and surgery at your clinic" | `prosthetics__service__zirconia_crowns.md` | Not one of the 5 authored comparison docs; zirconia crowns page does not address this distinction | none — `fullcontext_fallback` only |
| `s099` | unknown_wording | "alternative methods, avoiding usual terminology" (deliberately vague) | `implantation__service__all_on_4.md` | One specific implantation service is not "alternative/unconventional" by construction of the question | none — `fullcontext_fallback` only |
| `s100` | unknown_wording | "non-standard approach, no surgery at all" (deliberately vague) | `comparison__implant_vs_bridge.md` | Vague-by-design query; treating any one comparison doc as "the" answer over-interprets it | none — `fullcontext_fallback` only |
| `s101` | unknown_wording | "a new method you may not advertise yet" (deliberately vague) | `implantation__service__temporary_teeth.md` | No connection between "undisclosed new method" and temporary-teeth content | none — `fullcontext_fallback` only |

For the `treatment_plan_other_clinic` scenarios, `clinic__info__consultation.md` is the genuinely
relevant canonical document: its own authored frontmatter aliases include **"план лечения"** and
**"план лечения если не буду лечиться"**, and its body states "На приёме врач составит понятный
план лечения" (at the appointment the doctor will draw up a clear treatment plan) — this is exactly
the clinic's own answer to "I have an external plan, can you help." Verified, read-only, for
transparency (this does **not** change any expectation, since the frozen queries are unchanged):
`clinic__info__consultation.md` does appear in the real search results for all five queries, but its
score always ranks below the coincidentally-matching irrelevant document —

| Scenario | `clinic__info__consultation.md` score (exact matches) | Actual top score (wrong document) |
|---|---:|---:|
| `s051` | 4 (2 exact) | 7 |
| `s053` | 4 (2 exact) | 8 |
| `s054` | not in top 15 | 7 |
| `s055` | 4 (2 exact) | 5 |
| `s056` | 6 (3 exact) | 8 |

For the `cross_topic` and `unknown_wording` scenarios, no allowed target exists at all — both
classes exist specifically to test that the Builder honestly falls back on genuinely multi-topic or
deliberately novel questions; by their own design intent, no single document should ever be treated
as "the" correct answer for them.

### 3.3 The scoring-logic defect (fixed alongside the matrix)

Independently of the matrix's wrong expectations, `evals/v5/run_perf7c_local_evidence_package_eval.py`'s
`_classify` function had a second, compounding defect: when a widened package's target fell outside
the expected `lexical_target_options`, it was recorded in a soft, **non-critical**
`unexpected_scoped_target` bucket instead of `critical_false_narrow`. Even with corrected
expectations, this bucket would have hidden the same 10 defects behind a label that does not fail
the binding PASS criteria. This has been fixed: any widened package whose target is not in the
independently-derived allowed set is now **always** `critical_false_narrow`
(`critical_false_narrow_irrelevant_lexical_target`), regardless of `completeness_status`, regardless
of a unique top score, and regardless of whether the target happened to match a previous (now
corrected) expectation.

## 4. Matrix (118 scenarios, 18 classes, corrected)

`evals/v5/perf7c_local_evidence_package_eval_matrix.json`.

| # | Class | Count | Focus |
|---|---|---:|---|
| 1 | `exact_service` | 10 | exact `content_ref` from `service_catalog.json` → complete |
| 2 | `broad_service` | 6 | no exact service, broad wording → verified ambiguous tie → fallback |
| 3 | `price` | 8 | exact offer id(s) from pricebook offers → complete, price-only never needs content |
| 4 | `doctor` | 6 | exact canonical `doctors__doctor__{name}` id from `doctor_catalog.json` → complete |
| 5 | `contacts` | 4 | structured `policy_sections` field name only, never the value → complete |
| 6 | `parking` | 4 | same structured-policy path, parking field combinations → complete |
| 7 | `sterilization_safety` | 6 | 2 confident / 2 ambiguous / 2 zero-hit (morphology checks #1/#4) |
| 8 | `own_fresh_ct` | 6 | 3 exact (tomography content) + 3 lexical (2 confident, 1 ambiguous) |
| 9 | `treatment_plan_other_clinic` | 6 | **corrected**: 5 relevance-gated (all 5 currently fail as critical false-narrow, § 3) + 1 ambiguous |
| 10 | `pain_fear` | 8 | exact `external_kb`/fact evidence already present → complete, never fallback |
| 11 | `marketing_concern` | 6 | exact commercial-fact evidence from real `pricebook/facts.json` → complete |
| 12 | `comparison` | 8 | 4 confident comparison-typed / 3 ambiguous / 1 confident-but-wrong-doc-type |
| 13 | `cross_topic` | 6 | **corrected**: 4 ambiguous + 2 relevance-gated to empty (both currently fail as critical false-narrow, § 3) |
| 14 | `explicit_followup_price` | 8 | exact offer evidence + validated session ref coexist, no contamination |
| 15 | `new_independent_service` | 6 | 4 clean no-session-carry + 2 caller-contract-violation (must raise) |
| 16 | `unknown_wording` | 6 | **corrected**: 3 relevance-gated to empty (all 3 currently fail as critical false-narrow, § 3) + 3 ambiguous fallback |
| 17 | `no_matching_fact` | 6 | fabricated fact id, structurally absent from `facts.json` → structural fallback |
| 18 | `medically_risky_personal` | 8 | 4 confident (2 `answer` + 2 `medical_handoff`, mode-independence proof) / 4 ambiguous |

## 5. Required checks (per the brief's "ОБЯЗАТЕЛЬНЫЕ ПРОВЕРКИ") — unaffected by this correction

1. **"≥1 exact token, no tie" rule, single common tokens** (`лечение`/`врач`/`можно`/`зуб`/`клиника`):
   verified directly — each of these five bare common words ties across 4–8 distinct documents at
   the top score, forcing `lexical_ambiguous_top_match` every time.
2. **Russian morphology** (стерилизация/стерилизационное; имплант/имплантация;
   приживление/прижился; обеззараживание/стерилизация): all four pairs verified. `стерилизация`
   (bare) and `обеззараживание` both produce **zero hits** (`s031`, `s032`). No alias, no stemmer, no
   special-case rule was added anywhere to "fix" these misses.
3. **Fully paraphrased, zero-shared-token questions honestly fall back**: `s048` (`hits: 0`).
4. **Diabetes-personal-risk question**: confident, *topically correct* match to
   `implantation__info__contraindications.md` only where lexical signal genuinely supported it
   (`s113`–`s116`); otherwise honest ambiguous fallback (`s117`–`s120`).
5. **Parking/contacts go through structured policy, never require an MD lexical hit**: classes 5/6,
   zero lexical search calls.
6. **Price goes through exact offer ID, never MD price text**: class 3, structured-offer-JSON-only.
7. **Doctors via exact doctor ID**: class 4, real canonical `doctors__doctor__{name}` ids.
8. **New independent question after prior focus never inherits stale session**: class 15.
9. **Explicit follow-up gets only the validated session ref**: class 14.
10. **Cross-topic/ambiguous questions fall back conservatively**: class 13 — **as of this
    correction, this check is now honestly documented as failing for 2/6 scenarios** (§ 3), not
    passing as originally (wrongly) reported.

## 6. Binding PASS criteria — **NOT met**

| Criterion | Result |
|---|---:|
| `critical_false_narrow_count == 0` | **10** — **FAILS** |
| `session_contamination_count == 0` | 0 |
| missing exact offer/fact/doctor/policy IDs | 0 (`structured_id_mismatch_count = 0`) |
| `builder_exception_count == 0` | 0 |
| all exact structured scenarios recall exact required IDs | still true (unaffected classes) |
| all scenarios expected as fallback actually fell back | still true (unaffected classes) |
| no query/answer/SID/PII in result artifact | still true (§ 9) |
| deterministic rerun → identical categorical/source-ID result | still true (§ 9), two independent runs after correction |
| `clients/**` unchanged | still true (scoped `git diff`) |
| no provider calls | still true (AST-checked) |

**Binding PASS is not achieved.** The verdict is `PERF7C_LEXICAL_RELEVANCE_DEFECT_FOUND`, a distinct,
more specific verdict than the generic `PERF7C_CRITICAL_FALSE_NARROW_FOUND`, since every one of the
10 critical failures is specifically an irrelevant-lexical-target defect in the eval's own original
expectations (already corrected) and the run confirming this defect — not a session-contamination,
missing-ID, or exception defect, and not (per the owner's explicit instruction) a defect attributed
to `core/target_evidence_package_builder.py` itself, which was not touched.

## 7. Matrix corrections found and fixed (disclosed, not silently patched)

1. **Arithmetic** (§ 2): Phase 1 per-class counts summed to 126, not the claimed 118 — corrected
   allocation used.
2. **Doctor ID authoring bug**: the first draft of the `doctor` class used bare surname-style ids
   instead of the real canonical `doctors__doctor__{name}` ids. Caught by a dedicated contract test
   before the (still-wrong, at that point) PASS was first declared.
3. **Circular-evaluation defect** (§ 3, this correction's main subject): 10 scenarios across 3
   classes had their expectations set from search output instead of from question meaning and
   canonical authority, compounded by a scoring-logic bug that classified the resulting irrelevant
   matches as a soft, non-critical bucket instead of `critical_false_narrow`. Both the matrix
   expectations and the scoring logic have been corrected. **This is the correction this document
   now primarily records** — found via independent review after the original PASS was declared, not
   by this evaluation's own original design, which is itself worth stating plainly.

## 8. Metrics (real, this run, after correction)

```
total_scenarios: 118
scoped_complete_count: 61      scoped_widened_count: 22      scoped_count: 83 (70.3%)
fullcontext_fallback_count: 33 (28.0%)
critical_false_narrow_count: 10   (all 10: critical_false_narrow_irrelevant_lexical_target)
safe_over_fallback_count: 0
session_contamination_count: 0
structured_id_mismatch_count: 0
builder_exception_count: 0
lexical_hit_count: 22   lexical_ambiguous_count: 24   lexical_miss_count: 3
package_tokens p50: 616   package_tokens p95: 26,995 (fallback scenarios carry the full corpus)
full_context_estimated_tokens: 26,995 (recomputed live from the current corpus, never hardcoded)
```

`scoped_rate`/`fallback_rate`/`lexical_hit_count` are **descriptive** metrics (what fraction of
scenarios the Builder attempted to narrow) and are numerically unchanged by this correction, since
they count *what happened*, not *whether it was correct* — 10 of the 22 "widened" packages are, per
this correction, now known to be irrelevant, which is precisely why `critical_false_narrow_count`
(a *correctness* metric) is the number that governs PASS/FAIL, not `scoped_rate`. Of the 22
`insufficient_widened` outcomes, 12 are genuinely correct (`match_expected_widened`) and 10 are the
irrelevant-target defect documented in § 3.

**Estimated token reduction is not reported as a headline figure in this corrected document** — it
was computed against the (partially wrong) scoped-package set in the original version; recomputing
it honestly would require deciding what to do with the 10 defective packages (excluding them,
counting them as failures, or treating their size as moot since they should not have scoped at all),
which is a judgment call belonging to whoever authorizes any future correction of the underlying
lexical relevance mechanism, not to this evaluation-correction pass. The raw `package_tokens_p50`/
`p95` figures above are reported as-is, unfiltered, for transparency.

Deterministic rerun (after this correction): two independent `run_eval("demo", ...)` calls produce
byte-identical `verdict`/`actual_completeness_status`/`actual_fallback_reason`/
`actual_package_fingerprint` for every one of the 118 scenarios (only `timing_ms` differs, excluded
from the comparison by design).

## 9. Test results

- `tests/test_final_local_evidence_package_eval_contract.py` — updated and passing (matrix shape,
  governance discipline, canonical-ID cross-check, runner determinism/isolation, result
  sanitization, the corrected binding-verdict assertion, a 5-scenario real-
  `materialize_target_composer_request` integration subset, and new relevance-defect-specific
  assertions).
- `tests/test_final_local_evidence_package_builder_implementation.py`,
  `tests/test_final_local_lexical_paragraph_index_implementation.py` (including its own corrected
  isolation test, updated for PERF-7B's legitimate architectural dependency — see that file),
  `tests/test_final_local_evidence_package_builder_foundation_governance.py` — unaffected by the
  matrix/runner correction, re-run to prove PERF-7A/7B behavior is unchanged.

## 10. What PERF-7C did not do (explicitly out of scope, per both the original and correction briefs)

No Composer, Verifier, Boundary, Planner, or Ingress call anywhere. No runtime wiring. No
embeddings, no FTS5, no feature flag, no `context_groups.json`, no answer cache, no token streaming.
`clients/demo/**` byte-identical throughout (scoped `git diff` proof), before and after this
correction. **`core/target_evidence_package_builder.py` and `core/target_lexical_paragraph_index.py`
were not modified by this correction** — the defect found and fixed here was in the evaluation's own
expectations and scoring logic, not in either product module. **No speedup exists yet anywhere in
this repository from PERF-6, PERF-7A, PERF-7B, or PERF-7C.**

## 11. STOP conditions

**STOP before any Builder or lexical-index correction** — none is authorized by this document. The
10 scenarios found here demonstrate a real limitation of plain token-overlap lexical matching
(it can confidently rank a topically unrelated document above a genuinely relevant one that scores
lower), but deciding *how* to address that — a stricter acceptance bar, a different ranking
signal, embeddings, or accepting the limitation and routing these query shapes to FullContext by
some other means — is a **separate, future, owner-approved correction milestone**, not decided or
authorized here. **STOP before PERF-8** (Scoped Composer behind a local flag). **STOP before any
counterfactual FullContext-vs-Scoped-Composer evaluation.** **STOP before any embeddings work.**
**STOP before any LIVE/LLM GO of any kind** — none occurred in this correction.
