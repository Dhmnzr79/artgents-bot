# FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION (PERF-7) — Phase 1 governance + seam audit

**Baseline:** `codex/stage-a` @ `2d0769c` (`FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW` / PERF-6 Phase 2
shadow implementation complete).
**NO PRODUCT IMPLEMENTATION / NO CLIENT-PACK CHANGE / NO LIVE / NO PROVIDER / NO NETWORK /
NO FTS TABLE / NO SQLITE INDEX / NO EMBEDDINGS / NO VECTOR DATABASE / NO EVIDENCEPACKAGEBUILDER
PRODUCT MODULE / NO RUNTIME FLAG / NO MIGRATION / NO CONTEXT_GROUPS.JSON**

This is a design document. Nothing under `clients/demo/**`, `core/`, `contracts/`, or `app.py` is
changed by this milestone. It designs a local `EvidencePackageBuilder` foundation — a lexical
paragraph index, a typed Evidence Package contract, completeness/fallback rules, and an offline
evaluation plan — for a **separately owner-approved** future implementation series
(PERF-7A onward, § 14). PERF-6 remains a shadow-only, non-authoritative measurement mechanism; this
milestone does not extend its `service_exact → topic → context_group → full` ladder and does not
create `context_groups.json`.

## 0. Baseline and owner decision restated

Per the owner's brief for this milestone: PERF-6's ladder is not the target architecture. The
target shape is simpler — exact/structured paths stay on the existing typed `TurnFrame` →
deterministic policy → Composer chain unchanged; a new single `EvidencePackageBuilder` assembles a
minimally-sufficient evidence package from **independent sources** (existing `evidence_blocks`,
exact content refs, structured offers/facts/doctors/contacts, a relevant projection of session
state, locally-found MD paragraphs/sections, and a FullContext fallback when uncertain); lexical
retrieval is one input among these, never the sole routing mechanism. This document is Phase 1
governance for that shape: architecture map, PERF-6 debt verdicts, integration seam, lexical-index
comparison with a real local capability proof, paragraph-index design, the typed Evidence Package
contract, completeness/fallback/session rules, an offline evaluation design, and the future
milestone sequence. **No code from any of this is created in this commit.**

## 1. Current architecture map (producer → consumer, extended from PERF-6 §1)

| # | Layer | File(s) | Relevance to a future Builder |
|---|---|---|---|
| 1 | `TurnFrame` → `TargetResponseSpec` | `core/turn_frame_from_raw.py`, `core/target_response_policy.py::build_target_response_spec` | Unchanged entry point. `TargetResponseSpec` (`service_id`, `allowed_topics`, `required_fact_ids`, `required_components`, `response_stage`, …) is already the single arbitrated "what does this turn need" contract — a future Builder reads it, never re-derives it, exactly as `resolve_target_context_scope` already does. |
| 2 | `TargetComposerRequest.evidence_blocks` | `core/target_composer_request.py::materialize_target_composer_request` | **Already** the closed, validated, exact-source-checked evidence closure for the exact-service/price/generic-content paths (S22–S36 machinery, unchanged by PERF-6 or this design). A Builder's "existing evidence_blocks" input (brief item, first bullet) is this — read-only, no new closure logic, mirroring PERF-6 §1 item 8's finding verbatim. |
| 3 | Cached FullContext corpus | `core/target_cached_full_context.py::build_target_cached_full_context` | 55 MD docs, 107,980 chars / 26,995 tokens (chars/4 estimate), sha256 `758a64eb…` (unchanged since the PERF-6/dedup audits — client pack untouched, see § "PRE-CODE" governance test). Real per-file sizes: min 479, max 3,434, mean 1,863, median 2,034 chars (computed directly from the live `clients/demo/md/*.md` tree by this audit, § 5). This is the FullContext fallback target (§ 11) and the paragraph-index source corpus (§ 8). |
| 4 | MD frontmatter | every `clients/demo/md/*.md` | **Already carries `doc_id`, `doc_type`, `topic`, `subtopic`** on every one of the 55 files (confirmed by direct grep of the live pack, not assumed) — `doc_type ∈ {info, service, faq, comparison, doctor, contacts}` observed on the current pack. This directly satisfies brief item D's "document type if already derivable without new required fields": **no new frontmatter field is needed for `doc_type`** — it already exists and is already authored on every document. `topic` is the same field `core/topic_taxonomy.py::load_client_topic_taxonomy` and PERF-6's `topic` tier already consume. |
| 5 | Section/anchor extraction | `core/target_composer_request.py::_section`/`_EXPLICIT_HEADING`/`_FENCE` | **Already** a working, fence-aware, H2/H3-anchor-scoped section extractor (`## Heading {#anchor}` → the ProseText between it and the next heading of equal-or-higher level, code fences respected). This is the exact precedent for the paragraph-index's section-splitting rule (§ 8) — no new parser is proposed; the same regex/fence-tracking approach is reused conceptually, not reinvented. |
| 6 | Composer/Verifier static prefix | `core/target_composer_executor.py`, `core/target_response_verifier.py` | Unchanged. Both still receive the full 107,980-char corpus unconditionally on every turn (PERF-6 proved this by test, § 2 item 7 below). A Builder does not change this in Phase 1 — no real switch is authorized here either. |
| 7 | PERF-6 resolver/shadow | `core/target_context_scope_resolver.py`, `core/target_context_scope_shadow.py`, hook in `core/target_policy_bound_verified_response_pipeline.py` | Existing shadow-only measurement, unmodified. § 2 audits its debt. Not extended, not reused as the Builder's mechanism — the owner's brief explicitly rejects extending the `service_exact/topic/context_group/full` ladder further. |
| 8 | Client pack validator | `scripts/validate_client_pack.py` | Unchanged. A future paragraph-index generation step (PERF-7A) would be a **read-derived** artifact from the same MD tree this validator already checks — not a new required client-pack file, not validated by this script in Phase 1 (no such artifact exists yet). |

## 2. PERF-6 technical debt — verdicts

Per the brief's explicit list, each item is graded **PROVEN / NOT PROVEN / ALREADY FIXED /
ACCEPTABLE TEMPORARY DEBT** against the real code at this baseline (`2d0769c`), with exact
file/line evidence. This is a critical audit of shipped PERF-6 code, not a re-litigation of its
governance — no PERF-6 file is changed by this commit.

