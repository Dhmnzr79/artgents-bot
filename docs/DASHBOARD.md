# Дашборд и observability

**Статус:** активный контракт для боевых клиник.  
**Связь:** `MULTICLIENT.md` (M4–M5: PG + `admin_dashboard` для cesi/nikadent; demo — без PG или отдельно).

---

## Когда что нужно

| Режим | Postgres | Admin | Лёгкий `/dashboard` |
|-------|----------|-------|---------------------|
| **demo** (`features.yaml`: postgres off) | не обязателен | не нужен | достаточно для отладки |
| **боевая клиника** | **обязателен** (`BOT_PG_DSN`) | **обязателен** (`admin_dashboard/`) | запасной канал |

JSONL остаётся fallback при сбое PG и для локальной отладки.

---

## 1) Цель

Дашборд отвечает на вопросы:

- Бот сегодня работает нормально?
- Где и почему ошибается?
- Какие вопросы повторяются — доработка базы?
- Сколько лидов?
- Сколько стоит LLM?
- Какие диалоги требуют внимания?

---

## 2) Слои

- **Технический:** `bot_event` + JSONL-логи (`logging_setup.py`, `pg_sink.py`).
- **Продуктовый:** агрегаты в `admin_dashboard/` (диалоги, проблемы, лиды, cost).

---

## 3) Этапы

### Этап 1 — MVP (в коде)

1. События в PostgreSQL + JSONL (`BOT_PG_DSN`).
2. Таблицы: `bot_events`, `leads` (с `client_id`).
3. `turn_complete` с **redacted** полями (не raw PII).
4. `admin_dashboard/`: overview, dialogs, problems, leads, costs, events.

### Этап 2 — позже

Materialized views, `llm_calls`, ротация истории.

---

## 4) Контракт `bot_event`

- `kind = "bot_event"`, `event_type`, `schema_version`, `ts`, `request_id`, `sid`, **`client_id`**, `path`, `status`, `details`.

События: `user_turn_completed`, `bot_reply_completed`, `turn_complete`, `lead_submitted`, `llm_usage`, `llm_error`, `retrieval_selected`, `cta_shown`.

`retrieval_selected` — observability выбора чанка/ref (`orchestration/helpers.py`, `log_selection`). Это не embed-RAG. Событие `retrieval_fallback` снято вместе с RAG.

---

## 5) `turn_complete`

Обязательные `details`: `turn_number`, `user_text_redacted`, `user_preview_redacted`, `bot_text_redacted`, `intent`, `doc_id`, `route`, `low_score`, `lead_flow`, `handoff_filter`, `answer_chars`, `latency_ms`.

**PII (имя, телефон, текст «Расскажите о ситуации»):** на ходах `lead_flow` / `situation_collect` в PG/JSONL/Developer Mode **не хранятся** — placeholder + `pii_withheld: true` (`core/observability_pii.py`). Полные данные только email/CRM. Медицинские content-ходы — как раньше (redact только телефоны в тексте).

Stream: событие **после** финала ответа, не по дельтам.  
`route` задаётся в одном месте orchestration, не собирается постфактум.

**Retention (variant A):** `BOT_OBSERVABILITY_RETENTION_HOURS=24` — удаление всей `sid`, когда последний `bot_events.occurred_at` старше окна; SQLite-сессия тоже (`pg_retention.py`, фоновый worker при `BOT_PG_DSN`).

---

## 6) Admin API

Сервис: `admin_dashboard/` (порт `9100`).

- `GET /api/overview`, `/api/dialogs`, `/api/dialogs/<sid>/thread`, `/api/problems`, `/api/leads`, `/api/costs`, `/api/events`
- `GET /api/overview?period=today|week|month` — обзор за сегодня / 7 / 30 календарных дней UTC (то же `period` для `/api/costs`)
- `DELETE /api/dialogs/<sid>` — удалить **всю сессию** (sid): диалоги, заявки, ошибки; **`llm_usage` остаётся** (расход токенов)
- `POST /api/dialogs/<sid>/purge` — то же (использует UI)
- Фильтр **`?client_id=cesi`** на всех запросах
- `BOT_PG_DSN` обязателен; `ADMIN_DASHBOARD_TOKEN` в prod

Список диалогов — **визиты** внутри browser-сессии (`sid`): новый визит после **заявки** или паузы **>30 мин** (`ADMIN_DIALOG_VISIT_GAP_MIN`). Компактное превью + «Показать диалог» → `GET /api/dialogs/<sid>/thread?visit_index=N`. Метрика «Диалогов» = визиты; «Сессий» = distinct `sid`. Event Explorer — отладка.

---

## 7) Env

| Переменная | Назначение |
|------------|------------|
| `BOT_PG_DSN` | Postgres для bot sink |
| `BOT_OBSERVABILITY_RETENTION_HOURS` | Rolling purge PG+SQLite (default 24; 0 = off) |
| `BOT_OBSERVABILITY_RETENTION_INTERVAL_SEC` | Интервал purge job (default 3600) |
| `ADMIN_DASHBOARD_PORT` | default 9100 |
| `ADMIN_DASHBOARD_TOKEN` | prod |

---

## 8) Definition of Done (боевой клиент)

1. `BOT_PG_DSN` задан, события в PG + JSONL.
2. `turn_complete` с redacted текстами.
3. Admin показывает метрики «сегодня» по `client_id`.
4. Диалоги и проблемы видны; **заявки** — события `lead_submitted` (без name/phone), не таблица `leads`.
5. Demo не смешивается с боевыми в admin (фильтр или `features.admin: false`).

---

## 9) Известное (resolved)

Маскировка `prompt_tokens` как секрета — исправлено в `logging_setup.py` (`_USAGE_TOKEN_KEYS` allowlist).
