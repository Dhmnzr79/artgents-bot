# Tech Debt

Открытый долг. Runtime: **`CURRENT_ARCHITECTURE.md`**. Ops / prod: **`MULTICLIENT.md`**.

---

## До prod (M5)

| Задача | Примечание |
|--------|------------|
| **Freeze pack cesi / nikadent** | до отмашки владельца; вся продуктовая работа — **только `clients/demo/`** |
| VPS + Caddy + wildcard `*.bot.artgents.ru` | один bot-сервис |
| Smoke 10–20 вопросов на клиента | цена, врач, контакты, lead |
| `allowed_origins` — реальные домены сайтов клиник | не только bot-поддомены |
| Контент nikadent / финализация cesi | `NOT_PROD.md` в pack |
| `demo_video.mp4` в demo `video_catalog.yaml` | placeholder |

---

## Runtime / код

| Задача | Направление | Phase |
|--------|-------------|-------|
| **Stage 1.5 routing shims** (см. блок ниже) | planner-lite + aspect metadata; удалить после этапов 2–4 | **1.5 → 4** |
| Metadata-First: unified alias scoring pool (alias as bonus in one ranked list, not parallel arbiter channel) | `docs/METADATA_FIRST_V1.md` §5 target | post-V1 |
| Карта маршрутов | `docs/ROUTING_MAP.md` | **2 ✓** |
| Smoke routing guards + `meta.service_route` | `evals/v5/e2e_smoke.json`, runner | **3 ✓** |
| `orchestration/route_guards.py` | pre-Resolver guards | **3 ✓** |
| `orchestration/ask_turn.py` + price/catalog/retrieval flows | post-Resolver | **3 ✓** |
| `pre_resolver_turn` + `resolver_turn` + `lead_flow` | pre-Resolver + Resolver | **3 ✓** |
| `finalize_turn.py`; slim `app.py` | dispatch остаётся в `app.py` | **3 ✓** |
| Legacy `classify_intent` только safety-net / `RESOLVER_OFF` | `resolver.resolve_with_fallback` | **3 ✓** |
| Smoke multiclient (`client_id` per case) | cesi, nikadent contacts | **3 ✓** |
| `pending_followup_ref` / guide_router | после стабильного routing | **4** |
| **`pick_relevant_offer` / `offer` в ответе** | заглушка; promo через `promo_note` в answer slots | **2 частично** |
| **PriceBook v2 — остаток** | MVP 3.5a–3.5d ✅; детали — § PriceBook v2 ниже | **3.5 → 4** — см. `PRICEBOOK_V2.md` |
| **`price_concern` + протезирование:** каталог матчится, `concern_ref` пуст → `concern_default` на имплантационный cost-FAQ | контент `concern_ref` в catalog **или** fallback в A3 (`build_price_concern_payload` / topic) | **3** |
| **Lead flow v2** | Расширение gray-zone LLM (few-shot / eval на длинном хвосте отмен) | low |
| **Follow-up compatibility** | ✅ MVP 4a: `follow_up_rewrite`, `compatibility_guard`, `last_subject`, `follow_up_mode`. Осталось: flash rewrite gray zone; optional `aspect_routing.yaml` | **4** — optional |

---

## PriceBook v2 — остаток (3.5)

**Статус (2026-06-21):** MVP runtime на demo — loader + assembler + `price:*` refs. Шаги 3.5a–3.5d ✅; 3.5e ⚠️; 3.5f ❌. Спека: `PRICEBOOK_V2.md`.

### Блокеры UX

| # | Проблема | Суть |
|---|----------|------|
| 1 | **S2 пульпит — «Что входит»** | `pulpitis.json` → followup `price_aspect/includes` + `detail_ref`. Клик не работает: assembler требует `offers` (complex), у simple их нет. Нужен путь: aspect + `detail_ref` → retrieval/md **без новой цены**. |
| 2 | **S6 brand_group** | «Корейские импланты» — фильтра `brand_group` в маршруте нет (поле в данных есть, routing/planner — нет). |

### Данные / миграция

| # | Проблема | Суть |
|---|----------|------|
| 3 | **Тройной источник цен** | pricebook + `price_offers.json` + `prices.json` + md-fallback при miss. Принцип P1 («суммы только в PriceBook») не закрыт. |
| 4 | **`service_catalog.json`** | Ещё `price_ref` → pricing-md; целевой `pricebook_id` не внедрён. |
| 5 | **Promo `active_until`** | Для `service.promo` runtime не проверяет дату (для facts в `facts.json` — проверяет). |
| 6 | **Lint §9** | Нет проверки resolvable followup refs (`scripts/lint_pricebook.py`). |

### Eval / тесты

