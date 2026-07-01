# Roadmap: Controlled Composer

**Статус:** план работ (2026-07). Реализация — в Cursor, поэтапно.
**Прогресс:** Фаза 0 ✓ · Фаза 1 ✓ · Фаза 2 …
**Связано:** `CURRENT_ARCHITECTURE.md` (текущий runtime), `TECH_DEBT.md` (долг и shims), `PRICEBOOK_V2.md`.

Цель этого документа — дать точный, привязанный к реальному коду план перехода
от «выбрать один chunk + пришить маркетинг» к **controlled composer**:
правила собирают разрешённый пакет, LLM пишет из него один связный ответ.

Это НЕ переход к «агент сам вызывает инструменты». Модель не получает руль над
деньгами, промо, CTA и кнопками.

---

## 0. Working agreement (как вести работу в Cursor)

1. **Один этап = один PR.** Не смешивать фазы. Каждая фаза самодостаточна и включается флагом.
2. **Флаг по умолчанию OFF.** Новый путь живёт рядом со старым, пока не доказан паритет на eval.
3. **Не удалять старый путь**, пока новый не прошёл eval (§5) без регрессий. Удаление — отдельная фаза 5.
4. **Fail-open везде.** Любой новый LLM-шаг при ошибке/таймауте откатывается на существующее детерминированное поведение.
5. **После каждого PR — прогон eval** (§5). Красный eval блокирует мёрж.
6. **Инварианты §2 не нарушать ни в одной фазе.** Если фаза требует их обойти — стоп, вынести на обсуждение.
7. Пересборка индекса при изменении corpus/aspect: `python build_index.py --client demo`.

---

## 1. Цель и границы

| В скоупе | Вне скоупа |
|----------|------------|
| Составные вопросы (цена + боль + гарантия в одном) | Модель решает, какую цену назвать |
| Маркетинг-акценты вплетены в ответ, не пришиты снизу | Модель решает, какую акцию показать |
| Уточняющие вопросы словами + кнопки | Модель рисует произвольные кнопки/CTA |
| Меньше «regex → конкретный файл» на входе | Full tool-calling agent (модель рулит потоком) |

---

## 2. Инварианты (нельзя нарушать)

Эти правила — несущая стена. Ни одна фаза не имеет права их обойти.

- **I1. Числа — только из PriceBook.** ₽/%/сроки в ответе приходят из `core/price_answer_assembler.py` / `core/pricebook_loader.py`. Модель их вплетает, но не порождает.
- **I2. Промо — только через `core/marketing_policy.decide_promo_fact`**, вызванный **до** LLM. Запрещённая акция физически не попадает в пакет, а не «модель попросили не показывать».
- **I3. CTA и кнопки — из правил** (`policy.py`, `ux_builder.py`, каталог). Модель формулирует подводку, набор действий — детерминированный.
- **I4. `core/numeric_fact_gate.apply_numeric_fact_gate` остаётся** как финальный предохранитель на цифры.
- **I5. Marketing gate — только код, никогда промпт.** Отбор «что можно» не переносится в системный промпт.
- **I6. Fail-open.** Нет обязательного LLM в критическом пути: при сбое — старое поведение.

---

## 3. Целевой поток (после всех фаз)

```
Resolver (route_intent) → source_routing (A3, услуга/тема)
  → aspect planner (какие аспекты в вопросе: price|pain|warranty|…)      [Фаза 1]
  → answer packet assembler (детерминированно собрать разрешённые карточки) [Фаза 2]
       карточки: content-ref/факт, promo (через decide_promo_fact),
       cta (из правил), buttons (из каталога), числа (из pricebook)
  → composer LLM (один связный ответ из карточек, только слова)          [Фаза 3]
  → numeric_fact_gate + verifier (числа + хеджи)                          [Фаза 3]
  → policy: CTA/quick_replies (как сейчас)
```

