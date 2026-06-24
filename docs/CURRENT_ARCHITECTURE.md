# Текущая архитектура бота

**Статус:** фактический runtime (multiclient M1–M4 локально).  
**Целевое / ops:** `MULTICLIENT.md`.  
**Обновлено:** 2026-06.

---

## 0. Multiclient

| Реализовано | Ещё не prod |
|-------------|-------------|
| `clients/{id}/` — md, catalog, **pricebook/**, policies, tone, features | Контент nikadent / финализация cesi |
| `data/{id}/` — corpus, embeddings, aliases, `bot.db` | VPS deploy (Caddy, wildcard TLS) |
| `core/client_runtime.py`, `client_data_loader.py` | `allowed_origins` — домены сайтов клиник |
| `meta_loader`, `doctors_lookup` → только pack md | Golden evals per `client_id` |
| Host → `client_id` (prod `*.bot.*`) | |
| Origin guard (`core/origin_guard.py`) | |
| Per-client system prompt (`core/llm_system_prompt.py`) | |
| Leads: demo stub / email (`lead_service`, `lead_config.yaml`) | |
| Admin + PG (`admin_dashboard/`, `pg_sink.py`) | |
| Legacy `md/`, `clients/default/`, общий `data/corpus.jsonl` | **удалены** |

API: `client_id` в body/query; alias `default` → pack `demo`. `DEFAULT_CLIENT_ID=demo`.

---

## 1. HTTP-роуты

| Роут | Назначение |
|------|------------|
| `POST /ask` | Основной диалог |
| `POST /ask/stream` | SSE |
| `POST /lead` | Заявка (режим из `features.yaml`) |
| `GET /api/widget-config` | Конфиг embed |
| `GET /dashboard` | JSONL mini-dashboard (prod: 404) |

Debug: `/_debug/ping`, `/__debug/retrieval` — prod: 404 или token.

---

## 2. Пайплайн `/ask`

```
ingress / rate limit → flow_handlers → ref / continuation
→ Resolver (или classify_intent при RESOLVER_OFF=1)
→ contacts overlay → route_source (A3) → price_flow / retrieval (pool → rerank → arbiter)
→ chunk_responder: LLM → answer slots + price append → policy → session → JSON
```

На chunk-пути **детерминированная сборка** (без второго LLM): слоты из frontmatter, затем `generator_append_text` (legacy append) или полный price-ответ из PriceBook (`service_reply`), потом policy/CTA. Content retrieval: §4.5.

Детали маршрутов: `ROUTING_MAP.md`.

---

## 3. Модули

| Модуль | Роль |
|--------|------|
| `app.py` | HTTP, `_orchestrate_ask_turn` (тонкая склейка), dispatch |
| `orchestration/finalize_turn.py` | `finalize_ask`, telemetry route, bot events |
| `orchestration/pre_resolver_turn.py` | ingress, flows, guards до Resolver |
| `orchestration/resolver_turn.py` | Resolver + scope topic candidate (без parallel classify_intent) |
| `orchestration/lead_flow.py` | lead payload + flow → `AskOrchestrationResult` |
| `orchestration/policy_compat.py` | `apply_response_policy` signature shim |
| `orchestration/route_guards.py` | pre-Resolver guards (noise, duplicate, anti-spam, continuation clarify payload) |
| `orchestration/ask_turn.py` | post-Resolver: contacts → A3 → price fallback → content arbiter → selection |
| `orchestration/price_flow.py` | A3 `price_ref` / concern / unit clarify; PriceBook assembler или legacy append |
| `orchestration/catalog_flow.py` | A3 doctor list + catalog facts + md priority |
| `orchestration/retrieval_flow.py` | content arbiter path + legacy selection fallback |
| `orchestration/helpers.py` | decision_dump, scope ctx, price line, guided menu, selection log |
| `core/client_host.py` | Host → `client_id` (prod) |
| `core/origin_guard.py` | Origin/Referer vs `allowed_origins` |
| `core/startup_check.py` | Старт: артефакты `data/{id}/` |
| `ingress_gate.py` | Noise/offtopic до Resolver |
| `flow_handlers.py` | Lead, situation, **explicit booking (regex)**, «да» по pending |
| `policy.py` | CTA/UX; `booking_intent()` (regex + опц. LLM) **только для policy**, не lead gate |
| `resolver.py` | `DecisionFrame` + safety-net |
| `source_routing.py` | A3: doctor, catalog, price; commercial→content downgrade (см. §6) |
| `doctors_lookup.py` | Врачи из `clients/{id}/md/` |
| `query_selector.py` | Catalog/price match, regex price hints; unified pool + rerank hook |
| `core/candidate_builder.py` | Metadata boosts, alias→pool merge, facet guards, `selected_source` |
| `core/retrieval_rerank.py` | LLM rerank gate + fail-open; alias-strong skip (H3.1) |
| `retriever.py` | RAG embed/search; `llm_rerank` — deprecated shim → `retrieval_rerank` |
| `core/metadata_first_observability.py` | Metadata-first + retrieval pool telemetry (`meta.metadata_first`, events) |
| `core/answer_slots.py` | Слоты ответа из frontmatter service-md |
| `core/pricebook_loader.py` | `clients/{id}/pricebook/`: manifest, facts, services |
| `core/price_answer_assembler.py` | Детерминированная сборка price-ответа (S1–S8, `PRICEBOOK_V2.md`) |
| `core/price_offers.py` | Legacy offers + brand/unit detect; делегирует в PriceBook при наличии entry |
| `arbiter.py` / `content_arbiter.py` | Выбор ref при 2+ кандидатах (LLM arbiter, без score-margin skip) |
| `chunk_responder.py` | Chunk → LLM → slots + price append → policy; merge `price_offer_meta` в `meta` |
| `contracts/ask_orchestration.py` | `AskOrchestrationResult` (+ `generator_append_text`, `price_offer_meta`) |
| `session.py` | SQLite `data/{id}/bot.db` |
| `lead_service.py` | Email + PG |
| `pg_sink.py` | Async PG events |
| `admin_dashboard/` | Read-only admin UI |
| `contracts/`, `core/routing.yaml` | Схемы, пороги |

Legacy (не расширять): `llm.classify_intent`, `query_selector.select_catalog_content_route` — см. `DEPRECATED.md`.

---

## 4. Resolver

- Основной путь: `resolver.resolve()` → `DecisionFrame`
- Модель: **`qwen3.7-plus`** (`config.RESOLVER_MODEL`, override `MODEL_RESOLVER`)
- Bypass: env **`RESOLVER_OFF=1`** → `classify_intent`
- Contacts: regex overlay в `orchestration/ask_turn.py` (после Resolver, до A3)

### Booking / lead (pre-Resolver)

- **Lead сразу:** только `explicit_booking_intent()` — regex `BOOKING_INTENT_RE` в `flow_handlers` (кнопка `lead:booking`, pending «да» — отдельно). Pre-Resolver **booking LLM** для lead gate **убран** (см. `TECH_DEBT.md` «Закрыто»).
- **Не lead до Resolver:** контентные фразы с «хочу» без явной записи; мягкая запись («можете принять сегодня?») → Resolver / ingress / content.
- **`booking_intent()`** в `policy.py` — подсказка CTA после ответа; может вызывать flash-LLM, **не** перехватывает ход и **не** классифицирует слоты (имя/телефон).

Целевое поведение lead-flow — § **Lead flow v2** ниже. Текущий runtime частично расходится (slot-first, overlay только на chunk-path) — см. `TECH_DEBT.md` → **Lead flow v2**.

### Lead flow v2 — состояния

Три режима (не только `lead_flow: true/false`):

| Режим | Сессия | Поведение бота |
|-------|--------|----------------|
| **CONSULT** | нет active lead | Обычный диалог: Resolver → content / price / contacts |
| **LEAD_ACTIVE** | `lead_intent` ∈ collecting_name / collecting_phone / confirming_name | Сбор слотов; turn классифицируется **до** slot retry |
| **LEAD_PAUSED** | `lead_paused` + `lead_resume_step` | Ответ как в CONSULT + bridge и кнопки «Продолжить / Отменить» |

Refs: `lead:booking`, `lead:pause`, `lead:resume`, `lead:cancel` (`lead_interrupt.py`, `flow_handlers.py`).

### Lead flow v2 — UX (exit: доступен vs предложен)

**Принцип:** отмена **всегда доступна текстом** на любом шаге; кнопки exit **не обязаны** быть на каждом экране.

| Экран / момент | Что показываем | Что бэкенд понимает текстом |
|----------------|----------------|----------------------------|
| **Первый экран** после «хочу записаться» / `lead:booking` | Только вопрос про имя. **Без** «Отменить» / «Не сейчас» | «не хочу», «передумал», «не сейчас», «отменить» → выход в CONSULT |
| **LEAD_ACTIVE**, сбор имени/телефона** | По умолчанию без exit-кнопок; «Задать вопрос» — **не** на первом экране (добавлять по метрикам застревания) | cancel-синонимы; content-фразы (цена, адрес, страх); опционально «задать вопрос» / «сначала вопрос» → pause |
| **После сопротивления, retry, content** | Опционально QR «Задать вопрос» | то же |
| **LEAD_PAUSED**, после content-ответа | Bridge + **«Продолжить запись»** + **«Отменить запись»** (обязательно) | `lead:resume` / `lead:cancel` + текстовые синонимы |

**Не смешивать** в одной реплике бота: content-ответ и повтор «как вас зовут». Имя — только после `resume` или на шаге slot.

**Класс `defer`** («надо подумать», «подумаю»): мягкий выход в CONSULT без агрессивного slot retry («Хорошо, без спешки…»).

### Lead flow v2 — порядок обработки turn (LEAD_ACTIVE)

**Главное правило:** любое сообщение в lead-flow — **сначала намерение пользователя**, **потом** кандидат в слот. Slot retry — **последний** resort, не default.

```
LEAD_ACTIVE turn
  1. ref / meta command     (lead:pause | lead:cancel | lead:resume)
  2. explicit cancel        (regex + синонимы; всегда, без кнопки)
  3. explicit meta_pause    («задать вопрос», «сначала вопрос» — текст и ref)
  4. high-confidence slot   (accept_lead_name / extract_phone)
  5. content interrupt      → pause + обычный пайплайн (price / contacts / retrieval)
  6. defer                  → мягкий выход
  7. unclear                → мягкий retry: «Напишите имя или задайте вопрос» (+ опц. QR pause)
```

**Content interrupt** (детерминированно, до gray-zone LLM): `contacts_intent`, `price_intent`, явный вопрос (`?`, префиксы «подскажите…», «а больно/сколько/где…»), страх/боль (расширить beyond текущего `lead_interrupt`).

После content-ответа: **единый lead overlay** (bridge + resume/cancel QR) на **всех** маршрутах ответа (chunk, price, contacts) — не только `chunk_responder`.

### Lead flow v2 — классификация: LLM vs deterministic

| Класс | Примеры | Слой |
|-------|---------|------|
| Meta cancel | «не хочу», «передумал», «отменить запись» | regex / ref |
| Meta pause | `lead:pause`, «задать вопрос» | ref + короткие синонимы |
| Slot | «Мария», «+7…», «меня зовут Олег» | `name_gate.accept_lead_name`, `extract_phone` |
| Content (явный) | «сколько стоит», «адрес», «а больно?» | `lead_interrupt` + policy intents → pause |
| Content (gray) | «я переживаю», «дорого наверное», «надо подумать» | **structured mini-classifier** (Pydantic, temperature 0) — только если шаги 1–5 не сработали |
| Unclear | шум, «не знаю», низкий confidence classifier | мягкий retry, **не** «напишите имя» |

**Не использовать LLM для:** ref-кнопок, телефона, очевидного имени, явного cancel/pause, pre-Resolver lead gate (`explicit_booking_intent`).

**Fail-loud:** не «чинить» вывод classifier пост-hoc regex по тексту запроса; при `confidence` ниже порога из `routing.yaml` → `unclear`.

Целевой контракт turn (новый слой, `contracts/`):

```python
LeadTurnDecision.kind ∈ slot | meta_pause | meta_cancel | meta_resume | content | defer | unclear
LeadTurnDecision.content_hint ∈ price | contacts | pain | generic | None  # при kind=content
```

Модули (целевое разделение): state machine — `session` + `flow_handlers`; classifier — `lead_interrupt` → `core/lead_turn_classifier.py`; overlay — после `finalize_turn`, не только в `chunk_responder`.

### Lead flow v2 — связь с остальным пайплайном

- **Pause + content:** `bind_lead_context_turn(interrupt_kind=…)` → тот же Resolver / A3 / price_flow / retrieval, что и в CONSULT.
- **Planner-lite (этап 4):** subject/aspect для follow-up **в PAUSED**, не заменяет lead turn classifier.
- **Policy CTA:** `booking_intent()` после ответа — отдельно от lead-flow; не дублировать payment/promo в bridge paused lead.

Eval (целевое): `evals/v5/lead_turn_golden.json` — кейсы cancel/pause/content/defer/unclear + smoke из реальных застреваний (имя vs «боюсь боли» vs «не хочу записываться»).

### Follow-up & compatibility guard (этап 4a)

**Runtime (demo):**

- **Session focus:** `last_subject` `{ service_id, topic, label, last_route }`, `subject_turn_age`; пишется после content-ответа (`chunk_responder._persist_subject_focus`); сброс в `exit_lead_flow` / `clear_last_subject`.
- **Rewrite:** `core/follow_up_rewrite.py` — шаблон «а гарантия?» + focus → «гарантия на {label}»; используется в retrieval (`query_selector`) и arbiter guard.
- **Compatibility guard:** `core/compatibility_guard.py` — relevance(rewritten) + conflict (другая услуга); clinic/warranty/contacts **не** conflict; `doc_type` — boost only (`routing.yaml` → `follow_up.doc_type_boost`).
- **`follow_up_mode`:** `effective_scope_topic=None`, skip `alias_topic_guard` (`candidate_builder`); telemetry в `debug_meta`: `follow_up_rewritten`, `focus_used`, `guard_pass_reason`, `compat_score`.

Eval: unit — `tests/test_follow_up_*.py`, `tests/test_compatibility_guard.py`; E2E — `evals/v5/follow_up_golden.json` + `run_follow_up_eval.py`.

Optional позже: flash rewrite gray zone; `clients/{id}/aspect_routing.yaml`.

### Planner-lite (этап 4b)

**Runtime (demo):**

- **План:** `core/answer_planner.py` — без LLM; вход: `DecisionFrame`, A3 `SourceRouteResult`, session `last_subject` / `last_aspect`; regex → `aspects` + append kinds.
- **Hook:** сразу после `route_source` в `orchestration/ask_turn.py` → `request.ctx["answer_plan"]` (до ранних return catalog/price).
- **Append:** `core/answer_plan_apply.py` — `price_offer` (catalog), `payment_terms` (`clinic__info__payment_terms.md#korotko`); `boundary` в контракте, не в MVP append.
- **Dedup:** если price append / `price_offers_applied` уже содержит этапы оплаты — `payment_terms` suppress.
- **Session:** `last_aspect` отдельно от `last_subject` (telemetry текущего хода); **`clear_focus_context()`** сбрасывает subject+aspect+age (`exit_lead_flow`, смена темы в follow-up).
- **Focus после price:** `persist_focus_from_service_turn` в `_service_reply` → `last_subject` для follow-up «а гарантия?».
- **Lead PAUSED:** planner на обычном content-path после classifier; lead overlay — по-прежнему в `finalize_turn`.
- **Принцип:** append только при явном aspect в **текущем** вопросе; при сомнении — молчать. Follow-up (4a) важнее одноходового composite.

Eval: unit — `tests/test_answer_planner.py`; E2E — `evals/v5/planner_golden.json` + `run_planner_eval.py`.

---

## 4.5. Content retrieval (Retrieval 2.0)

Путь `route_intent=content` после A3: embed search → **единый candidate pool** → опциональный LLM rerank → arbiter при 2+ ref.

| Slice | Модуль | Суть |
|-------|--------|------|
| **H1** unified pool | `core/candidate_builder.py` | `merge_alias_into_candidate_pool`: alias и embed-кандидаты в одном пуле; `infer_selected_source`; tie-break по score |
| **H2** alias channel | `candidate_builder`, `arbiter.py`, `helpers.py` | `alias_channel_suppressed_for_arbiter` — не дублировать alias-сигнал в arbiter, если winner уже из pool |
| **H3** rerank | `core/retrieval_rerank.py` | `evaluate_rerank_trigger` + `maybe_rerank_top`; пороги `routing.yaml` → `rerank`; fail-open |
| **H3.1** alias guard | `retrieval_rerank.py` | Пропуск rerank при сильном pack-alias в gray-zone; при skip — prefer alias на tie (`pool_top_when_alias_rerank_skipped`) |
| **H4** telemetry | `metadata_first_observability.py` | `RETRIEVAL_POOL_CTX_KEYS`, nested `retrieval_pool` в `meta.metadata_first` (E2E hook) |

**Порядок в `query_selector`:** build embed candidates → metadata boosts / soft filters → merge alias → rerank (если trigger) → winner → content arbiter.

**Eval:** `tests/test_retrieval_rerank.py`, `tests/test_alias_arbiter_channel.py`, `tests/test_metadata_first_observability.py`; product + golden suites.

**Долг:** metadata soft filter v2 (aspect-exempt) — `TECH_DEBT.md` § Metadata soft filter.

---

## 5. LLM-стек (пилот Qwen)

| Слой | Модель (default) | Env |
|------|------------------|-----|
| Generator | `qwen3.7-plus` | `MODEL_CHAT` |
| Arbiter | `qwen3.7-plus` | `MODEL_ARBITER` |
| Resolver | `qwen3.7-plus` | `MODEL_RESOLVER` |
| Ingress, rerank, rewrite, classifiers | `qwen3.6-flash` | `MODEL_INGRESS_CLASSIFY`, `MODEL_RERANK`, … |
| Embeddings | OpenAI `text-embedding-3-large` | `MODEL_EMBED`, `OPENAI_API_KEY` |

Chat: `DASHSCOPE_API_KEY` + `CHAT_BASE_URL` (DashScope / MaaS). Дефолты — `config.py`, `.env.example`.

---

## 6. Контент, цены и индекс

| Что | Где |
|-----|-----|
| MD (контент, не ₽) | `clients/{id}/md/` |
| Catalog, policies | `clients/{id}/service_catalog.json`, `clinic_policies.yaml` |
| **PriceBook v2** (суммы, сценарии S1–S8) | `clients/{id}/pricebook/` — `manifest.json`, `facts.json`, `services/*.json` |
| Legacy цены (fallback) | `price_offers.json`, `prices.json` — если нет pricebook entry (cesi/nikadent) |
| Индекс | `data/{id}/corpus.jsonl`, `embeddings.npy`, `alias_*` |
| Пересборка | `python build_index.py --client {id\|all}` |

**Demo:** суммы только в `pricebook/`; legacy `prices.json` / `price_offers.json` удалены. Спека: `PRICEBOOK_V2.md`, контракт `contracts/pricebook.py`.

### Answer slots (stage 2)

После Generator, до policy, `chunk_responder._apply_answer_slots_and_price_append` дописывает **абзацы** (порядок merge — `core/answer_slots.merge_deterministic_appends`):

1. Суть (LLM по одному чанку)
2. `clinic_note` (0–1)
3. `consult_value` (0–1) — при наличии поля **отключается** `consult_nudge` в промпте
4. `promo_note` (0–1) — только commercial intent (`price_lookup` или `COMMERCIAL_INFO_RE`); не на pain / contraindications / `price_concern` / safety-query / lead
5. **Price append** (0–1) — если оркестратор передал `generator_append_text` (этап 3)
6. CTA / follow-ups (policy)

Поля: `clinic_note`, `consult_value`, `promo_note`, `h3_overrides` в frontmatter; читает `meta_loader.py`, логика — `core/answer_slots.py`. Повтор одного слота на doc — cooldown (`answer_slots.cooldown_turns` в `core/routing.yaml`, per `doc_id` в session). Telemetry: `meta.answer_slots`. Eval: `evals/v5/answer_slots_golden.json`.

### Цены на `price_lookup` (PriceBook v2 + legacy)

**Порядок в runtime** (`core/price_offers.build_price_answer_for_lookup` → `orchestration/price_flow.py`):

1. Есть `pricebook/services/{service_id}.json` → **`assemble_price_answer`** — полный детерминированный ответ (intro, ₽, fact_refs, quick replies по сценарию). Без LLM по pricing-md (`price_answer_mode=offers_only`, `service_reply`).
2. Нет pricebook entry → **legacy:** chunk из `price_ref` (если есть в catalog) + LLM объясняет состав; **`build_price_append_for_lookup`** дописывает «Точные цены» / этапы из `price_offers.json` или `prices.json`.
3. Опционально **`price_brand_aliases.json`** — нормализация бренда в запросе.

**Неоднозначный unit** («сколько имплантация» без зуб/челюсть) → `price_lookup_clarify` / mini-summary + quick_replies.

**Intent vs commercial:** вопрос с явной ценой (`PRICE_LOOKUP_RE`) остаётся `price_lookup`, даже при `COMMERCIAL_INFO_RE`. Порядок: `query_selector._lookup_intent_by_rules` → сначала `PRICE_LOOKUP_RE`; в `source_routing._resolve_route_intent` downgrade в `content` не при `PRICE_LOOKUP_RE`.

**Telemetry** (`meta`): `price_offers_applied`, `price_offer_ids`, `price_offer_unit`, `price_offer_service_id`, `price_offer_brand_filter`; при PriceBook — также fact/scenario meta из assembler. Merge: `chunk_responder._merge_price_offer_meta_into_payload`.

**Остаток (долг):** тройной legacy-path, миграция catalog на `pricebook_id`, сценарии S2/S6 — `TECH_DEBT.md` § PriceBook v2.

Eval: `tests/test_pricebook_golden.py`, `evals/v5/price_offers_golden.json`, `scripts/lint_pricebook.py`.

---

## 7. Observability

- JSONL + `emit_bot_event` → optional PG (`BOT_PG_DSN`)
- Боевая админка: `DASHBOARD.md`, `admin.bot.artgents.ru`
- Demo: PG не обязателен (`features.yaml`)

---

## 8. Виджет

Контракт ответа: `WIDGET_ANSWER_FORMAT.md`. Конфиг: `clients/{id}/widget_config.json` + `brand.yaml` (мерж в `load_widget_config`).

### Embed на сайте клиники (prod)

Одна строка на внешнем сайте:

```html
<script src="https://{client_id}.bot.artgents.ru/static/widget/embed.js" defer></script>
```

`embed.js` (classic script):

1. `apiBase` ← `origin` URL скрипта (не из JSON конфига).
2. `clientId` ← `data-client-id` на `<script>` или поддомен до `.bot.` в host скрипта.
3. Shadow DOM (`#clinic-widget-root` → `attachShadow`) + `widget.css` внутрь shadow.
4. `GET {apiBase}/api/widget-config?client_id=…` → после ответа **перезаписать** `config.apiBase` и `config.clientId`.
5. `import({apiBase}/static/widget/widget.js)` → `mountWidget(mountRoot, config)`.

Повторная вставка `embed.js` на странице игнорируется (global guard).

### Ассеты (лого, аватар)

Сервер отдаёт **относительные** пути (`/static/clients/{id}/…` из `brand.yaml`). Runtime резолвит их через `config.apiBase` в `widget.js` (`resolvePackAssetUrl`) — не через домен сайта клиники.

### Изоляция стилей

| Слой | Механизм |
|------|----------|
| Сайт клиники → виджет | Shadow DOM + `:host { all: initial }` в `widget.css` |
| Клиент → клиент | Один `widget.css`, палитра через `config.theme` (`applyWidgetTheme`) |

### Безопасность embed

| Мера | Где |
|------|-----|
| `allowed_origins` per client | `clients/{id}/widget_config.json` |
| Origin/Referer guard | `/ask`, `/ask/stream`, `/lead`, `/api/widget-config`, `/api/video-catalog`, `/api/media/*` — `core/origin_guard.py` |
| CORS (браузер) | Те же пути + `/static/widget/*` — `core/widget_cors.py` |

`apiBase` в `widget_config.json` — справочное; для embed источник правды — URL `embed.js`.

---

При расхождении док ↔ код: **этот файл + код**; ops/domains — `MULTICLIENT.md`.
