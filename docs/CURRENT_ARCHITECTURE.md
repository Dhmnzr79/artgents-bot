# Текущая архитектура бота

**Статус:** фактический runtime после Stage 3.4 и Stage 5.5.  
**Обновлено:** 2026-07-06.  
**Связано:** `ROUTING_MAP.md`, `MULTICLIENT.md`, `PRICEBOOK_V2.md`, `TECH_DEBT.md`.

---

## 1. Главное состояние

- RAG-поиск удалён в Stage 3.4. В runtime нет отдельного embed/search слоя и OpenAI-эмбеддингов.
- Единственный content-путь — full-context composer: композер получает всю md-базу клиента как контекст и пишет ответ поверх детерминированного пакета.
- `get_chunk_by_ref` и `core/md_chunks.py` остались. Это не поиск, а прямое чтение md-секции по ref для контактов, карточек, price/detail refs и служебных вставок.
- Плановый вызов живёт в `core/turn_planner_llm.py` и возвращает `route`, `aspects`, `service_id`, `patient_situation`, `brand_filter`.
- Цены детерминированы: PriceBook/legacy offers собирают суммы, бренды, порядок и кнопки до LLM.
- Stage 5.5 добавил read-only ядро услуги: `core/service_node.py`, `core/answer_lens.py`, ситуационную цену за флагом `SITUATION_PRICE_ON`, живые обрамления через `core/living_frame.py` за `LIVING_OVERVIEW_ON`.

---

## 2. Client pack и данные

Каждый клиент изолирован в `clients/{id}/`.

```text
clients/{id}/
  md/
  service_catalog.json
  pricebook/
    manifest.json
    facts.json
    services/*.json
  patient_playbook.yaml
  marketing.yaml
  clinic_policies.yaml
  video_catalog.yaml
  widget_config.json
  brand.yaml
  tone.yaml
  features.yaml
  lead_config.yaml

data/{id}/
  bot.db
```

`data/{id}/bot.db` — SQLite-сессии, в git не трекаются. Runtime не должен fallback'иться из одного client pack в другой.

---

## 3. `/ask` в одну строку

```text
ingress/pre-resolver guards
→ resolver / turn plan / source routing
→ ask_turn hard routes
→ composer or deterministic service reply
→ finalize/policy/session/widget payload
```

Фактический порядок в `orchestration/ask_turn.py`:

1. contacts overlay;
2. patient playbook overview для content-ситуаций;
3. situation price overview за `SITUATION_PRICE_ON`;
4. doctor route;
5. composer overlay;
6. catalog facts;
7. price flow;
8. fail-open composer fallback.

Детали маршрутов — `ROUTING_MAP.md`.

---

## 4. Основные модули

| Модуль | Роль |
|---|---|
| `app.py` | HTTP, dispatch, сборка ответа |
| `orchestration/pre_resolver_turn.py` | входные guards, lead/ref/continuation до resolver |
| `orchestration/resolver_turn.py` | `DecisionFrame` и fallback intent |
| `orchestration/ask_turn.py` | основной post-resolver порядок маршрутов |
| `orchestration/composer_flow.py` | full-context composer overlay |
| `orchestration/price_flow.py` | deterministic price replies |
| `orchestration/patient_playbook_flow.py` | situation overview и situation-price |
| `orchestration/catalog_flow.py` | doctors, catalog facts, md priority |
| `core/knowledge_base.py` | сборка всей md-базы клиента для composer |
| `core/md_chunks.py` | прямое чтение md-section по ref |
| `core/turn_planner_llm.py` | one-turn plan: route/aspects/service/situation/brand |
| `core/pricebook_loader.py` | загрузка PriceBook |
| `core/price_answer_assembler.py` | deterministic price answer |
| `core/price_offers.py` | нормализация offers/brands/legacy fallback |
| `core/price_scope.py` | regex price-scope routing, оставлен намеренно |
| `core/patient_situation.py` | semantic patient situation |
| `core/patient_playbook.py` | situation → ordered clinic options |
| `core/service_node.py` | read-only service view: catalog + pricebook |
| `core/answer_lens.py` | describe/price/situation projections |
| `core/living_frame.py` | live intro/closer вокруг пришпиленных facts |
| `session.py` | per-client SQLite session |