Цены на явный `price_lookup` по-прежнему могут идти полностью детерминированным
путём (`assemble_price_answer`) — либо как одна из карточек пакета. Композер не
обязателен там, где ответ уже полностью детерминирован.

---

## 4. Фазы

### Фаза 0 — Фундамент тестов + телеметрия пакета ✓

**Зачем:** сначала научиться *измерять* пакет отдельно от текста, чтобы тесты
проверяли структуру (что собрано), а не слова (как сформулировано). См. §5.

**Что делать:**
- Ввести в `request.ctx` / `meta` поле `answer_packet` (snapshot): список карточек с
  `aspect`, `source_ref`/`fact_id`, `promo_decision`, `cta_key`, `button_refs`, `included_reason`.
  На фазе 0 это просто расширение существующего `answer_plan` snapshot (`publish_answer_plan`).
- Прокинуть snapshot в eval-раннеры (`evals/v5/run_demo_eval.py`, `run_planner_eval.py`),
  чтобы кейсы могли ассертить по нему.

**Файлы:** `core/answer_planner.py` (snapshot), `contracts/answer_plan.py` (расширить при нужде),
`orchestration/ask_turn.py` (публикация), `core/metadata_first_observability.py` (ключи телеметрии).

**Оставляем/убираем:** ничего не убираем. Только добавляем наблюдаемость.

**Тесты:** unit на сериализацию snapshot; smoke, что поле появляется в `meta`.

**Готово:** в логах и eval-выдаче виден `answer_packet` для каждого хода. Поведение бота не изменилось.

---

### Фаза 1 — Aspect planner (bounded LLM, «уши») ✓

**Зачем:** составные вопросы. Сейчас `detect_aspects` в `core/answer_planner.py` — чистый regex
(`_PAIN_ASPECT_RE`, `_WARRANTY_ASPECT_RE`, …). На «сколько стоит all-on-4 и это не больно, и долго ли
заживает?» regex ловит аспекты нестабильно.

**Что делать:**
- Добавить `core/aspect_planner_llm.py`: bounded structured-output классификатор.
  Вход — вопрос (+ короткий контекст). Выход — подмножество фиксированного enum
  `AspectKind` (см. `contracts/answer_plan.py`: `price|payment|warranty|pain|included|duration|comparison|stages|overview`).
  Модель — flash (`QWEN_FLASH_MODEL`), `temperature=0`, Pydantic-валидация, как уже сделано в
  `core/patient_situation_llm.py` / `core/dialog_focus_llm.py`.
- `detect_aspects()` становится **fallback**: regex сначала (быстро/дёшево), LLM — только когда
  вопрос длинный/составной и regex дал 0–1 аспект. При ошибке LLM → regex-результат (fail-open, I6).
- Флаг `ASPECT_PLANNER_LLM_ON` (env, default 0).

**Файлы:** `core/aspect_planner_llm.py` (новый), `core/answer_planner.py` (интеграция),
`config.py` (флаг + модель), `llm.py` (системный промпт классификатора рядом с существующими).

**Оставляем/убираем:** regex `detect_aspects` **остаётся** (fast-path + fallback). Ничего не удаляем.

**Тесты:**
- Unit: составные фразы → ожидаемый **set аспектов** (ассерт по set, не по тексту). Мокать LLM детерминированно.
- `evals/v5/planner_golden.json`: добавить составные кейсы. Ассерт по `answer_plan.aspects`, **не** по словам ответа.

**Готово:** на составных вопросах `aspects` содержит все реальные аспекты; одиночные — без регрессий на `run_planner_eval.py`.

---

### Фаза 2 — Answer packet assembler (детерминированная сборка карточек)

**Зачем:** превратить план в разрешённый пакет — здесь и только здесь маркетинг-гейт стоит до LLM.

