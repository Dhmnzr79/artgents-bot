# FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT — Phase 1 (read-only)

**Baseline:** `codex/stage-a` @ `9073a22`. **Scope:** `clients/demo/**` content only.
**NO CLIENT-PACK CHANGE / NO PRODUCT CHANGE / NO LIVE / NO PROVIDER / NO NETWORK.**

This audit is read-only. Nothing in `clients/demo/**` was modified, merged, deleted, or renamed.
No embeddings, no LLM, no external API were used for duplicate detection — only deterministic
local text methods. `cached_full_context.sha256` recomputed by this audit from the current
`clients/demo/md/**` tree matches the value recorded in
[`demo_content_token_inventory.json`](demo_content_token_inventory.json); the governance checker
re-derives this hash on every run, which is also the mechanism that proves the pack was not
touched after this audit was produced.

## 0. Method

A one-off, read-only script (not committed — audit tooling only; see § 8 for why) walked
`clients/demo/**` and:

1. Parsed every `md/*.md` file into: one `frontmatter` block, one `heading` block per `##`/`###`
   header, and `paragraph`/`list` body blocks grouped under the nearest heading. `suggest_h3`,
   `situation_allowed`, `video_key`, `cta_key`, `cta_action`, `empathy_enabled`, frontmatter
   `aliases`, inline `<!-- aliases: [...] -->` comments, and `consultation_value` were extracted as
   separate metadata/content units and **excluded** from automatic content-duplicate classification
   (UI labels and frontmatter are not content dupes by construction, per the task brief).
2. Parsed `service_catalog.json`, every `pricebook/services/*.json` offer (`package.label` +
   `package.includes` as one `offer_package` block, `price.amount`+`currency` as one
   `offer_price_scalar` block), `pricebook/facts.json` (`text_fact` per fact), `doctor_catalog.json`
   (`name, position, стаж N лет` per doctor), `clinic_policies.yaml` (`contact:` fields, each
   `policies.*.answer`, each `service_alternatives[*].note`, and the four template strings),
   `marketing.yaml`, `clinic_strategy.yaml`, `brand_catalog.json`, `video_catalog.yaml` raw text.
3. Built the real production `TargetCachedFullContext` (`core/target_cached_full_context.py`,
   `build_target_cached_full_context`) and the real production Composer/Verifier static prefixes
   via `core/target_prompt_cache_prewarm.py`'s `build_dry_run_report("demo")` — the same pure,
   offline, zero-provider-call function the PERF-3 prewarm CLI uses for dry-run reporting. This
   reuses production message builders (`build_composer_sdk_messages`/`build_verifier_sdk_messages`)
   verbatim; it constructs strings and SHA-256 hashes only, **it never calls the provider**.
4. Ran deterministic exact/near/structured duplicate and conflict detection (§ 2–4) over the
   1060 extracted blocks (433 of them eligible for content-duplicate comparison; the rest are
   frontmatter/heading/metadata units tracked for size only).

**Tokenizer:** no local exact tokenizer was available/imported for this audit. All "token"
figures in the JSON artifacts are the explicitly-labelled estimate `chars // 4`
(`tokenizer: "chars_div_4_estimate_NOT_exact"`), the same rough estimator already used in
production by `core/target_prompt_cache_prewarm.py::_estimate_tokens` — this audit does not
introduce a second, different estimation method. These estimates are not compared against real
`prompt_tokens` from logs, because doing so would require reading production usage-log records,
which is out of scope for a read-only client-pack audit; that comparison, if wanted, is a Phase 2
question.

## 1. Token / char inventory (13 spec layers + 2 extras)

Source: [`demo_content_token_inventory.json`](demo_content_token_inventory.json).