| # | Проблема | Суть |
|---|----------|------|
| 7 | **`price_offers_golden.json`** | Ждёт legacy-формат («Точные цены», «Входит» в одном ответе). Конфликт с compact S4 (stages/includes — по кнопкам). |

### Документация

| # | Проблема | Суть |
|---|----------|------|
| 8 | **`CURRENT_ARCHITECTURE.md` / `ROUTING_MAP.md`** | Не описывают PriceBook v2; `price_offers.json` ещё указан как источник истины. |

### Конфликты с будущими этапами

| # | Проблема | Суть |
|---|----------|------|
| 9 | **Этап 4 planner-lite** | Риск дубля `installment_12`: fact_refs в price-ответе + append payment_terms md. |
| 10 | **Этап 5 verifier** | 5a numeric gate (demo) — done; 5b: `natural` facts, гарантии без ₽, другие client pack. |
| 11 | **S5 policy** | «1 member в group → сразу S4» не реализовано. |

### Demo-контент (не код)

| # | Проблема | Суть |
|---|----------|------|
| 12 | Цифры spec vs demo | Отбеливание 15k→18k, пульпит 15k→12k — осознанная «рыба». |
| 13 | Скуловая в `full_jaw` | Не решено (`PRICEBOOK_V2.md` §13). |

**При закрытии пункта** — удалить строку из таблицы в PR.

---

## Observability

| Задача | Направление |
|--------|-------------|
| Admin без PG для demo | норма (`features.yaml`) |
| JSONL + PG параллельно | см. `DASHBOARD.md` |

---

## Закрыто (не возвращать)

Multiclient M1–M4 локально: client packs, `data/{id}/`, `client_data_loader`, per-client session/SQLite, Host+Origin, leads email, admin token, legacy `md/` + `clients/default/` удалены.

Pre-Resolver **booking LLM** для lead gate убран: lead только `explicit_booking_intent()` (regex); `booking_intent()` LLM остаётся в `policy.py` для CTA.

**Answer slots + price offers (этапы 2–3, demo):** `core/answer_slots.py`, `core/price_offers.py` — см. `CURRENT_ARCHITECTURE.md` §6.

Arbiter **score-margin skip** убран: при 2+ кандидатах всегда LLM arbiter.

Короткий **service follow-up** (rewrite validate + arbiter guard): `core/service_followup.py` — contextual rewrite overlap, generic FAQ отсекается при активной `last_catalog_service_id`.

При закрытии новой задачи — удалить строку из таблицы в PR.

---

## Stage 1.5 — routing shims (временный слой, не финальная архитектура)

**Контекст:** implant golden **28/28** на demo достигнуты, но **не** «чистой» целевой схемой (Resolver → metadata-first → arbiter). Между этапами 1 и 2 добавлен **deterministic hint layer**: regex-сигналы, прямые маршруты на md, обход arbiter для части типов вопросов. Этапы **2–3** (answer slots, price offers) сделаны на demo; shims **ещё в коде** — замена в этапе 4 (planner-lite + aspect).

### Что считать продуктовой логикой (оставить, позже обобщить)

| Правка | Где | Замена в целевой архитектуре |
|--------|-----|------------------------------|
| Commercial vs `price_concern` | `COMMERCIAL_INFO_RE`, `_lookup_intent_by_rules`, `resolver_turn` | `aspect` + `route_intent`; рассрочка / «что входит» / «под ключ» / оценка по снимку — content/commercial facet, не concern |
| Comparison signal | `COMPARISON_QUERY_RE` → `query_mode=comparison` | aspect/query-mode signal; не «фраза → файл» |
| Алиасы в client pack | `clients/{id}/md`, `service_catalog.json` | основной путь doc selection; не единственный |

### Временные shims (удалить после этапов 2–4)

| Shim | Где | Риск |
|------|-----|------|
| `try_a3_catalog_md_direct` | `orchestration/catalog_flow.py` | жёсткий список `consultation` / `steps` / `temporary_teeth` / `methods_overview` / `tooth_one_day`; **обход arbiter** |
| Regex → конкретный md | `STEPS_VISITS`, `TEMPORARY_TEETH`, `CONSULTATION`, `IMPLANTATION_WHAT_IS`, `TREATMENT_SEQUENCE`, `PERMANENT_CROWN_WHY_WAIT` в `source_routing.py` | «если фраза похожа на X → файл Y» |
| Tomography topic guard | `source_routing._catalog_match_blocked_for_topic` | общий guard; снять после catalog/aspect boost |
| Comparison `query_mode` override | `resolver_turn.py` + skip A3 catalog при comparison | дублирует resolver, если golden не доведён |
| Сужение regex под golden | напр. `TEMPORARY_TEETH_QUERY_RE` после ложного q23 | **опасно:** словесные подборы под eval, не под живой диалог |