**Что делать:**
- Расширить `AnswerPlan` до `AnswerPacket` (новый контракт `contracts/answer_packet.py` или поля в `answer_plan.py`):
  список `PacketCard { aspect, kind (content|price|promo|payment|warranty|cta|buttons),
  source_ref | fact_id | text, facts[], included_reason, suppressed_reason }`.
- Новый `core/answer_packet.py`:
  - для каждого аспекта достать разрешённый материал:
    - `price` → `core/price_answer_assembler` / `price_offers` (I1),
    - `content`/`pain`/`warranty`/`payment` → ref из `source_routing` / `answer_planner` append refs
      (`payment_terms_ref()`, `warranty_terms_ref()` уже есть),
    - `promo` → **`filter_promo_facts` / `decide_promo_fact`** (I2, I5),
    - `cta` → `policy.py` по теме (I3),
    - `buttons` → из каталога/pricebook сценариев (I3).
  - записать `included_reason` / `suppressed_reason` в каждую карточку (новая поверхность отладки).
- Пока **не** менять генерацию: на фазе 2 пакет только собирается и логируется, ответ строится по-старому.

**Файлы:** `core/answer_packet.py` (новый), `contracts/answer_packet.py` (новый),
`core/marketing_policy.py` (переиспользовать), `core/answer_plan_apply.py` (источник append-логики),
`orchestration/ask_turn.py` (сборка после `build_answer_plan`).

**Оставляем/убираем:** `answer_slots` / `answer_plan_apply` пока **работают как есть**. Пакет — параллельно.

**Тесты:**
- Unit на `decide_promo_fact` уже есть — переиспользовать. Добавить: «промо на аспекте `pain` → карточки promo нет»
  (ассерт `suppressed_reason == aspect_blocked`, по **структуре**).
- Кейс: составной вопрос → пакет содержит карточки `price` + `pain` (ассерт по `aspect` в пакете).

**Готово:** `answer_packet` в телеметрии корректен; ни одна запрещённая промо-карточка не попадает в пакет (проверяется тестом на структуру).

---

### Фаза 3 — Composer (генерация из пакета) + verifier на хеджи

**Зачем:** живой связный ответ на весь вопрос, без шва.

**Что делать:**
- Новый путь генерации `llm.generate_answer_from_packet` (рядом с `generate_answer_with_empathy`):
  системный промпт из `core/llm_system_prompt.build_base_system` + правило «пиши один ответ из
  карточек ниже; факты/числа только из карточек; не добавляй акции/CTA/обещания, которых нет в карточках».
  То есть это `GENERATOR_SINGLE_SOURCE_RULE`, обобщённое на **несколько разрешённых карточек**.
- `chunk_responder.py`: при `COMPOSER_ON` и наличии `answer_packet` с ≥2 карточками — идти в композер;
  иначе — старый single-source путь (fail-open).
- **Расширить verifier** (`verifier.py`, `evals/v5/verifier_golden.json`): проверять не только числа
  (это делает `numeric_fact_gate`), а **сохранение хеджей** («обычно», «зависит», «после осмотра») и
  **отсутствие обещаний** («приживётся», «безболезненно», «гарантируем результат»). Это новый класс риска,
  который single-source не имел, а композер вносит.
- Флаг `COMPOSER_ON` (env, default 0).

**Файлы:** `llm.py` (новый генератор), `chunk_responder.py` (развилка), `verifier.py` (правила хеджей),
`core/numeric_fact_gate.py` (без изменений, остаётся), `config.py` (флаг).

**Оставляем/убираем:** single-source путь (`normalize_generator_sources` + `generate_answer_with_empathy`)
**остаётся** как fallback и как путь для чисто ценовых/одиночных ответов. Не удалять.

**Тесты:**
- `evals/v5/generator_golden.json`: составной вопрос → ответ **упоминает оба аспекта**. Ассерт: см. §5 —
  проверять по **наличию фактов/refs из пакета**, а не по конкретным словам.
