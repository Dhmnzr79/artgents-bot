# Мультиклиентность

**Статус:** фактическая схема client packs после удаления RAG.  
**Обновлено:** 2026-07-10.  
**Runtime:** `CURRENT_ARCHITECTURE.md`.

---

## 1. Принцип

Один кодовый движок обслуживает изолированные client packs. **Runtime (2026-07):** активен только `demo`; шаблон `clients/_template/` — scaffold, не runtime-клиент. Все клинические данные, бренд, цены и настройки лежат в `clients/{id}/`; сессии — в `data/{id}/bot.db`.

Нет fallback между клиентами. `default` нормализуется в `demo`.

---

## 2. Структура client pack

```text
clients/{id}/
  md/                       # база знаний клиента
  service_catalog.json      # услуги, aliases, md refs
  pricebook/                # основной источник цен, если есть
    manifest.json
    facts.json
    services/*.json
  patient_playbook.yaml     # удалён в C2d-D1; канон — target_response/clinic_strategy.yaml
  marketing.yaml            # promo/marketing facts
  clinic_policies.yaml      # ограничения и политики клиники
  video_catalog.yaml
  widget_config.json        # тексты/allowed_origins виджета
  brand.yaml                # цвета, логотипы, аватар
  tone.yaml                 # тон и тексты lead/situation
  ui.yaml                   # меню, fallback, price_symptom_consult
  features.yaml             # включённые подсистемы
  lead_config.yaml          # доставка заявок

data/{id}/
  bot.db                    # SQLite session store, не коммитить
```

Опциональные legacy price files (`prices.json`, `price_offers.json`) могут существовать у старых packs как fallback, но для demo основной путь — `pricebook/`.

---

## 3. Что в каком файле

| Файл | Назначение |
|---|---|
| `md/` | факты, FAQ, услуги, врачи, контакты |
| `service_catalog.json` | активные услуги, заголовки, aliases, `md_entry_ref`, price refs |
| `pricebook/` | суммы, units, бренды, сценарии, fact refs, followups |
| `patient_playbook.yaml` | ordered options для ситуаций пациента |
| `marketing.yaml` | promo rules и marketing facts |
| `features.yaml` | включение leads/admin/guide и других возможностей |
| `lead_config.yaml` | demo stub, email или будущий webhook |
| `widget_config.json` | тексты виджета и `allowed_origins` |
| `brand.yaml` | визуальная тема виджета |
| `tone.yaml` | тон ответа и служебные тексты |
| `ui.yaml` | guided menu, fallback, price_symptom_consult |

---

## 4. Runtime-изоляция

| Слой | Как изолирован |
|---|---|
| Content | `core/knowledge_base.py` читает только `clients/{id}/md/` |
| Ref chunks | `core/md_chunks.py` резолвит refs внутри pack |
| Prices | `core/pricebook_loader.py` и `core/price_offers.py` читают pack клиента |
| Service view | `core/service_node.py` сводит catalog + pricebook текущего клиента |
| Sessions | `session.py` пишет `data/{id}/bot.db` |
| Doctors | `doctors_lookup.py` читает `clients/{id}/md/doctors__*.md` |
| Widget | `widget_config.json` + `core/origin_guard.py` |
| Leads | `features.yaml` + `lead_config.yaml` |

---

## 5. Провайдеры

Chat, composer, resolver, planner и классификаторы работают через Qwen/DashScope:

- `DASHSCOPE_API_KEY`
- `CHAT_BASE_URL`
- `MODEL_CHAT`, `MODEL_RESOLVER`, `MODEL_ARBITER` и соседние env из `config.py`

OpenAI-эмбеддинги больше не нужны runtime после Stage 3.4.

---

## 6. Домены

Prod-схема:

```text
demo.bot.artgents.ru      → client_id=demo
cesi.bot.artgents.ru      → client_id=cesi
nikadent.bot.artgents.ru  → client_id=nikadent
```

Host → client_id делает `core/client_host.py`. `allowed_origins` в `widget_config.json` ограничивает сайты, с которых можно обращаться к `/ask`, `/lead`, `/api/widget-config` и media routes.

---

## 7. Локальная разработка

Обычный цикл:

1. править `clients/demo/` и общий код;
2. не трогать `clients/cesi/` и `clients/nikadent/` без явной задачи владельца;
3. запускать unit/product/eval по конкретному client id;
4. не коммитить `data/{id}/bot.db`.

Для нового клиента копируется каркас pack, заполняются md/catalog/pricebook/widget/lead configs, затем добавляется домен `{client_id}.bot.artgents.ru`.

---

## 8. Готовность к prod

- pack клиента заполнен и прошёл smoke: цена, врачи, контакты, lead;
- `allowed_origins` содержит реальные домены сайта клиники;
- `features.yaml` и `lead_config.yaml` соответствуют режиму demo/prod;
- admin/PG включены только там, где нужно;
- нет fallback на чужой pack;
- `data/{id}/bot.db` и секреты не попадают в git.
