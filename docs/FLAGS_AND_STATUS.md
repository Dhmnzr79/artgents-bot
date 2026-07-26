# Флаги и статус проекта (фикс-реестр)

**Что это.** Единый сканируемый список: что за флаг, что делает, включён ли по умолчанию, и почему. Исторический подробный нарратив перенесён в [`archive/FULLCONTEXT_ROADMAP.md`](archive/FULLCONTEXT_ROADMAP.md); здесь — текущая короткая правда одним взглядом.

**Контекст (важно для трактовки флагов).** Это **локальная разработка**: нет прода, нет реальных клиентов, бот на localhost, один разработчик (Denis). Флаг здесь — НЕ ремень безопасности для клиентов (их нет), а: (1) переключатель для сравнения старого/нового поведения без правки кода; (2) стабильность тест-эталонов (менять дефолты = сдвигать «правильное» по всей eval-сьюте); (3) способ отложить **продуктовое решение** там, где поведение спорное.

---

## Ядро — включено по умолчанию (доказано паритетом, работает у всех)

| Флаг | Что делает |
|---|---|
| `SERVICE_SELECT_LLM_ON` | Модель выбирает услугу (чинит «generic → дорогой протокол») |
| `TURN_PLANNER_ON` | Один плановый вызов вместо цепочки классификаторов |
| `PATIENT_SITUATION_LLM_ON` | Распознавание ситуации пациента («нет зуба») смыслом, не регексом |
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

---

## Выключено по умолчанию — по причине, а не «недоделано»

### Проверенные гварды — включены по умолчанию (флип 2026-07-09/10)

Для demo-клиента включены насовсем: env-дефолт `"1"` (в `config.py`) + `clients/demo/features.yaml`. Env `="0"` остаётся kill-switch. «Ключей» = сколько выключателей надо, чтобы работало.

| Флаг | Что делает | Ключей |
|---|---|---|
| `PRICE_STRICT_SERVICE_ON` | Цена без явно названной услуги → честный defer, не выдуманная цена (уважает ситуационный фокус) | 1 (env) |
| `BOOKING_DATE_DEFER_ON` | Не подтверждать/не эхоить дату и слот записи | 2 (env + features.yaml) |
| `BRAND_FILTER_ON` | Бренд-фильтр + бюджетный якорь на ценовом пути имплантов: «корейские/нобель» → один бренд; «подешевле» → честный якорь (доступный + рекомендованный + платёж + консультация); прочее «дешевле» → тёплый fallback | 2 (env + features.yaml) |

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
$env:SERVICE_SELECT_LLM_ON="1"; $env:E2E_USE_TEST_CLIENT="1"; $env:PYTHONIOENCODING="utf-8"
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
5. Гигиена: красные playbook-тесты не в CI, мёртвый `core/claim_gate.py`, ветка `feature/controlled-composer`.

⚠️ **Мёртвый конфиг (найдено 2026-07-10):** блок `limits:` в `clients/demo/marketing.yaml` (`max_text_ingredients`, `max_cta`, `promo_cooldown_turns`, `proof_cooldown_turns`) грузится, но **нигде не применяется**. Работают только `blocked_aspects_for_promo` и `service_marketing`. Разбор — в Этапе 7.

---

*Обновлять при добавлении/переключении флага или закрытии крупного блока. Дефолты — в `config.py`.*