- verifier golden: ответ с оброненным «обычно» / с «приживётся» → verifier помечает. Ассерт по вердикту verifier.
- Числовой gate golden не ослаблять.

**Готово:** `run_demo_eval.py --suite product` и `--suite golden` зелёные при `COMPOSER_ON=1`; составные кейсы отвечают на всё; verifier ловит дропнутые хеджи.

---

### Фаза 4 — Clarify slice (`pending_clarify` state machine)

**Зачем:** уточнения словами + кнопки; обработка «да» на вопрос-выбор; уход за человеком в другую тему.

**Что делать:**
- Состояние сессии `pending_clarify { question, options[{id,label,action_ref}], asked_at_turn, topic }` —
  по образцу существующего lead-flow (`session.py`, `flow_handlers.py`, `lead_interrupt.py`).
- Разбор ответа (bucket-классификатор), порядок:
  1. клик по кнопке (ref) — детерминированно, без LLM;
  2. явный выбор словами → сопоставить с `options` (bounded LLM, fail-open к «не понял»);
  3. другая тема → переиспользовать существующие интенты (`contacts_intent`, price intent, catalog match) → ответить на новое, clarify отложить;
  4. не-выбор/мусор → мягкий переспрос, **не более 1–2 раз** (счётчик), затем коротко про оба;
  5. устарело (`asked_at_turn` далеко) → забыть `pending_clarify`.
- Подключить к двум реальным точкам: `price_lookup_clarify` (юнит, `orchestration/price_flow.py`) и
  `patient_options_overview` (`orchestration/patient_playbook_flow.py`). Кнопки — из каталога/сценариев (I3),
  вопрос формулирует композер.
- Флаг `CLARIFY_STATE_ON` (env, default 0).

**Файлы:** `session.py` (состояние), `flow_handlers.py` (разбор), `core/clarify_state.py` (новый, классификатор),
`orchestration/price_flow.py` и `orchestration/patient_playbook_flow.py` (точки подключения),
`ux_builder.py` (рендер вопрос+кнопки вместе), `config.py` (флаг).

**Оставляем/убираем:** существующие button-clarify (`build_price_unit_clarify_payload`, `guided_menu_payload`)
**остаются**; добавляется понимание текстового ответа и память хода. Ничего не удаляем.

**Тесты:**
- Unit на bucket-классификатор: «да» → re-ask; «а сколько стоит» → topic_change; «второе» → select option 2;
  8-й ход после вопроса → stale. Ассерт по **bucket-решению**, не по тексту.
- Кейс «переспрос ≤ 2, потом про оба» (ассерт по счётчику/структуре).
- E2E smoke: диалог «А/Б → да → переспрос → выбор».

**Готово:** `run_e2e_smoke.py` покрывает clarify-диалог; нет зацикливания переспросов.

---

### Фаза 5 — Cleanup (только после паритета фаз 1–4)

**Зачем:** снять долг, ради которого всё затевалось. **Строго после** зелёного eval с включёнными флагами.

**Что делать (по одному, с eval после каждого):**
- Снять Stage 1.5 shims (`TECH_DEBT.md` таблица «Временные shims»): `try_a3_catalog_md_direct`,
  `STEPS_VISITS`/`TEMPORARY_TEETH`/`PERMANENT_CROWN_WHY_WAIT` regex→md — заменены aspect+packet.
- Свести «5 памятей» к одному focus: `last_subject`/`last_aspect`/`dialog_focus`/`last_patient_situation`/
  `last_catalog_service_id` → один `DialogState` (постепенно, читатели остаются, источник правды один).
