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

⚠️ **Мёртвый конфиг (найдено 2026-07-10):** блок `limits:` в `clients/demo/marketing.yaml` (`max_text_ingredients`, `max_cta`, `promo_cooldown_turns`, `proof_cooldown_turns`) грузится, но **нигде не применяется**. Работают только `blocked_aspects_for_promo` и `service_marketing`. Разбор — в Этапе 7.

---

*Обновлять при добавлении/переключении флага или закрытии крупного блока. Дефолты — в `config.py`.*