### 1. False-positive `shadow_hit` when source identity is missing — **PROVEN**

`core/target_context_scope_shadow.py::compare_target_context_scope_shadow` (lines 68–74):

```python
validated_used: set[str] = set(verified.used_content_refs)
if verified.primary_content_ref:
    validated_used.add(verified.primary_content_ref)
missing: list[str] = []
if not validated_used.issubset(set(decision.included_content_refs)):
    missing.append("content")
```

An empty set is trivially a subset of any set. When `verified.used_content_refs == ()` and
`verified.primary_content_ref is None` — a real, reachable state: the Composer's self-reported
`source_identity` (`core/target_composer_output.py::parse_composer_backend_output`) is optional and
soft-validated; for the generic FullContext content-only path
(`core/target_response_verifier.py::_resolve_validated_source_identity`, `exact_service_authority=
False` branch, lines 655–671) an empty/`None` self-report falls through to `package_used`/
`package_primary`, which for `is_fullcontext_service_optional_spec` turns can themselves be empty —
the "content" miss check is silently skipped, and `shadow_hit` can be recorded `True` even though
the real answer may have drawn on MD content that the candidate closure never included and no
mechanism ever checked. This is a real gap in what `shadow_hit` can honestly claim, not a
hypothetical: it happens whenever the Composer answers from `CACHED_FULL_CONTEXT` general knowledge
without a resolvable self-reported ref, which the system prompt (`TARGET_COMPOSER_SYSTEM_POLICY`
rule 11) permits (`"primary_content_ref":null` is a valid output).

### 2. "Any offer/doctor present" instead of the exact required source — **PROVEN** (topic/context_group tiers only; not a defect at `service_exact`)

`core/target_context_scope_shadow.py` lines 80–84 and `core/target_context_scope_resolver.py::
_has_required_components` (lines 161–169) both check only `bool(closure.offer_ids)` /
`bool(closure.doctor_ids)` for `required_components=("price"|"doctors",...)` — never that the
*specific* offer/doctor id the real turn actually needed is among them. At `service_exact`, this is
provably harmless by construction: that tier's closure is read directly from
`TargetComposerRequest.evidence_blocks` (§ 1 item 2), which S22–S36 already narrows to exactly the
turn's required offers/doctors — "any present" and "the correct one present" are the same set by
construction there. At `topic`/`context_group`, the closure is instead built independently by
scanning **every** active offer whose `service_id` falls in the matched services
(`core/target_context_scope_resolver.py::_try_topic`, lines 303–307) — a topic with multiple
services and multiple price-bearing offers can satisfy `bool(closure.offer_ids)` with an offer that
is not the one the real turn's spec actually required, and neither the resolver's own completeness
gate nor the shadow's post-hoc comparison would ever catch that. Confirmed as a real, reachable gap
for those two tiers specifically — not for `service_exact`.

### 3. Incomplete token estimate — only MD counted — **PROVEN**

`core/target_context_scope_resolver.py::_closure_size` (lines 150–158) sums only
`len(path.read_text(...))` over `closure.content_refs` — offers, facts, doctors, and policy
sections (all real per-turn `PRIMARY_EVIDENCE_JSON` bytes the actual Composer/Verifier receive, see
`core/target_composer_executor.py::_invocation`, lines 386–396) are never added to
`estimated_chars`/`estimated_tokens`. This means every `estimated_reduction_tokens` figure PERF-6
ever reports (including the real numbers in TASK.md's PERF-6 completion record, e.g. "484 tokens"
for `classic`) **understates** the real per-turn package cost and therefore **overstates** the
apparent savings percentage — the missing bytes are real, non-MD, structured evidence JSON that a
real narrower Composer call would still have to pay for.

### 4. `context_group` unreachable on demo — **ACCEPTABLE TEMPORARY DEBT** (already honestly disclosed, not a hidden defect)

Confirmed still true at this baseline: `context_groups` is always `None` at the one real call site
in `core/target_policy_bound_verified_response_pipeline.py`, and no
`clients/demo/target_response/context_groups.json` or
`clients/_template/target_response/context_groups.json` exists (re-verified by this audit's own
filesystem check, § "PRE-CODE"). This was disclosed as an honest gap by PERF-6's own seam audit §12
and TASK.md, gated behind a separate, still-unauthorized future milestone. Not a bug to fix here —
correctly labelled debt, not silently hidden.

### 5. Non-deterministic `context_group` selection — **PROVEN**

`core/target_context_scope_resolver.py::_try_context_group` (lines 344–352):

```python
candidate_topics: set[str] = set(spec.allowed_topics)
matched_group: TargetContextGroup | None = None
for topic in candidate_topics:
    group = context_groups.group_for_topic(topic)
    if group is not None:
        matched_group = group
        break
```

Iterating a Python `set[str]` is ordered only by object hash, and `str` hashing is randomized
per-process by default (`PYTHONHASHSEED` unset ⇒ randomized in CPython 3). When `spec.allowed_topics`
has two or more members that each resolve to a *different* authored group, `matched_group` can
differ across process restarts for the identical input — a genuine reproducibility defect in a
function whose own docstring promises "pure, offline, deterministic." Unreachable on the real demo
pack today (item 4), so it has caused no observed harm, but it is a real bug in code that already
exists and is already tested only against synthetic single-topic-group fixtures
(`core/target_context_scope_resolver.py` docstring, lines 16–18) that happen not to exercise this
path. Must be fixed (e.g. `sorted(spec.allowed_topics)` before iterating) before any
`context_groups.json` milestone ships multi-group-per-request test coverage.

### 6. Source coverage does not prove answer equivalence — **PROVEN** (structural limitation, not a bug)

By design, `compare_target_context_scope_shadow` only ever checks *set membership* of sources
against the candidate closure — it never re-runs the Composer against the narrower candidate and
never compares generated text. This is not a coding error; it is the explicit, disclosed shape of a
shadow measurement (PERF-6 seam audit §16: "shadow measurement … must prove [before any real
switch]"). It is restated here as a confirmed structural fact because it is exactly the gap this
milestone's offline evaluation design (§ 13) must close with a **separate**, later,
owner/LIVE-gated "counterfactual Composer evaluation" mode — source-set coverage is a necessary,
not sufficient, signal for package sufficiency.

### 7. Unconditional per-turn shadow overhead — **PROVEN**

