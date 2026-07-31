# Флаги и статус проекта (фикс-реестр)

**Что это.** Единый сканируемый список: что за флаг, что делает, включён ли по умолчанию, и почему. Исторический подробный нарратив перенесён в [`archive/FULLCONTEXT_ROADMAP.md`](archive/FULLCONTEXT_ROADMAP.md); здесь — текущая короткая правда одним взглядом.

**Контекст (важно для трактовки флагов).** Это **локальная разработка**: нет прода, нет реальных клиентов, бот на localhost, один разработчик (Denis). Флаг здесь — НЕ ремень безопасности для клиентов (их нет), а: (1) переключатель для сравнения старого/нового поведения без правки кода; (2) стабильность тест-эталонов (менять дефолты = сдвигать «правильное» по всей eval-сьюте); (3) способ отложить **продуктовое решение** там, где поведение спорное.

---

## Ядро — включено по умолчанию (доказано паритетом, работает у всех)

| Флаг | Что делает |
|---|---|
| `TURN_PLANNER_ON` | Один плановый вызов вместо цепочки классификаторов |
| `DIALOG_FOCUS_LLM_CLASSIFY_ON` | Перенос фокуса между ходами |
| `LEAD_TURN_LLM_CLASSIFY_ON` | Серая зона намерения оставить контакт |
| `BOOKING_INTENT_LLM_ON` | Намерение «записаться» |
| `PRICE_INTENT_LLM_ON` | Ценовое намерение |

**C1 (removed orphan flags):** `COMPOSER_ON`, `FULLCTX_ON`, `QUERY_REWRITE_*`, `ANSWER_PACKET_ASSEMBLER_ON`, `LIVING_OVERVIEW_ON`, `SITUATION_PRICE_ON`, `PRICE_SYMPTOM_CONSULT_ON` — deleted from `config.py`; legacy packet/retrieval code removed. Target FullContext does not read them.

**C2d-D2 (canonical pricebook):** product path reads only `pricebook/services/*.json` — no `prices.json` / `price_offers.json` loaders; orphan `patient_playbook` / `answer_lens` / `service_node` / `numeric_fact_gate` modules removed.

**C2e (cleanup-series complete):** final orphan legacy removed — `aspect_arbitration`, `consult_nudge`, `retrieval_candidate`; `answer_planner` legacy plan API pruned; active path remains FullContext + `detect_aspects` only.

Эти в консоли включать не надо — они и так ON.

---

## Target FullContext product authority (S61 / S65 / S69)

**S69 (owner-approved, completed):** legacy product answer chain удалён. `/ask` и `/ask/stream` **всегда** идут только через target FullContext. Kill-switch `TARGET_FULLCONTEXT_DEV` и legacy RAG/chunk/composer dispatch **удалены** — отката на legacy path нет.

**S65 (owner-approved):** product authority передана target FullContext по умолчанию.

**S67 (owner-approved):** legacy answer-production stack изолирован до S69.

**S68 (read-only):** inventory — `docs/S68_LEGACY_DELETION_INVENTORY.md`.

**Offline tests** используют fake/recording backends.

**FULLCONTEXT_PRESENTATION_PARITY:** governance @ `50c6cf9`; Phase 2 partial @ `7c716df`.

**FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE:** governance @ `7c716df` — Composer source
identity sidecar, contact PRIMARY_EVIDENCE, UI channel mutex, situation priority/HTTP tests,
`time`/`result_reliability` projection, fallback canonical phone. Seam audit:
`docs/evidence/presentation/FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE_SEAM_AUDIT.md`.
Partial implementation @ `84b2741`–`029c38b`.

**FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE:** COMPLETE @ `225ee56` — marketing-after-final-spec,
typed contacts, verifier observability, widget-faithful offline matrix.

**FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION:** COMPLETE @ `codex/stage-a`
(contact value-only verifier; scenario decouple; `turn_topic` chain; layer P/R/E/S matrix).

**FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE:** COMPLETE @ `525474c` — scenario-only aspects;
structured contacts (0 Boundary/Composer/Semantic); boundary uncertain degrade; verifier `client_id`;
terminal phone alignment. Seam audit:
`docs/evidence/runtime/FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE_SEAM_AUDIT.md`.

**FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY:** COMPLETE @ `d8dbe93` — planner-independent
`generic_fullcontext_content`; advisory `needs_clarification`; Medical Boundary before generic.
Seam audit: `docs/evidence/runtime/FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY_SEAM_AUDIT.md`.

**FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING:** COMPLETE @ `c4de72c` — typed
`service_availability`; ingress catalog-miss → normal; `structured_service_availability`.
Seam audit: `docs/evidence/runtime/FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING_SEAM_AUDIT.md`.

**FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE:** COMPLETE @ `a1dc4f2` — converge Scoped Evidence
and Composer Request on price-only offer source sufficiency; shared predicate; cross-turn tomography price
fixture. Seam audit:
`docs/evidence/runtime/FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE_SEAM_AUDIT.md`.

**FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING:** governance @ `a1dc4f2` — restore agreed existing-scan
fact in MD; Planner must not route own-scan FAQ to `service_availability`. Seam audit:
`docs/evidence/runtime/FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING_SEAM_AUDIT.md`.
Implementation **STOP** until PRE-CODE ✅ + owner GO.

**FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION:** governance @ `ce256c5` — post-Verifier CTA from
validated `primary_content_ref` only; generic `allow_cta=False` preserved. Seam audit:
`docs/evidence/presentation/FINAL_VERIFIED_PRIMARY_CONTENT_CTA_PROJECTION_SEAM_AUDIT.md`.
Implementation **STOP** until PRE-CODE ✅ + owner GO.

### A9 patient scope authority (A9R3 — unconditional post-closeout)

Patient-scope projection (`extent` / `jaw` / `stage`) and per-axis `EffectiveScope` merge are **always on** in product runtime. Temporary kill-switch `A9_PATIENT_SCOPE_AUTHORITY` removed @ FINAL_SCOPE_WIDGET_E2E_CLOSEOUT (`3adc0e7` governance → implementation).

| Setting | Value |
|---|---|
| `TURN_PLANNER_LLM_MODEL` | **`qwen3.7-plus`** (env override — обычная model config) |

`reported_context` остаётся diagnostic-only: не входит в product AC2 и session persistence.

**FINAL_SCOPE_WIDGET_E2E:** governance + offline pre-live @ `70a96c1`; live harness `evals/v5/run_final_scope_widget_e2e_live.py --dry-run`. Attempt #1 preflight-abort frozen.

**FINAL_SCOPE_WIDGET_E2E_RETRY1:** official live FAIL @ `d76870a`; rerun blocked.

**FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION:** COMPLETION ✅ @ `c670b96`; T2/T5 product correction landed. Forensic `_retry1_live_run_stdout.txt` verified and removed @ RETRY2 pre-live.

**FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT:** implementation COMPLETION ✅ @ `6b67e35`; `TargetComposerActionContext` wired to Composer directives/invocation; `price:None` fail-closed; offline T1–T8 pass.

**FINAL_SCOPE_WIDGET_E2E_RETRY4:** live AUTOMATED_PASS 8/8 + owner manual **PASS 8/8** @ `5ff9893`; immutable artifacts pinned.

**FINAL_SCOPE_WIDGET_E2E_CLOSEOUT:** **FINAL_SCOPE_CLOSEOUT_COMPLETE** ✅ — A9 kill-switch removed; unconditional patient-scope authority.

**FINAL_PRICE_AND_SERVICE_COVERAGE:** implementation COMPLETE @ `f5c5c96` — typed `family_prices.json` contract, deterministic family-only broad mode B, branches 1–3 verified via offline tests; rich demo unchanged.

**FINAL_PRICE_SCOPE_COVERAGE_NAV:** implementation COMPLETE @ `2b5e90d` — `applies_to_extents` on offers; AC2/AC3 filter anchors and scope-nav to confirmed price routes; `few_teeth` without route → data_gap.

**FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY:** implementation COMPLETE @ `19297fc` — one-hop navigable scope-nav; explicit `applies_to_extents` on demo prosthetics offers.

**FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY:** governance @ `19297fc` — seam audit + PRE-CODE; implementation **STOP** until PRE-CODE ✅.

**FINAL_CLIENT_PACK_DATA_CONVERGENCE:** Checkpoint B implementation complete — demo pack uses only
`target_response/**`; legacy root mirrors deleted; `scripts/validate_client_pack.py` +
`docs/CLIENT_PACK_AUTHORING.md` + `clients/_template` scaffold in place.

---

## Выключено по умолчанию — по причине, а не «недоделано»

### Проверенные гварды — включены по умолчанию (флип 2026-07-09/10)

Для demo-клиента включены насовсем: env-дефолт `"1"` (в `config.py`) + `clients/demo/features.yaml`.

| Флаг | Что делает | Ключей |
|---|---|---|
| `BOOKING_DATE_DEFER_ON` | Не подтверждать/не эхоить дату и слот записи | 2 (env + features.yaml) |

### A. Ждёт доработки/решения (технически работает, но есть нюанс)

_Удалено в C2c-dead-clarify:_ `CLARIFY_STATE_ON` / persistent `pending_clarify` session state (legacy modules deleted S69; target uses terminal clarify/defer only).

### B. В работе / не доказан паритет (единая карта 5.5)

_Удалено в C1:_ `SITUATION_PRICE_ON`, `LIVING_OVERVIEW_ON` (legacy price overview modules deleted).

### C. Переходные / кандидаты на уборку

| Флаг | Примечание |
|---|---|
| `ASPECT_PLANNER_LLM_ON` | Старый аспект-планировщик; по большей части заменён `TURN_PLANNER_ON`. Проверить и списать |

_Удалено в C1:_ `ANSWER_PACKET_ASSEMBLER_ON`.

---

## Канонный набор флагов для eval-прогонов

Чтобы красный в тесте означал настоящую проблему, а не «забыл флаг». Стандартный композер-прогон (PowerShell):

```powershell
$env:E2E_USE_TEST_CLIENT="1"; $env:PYTHONIOENCODING="utf-8"
```

**Кейсы, зависящие от доп. флагов** (без них краснеют «ложно»):

| Кейсы | Нужен флаг | Иначе |
|---|---|---|
| F1, F2 (коронка / на имплант) | — | target terminal clarify/defer (no persistent clarify state) |

(H2/H3, G1, brand-кейсы и симптом/дата-кейсы больше флагов не требуют — соответствующие гварды теперь дефолт-ON.)

⚠️ **Windows-засада:** `$env:` живут до закрытия окна PowerShell. Флаг от прошлого прогона «залипает» и даёт **ложные красные**. Перед контрольным прогоном — **новое окно** или явно погасить лишние флаги в `"0"`.

---

## Статус работы (крупными мазками)

**Закрыто (всё в main):** ядро на композере + вся база в контексте (старый RAG-поиск снесён), кэш базы, история диалога, один плановый вызов, детерминированные деньги/числовой гейт/промо-гейт, ситуационная цена. Паритет-гейт цен в CI. Медзона «цена→консультация» и «дата записи не обещается» — **дефолт-ON**.

**Закрыто 2026-07-09/10:**
- **Интент «НЕТ ОТВЕТА» полностью:** строгая услуга в цене (дефолт-ON), оффтоп hard-stop, педиатрия не ловит услугу-с-детской-ассоциацией, композер не выдумывает вне базы, базальная → политика (не обзор протоколов).
- **Ситуационный фокус цен:** оба defer'а (strict + symptom-consult) уважают ситуацию — «нет одного зуба → а сколько?» даёт цену за зуб, а не defer.
- **Бренд-фильтр + бюджетный якорь** (`BRAND_FILTER_ON`, дефолт-ON с 2026-07-10): закрыт долг S6; якорь **портируемый** (доступный = min-цена, рекомендованный = `recommended:true`, услуга-якорь из `features.yaml` — без брендовых литералов в коде).

