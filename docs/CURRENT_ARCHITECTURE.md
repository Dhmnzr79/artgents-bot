# Текущая архитектура бота

**Статус:** фактический runtime (multiclient M1–M4 локально).  
**Целевое / ops:** `MULTICLIENT.md`.  
**Обновлено:** 2026-06.

---

## 0. Multiclient

| Реализовано | Ещё не prod |
|-------------|-------------|
| `clients/{id}/` — md, catalog, prices, policies, tone, features | Контент nikadent / финализация cesi |
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
→ contacts overlay → route_source (A3) → retrieval + arbiter
→ chunk_responder → policy → session → JSON
```

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
| `orchestration/price_flow.py` | A3 price route + `price_lookup` intent fallback |
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
| `source_routing.py` | A3: doctor, catalog, price |
| `doctors_lookup.py` | Врачи из `clients/{id}/md/` |
| `query_selector.py` / `retriever.py` | RAG + rerank |
| `arbiter.py` / `content_arbiter.py` | Выбор ref при 2+ кандидатах (LLM arbiter, без score-margin skip) |
| `chunk_responder.py` | Chunk → LLM → **answer slots** → policy |
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

- **Lead сразу:** только `explicit_booking_intent()` — regex `BOOKING_INTENT_RE` в `flow_handlers` (кнопка `lead:booking`, pending «да» — отдельно).
- **Interrupt во время сбора:** contacts/price/`?`/префиксы → `paused`; QR **«Задать вопрос»** (`lead:pause`); resume явный; отмена — `lead:cancel` / «не сейчас».
- **Не lead до Resolver:** контентные фразы с «хочу» без явной записи; мягкая запись («можете принять сегодня?») → Resolver / ingress / content.
- **`booking_intent()`** в `policy.py` — подсказка CTA после ответа; может вызывать flash-LLM, **не** перехватывает ход.

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

## 6. Контент и индекс

| Что | Где |
|-----|-----|
| MD | `clients/{id}/md/` |
| Catalog, prices, policies | `clients/{id}/` |
| Индекс | `data/{id}/corpus.jsonl`, `embeddings.npy`, `alias_*` |
| Пересборка | `python build_index.py --client {id\|all}` |

### Answer slots (stage 2)

После Generator, до policy, `chunk_responder` дописывает **абзацы** из frontmatter service-md:

1. Суть (LLM по одному чанку)
2. `clinic_note` (0–1)
3. `consult_value` (0–1) — при наличии поля **отключается** `consult_nudge` в промпте
4. `promo_note` (0–1) — только commercial intent (`price_lookup` или `COMMERCIAL_INFO_RE`); не на pain / contraindications / `price_concern` / safety-query / lead
5. CTA / follow-ups (policy)

Поля: `clinic_note`, `consult_value`, `promo_note`, `h3_overrides` в frontmatter; читает `meta_loader.py`, логика — `core/answer_slots.py`. Повтор одного слота на doc — cooldown (`answer_slots.cooldown_turns` в `core/routing.yaml`, per `doc_id` в session). Telemetry: `meta.answer_slots`. Eval: `evals/v5/answer_slots_golden.json`.

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
