# Production Compose (T6B Pass 3 + G4 manual deploy contract)

Один экземпляр движка обслуживает несколько клиник по hostname (`{client_id}.bot.artgents.ru`). Этот каталог — **контейнерный пакет и документация**. Автоматический deploy на VPS **не** выполняется из репозитория на вашей машине.

## G4 — manual production deploy (repository only)

- Workflow **`Deploy production`** (`.github/workflows/deploy-production.yml`) появится в GitHub UI **только после merge в default branch `main`**.
- Запуск **только** `workflow_dispatch` с полным `source_sha` (40 hex) и `confirm_production: true`.
- Workflow проверяет ancestry на `main`, успешный G3 publish receipt и digest тега GHCR `<sha>` — **без** Docker build и **без** mutable tags (`latest`, `main`, `prod`).
- SSH на VPS вызывает фиксированную команду; серверные шаблоны в `deploy/production/server/` (исключены из Docker image).
- **GitHub Free:** без `environment: production`; будущие имена secrets/variables перечислены в `deploy/production/server/README.md` — **реальные значения в G4 не создаются**.
- **Не запускать workflow**, пока не выполнены внешние gates:
  - **G7** — утилита `/opt/artgents/bin/backup-postgres` (deploy fail-closed без неё);
  - **G8** — квалификация PostgreSQL;
  - **G10** — VPS, DNS, TLS, установка server assets.
- Rollback (**G5**), настоящий backup (**G7**), disposable PG qualification (**G8**) и VPS setup (**G10**) **не** входят в G4 как runtime на вашей машине; **G5 rollback workflow/script** добавлены в репозиторий как контракт (без запуска до gates).

## G5 — manual production rollback (repository only)

- Workflow **`Rollback production`** — только `workflow_dispatch` с `expected_current_sha` + `confirm_rollback: true`; **без** выбора target SHA/digest пользователем.
- Сервер читает **`previous.json`**, сверяет **`expected_current_sha`** с **`current.json`**, проверяет **migration bundle fingerprint** (manifest + содержимое SQL); при несовпадении — блок до остановки сервисов, текущая версия остаётся online.
- Rollback **не** восстанавливает БД и **не** выполняет миграции/downgrade. Нужны **G7** (`backup-postgres --reason pre-rollback`), **G8**, **G10**. Workflow **не запускать** до готовности VPS.
- Подробности: `deploy/production/server/README.md`.

---

## Контейнеры

| Сервис | Назначение |
|--------|------------|
| **postgres** | PostgreSQL только во внутренней сети; данные в named volume. |
| **migrate** | One-shot: `python -m deploy.postgres.migrate` по `BOT_MIGRATOR_PG_DSN`. |
| **bot** | Gunicorn → `app:app`, порт **8000 только внутри Docker**. |
| **admin** | Gunicorn → `admin_dashboard.app:app`, порт **9100 только внутри Docker**. |
| **caddy** | Единственный сервис с **публичными** портами 80/443 и loopback 9100. |

Redis в пилоте **не** используется.

## Порты

| Где | Порт | Доступ |
|-----|------|--------|
| Caddy | 80, 443 | Публичный HTTP/HTTPS для clinic domains |
| Caddy | 9100 | Только `127.0.0.1:9100` на хосте (SSH tunnel) |
| bot | 8000 | Внутренний, **не** publish |
| admin | 9100 | Внутренний, **не** publish |
| postgres | 5432 | Внутренний, **не** publish |

Публичного `admin.bot.artgents.ru` **нет**.

## Сети

- **db_internal** (`internal: true`): `postgres`, `migrate`, `bot`, `admin`.
- **edge**: `bot`, `admin`, `caddy`.

`caddy` **не** подключён к `db_internal` — нет доступа к PostgreSQL. `bot` на обеих сетях: БД + исходящий интернет (Qwen/SMTP). Docker socket нигде не монтируется; `network_mode: host` и `privileged` не используются.

## Volumes

| Volume | Содержимое |
|--------|------------|
| `postgres_data` | Данные PostgreSQL |
| `caddy_data`, `caddy_config` | TLS/ACME и состояние Caddy |
| `bot_data` | `/app/data` (SQLite sessions per client, UID 10001) |
| `bot_logs` | `/app/logs` (JSONL) |

Client packs и KB поставляются из **Git/image**, не правятся вручную в контейнере.

**Backup contract (Pass 3):** SQLite sessions и JSONL logs **не** входят в обязательный backup. Backup PostgreSQL — отдельный pass.

## Секреты и env

Внешний файл (см. `env.production.example`) передаётся при запуске Compose; **весь файл не пробрасывается** во все контейнеры.

| Сервис | Видит |
|--------|--------|
| postgres | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| migrate | `BOT_MIGRATOR_PG_DSN` |
| bot | `BOT_PG_DSN`, Qwen, SMTP, multiclient/runtime tuning — **без** migrator/bootstrap |
| admin | `BOT_PG_DSN`, `ADMIN_DASHBOARD_TOKEN`, admin tuning — **без** migrator/Qwen/SMTP |
| caddy | ACME email, Basic Auth user/hash, `ADMIN_DASHBOARD_TOKEN` (для `X-Admin-Dashboard-Token`) — **без** DB/Qwen/SMTP |

Обязательные переменные помечены `${VAR:?set VAR}` в `compose.yml`. Пароли, DSN и токены **не** хранить в Git.