- Убрать legacy price paths, когда пакет полностью покрывает (`TECH_DEBT.md` §PriceBook #3): `prices.json` / часть `price_offers.json`.
- Флаги фаз 1–4 сделать default ON, старые пути удалить.

**Правило:** каждая удалённая строка — с прогоном `run_demo_eval.py --suite product` и `--suite golden`.
Ничего не удалять «на глаз».

---

### Фаза E — Миграция эмбеддингов с OpenAI (независимая; можно делать первой)

**Зачем:** сейчас поиск по базе — единственная не-китайская зависимость: OpenAI `text-embedding-3-large`.
Для РФ это риск доступа. Фаза **не связана** с composer — делается в любой момент, в т.ч. **до Фазы 1**,
если OpenAI недоступен.

**Точки в коде (их всего две — индекс и запрос, через один клиент):**
- `llm.py:51` — `embed_client = OpenAI(api_key=EMBED_API_KEY)`
- `build_index.py:131` — `embed_batch()` (индексация)
- `retriever.py:943` — `embed_q()` (запрос)
- `config.py` — `EMB_MODEL`, `EMBED_API_KEY`
- `core/client_data_loader.py:85` — `_embedding_dim_for_empty_alias_matrix` (размерность)

**Что делать:**
- Ввести единую абстракцию `core/embeddings.py: embed(texts) -> np.ndarray`, за которой прячется провайдер.
  Обе точки (`embed_batch`, `embed_q`) зовут её. Провайдер — env `EMBED_PROVIDER=openai|dashscope|local`.
- **Вариант A — DashScope** (`text-embedding-v3/v4`): OpenAI-совместимый SDK, минимум правок
  (base_url/key/model). Один провайдер со всем остальным стеком.
- **Вариант B — локальный** (`bge-m3` или `multilingual-e5-large` через sentence-transformers):
  ноль внешних зависимостей, отлично с русским, для 50–70 md крутится даже на CPU. Максимальная устойчивость для РФ.

**Критичные подводные камни (обязательно):**
- **Размерность меняется** (3-large = 3072; bge-m3 / e5 / v3 ≈ 1024). Значит **все** `.npy` пересобрать:
  `python build_index.py --client all`. Проверить обработку dim в `_embedding_dim_for_empty_alias_matrix` и alias-матрицах.
- **Индекс и запрос — одна и та же модель.** Нельзя строить индекс одной, искать другой. Обе точки переключаются вместе.
- **Пороги перекалибровать.** `LOW_SCORE_THRESHOLD`, `ALIAS_STRONG_THRESHOLD`, `ALIAS_SOFT_THRESHOLD` в `config.py`
  настроены под распределение косинусов OpenAI. У новой модели распределение другое — пороги почти наверняка сдвинутся.
  Не оставлять старые «на глаз».
- **Нормализация векторов** — убедиться, что новый эмбеддер даёт нормализованные векторы (или нормализовать),
  иначе косинус поедет.

**Флаг:** `EMBED_PROVIDER` (env). OpenAI остаётся дефолтом, пока новый провайдер не проверен.

**Тесты / eval:**
- После пересборки — `run_demo_eval --suite product|golden|risk`: retrieval не должен просесть.
- Отдельно проверить alias-матчинг (сильные/мягкие алиасы) — он чувствителен к порогам.
- Если просело — **перекалибровать пороги**, а не ослаблять golden (правило T5).

**Оставляем/убираем:** OpenAI-путь остаётся за флагом до проверки; после паритета — `OPENAI_API_KEY` больше не нужен рантайму.

**Готово:** `EMBED_PROVIDER=dashscope|local`, индексы пересобраны, пороги перекалиброваны, eval зелёный,
рантайм не требует OpenAI.

---

## 5. Тесты — обязательные правила качества

Прецедент: тест ждал слово «цен» в ответе, бот сказал «стоимость» — тест упал, хотя ответ верный.
Это тест-антипаттерн. Правила ниже обязательны для всех новых и правимых тестов.

### Правило T1 — ассертить по структуре, не по словам

Проверяй то, что решил **детерминированный** слой (стабильно), а не формулировку LLM (вариативна):
- `answer_packet` / `answer_plan.aspects` — какие аспекты и карточки собраны;
- `meta.source_route` / `source_ref` / `doc_id` / `service_id` — какой источник выбран;
- `meta.price_offer_ids` / `fact_id` / `pricebook_*` — какие числа/факты разрешены;
- `promo_decision` / `suppressed_reason` — решение маркетинг-гейта;
- вердикт `verifier` / `numeric_fact_gate.action`.

```python
# ХОРОШО — проверяем решение, не слова
assert "price" in plan.aspects and "pain" in plan.aspects
assert packet_has_card(meta, aspect="promo") is False  # промо на pain подавлено
assert meta["source_route"]["service_id"] == "all_on_4"

# ПЛОХО — ломается от синонима «цена»→«стоимость»
assert "цен" in answer
```

### Правило T2 — если проверяешь текст, проверяй смысл, а не подстроку

Когда без проверки текста нельзя (напр. «ответ упомянул оба аспекта»):
- проверяй **наличие факта/числа из пакета** (`"250 000" in answer` или сумма из `fact`), не служебное слово;
- для темы — набор синонимов, а не одно слово: `any(w in low for w in ("стоимост","цен","₽","руб"))`;
- никогда не ассертить одно конкретное вводное слово, вежливость или порядок предложений.

### Правило T3 — детерминизм теста

- LLM-шаги (aspect planner, composer, clarify-классификатор) в unit-тестах **мокаются** фиксированным выводом.
- E2E/golden с реальным LLM — только там, где это осознанно (генерация), и ассерты по T1/T2.
- `temperature=0` для всех классификаторов.

### Правило T4 — не подгонять regex/промпт под падающий кейс

Если golden падает — чинить **причину** (аспект/пакет/источник), а не добавлять слово в ответ или сужать regex
под конкретную фразу. Подгонка под eval — это долг (см. `TECH_DEBT.md` Stage 1.5), а не решение.

### Правило T5 — не ослаблять ожидания ради зелёного

Числовой gate и verifier golden не ослаблять. Промо-подавление на чувствительных аспектах не ослаблять.
Если новый код требует ослабить такой тест — это сигнал, что нарушен инвариант §2.

### Команды eval (запускать после каждого PR)

```
python build_index.py --client demo            # если менялся corpus/aspect
python -m evals.v5.run_demo_eval --suite product
python -m evals.v5.run_demo_eval --suite golden
python -m evals.v5.run_demo_eval --suite risk
python -m evals.v5.run_planner_eval            # фазы 1–2
python -m evals.v5.run_e2e_smoke               # фаза 4
python scripts/lint_pricebook.py               # инварианты цен/промо
```
(Точные аргументы раннеров — сверить с `--help`; имена файлов в `evals/v5/`.)

---

## 6. Что удаляем и КОГДА

| Удаляем | Когда | Условие |
|---------|-------|---------|
| Stage 1.5 regex→md shims | Фаза 5 | packet покрывает эти маршруты, golden зелёный без shims |
| 4 из 5 «памятей» диалога | Фаза 5 | единый `DialogState`, follow-up eval зелёный |
| legacy `prices.json` / часть `price_offers.json` | Фаза 5 | pricebook покрывает, `lint_pricebook` зелёный |
| single-source content-путь | Фаза 5 | composer на паритете product+golden |

**Никогда не удаляем:** pricebook, `decide_promo_fact`, `numeric_fact_gate`, marketing.yaml/md/YAML-контент,
lead state machine. Это фундамент безопасности (§2).

---

## 7. Как проверяется здесь (Claude)

После каждой фазы присылай: изменённые файлы + вывод eval-команд (§5). Проверяю:
- инварианты §2 не нарушены (числа/промо/CTA/кнопки — из правил, гейт до LLM);
- тесты соответствуют §5 (структура, не слова; ничего не ослаблено);
- флаг присутствует и default OFF; старый путь не удалён раньше фазы 5;
- eval без регрессий (product/golden/risk).