**Осталось:**
1. Опц. усиление Impro-якоря в брифе («рекомендуем/пожизненная гарантия»).
2. **Исторический этап 7 — концерн-схемы** (см. [`archive/FULLCONTEXT_ROADMAP.md`](archive/FULLCONTEXT_ROADMAP.md)). Его старые product-правила не являются target-каноном; актуальный контракт — [`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md).
3. Вопросы доверия («врачи опытные?», «отзывы?») — через общий target planner/scenario и doctor/content sources, без отдельного thematic route.
4. Скорость/стриминг (крупно). Сложный расчёт («посчитайте 3 зуба») — беклог.
   **FINAL_RESPONSE_LATENCY_OBSERVABILITY / PERF-0** implementation **COMPLETE** @ `228ee28` — per-stage
   timing marks (Ingress/Planner/Boundary/Composer/verifier_deterministic/verifier_semantic/widget) live
   in `core/turn_timing.py`, no answer/route/LLM-call-count change. Seam audit:
   `docs/evidence/performance/FINAL_RESPONSE_LATENCY_OBSERVABILITY_SEAM_AUDIT.md`.
   **FINAL_EARLY_SSE_STATUS_STREAMING / PERF-1** implementation **COMPLETE** @ `aa633f2` — `/ask/stream`
   emits honest early `event: status` before orchestration starts, via a bounded background worker
   (admission `Semaphore` + `ThreadPoolExecutor`) with a safe synchronous fallback under overload; `/ask`
   and LLM call count unchanged. Seam audit:
   `docs/evidence/performance/FINAL_EARLY_SSE_STATUS_STREAMING_SEAM_AUDIT.md`.
   **FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS / PERF-2** implementation **COMPLETE** @ `897cdb7` —
   typed-contract deterministic bypass of Medical Boundary's one blocking LLM call for **governed UI
   scope/stage clicks only** (`bypass_governed_ui`) — the one category provably safe by construction
   (session-bound ref-whitelist, deterministic TurnFrame, structurally cannot carry free text). Pure
   free-text price lookup and exact FAQ audited and kept `required` — the typed capabilities needed to
   make them safe do not exist yet. Verifier remains unconditional after any bypass. Seam audit:
   `docs/evidence/performance/FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS_SEAM_AUDIT.md`.
   **FINAL_PROVIDER_PROMPT_CACHE_PREWARM / PERF-3** (governance @ `897cdb7`) — четвёртый этап: можно ли
   безопасно и измеримо прогревать provider prompt cache для статических Composer/Verifier-префиксов.
   Seam audit доказывает **prefix identity** из кода (Composer и Verifier — доказанно разные namespaces,
   расходятся с первого символа system-сообщения); TTL и реальное cache-hit поведение provider'а остаются
   неизвестными без live-вызова. Выбран вариант **только B** (owner-controlled CLI перед demo/deploy) —
   automatic startup prewarm (C) отложен в отдельный future milestone до измеренных результатов CLI, без
   изменений `app.py`. С двумя воротами: owner GO на implementation CLI, и отдельное owner LIVE/LLM
   разрешение перед первой `--live` активацией. Seam audit:
   `docs/evidence/performance/FINAL_PROVIDER_PROMPT_CACHE_PREWARM_SEAM_AUDIT.md`.
   Implementation shipped (CLI + offline tests, @ `f8db2e0`). Owner LIVE/LLM GO ran exactly one live
   attempt (`perf3-demo-2026-07-30-01`, @ `64fd54c`/`61cd93e`): 2/2 calls completed, `cached_tokens=0` on
   both (expected — first-ever warm, nothing previously cached). Gate closed back to blocked after the one
   attempt; the marker is committed as immutable evidence so replay stays blocked. **A subsequent real
   request still showed Composer/Verifier `cached_tokens=0`** — the practical cache-hit benefit has **not**
   been demonstrated; automatic startup prewarm (Option C) remains deferred/not recommended. See
   `docs/evidence/performance/PERF3_PROMPT_CACHE_PREWARM_LIVE_ATTEMPT_AUDIT.md` and TASK.md's PERF-3
   completion records.
   **FINAL_PARALLEL_INGRESS_PLANNER_LATENCY / PERF-4** (Phase 1 governance @ `61cd93e`) — real request
   ("Что такое костная пластика?", 18.2s total) showed Ingress 3.4s + Planner 3.8s running sequentially
   though both only need the original question. Seam audit proves the compute/publish split is clean
   (`plan_turn_attempt` touches zero `request.ctx`; Ingress's own LLM path does, so Ingress stays
   untouched) and selects **Variant C** (parallelize only Planner's pure compute, never merge the two
   contracts) — flags the nested-executor deadlock hazard against PERF-1's `_sse_worker_executor` as the
   most important risk to avoid in Phase 2. Seam audit:
   `docs/evidence/performance/FINAL_PARALLEL_INGRESS_PLANNER_LATENCY_SEAM_AUDIT.md`.
   **Implementation COMPLETE** (Phase 2, owner GO): Planner's compute forks into a dedicated bounded
   executor via an additive `on_llm_path` hook on `classify_ingress` (invoked only immediately before its
   own real LLM call); publish stays unchanged in the main thread. Ships **inert by default**
   (`PLANNER_SPECULATION_CAPACITY=0`) — real concurrent-call activation is a separate, later owner step,
   mirroring PERF-3's two-gate pattern; this was chosen after finding several pre-existing tests assumed
   `run_pre_resolver_turn` alone could never reach Planner. 31 new tests + 520-test regression sweep, zero
   real-network calls. See TASK.md's PERF-4 Phase 2 completion record.
   **FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS / PERF-5** (Phase 1 governance @ `2fe7437`) — шестой
   этап: можно ли ускорить генерацию Composer и улучшить конверсию через адаптивную soft-длину
   ответа, без hard truncation, без retry-по-длине и без изменения Verifier policy. Seam audit
   подтверждает, что Verifier сегодня полностью «length-blind» (ноль length-related проверок),
   а единственный существующий прецедент структурного управления — стейдж-условный оверлей
   `broad_family_price_compact`/`max_price_anchors`. Выбран вариант **A + E** (soft-budget
   директива в Composer + структурный outline: прямой ответ → 2–4 факта → условия → next-step),
   явно **не** C (обрезание готового текста — рвёт `must_preserve_exact`/numeric grounding) и
   **не** D (retry на обычном пути). Определён typed contract `TargetResponseLengthProfile`
   (7 профилей) и единственный producer `select_target_response_length_profile` в
   `core/target_response_policy.py`; корректность всегда важнее бюджета — обязательный факт
   никогда не режется ради лимита. Seam audit:
   `docs/evidence/performance/FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS_SEAM_AUDIT.md`.
5. Гигиена: красные playbook-тесты не в CI, мёртвый `core/claim_gate.py`, ветка `feature/controlled-composer`.
6. **FINAL_TEST_SUITE_CONVERGENCE (governance @ `1980ab7`):** 185 wide failures inventoried; TSC-A..D checkpoints defined. See `docs/TEST_SUITE_ARCHITECTURE.md`, `docs/evidence/testing/final_test_failure_inventory.json`. Implementation blocked until owner GO.
7. **FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT (governance @ `9073a22`, read-only):** demo
   client pack token/char inventory (13 layers) + duplicate/conflict candidate scan (exact/near/
   structured methods, no embeddings/LLM). Found: 5 `EXACT_DUPLICATE` + 2 `INTENTIONAL_DUPLICATE` +
   10 `NEAR_DUPLICATE` offer-package-text candidates (~1,609 chars / ~402 tokens safe potential
   savings), zero structured duplicates/conflicts across authority (contacts/doctors/marketing-facts
   scans all clean). Confirms cached FullContext (107,980 chars) is transmitted in full by both
   Composer and Verifier static prefixes independently (116,571 / 114,719 chars) — a known
   architecture fact, not a client-pack defect. See
   `docs/evidence/client_pack/FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT.md`. **NO CLIENT/PRODUCT
   CHANGE.** Phase 2 cleanup/tooling not started; STOP until owner GO.
8. **FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW / PERF-6:** governance (design) @ `c0dfde6` →
   **Phase 2 shadow implementation COMPLETE**, owner GO. `contracts/target_context_scope_decision.py`
   + `core/target_context_scope_resolver.py` (`service_exact → topic → context_group → full`,
   fail-closed to `full` on any exception) + `core/target_context_scope_shadow.py`
   (post-verification comparison against the post-validation source identity, log-only). Hook wired
   into `core/target_policy_bound_verified_response_pipeline.py` (moved one level up from the
   Phase-1 sketch — the originally-targeted file is protected by an S39 "exact straight-line" AST
   test; documented deviation in TASK.md). Real demo decisions: `service_exact` 94.9–98.4% smaller
   than the 26,995-token full corpus, `topic` 46.4–97.7% smaller depending on topic size,
   synthetic `context_group` fixture proven at 86.2% smaller (structurally unreachable on the real
   demo pack — no `context_groups.json`). Real Composer/Verifier **still receive the full corpus
   unconditionally on every turn — no speedup yet**, proven by test (call counts, invocation
   content, output all unchanged; `clients/demo/**` untouched, SHA-256 verified). See
   `docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md` and TASK.md's
   PERF-6 Phase 2 completion record. **NO CLIENT-PACK CHANGE. NO LIVE.** STOP before authored
   `context_groups.json` and before any real Composer/Verifier switch.
9. **FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION / PERF-7 (governance + seam audit @ `2d0769c`,
   read-only):** owner directs a simpler target shape than PERF-6's ladder — one
   `EvidencePackageBuilder` over independent sources (existing `evidence_blocks`, exact content
   refs, structured offers/facts/doctors/contacts, session projection, lexical MD retrieval,
   FullContext fallback), not a deeper `service_exact/topic/context_group/full` ladder;
   `context_groups.json` still not created. Critically re-audited PERF-6's own shipped debt: 5 of 7
   named items **PROVEN** real gaps (false-positive `shadow_hit` on missing source identity;
   "any offer/doctor present" instead of exact required source at `topic`/`context_group` tiers;
   token estimate counts only MD, never offer/fact/doctor/policy JSON; non-deterministic
   `context_group` selection via unordered `set` iteration; unconditional per-turn shadow overhead
   with no flag gate), 1 structural-not-a-bug (source coverage ≠ answer equivalence), 1 accepted
   disclosed gap (`context_group` unreachable on demo). Local `sqlite3` FTS5/`bm25()` capability
   proven available and functional by direct offline probe (no product code, no network); selected
   **Option A — simple in-memory Python token-overlap lexical scan** over FTS5 as the simplest
   sufficient option for 55–150 short MD, with FTS5 documented as a ready fallback only if future
   measurement proves it necessary. Designed (not built): generated paragraph index reusing
   already-authored `doc_id`/`doc_type`/`topic` frontmatter, typed `TargetEvidencePackage` contract,
   exact-ID completeness rules, FullContext-before-single-call fallback, explicit-follow-up-only
   session projection, and a two-mode offline evaluation plan (package eval; separately-gated
   counterfactual Composer eval, no raw question/answer persistence ever). See
   `docs/evidence/performance/FINAL_LOCAL_EVIDENCE_PACKAGE_BUILDER_FOUNDATION_SEAM_AUDIT.md`.
   **NO PRODUCT CODE. NO CLIENT-PACK CHANGE. NO LIVE.** STOP before PERF-7A (lexical index
   implementation).
   **PERF-7A implementation COMPLETE** (`core/target_lexical_paragraph_index.py`, owner GO): pure
   in-memory paragraph index + token-overlap/prefix lexical search over client MD, unwired.
   **PERF-7B implementation COMPLETE** (`contracts/target_evidence_package.py` +
   `core/target_evidence_package_builder.py`, owner GO): one canonical, unwired
   `build_target_evidence_package` combining exact `evidence_blocks`, conservative lexical
   widening (exact-token-match bar, ambiguous-tie fallback, no invented confidence score),
   explicit-only session projection, and FullContext fallback into one typed
   `TargetEvidencePackage`. Neither module is imported by any runtime path (`app.py`, Composer,
   Verifier, pipeline, `TurnFrame`, `session.py`) — proven by `git grep`-restricted-to-imports
   tests. Real Composer/Verifier still receive the full FullContext corpus unconditionally via
   PERF-6's own unchanged shadow hook — **no speedup exists yet from PERF-6, PERF-7A, or PERF-7B**.
   See TASK.md's PERF-7A/PERF-7B completion records. **NO CLIENT-PACK CHANGE. NO LIVE.** STOP
   before PERF-7C (offline package evaluation).
   **PERF-7C offline package evaluation — CORRECTED, verdict `PERF7C_LEXICAL_RELEVANCE_DEFECT_
   FOUND`** (owner GO for the eval, then a separate owner GO for the correction): 118 synthetic
   scenarios across 18 classes run through the real, unmodified `build_target_evidence_package`.
   An original `PERF7C_OFFLINE_PACKAGE_EVAL_PASS` verdict was **withdrawn** after independent review
   found a circular-evaluation defect — 10 scenarios (treatment-plan-from-another-clinic,
   cross-topic, unknown-wording classes) had their "expected" lexical target set to whatever the
   search function actually returned rather than to what the question's meaning and canonical
   demo-pack authority require, so a topically irrelevant confident match (e.g. a "plan from
   another clinic" question resolving to a page about 3D/AI diagnostic technology) was graded as
   correct. Corrected: `critical_false_narrow_count = 10`, zero session contamination, zero
   structured-ID mismatch, zero Builder exceptions — the defect is entirely in the evaluation's own
   expectations/scoring logic, not in `core/target_evidence_package_builder.py` or
   `core/target_lexical_paragraph_index.py`, **neither of which was touched by this correction**.
   See TASK.md's PERF-7C eval-correction completion record and
   `docs/evidence/performance/PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md`. **NO PRODUCT CHANGE. NO
   CLIENT-PACK CHANGE. NO LIVE/LLM/NETWORK. No speedup exists yet anywhere.** STOP before any
   Builder/lexical-index correction, before PERF-8, and before any counterfactual
   FullContext-vs-Scoped-Composer evaluation.
10. **FINAL_RETRIEVAL_RELEVANCE_DECISION / PERF-8 Phase 1 —
    `EMBEDDINGS_EVALUATION_JUSTIFIED`:** 49 retrieval-dependent scenarios compared the current
    token-overlap baseline, an IDF-weighted conservative prototype, and local FTS5/BM25. Current
    lexical produced 11 critical false-narrow results. Conservative prototypes produced zero on
    the same development matrix only with 85–88% fallback and thresholds tuned on that matrix;
    therefore neither is authorized for runtime. Local embeddings were `NOT_EVALUATED` because no
    repository-configured offline model artifact exists. **No runtime candidate, no product/client
    change, no speedup.** See TASK.md and
    `docs/evidence/performance/FINAL_RETRIEVAL_RELEVANCE_DECISION_AUDIT.md`. STOP before a separately
    approved embeddings/hybrid holdout evaluation and before Scoped Composer wiring.

11. **PERF-9 QWEN EMBEDDINGS HOLDOUT — FAIL, NO RUNTIME CANDIDATE:** the 60-question blind holdout
    and independent gold were frozen at `27c8340`; development thresholds were committed at
    `9273630` before the one holdout run. Qwen dense returned 4 critical false-narrow decisions
    (Recall@1 81.3%, fallback 51.7%); Qwen dense + local lexical RRF returned 2 (Recall@1 72.9%,
    fallback 75.0%). Binding safety bar is zero, so neither may be wired to Scoped Composer.
    Runtime/client pack are unchanged, LIVE gate is closed, and no speedup exists. All inference
    remained Alibaba Qwen `text-embedding-v4`; no Western model was used. See
    `docs/evidence/performance/PERF9_QWEN_EMBEDDINGS_HOLDOUT_DECISION.md`.

⚠️ **Мёртвый конфиг (найдено 2026-07-10):** блок `limits:` в `clients/demo/marketing.yaml` (`max_text_ingredients`, `max_cta`, `promo_cooldown_turns`, `proof_cooldown_turns`) грузится, но **нигде не применяется**. Работают только `blocked_aspects_for_promo` и `service_marketing`. Разбор — в Этапе 7.

---

*Обновлять при добавлении/переключении флага или закрытии крупного блока. Дефолты — в `config.py`.*
