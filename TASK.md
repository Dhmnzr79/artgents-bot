# TASK — S44 Deterministic Cached FullContext Composer Input

**Branch / baseline:** `codex/stage-a` / `f14be0a feat: capture S43 first live eval audit artifacts`

**Goal:** финальный target Composer получает **весь валидированный MD-корпус** клиента как
постоянный cached FullContext input; scoped primary evidence остаётся отдельным точным sidecar.
**Build once → inject → reuse.** Без live/LLM, без provider caching, без исправления
`service_id` gate.

## Owner laws

- **FINAL_FULLCONTEXT_ONLY:** cached FullContext = primary knowledge input Composer;
  scoped primary evidence = sidecar для цен, этапов оплаты, врачей, marketing facts, CTA и
  verification — **не заменяет** corpus.
- **One canonical path:** `build_target_cached_full_context(md_root)` once → immutable
  `TargetCachedFullContext` → inject through S39/S40/S41 → Composer. **No** dual path
  «передай объект или собери из md_root в pipeline».
- **No per-turn rebuild:** pipeline must not scan `md_root` or rebuild corpus per question.
- **All valid `.md`:** include every `.md` under explicit client `md_root` once, including
  doctors MD; **no** silent filename/topic/type exclusions.
- **Do not use `core/knowledge_base.py` as-is** (legacy doctors__ exclusion + non-MD policies).
- **Provider prompt caching:** S44 prepares deterministic stable corpus/prefix only; **not**
  implemented provider cache integration.
- **S44 does NOT fix `service_id` gate** (S34/S41 unchanged). After S44 Composer sees full
  corpus, but service_id-free general/medical answer is **not** end-to-end yet.
- A9, runtime, UI, session, product authority, S43 artifacts — untouched.
- No RAG/retriever/chunk routing/per-MD routes; no legacy compatibility bridge.

## Deliverables

1. **`TargetCachedFullContext` contract** with: `corpus_text`, `document_count`,
   `document_paths` (stable relative paths), `sha256`, explicit inter-document boundaries.
2. **`build_target_cached_full_context(md_root)`** — bootstrap/offline builder only;
   fail-closed on empty/invalid/unreadable corpus.
3. **`TargetComposerInvocation`** — explicit fields: `system_policy`, `cached_full_context`,
   `response_directives_json`, `primary_evidence_json`, `user_message`.
4. **Pipeline propagation** — same prebuilt object through S37/S39/S40/S41 without rebuild,
   mutation, or filesystem scan inside pipeline.
5. **Offline tests** (synthetic + demo corpus + recording backend + no-rebuild spy + import
   firewall).
6. **ARCH/ROADMAP** status update for S44 only.

## Canonical corpus rules

- Discover all `*.md` under `md_root` recursively; order by canonical relative POSIX path.
- Each document included **exactly once** with deterministic boundary markers documented in
  module docstring.
- Preserve full on-disk UTF-8 content (including frontmatter) so consultation values and
  doctor profile text are not lost.
- `sha256` = SHA-256 hex of final `corpus_text` (UTF-8).

## Boundaries / allowlist

- `TASK.md`
- `contracts/target_cached_full_context.py`
- `core/target_cached_full_context.py`
- `core/target_composer_executor.py`
- `core/target_verified_response_pipeline.py`
- `core/target_policy_bound_verified_response_pipeline.py`
- `core/target_turn_frame_bound_response.py`
- `tests/test_target_cached_full_context.py`
- `tests/test_target_composer_executor.py`
- `tests/test_demo_target_composer_executor.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `tests/test_demo_target_turn_frame_bound_response.py`
- `tests/test_target_verified_response_pipeline.py` (only if signature/neighbor updates)
- `tests/test_target_policy_bound_verified_response_pipeline.py` (only if needed)
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

**Forbidden:** S34/S41 service_id semantics; S43 artifacts; A9/runtime/authority; live/LLM;
provider integration; `knowledge_base.py` reuse; auto-build inside pipeline.

## Minimal protected acceptance

- synthetic: all MD once, stable order, boundaries, deterministic hash, fail-closed errors;
- demo: `document_count` matches validated demo corpus (54); doctors MD present; sample docs
  from multiple families; no silent exclusions;
- recording backend: invocation has full `cached_full_context` **and** scoped
  `primary_evidence_json`; corpus identical across turns; directives/evidence not in corpus;
- pipeline spy: builder **not** called inside S39/S40/S41;
- import firewall: target FullContext builder independent of `llm.py`, `orchestration`, runtime;
- neighbor offline tests green; no skip/xfail; no live.

Run only:

- `tests/test_target_cached_full_context.py`
- `tests/test_target_composer_executor.py`
- `tests/test_target_verified_response_pipeline.py`
- `tests/test_demo_target_composer_executor.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `tests/test_demo_target_turn_frame_bound_response.py`

Use external `--basetemp` and `-p no:cacheprovider`. **No full pytest. No live run.**

## Gates

1. Independent **PRE-CODE** checker on governance TASK.
2. Commit/push `docs: govern S44 cached FullContext composer input` (**TASK.md only**).
3. Implement allowlist; run targeted offline tests.
4. Independent **COMPLETION** checker.
5. One completion commit; push; clean/synced.

## Explicitly deferred (next milestone)

One vertical slice: **service-optional FullContext materialization + missing-base response +
medical grounding verification** — not in S44.