`core/target_policy_bound_verified_response_pipeline.py::
run_target_offline_policy_bound_verified_response_pipeline_with_selection` calls
`_resolve_shadow_decision_safely(...)` (line 265) **unconditionally, on every real turn**, with no
flag gate anywhere in this call path (unlike PERF-4's `PLANNER_SPECULATION_CAPACITY=0`-gated
speculative hook, or PERF-3's two-gate CLI-only pattern). This re-materializes a second
`TargetComposerRequest` (re-running `build_target_scoped_response_evidence` and re-reading MD
section bodies from disk) and runs the full resolver, purely for a value that is discarded from the
real request — real, measured (`SHADOW_TIMING_MARK = "scoped_context_shadow_ms"`), unconditional CPU
and disk-I/O cost on every local turn today. Accepted at PERF-6 Phase 2 time as the cost of
proving the design without a flag; flagged here as a lesson for PERF-7 onward (§ 15): a future
Builder must not repeat this pattern by adding a second unconditional, ungated pass of its own on
top of the one PERF-6 already added.

## 3. Integration seam — request materialization count

**Today (this baseline), the real request path materializes `TargetComposerRequest` twice per
turn**, not three times: once, real, inside `core/target_verified_response_pipeline.py::
run_target_offline_verified_response_pipeline` (line 50) — that same object is already threaded into
**both** `execute_target_composer(request, ...)` (line 61) **and**
`verify_target_composed_response(request, ...)` (line 72), so Composer and Verifier already share
one materialization; and once, redundant-by-design, inside PERF-6's
`_resolve_shadow_decision_safely` (`core/target_policy_bound_verified_response_pipeline.py`, line
169), which the PERF-6 completion record documents as a **deliberate, safe redundancy** forced by
the S39 straight-line protection (§ below).

**The "triple materialization" this milestone's brief warns against is a forward risk, not today's
state**: if a future `EvidencePackageBuilder` were bolted on using the same pattern PERF-6 used —
its own independent third `materialize_target_composer_request` call, alongside the existing real
one and the existing shadow one — the count would become 3. This section's job is to design against
that outcome.

**Why the real materialization cannot simply move up a level (checked, not assumed):**
`tests/test_target_verified_response_pipeline.py::
test_public_signature_and_function_is_exact_straight_line` pins, by AST assertion, **both** the
exact parameter list of `run_target_offline_verified_response_pipeline` (13 named parameters,
`bound_package`/`bundle`/… — no `request` parameter) **and** the exact ordered call sequence inside
it (`materialize_target_composer_request`, `execute_target_composer`,
`_used_content_refs_from_package`, `bool`, `verify_target_composed_response` — in that order, with
zero `If`/`Try`/`Raise`/`For`/`While`/`Match` nodes anywhere in the function body). Changing this
function's signature to *accept* an already-materialized `request` instead of building one itself
would require the exact same category of documented, owner-approved deviation PERF-6 Phase 2 needed
for the hook point — this document does not propose making that change without a **separate** future
owner GO, since it touches a second protected contract test, not just the first one PERF-6 already
touched.

**Recommended seam for PERF-7A/B (design only, not built here):** keep the real materialization
exactly where it is (inside the protected S39 function, byte-for-byte unchanged, as PERF-6 left
it). Move the **one** pre-existing redundant copy (today used only by PERF-6's shadow) to be shared:
call `materialize_target_composer_request` **once**, in
`core/target_policy_bound_verified_response_pipeline.py`, before the real pipeline call — exactly as
PERF-6 already does — and thread that **same** object into **all** of: (a) the future
`EvidencePackageBuilder` (read-only consumer of `.spec`/`.evidence_blocks`, exactly like
`resolve_target_context_scope` already is), (b) PERF-6's existing shadow resolver (unchanged), and
(c) any future counterfactual-Composer evaluation harness (§ 13, offline/test-only, never the real
request path). This keeps the real per-turn materialization count at exactly **2** (real + one
shared redundant copy) — never 3 — without touching the S39-protected function's signature or call
sequence at all. A later milestone may propose collapsing to a true single materialization by
extending the S39/S40 protected-signature deviation the same way PERF-6 documented for the hook
point, but that is explicitly **not** decided or authorized by this Phase 1 document — it is named
here only as the honest "why not now" seam analysis the brief asked for.

## 4. Lexical index comparison (Option A/B/C)

| Option | Description | Verdict |
|---|---|---|
| **A — in-memory Python token-overlap scan** | Normalize (NFKC, casefold, strip punctuation) paragraph/section text and query into token sets at process start (or lazily, cached); rank candidates by count of matching tokens (exact + prefix match on the query token, approximating stemming); pure Python, stdlib `re`/`unicodedata` only. | **Selected** (§ 7) — simplest option that is sufficient for 55–150 short documents; no new file format, no query-language injection surface (§ 6), no build step to keep in sync (recomputed from the same MD tree the corpus already reads). |
| B — SQLite FTS5, in-memory (`:memory:`) | Build a fresh `CREATE VIRTUAL TABLE ... USING fts5(...)` at process start from the same MD paragraphs, query via `MATCH`, rank via `bm25()`. Proven available and functional on this machine (§ 5). | **Not selected now** — real, working upgrade path if Option A's plain token-overlap ranking proves insufficient once PERF-7A is actually implemented and measured (e.g. genuine need for tf-idf-style weighting at a larger future corpus). Adds a SQL query-language surface that must be sanitized (§ 6) for no proven benefit yet at this corpus size. Rejected as the **first** choice specifically because it would be choosing a more sophisticated mechanism before Option A has been shown insufficient — the brief's explicit warning against choosing tech "because it's modern." |
| C — generated per-client SQLite FTS5 file, persisted to disk | Like B, but built once (e.g. at deploy/pack-validation time) and committed/generated as a versioned artifact per client, avoiding a rebuild-at-startup cost. | **Rejected for now** — introduces a new artifact type that must be kept in sync with `clients/{id}/md/**` (staleness risk, a new thing `scripts/validate_client_pack.py` would eventually need to check), for a rebuild cost (§ 5: milliseconds for 55 short docs) that does not justify the complexity at this corpus size. Revisit only if a future client pack grows into the hundreds-to-thousands of documents range where an in-memory rebuild-per-process becomes measurably expensive. |

## 5. FTS5 capability proof (real local probe, this machine, no network)

Run directly via `python -c "import sqlite3; ..."` against a throwaway `:memory:` database — no
client-pack data, no MD content, no product code imported:

```
sqlite3 version: 3.49.1
FTS5: available (CREATE VIRTUAL TABLE ... USING fts5(...) succeeds)
bm25(): available (SELECT ... , bm25(t) FROM t WHERE t MATCH ... succeeds)
tokenize='unicode61 remove_diacritics 2': available
tokenize='trigram': available
```

Russian-morphology probe (three short synthetic Russian sentences, `unicode61 remove_diacritics 2`
tokenizer, no client data):

```
'имплант'        -> []                                  (bare stem alone: no match — no stemming)
'импланты'       -> 1 row                                (exact token match)
'имплантация'    -> 2 rows                                (exact token match)
'импланта*'      -> 2 rows                                (prefix wildcard matches импланты/имплантация/имплантолог/импланта)
'стоимост*'      -> 1 row                                (prefix wildcard matches стоимость)
'зуб*'           -> 2 rows                                (prefix wildcard matches зубов/зуба)
'цена OR стоимост*' -> 2 rows                              (boolean OR + prefix combine)
```

Malformed-query probe (proves raw user text cannot be passed to `MATCH` unsanitized):

```
'имплант"'      -> OperationalError: unterminated string
'((('           -> OperationalError: fts5: syntax error near ""
'a b c AND'     -> OperationalError: fts5: syntax error near ""
'"unterminated' -> OperationalError: unterminated string
```

## 6. Russian-language limitations and query-safety finding

- **No stemming/lemmatization anywhere in stock FTS5.** `unicode61` (the built-in default-adjacent
  tokenizer) and `trigram` both split on Unicode word boundaries only — Russian morphology
  (импланты / имплантация / имплантолога / импланту, all sharing the root "имплант") is **not**
  unified automatically. The only stock mitigation is prefix-wildcard queries (`импланта*`), proven
  functional above, which recovers most same-root forms in practice for this domain's short,
  fact-dense MD but is not linguistically exact (it also matches unrelated same-prefix words).
  No morphological analyzer (`pymorphy2`/`snowball`-class stemmer) is proposed or installed by this
  milestone — out of scope per the brief's embeddings-deferral instruction, and not requested.
- **`MATCH` is a real query language with a real syntax-error surface**, proven above: an
  unescaped `"`, unbalanced parentheses, or a trailing boolean operator raises
  `sqlite3.OperationalError` — passing raw user message text into `MATCH` unsanitized is unsafe
  (crashes, not injection in the SQL-statement sense, since `?`-parameter binding is already used,
  but a real fail-closed hazard). Any future FTS5 adoption (Option B/C) would need to **tokenize the
  query with the same normalizer used for indexing and rebuild a safe `MATCH` expression from
  quoted, individually-validated tokens** (e.g. `'"имплант"* OR "цена"*'`), never forward the raw
  user string. This is exactly the safety question the brief asked to verify — verified, and it is
  a real cost of Option B/C that Option A (§ 4, pure Python token-overlap, no query language at all)
  avoids entirely by construction.
- **Implication for the paragraph index design (§ 8):** whichever option ships, the *indexing-side*
  normalization (casefold, NFKC, punctuation strip) must be applied identically to both documents
  and queries, and prefix-style matching (not exact-token-only) is required for acceptable Russian
  recall — this applies equally to Option A's token-overlap scorer and to a possible future Option B
  upgrade.

## 7. Selected lexical option

**Option A — in-memory Python token-overlap scan with prefix matching**, for the reasons in § 4/§ 6:
simplest option proven sufficient for a 55–150-short-document corpus, zero new query-language
surface to secure, zero new artifact/build step, deterministic and trivially unit-testable. Option B
(SQLite FTS5 in-memory) is the **documented, ready fallback** if PERF-7A's own implementation and
measurement (not this design) finds real recall gaps a token-overlap scorer cannot close — this is
an explicit, named escape hatch, not a silent door left open. Option C remains rejected until corpus
size changes the calculus (§ 4).

## 8. Paragraph index design (generated, not authored — no new required MD field)

**Source:** the same `clients/{id}/md/**` tree the cached FullContext corpus already reads
(`core/target_cached_full_context.py::_discover_markdown_files`) — no new directory, no new file
type.

**Splitting rule** (reuses the existing `core/target_composer_request.py::_section`/
`_EXPLICIT_HEADING`/`_FENCE` precedent conceptually — a new, simpler generation-time walker, not a
shared runtime import, since the paragraph index is an offline-generated artifact, not a per-turn
composer-request-time lookup):

1. Split each document at `##`/`###` headings (H2/H3) — same two levels
   `core/target_composer_request.py::_HEADING`/`_EXPLICIT_HEADING` already recognize. H1 (`#`, the
   document's own title, rare in this pack) is treated as the document's own header, not a
   sub-section boundary.
2. Within a heading's span, split further on blank-line-delimited paragraphs and Markdown list
   blocks (a contiguous run of `-`/`*`/numbered list lines is one indexable unit, not split
   per-bullet — a bullet list is usually one coherent micro-fact group in this pack, e.g. the "how
   to make implantation cheaper" list in `implantation__faq__cost.md`).
3. **Fence-aware**: code fences (`` ``` ``/`~~~`) are never split inside, mirroring
   `core/target_composer_request.py::_FENCE` exactly (this pack has none today, but the rule is
   inherited for correctness, not invented new).
4. **Minimum unit size:** 40 characters (below this, a fragment is merged into the next sibling
   unit within the same heading — mirrors the existing near-duplicate detector's own "minimum block
   length 40 chars" threshold from `FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT.md` § 3, so this
   design does not invent a third unrelated size constant).
5. **Maximum unit size:** none imposed beyond the natural heading/paragraph boundaries — given the
   real per-document size distribution measured directly from the live pack (§ 1: min 479, max
   3,434, median 2,034 chars per whole document), and that most documents have 1–4 headings, a
   single paragraph unit rarely exceeds a few hundred characters in practice; no complex
   overlapping/sliding-window chunking (large-RAG style) is designed, per the brief's explicit
   instruction not to over-engineer for short MD.
6. **Document identity preserved on every unit:** every paragraph carries its parent `doc_id`
   (already authored in frontmatter, § 1 item 4) and the document's relative path, so a match can
   always resurface either the paragraph, its enclosing section, or the whole document — the
   Builder decides which granularity to include in the evidence package (§ 9) based on
   completeness needs, not the index.

**Minimum fields per index row** (exactly the brief's list, no additions):

| Field | Source |
|---|---|
| `paragraph_id` | deterministic: `f"{doc_id}#{heading_anchor or 'body'}#{ordinal}"` |
| `document_path` | relative POSIX path under `md/`, same convention as `TargetCachedFullContext.document_paths` |
| `document_identity` | frontmatter `doc_id` (already authored, § 1 item 4) |
| `heading` | the nearest enclosing `##`/`###` heading text (or `None` for pre-heading body text) |
| `topic` | frontmatter `topic:` (already authored, same source `core/topic_taxonomy.py` uses) |
| `document_type` | frontmatter `doc_type:` (**already authored on every current file** — confirmed `{info, service, faq, comparison, doctor, contacts}` by direct grep of the live pack; no new required field) |
| `normalized_searchable_text` | NFKC-normalized, casefolded, punctuation-stripped paragraph text (index-time only; never the raw display text is what gets matched against) |
| `content_hash` | sha256 of the raw (unnormalized) paragraph text, for change detection between generations |

No `chunk_overlap`, no sliding window, no embedding vector field — explicitly out per the brief.

## 9. Typed Evidence Package contract (design only — not implemented)

One contract, `TargetEvidencePackage` (proposed name, `contracts/target_evidence_package.py`, does
not exist), mirroring `TargetContextScopeDecision`'s proven shape (frozen, `extra="forbid"`,
strict, no raw text/PII):

```python
class TargetEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    selected_md_refs: tuple[str, ...]              # whole-document filenames (Composer-input unit)
    selected_paragraph_refs: tuple[str, ...]        # paragraph_id values (§8), for provenance only
    exact_evidence_block_refs: tuple[str, ...]      # refs already in TargetComposerRequest.evidence_blocks
    structured_record_ids: TargetEvidenceRecordIds  # nested: offer_ids, fact_ids, doctor_ids, policy_sections
    session_derived_refs: tuple[str, ...]           # refs pulled in only via §12's explicit-follow-up rule
    retrieval_derived_refs: tuple[str, ...]         # paragraph/doc refs found via §7's lexical index
    provenance: tuple[TargetEvidenceSourceProvenance, ...]  # one entry per included ref: source_kind + reason
    completeness_status: Literal["complete", "insufficient_widened", "fullcontext_fallback"]
    fallback_reason: str | None                     # canonical short code, required iff not "complete"
    estimated_chars: int
    estimated_tokens: int                            # explicit chars//4 estimate, labelled as such
    package_fingerprint: str                          # sha256 hex, same identity pattern as §10/PERF-6 §10
```

`TargetEvidenceSourceProvenance` (nested, same file): `ref: str`, `source_kind: Literal["evidence_block",
"exact_content_ref", "structured_record", "session_projection", "lexical_retrieval",
"fullcontext_fallback"]`, `reason: str` (canonical code, e.g. `"required_fact_id_match"`). Every
field on both models is an enum, a count, a hash, or a reference/ID string — **never** the referenced
text, the user's question, the composed answer, a session ID, or a contact value, exactly matching
`TargetContextScopeDecision`'s existing anonymization discipline (`contracts/
target_context_scope_decision.py`, module docstring).

**One canonical producer** — a single, not-yet-created `build_target_evidence_package(...)` function
in a single, not-yet-created `core/target_evidence_package_builder.py` module, mirroring the
PERF-5/PERF-6 single-producer precedent (`select_target_response_length_profile`,
`resolve_target_context_scope`) — never a second producer, never a parallel per-service/per-topic
variant contract. This is a **naming/shape decision for a future milestone**; no such file is
created here.

## 10. Completeness rules (specific deficits, never "any offer/doctor present")

Directly addressing PERF-6 debt item 2 (§ 2): completeness must be checked against **specific
required IDs**, not class presence. For a future Builder (not built here), the check reads exactly
the ground truth PERF-6 §6/§8 already identified as authoritative and never invents a new one:

1. **Content:** every MD ref the turn's `TargetResponseSpec`/`evidence_blocks` already designates as
   required (`content:`/`kb:` refs in `evidence_blocks`, plus the exact service's `content_ref` when
   `spec.service_id` is set) must be in `selected_md_refs`.
2. **Exact offer IDs:** every `offer_id` present in the real `evidence_blocks` (not "any offer for
   this service") must be in `structured_record_ids.offer_ids` — closes debt item 2 exactly.
3. **Required fact IDs:** `spec.required_fact_ids ⊆ structured_record_ids.fact_ids` — identical rule
   to PERF-6's own (already correct there).
4. **Doctor IDs:** every `doctor_id` present in the real `evidence_blocks` — same exactness fix as
   offers.
5. **Contact fields:** when the turn's evidence includes any `clinic_contact` block, the specific
   field name(s) (never values) must be in `structured_record_ids.policy_sections` — identical rule
   to PERF-6's own.
6. **Consultation value:** when `spec.allow_consultation_close` and a consultation block exists in
   `evidence_blocks`, its `content_ref` must be represented.
7. **Comparison/related content:** when `"comparison" in turn_frame.aspects` (or the equivalent
   signal available at the real call site), at least one `doc_type == "comparison"` paragraph/doc
   ref for the relevant topic must be present, sourced via the lexical index (§ 7) or the Builder
   falls back to FullContext (§ 11) — this closes the honest PERF-6 §12 gap #1 (no authored
   service↔comparison cross-ref exists) with a **retrieval-assisted**, not authored-cross-ref-only,
   path, exactly matching the owner's brief ("Retrieval является вспомогательным способом найти
   дополнительные документы").
8. **Global microfacts:** any MD paragraph whose normalized text lexically matches the user's
   message tokens above a to-be-tuned relevance floor (PERF-7A implementation detail, not decided
   here) and whose `doc_type` is not already covered by 1–7 is a candidate addition — this is the
   "retrieval finds additional documents" path, never the primary completeness gate.

A package is **never** marked `complete` merely because any one deficit class has a non-empty count
— every applicable check above must individually pass, closing PERF-6 debt item 2 for the future
Builder by design.

## 11. FullContext fallback rules

1. **Chosen before the single Composer call**, never after a failed narrower attempt and never as a
   second Composer retry — identical constraint to PERF-6's own "no repeated Composer call at any
   step" rule (seam audit §6), restated here because the brief explicitly repeats it (constraint 14).
2. **Triggers:** any of PERF-6's own existing `full`-fallback triggers (§ 5 of the PERF-6 seam
   audit — missing service/topic signal, unresolvable ambiguity, any resolver exception) **plus**
   the new completeness deficits in § 10 whenever the lexical index (§ 7/§ 8) cannot resolve them
   with sufficient confidence (no numeric confidence threshold is invented here — "sufficient" is a
   PERF-7A implementation decision against real recall data, not a number picked in this Phase 1
   document, matching PERF-6's own precedent of never inventing a confidence cutoff, § 2 of the
   PERF-6 seam audit).
3. **Never surfaced as a user-visible error** — fail-closed to FullContext exactly as
   `resolve_target_context_scope` already fails closed to `full` on any exception
   (`core/target_context_scope_resolver.py`, lines 564–571) — this precedent is reused conceptually,
   not reimplemented as a shared function (the future Builder is a different module with a
   different contract).
4. **`fullcontext_fallback` is not itself an error status** — it is a valid, expected
   `completeness_status` value on `TargetEvidencePackage` (§ 9), exactly mirroring PERF-6's own
   "`full` is not an error — it is the same content the real Composer/Verifier already receive
   today" framing (PERF-6 seam audit §5).

## 12. Session projection rules (explicit follow-up only)

Restates constraint 13 verbatim as a design rule, grounded in the same existing mechanism PERF-6 §1
item 2 already traced and reused without re-implementing: session state is read only through the
**existing** age-guarded, hydration-gated `TurnFrame.service_id`/topic already produced by
`core/target_runtime_turn_frame_hydration.py`/`core/dialog_focus.py` — a future Builder's
`session_derived_refs` field (§ 9) is populated **only** when the already-arbitrated
`TargetResponseSpec` (§ 1 item 1) carries a session-hydrated `service_id`/topic, i.e. only when the
existing contextual-follow-up detection has already fired. **No new staleness policy, no second
session reader, no automatic carry-forward of a prior turn's service/extent/jaw/price into an
independent new question** — a standalone new question (no detected follow-up) never receives
session-derived evidence, exactly as PERF-6 §1 item 2 already established for its own `service_exact`
tier. This closes constraint 13 by reuse, not by inventing a new mechanism.

## 13. Offline evaluation design (two modes, neither implemented in Phase 1)

### Mode 1 — offline package evaluation (no LLM, Builder-only)

For each scenario: the (future) Builder selects a package from a frozen scenario input
(`TurnFrame`/`TargetResponseSpec` fixture, never real live user text); the harness asserts
`selected_md_refs`/`structured_record_ids` match expected source IDs (§ 10), `completeness_status`
matches expectation, and `estimated_tokens` falls in an expected range. Zero provider calls, zero
network — same shape as PERF-6's own offline resolver tests
(`tests/test_target_context_scope_resolver.py`).

### Mode 2 — counterfactual Composer evaluation (LIVE/LLM, separate future owner gate)

FullContext-package vs. scoped-package answers compared **in memory only** for a single evaluation
process run; **raw questions/answers are never persisted** — only: scenario ID, source IDs used,
categorical verdicts (`match`/`degraded`/`improved`/`unsafe`), hashes of the two answer texts (for
byte-identity/drift detection without storing the text itself), token counts, call counts, timing,
and error codes are written to any artifact. This mirrors constraint 8's storage rule exactly (no
text persistence) and constraint 7's "not a shadow gate, not a route change" framing — this mode
never runs against the real product path, only an isolated evaluation harness, and only after a
**separate** owner LIVE/LLM GO, matching every prior PERF-N live-eval precedent in this repo (S43,
S47, S53/S55, PERF-3's live attempt).

### Required scenario classes (17, per brief) and design-time target counts

Design only — no scenario is written out as literal user-facing text in this document or in any
committed artifact (that would itself violate constraint 8's spirit ahead of the harness existing).
Target counts are a *design allocation*, to be filled with frozen fixture `TurnFrame`/spec inputs at
PERF-7C, not live text:

| # | Class | Target count | What Mode-1 checks |
|---|---|---:|---|
| 1 | Exact service | 10 | `service_exact`-equivalent completeness, exact content ref |
| 2 | Broad service | 8 | topic-level completeness across multi-doc topics |
| 3 | Price | 8 | exact offer id present, not "any offer" (§ 10.2) |
| 4 | Doctor | 6 | exact doctor id present (§ 10.4) |
| 5 | Contacts | 4 | policy section field presence, never value (§ 10.5) |
| 6 | Parking | 4 | same contact-authority path as #5, distinct scenario |
| 7 | Sterilization | 6 | clinic-capability MD-only path (no catalog service), per `docs/CLIENT_PACK_AUTHORING.md`'s existing capability-routing rule |
| 8 | Own fresh CT | 6 | tomography own-scan FAQ routing (existing `FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING` precedent) |
| 9 | Treatment plan from another clinic | 6 | medical_handoff / external-plan boundary, no diagnosis |
| 10 | Pain/fear | 8 | marketing amplifier + service content, not fallback |
| 11 | Marketing concern | 6 | scenario-gated fact inclusion |
| 12 | Comparison | 8 | § 10.7 retrieval-assisted comparison inclusion or honest fallback |
| 13 | Cross-topic question | 8 | multi-topic ambiguity → FullContext fallback (§ 11), not a guess |
| 14 | Follow-up "а сколько это стоит?" | 8 | § 12 session projection fires correctly |
| 15 | New independent service after prior focus | 8 | § 12 session projection does **not** fire (negative case) |
| 16 | Unknown wording | 8 | lexical index (§ 7) prefix/overlap recall, honest miss → fallback |
| 17 | No matching fact | 6 | honest `data_gap`/fallback, never invented content |
| 18 | Medically risky personal question | 8 | medical_handoff boundary unchanged, no Builder override |
| — | **Total** | **~118** | within the brief's 100–150 range |

(18 rows because the brief's prose lists "medically risky personal question" as an 18th item after
17 named classes — counted here, not merged, so nothing from the brief's list is silently dropped.)

## 14. Implementation milestone sequence (not started; future, separately owner-approved)

Exactly the sequence named in the brief, restated as the canonical order — no milestone here is
begun:

1. **PERF-7A** — local lexical index implementation (§ 7/§ 8: Option A token-overlap scan +
   paragraph-index generator).
2. **PERF-7B** — `EvidencePackageBuilder` implementation (§ 9/§ 10/§ 11/§ 12).
3. **PERF-7C** — offline source/package evaluation (§ 13 Mode 1, the 18-class/~118-scenario matrix
   materialized as frozen fixtures).
4. **PERF-8** — Scoped Composer behind a local feature flag (real Composer switch — explicitly
   **not** authorized by this document, mirroring every prior "real switch is a separate milestone"
   precedent in this repo, e.g. PERF-6 §16).
5. **PERF-9** — evidence-only Verifier (the question PERF-6 §5 explicitly flagged and declined to
   answer — still not answered here).
6. **PERF-10** — real Composer answer token streaming.
7. Final local widget E2E (post-authority, mirroring the A9R3/S62/S63 live-verification pattern
   already used for every other authority cutover in this repo).
8. Cleanup of the old PERF-6 ladder/contracts (`TargetContextScopeDecision`,
   `resolve_target_context_scope`, the shadow hook) — **only after** PERF-8/9 prove the new Builder
   path is the real mechanism; PERF-6 is not deleted by this document or by PERF-7A/B/C.

## 15. Risks

1. **Repeat of PERF-6 debt item 7** (§ 2): a naive PERF-7B implementation could add its own
   unconditional, ungated per-turn pass on top of PERF-6's existing one. Mitigation: any Phase 2
   implementation must either reuse PERF-6's existing single shared redundant materialization (§ 3)
   or gate its own pass behind a flag from the start, unlike PERF-6.
2. **Lexical false negatives on genuine unknown wording** (scenario class 16, § 13) could silently
   under-serve the answer if the Builder is ever made authoritative without first proving recall via
   Mode 1 evaluation — mitigated structurally by § 11's fallback-before-single-call rule: an
   under-confident lexical match must fall back to FullContext, never guess narrow.
3. **Comparison-content gap (PERF-6 §12 gap #1) is only partially closed**, not eliminated: § 10.7's
   retrieval-assisted comparison inclusion depends on lexical recall quality, unproven until PERF-7A
   ships and PERF-7C measures it. Until then, comparison questions should be expected to fall back
   to FullContext more often than other classes — an honest, not hidden, limitation.
4. **`doc_type`/`topic` frontmatter coverage is a demo-pack-only observation** (§ 1 item 4) — a
   future client onboarded via `clients/_template/` (per `docs/CLIENT_PACK_AUTHORING.md`) is not
   guaranteed to author `doc_type` on every MD file today (it is optional metadata, not in the
   validator's required-file list, § "PRE-CODE"). PERF-7A must treat a missing `doc_type` as `None`,
   never a hard error, and the paragraph index (§ 8) must degrade gracefully (heading/topic-based
   grouping only) when `doc_type` is absent — not silently assume every future client pack matches
   demo's current authoring discipline.
5. **Non-deterministic `context_group` selection (PERF-6 debt item 5)** must be fixed before any
   future `context_groups.json` milestone, independent of PERF-7 — flagged here so it is not
   forgotten as an orphaned finding once this document's attention moves to the Builder.

## 16. Exact future allowlists (none created by this Phase 1 commit)

- `core/target_lexical_paragraph_index.py` (PERF-7A, Option A scanner + paragraph-index generator)
  — **does not exist**.
- `contracts/target_evidence_package.py` (`TargetEvidencePackage`, § 9) — **does not exist**.
- `core/target_evidence_package_builder.py` (`build_target_evidence_package`, § 9) — **does not
  exist**.
- Any generated per-document paragraph-index artifact/cache file — **does not exist**.
- `clients/demo/target_response/context_groups.json` / `clients/_template/target_response/
  context_groups.json` — **still does not exist** (PERF-6's own gap, unchanged, re-verified by this
  audit's governance test).
- Any runtime flag (e.g. `EVIDENCE_PACKAGE_BUILDER_ON`) — **does not exist**.
- Any FTS5/SQLite virtual table, embeddings model, or vector database dependency — **none added**.
- Explicitly **NOT** in this allowlist for any future milestone without a further, separate owner
  GO: any change to `core/target_composer_request.py`'s or `core/target_response_verifier.py`'s real
  invocation arguments; any change to the S39-protected `run_target_offline_verified_response_
  pipeline` signature (§ 3); any real Composer/Verifier switch onto a narrower package (PERF-8,
  explicitly deferred); any embeddings/vector/RAG code (explicitly deferred past PERF-7 entirely,
  per the brief).

## 17. Governance acceptance matrix (this Phase 1 design's own structural claims — 40 rows)

Each row is a claim this document makes about the *current, already-shipped* code (never about
unbuilt PERF-7A/B/C code) — verifiable today, independent of any future implementation.

| # | Claim | Verified by |
|---|---|---|
| 1 | `doc_type` frontmatter exists on every current demo MD file | direct grep of `clients/demo/md/*.md`, § 1 item 4 |
| 2 | `doc_id`/`topic`/`subtopic` frontmatter exists on every current demo MD file | same grep |
| 3 | Real per-file MD sizes: min 479 / max 3,434 / median 2,034 chars | direct computation over the live pack, § 1 |
| 4 | `TargetComposerRequest.evidence_blocks` is shared by Composer and Verifier today (one real materialization serves both) | `core/target_verified_response_pipeline.py` lines 61/72 pass the same `request` object |
| 5 | The real per-turn materialization count today is 2 (real + PERF-6 shadow copy), not 3 | § 3, direct trace of the two call sites |
| 6 | `run_target_offline_verified_response_pipeline`'s signature and call sequence are AST-pinned by a frozen test | `tests/test_target_verified_response_pipeline.py::test_public_signature_and_function_is_exact_straight_line` |
| 7 | `compare_target_context_scope_shadow` treats an empty `used_content_refs`/`primary_content_ref` as a trivial subset match | `core/target_context_scope_shadow.py` lines 68–74 |
| 8 | `_resolve_validated_source_identity`'s non-exact-authority branch can legitimately return an empty validated-used set | `core/target_response_verifier.py` lines 655–671 |
| 9 | `_has_required_components`/the shadow's price/doctor check test only non-emptiness, not exact id membership | `core/target_context_scope_resolver.py` lines 161–169; `core/target_context_scope_shadow.py` lines 80–84 |
| 10 | `service_exact`'s closure is read directly from `evidence_blocks`, making the item-9 gap harmless at that tier specifically | `core/target_context_scope_resolver.py::_try_service_exact`, `_evidence_closure` |
| 11 | `topic`'s closure independently scans all active offers by matched service id, not the spec's exact required offer | `core/target_context_scope_resolver.py::_try_topic` lines 303–307 |
| 12 | `_closure_size` sums only `content_refs`, never offers/facts/doctors/policy | `core/target_context_scope_resolver.py` lines 150–158 |
| 13 | `core/target_composer_executor.py::_invocation` includes offer/fact/doctor/policy text in the real per-turn evidence JSON | lines 386–396 |
| 14 | No `context_groups.json` exists anywhere in the repo at this baseline | filesystem check, this milestone's own governance test |
| 15 | `context_groups` param is always `None` at the one real call site | `core/target_policy_bound_verified_response_pipeline.py` call to `_resolve_shadow_decision_safely`/`resolve_target_context_scope` |
| 16 | `_try_context_group` iterates a `set[str]` built from `spec.allowed_topics` before matching a group | `core/target_context_scope_resolver.py` lines 344–352 |
| 17 | Python's default `str` hash (and therefore `set` iteration order) is randomized per process unless `PYTHONHASHSEED` is fixed | CPython documented behavior (`PYTHONHASHSEED`), not asserted from this repo's code |
| 18 | `_resolve_shadow_decision_safely` is called unconditionally, with no flag check, on every real turn | `core/target_policy_bound_verified_response_pipeline.py` line 265 |
| 19 | `PLANNER_SPECULATION_CAPACITY=0`-style gating exists elsewhere in this repo (PERF-4) but is not used by PERF-6's shadow hook | `docs/FLAGS_AND_STATUS.md` PERF-4 entry vs. PERF-6's ungated hook |
| 20 | `core/target_composer_request.py::_section` is fence-aware and anchor-scoped, the precedent reused conceptually by § 8 | `core/target_composer_request.py` lines 217–268 |
| 21 | The cached FullContext corpus is 107,980 chars / 55 docs / sha256 `758a64eb…`, unchanged since PERF-6 | `core/target_cached_full_context.py::build_target_cached_full_context`, cross-checked live by this milestone's governance test |
| 22 | Local `sqlite3` in this environment reports version 3.49.1 | direct `python -c "import sqlite3; print(sqlite3.sqlite_version)"` run by this audit |
| 23 | `CREATE VIRTUAL TABLE ... USING fts5(...)` succeeds locally | § 5 probe |
| 24 | `bm25()` is callable locally | § 5 probe |
| 25 | `tokenize='unicode61 remove_diacritics 2'` is accepted locally | § 5 probe |
| 26 | `tokenize='trigram'` is accepted locally | § 5 probe |
| 27 | FTS5 with `unicode61` does not match a bare Russian stem against a longer same-root word without a prefix wildcard | § 5 probe, `'имплант' -> []` |
| 28 | FTS5 prefix wildcard (`импланта*`) recovers same-root Russian forms | § 5 probe |
| 29 | An unescaped `"` in a raw `MATCH` query raises `sqlite3.OperationalError` | § 5 probe |
| 30 | Unbalanced parentheses in a raw `MATCH` query raise `sqlite3.OperationalError` | § 5 probe |
| 31 | A trailing dangling boolean operator in a raw `MATCH` query raises `sqlite3.OperationalError` | § 5 probe |
| 32 | No FTS table, index file, embeddings model, or vector database exists anywhere in this repo at this baseline | this milestone's own governance test, filesystem check |
| 33 | No `core/target_evidence_package_builder.py`/`contracts/target_evidence_package.py` exists at this baseline | governance test, filesystem check |
| 34 | No runtime flag named for this milestone (e.g. `EVIDENCE_PACKAGE_BUILDER_ON`) exists in `config.py` at this baseline | governance test, source grep |
| 35 | `clients/demo/**` is untouched by this commit (SHA-256/byte-identity, same method PERF-6 used) | governance test, `git diff` scoped check |
| 36 | Zero live/provider/network calls were made in the production of this document (only local `sqlite3`/filesystem probes) | this section's own probe log, § 5, no API keys/URLs referenced |
| 37 | This document's own scenario table (§ 13) contains no literal question/answer text — only class labels and counts | direct read of § 13 |
| 38 | The 18-class/~118-scenario allocation sums correctly | § 13 arithmetic (10+8+8+6+4+4+6+6+6+8+6+8+8+8+8+8+6+8 = 118) |
| 39 | Every field on the proposed `TargetEvidencePackage`/`TargetEvidenceSourceProvenance` contracts (§ 9) is an enum, count, hash, or reference id — never raw text | direct read of § 9's field table |
| 40 | This document's own PRE-CODE test suite (§ below) imports no product code itself (pure filesystem/text checks, mirroring PERF-6's own governance-checker discipline) | `tests/test_final_local_evidence_package_builder_foundation_governance.py::
test_no_product_code_imported_by_this_governance_module` |

## 18. STOP conditions

**STOP before any PERF-7A implementation.** Nothing in §§ 7–14 is created by this commit. Required
before PERF-7A starts:

- owner GO on this design (lexical option selection, paragraph-index shape, Evidence Package
  contract shape, completeness/fallback/session rules);
- a separate governance TASK for the PERF-7A lexical index implementation itself;
- a separate, later governance TASK for PERF-7B (`EvidencePackageBuilder`), gated on PERF-7A's own
  measured recall, not assumed;
- a separate, later governance TASK for PERF-7C's offline evaluation harness, gated on PERF-7B;
- **no real switch of Composer/Verifier onto a Builder-produced package is authorized by this
  document at all** — that is PERF-8, a still-later, still-separately-owner-gated milestone,
  contingent on PERF-7C's own offline measurement (once implemented and run) actually proving
  sufficient package quality;
- PERF-6's existing debt items 2 and 5 (§ 2) should be fixed as part of PERF-7A/B, not left to drift
  further, but that fix is itself future implementation work, not authorized here.