---

## 5. Content path

Composer — единственный путь для content-ответов.

1. `core/knowledge_base.py` собирает md-базу текущего клиента.
2. `core/answer_packet.py` и соседние модули готовят детерминированный пакет фактов, карточек, price/promo вставок.
3. `llm.generate_answer_from_packet_fullctx` / composer flow пишет финальный текст.
4. Numeric gate проверяет числа по базе и карточкам.

Прямые md refs (`get_chunk_by_ref`) используются только там, где нужен конкретный фрагмент: контакты, detail refs, service cards, legacy price refs, follow-up snippets.

---

## 6. Price path

PriceBook — основной источник денег на demo.

- `query_selector.select_price_service_route` определяет price route и price scope.
- `core/price_scope.py` и `core/patient_scope_cues.py` остаются рабочим dental-router для метод-ценовых вопросов вроде «сколько имплантация».
- `core/price_answer_assembler.py` собирает суммы, brands, units, followups и кнопки без LLM.
- `core/price_group_overview.py` строит обзор группы протоколов; при `LIVING_OVERVIEW_ON=1` intro/closer пишет composer через `core/living_frame.py`, цены остаются пришпилены.
- `orchestration/patient_playbook_flow.try_patient_options_price_overview` строит цену за ситуацию за `SITUATION_PRICE_ON=1`: герой с одной inline-ценой, остальные варианты кнопками.

Эксперимент planner → price-scope отменён: планировщик не заменяет regex price-routing.

---

## 7. Patient situation и Stage 5.5

`core/patient_situation.py` определяет ситуацию пациента: один зуб, вся челюсть, верхняя челюсть, протезный этап и т.п.

`core/patient_playbook.py` превращает ситуацию в упорядоченные опции клиники из `patient_playbook.yaml`.

Stage 5.5 добавляет общий read-only слой:

- `ServiceNode`: единый вид услуги из catalog + pricebook;
- `DescribeView`: content ref, intro, followups;
- `PriceView`: offers, min_total, brand choice;
- `SituationView`: ordered `ServiceNode` items с role/positioning/priority.

Потребители подключены только там, где это уже нужно: situation-price. Остальные линзы остаются фундаментом для будущего рендера.

---

## 8. LLM и провайдеры

Chat/classifier модели идут через Qwen/DashScope (`DASHSCOPE_API_KEY`, `CHAT_BASE_URL`). OpenAI-эмбеддинги больше не являются частью runtime.

Модели и флаги задаются в `config.py`. Важные флаги текущего слоя:

| Флаг | Назначение |
|---|---|
| `FULLCTX_ON` / composer defaults | full-context composer path |
| `SERVICE_SELECT_LLM_ON` | LLM service selection for composer price aspects |
| `LIVING_OVERVIEW_ON` | live intro/closer для overview frames |
| `SITUATION_PRICE_ON` | situation price overview |

---

## 9. Widget, leads, observability

- Widget contract: `WIDGET_ANSWER_FORMAT.md`.
- Widget config и allowed origins: `clients/{id}/widget_config.json`.
- Leads включаются через `features.yaml` и доставляются по `lead_config.yaml`.
- Events пишутся в JSONL и опционально в Postgres.
- Admin dashboard описан в `DASHBOARD.md`.

---

## 10. Что считать legacy

- Старый RAG/search стек удалён. Не возвращать его в docs как runtime.
- Старые roadmaps композера, dialog focus и marketing cleanup удалены из `docs/`; git-история остаётся источником архива.
- `build_index.py` может оставаться хвостом в коде, но текущие docs не должны описывать его как обязательную операцию runtime.

При расхождении docs и кода править вместе: этот файл отражает текущий runtime, а не желаемую архитектуру.