| # | Layer | Chars | Token est. (chars/4) | Count |
|---|---|---:|---:|---|
| 1 | MD body (55 docs) | 67,560 | 16,890 | 55 `.md` files |
| 2 | MD frontmatter (55 docs) | 24,071 | 6,018 | 55 `.md` files |
| 3 | `service_catalog.json` | 13,161 | 3,290 | 22 services |
| 4 | Offers (`pricebook/services/*.json`) | 23,545 | 5,886 | 32 offer files |
| 5 | `pricebook/facts.json` | 3,277 | 819 | 6 facts |
| 6 | `doctor_catalog.json` | 2,388 | 597 | 6 doctors |
| 7 | `clinic_policies.yaml` | 3,227 | 807 | — |
| 8 | `marketing.yaml` | 2,135 | 534 | — |
| 9 | Consultation content (`consultation_value` frontmatter field) | 380 | 95 | subset of #2 |
| 10 | Presentation metadata (`suggest_h3`+`situation_allowed`+`video_key`+`cta_key`+`cta_action`+`empathy_enabled`) + `video_catalog.yaml` | 5,829 (5,601 subset of #2 + 228 additive) | 1,457 | — |
| 11 | Cached FullContext corpus (all 55 `.md`, verbatim, with `BEGIN/END DOC` markers) | 107,980 | 26,995 | sha256 `758a64eb…` |
| 12 | Composer static prefix (system policy + static user content through end of corpus) | 116,571 | 29,142 | model `qwen3.7-plus` |
| 13 | Verifier static prefix (system policy + static user content through end of corpus) | 114,719 | 28,679 | model `qwen3.7-plus` |
| extra | `target_response/clinic_strategy.yaml` (not one of the 13 named layers) | 1,947 | 487 | — |
| extra | `target_response/brand_catalog.json` (not one of the 13 named layers) | 488 | 122 | — |

**Rows #9 and #10 are subsets of row #2** (S18 stores `consultation_value` inside MD frontmatter;
presentation keys live in the same frontmatter block) — they are reported separately per the task
brief's "separate unit" instruction, but are **not** additive to a grand total. `video_catalog.yaml`
(228 chars) is a genuinely separate file and is additive.