**Цель замены:** `core/answer_planner.py` + **`aspect`** / subject metadata (boost/filter, не hard route) + session `last_subject` / `last_aspect`. См. `PRODUCT_WORK_PLAN.md` §3.1.

**Правило на этапы 2–4:** не добавлять новые **direct regex → doc** маршруты без крайней необходимости; новые словесные сигналы — **флаг плана / aspect**, не `ref` на md. Этап 4 planner-lite должен **поглотить** эти shims.

**Файлы:** `config.py`, `source_routing.py`, `orchestration/resolver_turn.py`, `orchestration/catalog_flow.py`, `orchestration/ask_turn.py`, `query_selector.py`.

**Freeze (2026-06):** новые **regex → конкретный md** в общем коде **запрещены** до снятия shims (замена: aliases + aspect boost + catalog). Исключение — явная задача в PR с записью в таблицу снятия ниже.

### Golden §2.1 → shim → aspect → pack (demo)

План снятия Stage 1.5 для `evals/v5/demo/golden.json` §2.1 (14 кейсов). Связка с **этапом 6** (`PRODUCT_WORK_PLAN.md` §604): `aspect` в corpus + soft boost в `candidate_builder`, без hard route.

| golden_ref | Вопрос (кратко) | Временный shim (код) | Aspect (planner) | Целевой doc / route | Pack (aliases / catalog) |
|------------|-----------------|---------------------|------------------|---------------------|--------------------------|
| 1 | Что такое имплантация | `IMPLANTATION_WHAT_IS_RE` → methods_overview; `_DIRECT_CATALOG` | `overview` | `implantation__info__methods_overview` | alias «что такое имплантация зубов» ✅ |
| 2 | Как проходит | `STEPS_VISITS` (частично) | `stages` | `implantation__info__steps` | aliases на steps ✅ |
| 3–4 | Сроки / время в кресле | — | `duration` | `implantation__faq__duration` | aliases duration ✅ |
| 5 | Когда коронка | `TEMPORARY_TEETH` (частично) | `duration` | `temporary_teeth` / duration / aftercare | alias на temporary_teeth ✅ |
| 6 | Почему не постоянная коронка сразу | `PERMANENT_CROWN_WHY_WAIT_RE` | `duration` | `tooth_one_day` | aliases tooth_one_day ✅ |
| 7 | Зуб за один день | — | `duration` | `tooth_one_day` / `one_stage` | existing aliases |
| 8–9 | Удаление + имплант / сроки | — | `stages` / `duration` | one_stage / extraction / comparison | h3 aliases extraction |
| 10 | Нет зуба 8 лет | — | `overview` | `bone_graft` / classic | aliases bone_graft ✅ |
| 11 | Не ставить имплант | — | `overview` | `osseointegration` h3 | alias в md ✅ |
| 12 | КТ перед имплантацией | tomography topic guard | `overview` | `catalog_facts` + `tomography` | facts OK при явном КТ |
| 13 | Зачем 3D | — | `overview` | `clinic__info__technology` | aliases technology ✅ |
| 14 | Что сначала (КТ, удаление…) | `TREATMENT_SEQUENCE_RE` | `stages` | `implantation__info__steps` | aliases steps ✅ |

**Spike этапа 6 (код, без снятия shims):** `core/aspect_metadata.py`, поле `aspect` в `build_index`, `aspect_match_boost` в `routing.yaml`, boost в `apply_metadata_candidate_boosts` при `detect_aspects(q)`.

**Порядок снятия shims (E1–E8):** см. `PRODUCT_WORK_PLAN.md` этап 6 + таблица «Временные shims» выше. После каждого шага: `run_demo_eval.py --suite product` + `--suite golden`.

### Критерий «готово к multiclient» (routing)

| # | Критерий |
|---|----------|
| M1 | Нет новых direct regex→md после freeze |
| M2 | Таблица «Временные shims» — все строки закрыты или перенесены в pack-driven hints |
| M3 | `aspect` в corpus + `aspect_match_boost` включены; индекс пересобран per client |
| M4 | `run_demo_eval.py --suite product` и `--suite golden` green **без** shims E1–E7 |
| M5 | `audit_client_readiness` (этап 6) для 2-й клиники — пробелы задокументированы |
| M6 | `CURRENT_ARCHITECTURE.md` / `ROUTING_MAP.md` описывают retrieval 2.0, не regex→md |

**Не путать с M5 prod (VPS):** таблица «До prod» выше — деплой; M1–M6 — чистота routing перед onboarding нового client pack.
