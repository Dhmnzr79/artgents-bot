# VPS — чеклист деплоя (M5)

**Статус:** рабочий чеклист для prod.  
**Связь:** `MULTICLIENT.md` (§7–8, §11), `DASHBOARD.md`, `CURRENT_ARCHITECTURE.md`.  
**Фаза:** M5 — VPS, Caddy, prod smoke.

Скопируй блок «Старт нового чата» в Cursor, если контекст пустой.

---

## Старт нового чата (шаблон)

```text
Деплой M5 dental-bot (demo-bot-local).
VPS: [ОС, vCPU/RAM, что уже установлено: Docker/Caddy/DNS].
Нужен шаг: [Caddy / docker-compose / .env prod / smoke / ошибка: …].
Доки: docs/VPS_CHECKLIST.md, MULTICLIENT §8.
```

---

## 1. Домены (prod-контракт кода)

| URL | Назначение |
|-----|------------|
| `artgents.ru` | Промо (отдельный хостинг), embed виджета demo |
| `demo.bot.artgents.ru` | API бота, `client_id=demo` (leads/admin/pg off) |
| `cesi.bot.artgents.ru` | API, боевая клиника |
| `nikadent.bot.artgents.ru` | API, боевая клиника |
| `{new}.bot.artgents.ru` | 4-й клиент (после client pack + индекс) |
| `admin.bot.artgents.ru` | Admin dashboard (token) |

**Правило:** в prod `client_id` берётся из **Host** `{id}.bot.{domain}` (`core/client_host.py`).  
Один хост `bot.artgents.ru` **без** префикса клиента при `APP_ENV=prod` **не работает**.

**DNS:** A-запись на VPS + wildcard `*.bot.artgents.ru` (или отдельные A на каждый поддомен).

---

## 2. Инфраструктура на VPS

### Обязательно

| Компонент | Зачем |
|-----------|--------|
| VPS **2 vCPU, 6–8 GB RAM**, 60 GB SSD | bot + PG + Caddy; LLM — внешние API |
| **Swap 2 GB** | подстраховка на малых тарифах |
| **Docker** + Compose | деплой bot, PG, Caddy |
| **UFW / firewall** | 22, 80, 443; PostgreSQL **не** в интернет |
| **Caddy** | HTTPS, wildcard `*.bot.artgents.ru`, прокси |
| **PostgreSQL 16** | события, лиды (`BOT_PG_DSN`) |
| **Bot** (`Dockerfile`, gunicorn `-w 1`, :8000) | один сервис на все поддомены |
| **admin_dashboard** (:9100) | `ADMIN_DASHBOARD_TOKEN` |
| **`.env` на сервере** | секреты, не в git |

### Желательно

| Компонент | Зачем |
|-----------|--------|
| Ротация Docker-логов | диск не забивается |
| Ежедневный бэкап PostgreSQL | лиды и диалоги |
| Uptime healthcheck | простой ping на bot |

### Не нужно на старте (4 клиента)

| Компонент | Почему |
|-----------|--------|
| **Redis** | см. `MULTICLIENT.md` §8 |
| **n8n** | лиды: email + PG; webhook позже |
| **pgvector** | embeddings в `data/{id}/embeddings.npy`, не в PG |

---

## 3. LLM и индекс

| Слой | Провайдер | Env |
|------|-----------|-----|
| Chat, resolver, arbiter, … | Qwen (DashScope/MaaS) | `DASHSCOPE_API_KEY`, `CHAT_BASE_URL` |
| Embeddings | OpenAI | `OPENAI_API_KEY`, `MODEL_EMBED=text-embedding-3-large` |

После правок контента:

```bash
python build_index.py --client cesi
python build_index.py --client all
```

Build и runtime **должны** использовать одну `MODEL_EMBED` (см. `config.py`, `build_index.py`).

---

## 4. `.env` prod (ключевые переменные)

```env
APP_ENV=prod
ALLOWED_CLIENTS=demo,cesi,nikadent,<new>

BOT_PG_DSN=postgresql://bot:***@postgres:5432/bot_events
ADMIN_DASHBOARD_TOKEN=<длинный секрет>
ADMIN_DASHBOARD_PORT=9100

DASHSCOPE_API_KEY=...
CHAT_BASE_URL=...
OPENAI_API_KEY=...
MODEL_EMBED=text-embedding-3-large

# модели Qwen — см. .env.example / config.py
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...
```

Полный список — `.env.example` в корне репо.

---

## 5. Готовность клиентов (качество в prod)

Для **каждого** `client_id`:

- [ ] `clients/{id}/` — md, `service_catalog.json`, `prices.json`, `price_offers.json` (если сложный прайс), `widget_config.json` (`allowed_origins`)
- [ ] `data/{id}/` — `corpus.jsonl`, `embeddings.npy`, `alias_*`, `bot.db`
- [ ] `features.yaml` — demo: leads/admin/pg **off**; cesi/nikadent: **on**
- [ ] `lead_config.yaml` + SMTP для email-лидов (боевые)
- [ ] DNS: `{id}.bot.artgents.ru` → VPS

4-й клиент: скопировать `clients/_template/` → заполнить → `build_index` → добавить в `ALLOWED_CLIENTS`.

---

## 6. Безопасность (кратко)

- [ ] `APP_ENV=prod` — Host-binding, Origin-guard на `/ask`
- [ ] `allowed_origins` в `widget_config.json` + проверка на сервере
- [ ] Сильный `ADMIN_DASHBOARD_TOKEN`, HTTPS на admin
- [ ] Rate limit: `RATE_LIMIT_*` в боте + по желанию на Caddy
- [ ] Debug-роуты недоступны на prod

---

## 7. После деплоя — smoke

- [ ] `demo.bot...` — 3–5 вопросов; виджет с `artgents.ru` (Origin в whitelist)
- [ ] `cesi` / `nikadent` — цена, контакты, короткий multi-turn follow-up
- [ ] Заявка (cesi) → email + строка в PG + видна в admin
- [ ] Demo: заявка → `demo_stub`, **нет** записи в `leads`
- [ ] `/ask` с чужим `Origin` → отказ
- [ ] Локально: `python evals/v5/run_e2e_smoke.py` (если настроен URL prod)

Критерии «можно в prod» — `MULTICLIENT.md` §11.

---

## 8. Порядок работ (M5)

1. VPS: OS, swap, firewall, Docker  
2. PostgreSQL (compose или отдельный контейнер)  
3. Собрать/запушить образ bot, `.env` prod  
4. Caddy: TLS + маршруты на bot:8000 и admin:9100  
5. DNS wildcard / поддомены  
6. `build_index --client all` на сервере (или в CI перед деплоем)  
7. Smoke по §7  
8. Мониторинг логов (`BOT_LOG_DIR`, PG, Caddy)

---

## 9. Архитектура (схема)

```text
artgents.ru (промо, другой хостинг)
       │ embed
       ▼
*.bot.artgents.ru ──► Caddy (HTTPS)
       │                    │
       ├─► gunicorn bot :8000 ──► data/{demo,cesi,nikadent}/ 
       │
       └─► admin :9100 ──► PostgreSQL (bot_events, leads)
```

---

*Обновлять вместе с `MULTICLIENT.md` при смене prod-контракта (домены, env, M5).*