**Raw client-pack sum, layers #1–#8 + the two extras + `video_catalog.yaml`, excluding the #9/#10
subsets:** 142,027 chars ≈ 35,507 tokens (est.). This is the entire authored client pack on disk
(everything except the two generated/derived rows #11–13).

**Arithmetic checks performed by the audit script and re-verified by the governance checker:**

- `cached_full_context.chars` (107,980) was independently reconstructed as
  `sum(len(doc.rstrip("\n")) for doc in the 55 md files) + BEGIN/END marker overhead + 54 join
  newlines` and matched exactly — proving the 107,980 figure is the real corpus, not an estimate.
- `composer_static_prefix.chars (116,571) − cached_full_context.chars (107,980) = 8,591` chars is
  the Composer-only overhead: `TARGET_COMPOSER_SYSTEM_POLICY` (`core/target_composer_executor.py`)
  plus the `_COMPOSER_USER_TEMPLATE` wrapper text up to (not including) the placeholder
  `RESPONSE_DIRECTIVES_JSON`/`PRIMARY_EVIDENCE_JSON`/`USER_MESSAGE` tail.
- `verifier_static_prefix.chars (114,719) − cached_full_context.chars (107,980) = 6,739` chars is
  the Verifier-only overhead: `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY`
  (`core/target_response_verifier.py`) plus the `_VERIFIER_USER_TEMPLATE` wrapper text.
- Both static prefixes independently embed the **entire** 107,980-char corpus once each — see § 5.

**Not measured here (explicitly out of scope):** the per-turn dynamic tail
(`response_directives_json`/`primary_evidence_json`/`user_message` for Composer;
`response_spec_json`/`primary_evidence_json`/`candidate_text` for Verifier). `build_dry_run_report`
uses fixed non-PII placeholders (`"{}"`, `""`) for these fields by design (PERF-3), so this audit's
Composer/Verifier prefix numbers are the **static** part only; real per-turn totals are larger and
turn-dependent, and reading real `prompt_tokens` from logs is out of scope (see § 0).

## 2. Exact duplicates (A)

**Method:** `normalized_hash` — Unicode NFKC normalize, casefold, strip leading `#`/list markers
and `*_\`>` markdown emphasis, collapse whitespace, then SHA-256 (first 16 hex chars). Numbers,
currency symbols, and negation words are preserved (not stripped). Minimum block length 12 chars.
7 exact-hash groups found across the 433 content-eligible blocks; 2 are template section labels
(classified `INTENTIONAL_DUPLICATE`, see below), 5 are real repeated prose across brand-variant
offer files.

| Group | Class | Files | Chars/copy | Potential savings |
|---|---|---|---:|---:|
| `dup00006` — `one_stage.one_tooth.*` package text | EXACT_DUPLICATE | 3 (implantium/impro/nobel) | 221 | 442 chars (~110 tok) |
| `dup00004` — `all_on_6.jaw.*` package text | EXACT_DUPLICATE | 3 | 195 | 390 chars (~98 tok) |
| `dup00003` — `all_on_4.jaw.*` package text | EXACT_DUPLICATE | 3 | 194 | 388 chars (~97 tok) |
| `dup00005` — `classic.one_tooth.*` package text | EXACT_DUPLICATE | 3 | 146 | 292 chars (~73 tok) |
| `dup00007` — `removable_dentures.jaw.*` package text | EXACT_DUPLICATE | 2 (full/partial) | 97 | 97 chars (~24 tok) |
| `dup00001` — doctor label "Опыт и специализация:" | INTENTIONAL_DUPLICATE | 6 (all doctor profiles) | 21 | 105 chars (not recommended for merge) |
| `dup00002` — doctor label "Подход в работе:" | INTENTIONAL_DUPLICATE | 6 (all doctor profiles) | 16 | 80 chars (not recommended for merge) |

The five real `EXACT_DUPLICATE` groups are the **same `package.label` + `package.includes` text**
copied verbatim across the 2–3 brand-SKU offer files of one service (`all_on_4`, `all_on_6`,
`classic`, `one_stage`, `removable_dentures`) — the package description does not vary by implant
brand, only the price does. **Total safe potential savings: 1,609 chars ≈ 402 tokens** (`EXACT_DUPLICATE`
only; the two `INTENTIONAL_DUPLICATE` doctor-card section labels are template UI structure repeated
by design across 6 near-identical profile cards and are **not** recommended for merge).

## 3. Near duplicates (B)

**Method:** word 5-gram shingles (`[a-zа-яё0-9]+` tokens, casefolded) compared with Jaccard
similarity; **threshold 0.6**; minimum block length 40 chars; excludes pairs already counted as
exact. 10 candidates found, **all `offer_package` text**, all `REQUIRES_OWNER_REVIEW` (near-dup is
a manual-review signal only, never a merge basis per the task brief):

- 9 pairs at similarity **0.625** between `all_on_4.jaw.*` and `all_on_6.jaw.*` package text across
  the 3 brand combinations (same wording, "4 импланта" vs "6 имплантов" is the only difference).
- 1 pair at similarity **0.739** between `sinus_lift.one_site.open` and `sinus_lift.one_site.closed`
  package text.

## 4. Structured duplicates and conflicts (C, D)

Four structured cross-authority scans ran; **all four returned zero hits** on the current pack —
itself a finding, reported honestly rather than omitted:

| Check | Method | Result |
|---|---|---|
| Price repeats/conflicts | offer canonical `price.amount` (RUB) cross-referenced against `\d[\d ]*\s?(₽|руб)` matches inside that service's own `content_ref` MD body | **0 hits** — no MD body restates an offer price literally, and none conflicts |
| Contact facts outside authority | `+7…` phone regex and `HH:MM–HH:MM` hours regex searched across every non-`clinic_policies.yaml` content block | **0 hits** — confirms the existing `_CONTACT_MD_FORBIDDEN` validator guard (`scripts/validate_client_pack.py`) is effective, and no other file leaks contact facts |
| Doctor facts outside authority | each doctor's full name searched across all `paragraph`/`list` MD blocks outside that doctor's own profile MD | **0 hits** |
| `facts.json` text literally re-typed in `marketing.yaml` | each `text_fact` string (>15 chars) searched verbatim inside `marketing.yaml` raw text | **0 hits** — `marketing.yaml` correctly uses `fact:<id>` refs only, as `docs/CLIENT_PACK_AUTHORING.md` prescribes |

`no_public_price` appears exactly once in the pack (`bone_graft.default.json`) — no duplication to
report. No `POSSIBLE_CONFLICT` candidates were produced by this audit; the demo pack shows no
detected numeric/currency/date/guarantee contradictions under the methods in § 0.

## 5. FullContext duplication map (audit-only; no Scoped FullContext/Verifier change)

- **What goes into the corpus once:** all 55 `clients/demo/md/*.md` files, verbatim (frontmatter +
  body), each wrapped once in `---BEGIN DOC:{path}---…---END DOC:{path}---` and joined with `\n`
  (`core/target_cached_full_context.py`). 107,980 chars / ~26,995 tokens (est.), sha256 `758a64eb…`.
- **What is NOT in the corpus:** `service_catalog.json`, offers, `facts.json`, `doctor_catalog.json`,
  `clinic_policies.yaml`, `marketing.yaml`, `brand_catalog.json`, `clinic_strategy.yaml` — none of
  these structured files are serialized into the cached corpus. They reach Composer/Verifier only
  through the per-turn `PRIMARY_EVIDENCE_JSON`/`RESPONSE_DIRECTIVES_JSON`/`RESPONSE_SPEC_JSON`
  scoped tail, which this audit does not size (§ 0/§ 1).
- **What is accidentally serialized twice:** nothing found inside the corpus itself — each of the 55
  MD files appears exactly once (`build_target_cached_full_context` fails closed on an empty corpus
  and de-dupes by construction: one file → one block, sorted by POSIX path, no re-inclusion path).
- **System policy overhead:** Composer +8,591 chars, Verifier +6,739 chars (§ 1) — this is the
  "systemic policy" layer per role, separate from and additive to the shared corpus.
- **What the corpus costs today, per role, per turn:** both Composer (116,571 chars) and Verifier
  (114,719 chars) independently transmit the **full** 107,980-char corpus as part of their own
  static prefix — this is the documented, **known** fact called out in the task brief (not a
  client-pack internal duplicate; it is a runtime-architecture fact, already surfaced by
  `FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md`/PERF-3). Combined redundant corpus bytes per
  turn (both roles, no cache hit): 215,960 chars. The one real PERF-3 live attempt observed
  `cached_tokens=0` on both calls — provider-side caching benefit is **not** demonstrated, so this
  215,960-char redundancy is real cost today, not a theoretical one.
- **What the Verifier actually needs vs. gets:** `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY`
  (`core/target_response_verifier.py`) instructs it to assess the candidate answer against
  `CACHED_FULL_CONTEXT` and `PRIMARY_EVIDENCE` for grounding, topic scope, and medical-boundary
  issues (`unsupported_clinic_claim`, `personal_medical_conclusion`,
  `material_external_medical_claim`, `minor_external_detail`) — i.e. it needs the same knowledge
  base as Composer to judge whether the answer stayed inside it, not a narrower slice. Whether a
  **smaller, evidence-only** grounding check (bounded to only the `primary_evidence` + the specific
  MD sections Composer cited) could replace the full corpus for the Verifier is exactly the
  "evidence-only verification" question the task brief asks to flag, not answer. **This audit does
  not implement, size, or recommend a Scoped FullContext or a compact Verifier** — that is
  explicitly forbidden in Phase 1.

## 6. Authority matrix — proposed vs. observed

Proposed rule (repeated here for one-shot readability; canonical source is `docs/CLIENT_PACK_AUTHORING.md`):

| Data | Sole authority |
|---|---|
| Service identity, aliases, routing, refs | `target_response/service_catalog.json` |
| Response text, follow-ups, presentation metadata | `md/*.md` |
| Prices, billing units, inclusions, `no_public_price` | `target_response/pricebook/services/*.json` |
| Doctor data | `doctor_catalog.json` |
| Contacts, hours, general policy | `clinic_policies.yaml` |
| Reusable approved commercial/clinic facts | `target_response/pricebook/facts.json` |
| Applicability/selection (refs to facts, not text) | `target_response/marketing.yaml` |
| Consultation value | exact service MD frontmatter |

**Observed match:** all four cross-authority scans in § 4 returned zero violations — contacts stay
in `clinic_policies.yaml` only, doctor facts stay in doctor profile MD only, marketing.yaml holds
refs only (never literal fact text), and no MD literally restates a canonical offer price. **No
authority gap found in the current demo pack.** The only real content duplication found (§ 2) is
*within* one authority layer (offer `package` text repeated across brand-variant offer files of the
same service) — not a cross-authority violation, and not covered by the authority matrix as
written (the matrix says offers own price/inclusions, but does not say whether package *prose* may
repeat across sibling brand offers of the same service). This is a minor documentation gap in
`docs/CLIENT_PACK_AUTHORING.md`, not a data-placement violation — flagged for Phase 2, not fixed here.

## 7. Top expensive duplicate candidates (ranked by concrete char savings)

1. `dup00006` — `one_stage.one_tooth.*` offer package text × 3 — 442 chars
2. `dup00004` — `all_on_6.jaw.*` offer package text × 3 — 390 chars
3. `dup00003` — `all_on_4.jaw.*` offer package text × 3 — 388 chars
4. `dup00005` — `classic.one_tooth.*` offer package text × 3 — 292 chars
5. `dup00007` — `removable_dentures.jaw.*` offer package text × 2 — 97 chars
6. `dup00001` — doctor label "Опыт и специализация:" × 6 — 105 chars (`MARK_INTENTIONAL`, not counted in savings)
7. `dup00002` — doctor label "Подход в работе:" × 6 — 80 chars (`MARK_INTENTIONAL`, not counted in savings)
8. `dup00017` — sinus_lift open/closed near-dup (0.739 similarity) — no automatic savings figure (near-dup, manual review only)
9–10. remaining `all_on_4`/`all_on_6` near-dup pairs (0.625 similarity each) — no automatic savings figure

**Total realistic savings from this audit: ~1,609 chars (~402 tokens), all in `target_response/pricebook/services/*.json` `package` text.** This is small relative to the 142,027-char raw pack and negligible relative to the 107,980-char cached FullContext corpus — client-pack-internal duplication is **not** the dominant cost driver here; the Composer/Verifier double-transmission of the full corpus (§ 5) is orders of magnitude larger, and is explicitly out of scope for remediation in this Phase 1.

## 8. Why no analysis script is committed

The parsing/hashing/shingling script used to produce §§ 1–4 and the two JSON artifacts is audit
tooling, not a product or cleanup implementation artifact. Per the task's Forbidden list
("product scripts реализации" / "automatic merging" are forbidden in Phase 1), it was run locally
and its **outputs** are committed (the two JSON files + this report); the script itself is not
committed so it cannot be mistaken for an approved Phase 2 implementation tool. A Phase 2 script
contract (§ 9) is proposed for a future, separately-owner-approved milestone.

## 9. Proposed Phase 2 script contract (not implemented)

A future, separately owner-approved milestone could add a **read-only verification script**
(e.g. `scripts/audit_client_pack_dedup.py --client-id demo --check`) that:

- re-derives the same exact/near/structured-duplicate candidate set deterministically from the
  live pack (same methods as § 0/§ 2–4, versioned and pinned so results are reproducible);
- fails CI if a **new** `POSSIBLE_CONFLICT` or `EXACT_DUPLICATE` appears in a class that was
  previously empty, without auto-fixing anything;
- never writes to `clients/**`, never merges, never deletes.

Actual **cleanup** (e.g. hoisting the 5 repeated `package` texts in § 2 into a per-service shared
field referenced by each brand offer) is a separate, owner-approved Phase 2 implementation
milestone — out of scope here, and not proposed as auto-mergeable by this audit.

## 10. Cleanup acceptance matrix (for the future Phase 2 owner decision — not started)

| Candidate class | Safe to auto-apply? | Why |
|---|---|---|
| `EXACT_DUPLICATE` (offer `package` text across brand SKUs) | No — requires a schema decision (new shared field + all 13 offer files updated + validator change) | Cross-file structural change, not text-only |
| `INTENTIONAL_DUPLICATE` (doctor card section labels) | Never — by definition intentional | Removing would break the per-doctor card template |
| `NEAR_DUPLICATE` | Never automatically | Similarity, not identity; risk of merging genuinely distinct facts (e.g. "4 импланта" vs "6 имплантов") |
| `STRUCTURED_DUPLICATE`/`POSSIBLE_CONFLICT`/`REQUIRES_OWNER_REVIEW` | Never automatically | Requires human judgement on which source is canonical |

## 11. Exact implementation allowlist for a future Phase 2 (not started)

None of the following exist yet and none are created by this Phase 1 commit:

- `scripts/audit_client_pack_dedup.py` (proposed, § 9) — does not exist.
- Any schema change to `pricebook/services/*.json` (e.g. a shared `package_ref`) — does not exist.
- Any change to `docs/CLIENT_PACK_AUTHORING.md` documenting the § 6 minor gap — not made in Phase 1.

## 12. STOP conditions

**STOP before any cleanup or Phase 2 implementation** — this Phase 1 commit is audit/governance
only. Owner GO required before:

- creating the Phase 2 script in § 9;
- merging/hoisting any of the 5 `EXACT_DUPLICATE` offer-package texts in § 2;
- documenting the § 6 authoring-doc gap as a rule change;
- any Scoped FullContext or compact-Verifier work referenced in § 5 (explicitly forbidden here).