**BCrypt для Caddy Basic Auth:** хеш генерируется на VPS, не коммитится. В production env значение с символом `$` заключайте в **одинарные кавычки**, иначе Compose/dotenv испортят хеш, например: `CADDY_ADMIN_BASIC_AUTH_HASH='$2a$14$…'`. Реальный хеш не логировать и не вставлять в отчёты.

Образы параметризованы: `BOT_IMAGE`, `POSTGRES_IMAGE`, `CADDY_IMAGE`. Конкретные проверенные теги/digests фиксируются на VPS перед первым deploy (без сетевой проверки в Pass 3).

## PostgreSQL roles (до первого migrate)

1. Bootstrap создаёт БД и роли `bot_migrator` / `bot_runtime` по `migrations/postgresql/roles_template.sql` (superuser **не** в application env).
2. `postgres` healthy.
3. `migrate` завершается успешно.
4. Только затем стартуют `bot` и `admin`.

Подробности: `migrations/postgresql/README.md`.

## Порядок старта (staged — без автоматического public traffic)

Сервис **`caddy` в профиле `public`**. Обычный `up` backend **не** запускает Caddy. Публичный ingress включается только после успешного readiness gate. Pass 4 автоматизирует этот flow; Pass 3 — documentation only.

1. **postgres** — поднять и дождаться healthy (`pg_isready`).
2. **Bootstrap roles** — отдельный infra-step на VPS (`migrations/postgresql/roles_template.sql`); не из bot/admin.
3. **migrate / bot / admin** — без Caddy:

   ```bash
   docker compose --env-file /secure/production.env -f deploy/production/compose.yml up -d postgres
   # … bootstrap roles …
   docker compose --env-file /secure/production.env -f deploy/production/compose.yml run --rm migrate
   docker compose --env-file /secure/production.env -f deploy/production/compose.yml up -d bot admin
   ```

4. Дождаться **healthy** `bot` и `admin` (Docker healthchecks: bot `/health/live`, admin `/api/health` с токеном внутри контейнера).
5. **Internal readiness (обязательно до Caddy):** из контейнера `bot`, без внешнего URL:

   ```bash
   docker compose --env-file /secure/production.env -f deploy/production/compose.yml exec -T bot \
     python -c "import sys, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=15); sys.exit(0 if r.status==200 else 1)"
   ```

   Только при **HTTP 200** переходить к шагу 6. При любом failure **не** запускать Caddy.

6. **Public profile** — Caddy (единственный публикующий ports):

   ```bash
   docker compose --env-file /secure/production.env -f deploy/production/compose.yml --profile public up -d caddy
   ```

Caddy в compose ждёт `bot` и `admin` **healthy**; оператор дополнительно обязан пройти шаг 5 до шага 6.

DDL из `bot`/`admin` **не** выполняется.

## Health

- **Liveness (bot):** `GET /health/live` — Docker healthcheck.
- **Liveness (admin):** `GET /api/health` на порту **9100** с заголовком `X-Admin-Dashboard-Token` (токен из `os.environ` в probe; не в compose command).
- **Readiness (release gate):** `GET /health/ready` на **bot** — обязательная проверка **до** `--profile public`; не используется как частый Docker liveness probe.

## Caddy — публичные клиники

Явный список в `Caddyfile` (первые: `demo.bot.artgents.ru`, `nikadent.bot.artgents.ru`). Новая клиника: добавить site block, обновить `ALLOWED_CLIENTS`/pack, redeploy/reload. Неизвестные hostname **не** проксируются в приложение. TLS — per-host (без on-demand TLS и без wildcard на этом этапе). Заголовок `Host` сохраняется для tenant ingress.

Security headers: `X-Content-Type-Options`, `Referrer-Policy`, HSTS на HTTPS public sites. CSP не задан (виджет/embed/SSE).

## Админка (только владелец)

1. SSH tunnel:

   ```bash
   ssh -L 9100:127.0.0.1:9100 deploy@VPS_IP
   ```

2. Браузер: `http://127.0.0.1:9100`

Caddy на `:9100`: HTTP Basic Auth, затем прокси в `admin:9100` с заголовком `X-Admin-Dashboard-Token` (токен не уходит в браузер и не в Git). Caddy admin API отключён (`admin off`).

## Проверка конфигурации (без production up)

Из корня репозитория, с тестовым env **без реальных секретов**:

```bash
docker compose --env-file deploy/production/env.production.example -f deploy/production/compose.yml config
```

(На машине без Docker — только статические тесты `tests/test_t6b_pass3_production_deploy_offline.py`.)

## Запуск на VPS (документация only — Pass 3 не выполняет)

**Не** использовать полный `docker compose up -d` без профиля как «всё сразу» — это не открывает public ports (Caddy в `public`), но оператор всё равно должен следовать staged flow выше и **не** включать `--profile public`, пока internal `/health/ready` не вернул **200**.

## Pass 4 / VPS verification

- GitHub deploy и rollback — Pass 4.
- Реальная интеграция PostgreSQL (`BOT_TEST_PG_DSN`, 0 skipped) обязательна до traffic.
- Hardening Caddy/PostgreSQL beyond defaults — проверка на VPS, не угадывается здесь.

## Явные ограничения

- PostgreSQL **не** публикуется наружу.
- Bot **не** публикует 8000.
- Этот Compose **не** является автоматическим deploy.
