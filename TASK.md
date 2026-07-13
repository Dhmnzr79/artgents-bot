# TASK — A6: заморозить матрицу качества native topic

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — `docs/ARCH_TARGET_DESIGN.md` v4, `docs/TURN_FRAME_SHADOW_AUDIT_A3.md` и A5 commit `8662300`.

---

## 1. Зафиксированная точка старта

- A0 frozen preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A1 TurnFrame: `0761213`.
- A2 shadow observability: `3746d77`.
- A3 audit: `0cb8ca3`.
- A4 client topic taxonomy + contract: `2757cae`.
- A5 native topic в planner/shadow: `8662300`.
- После A5 рабочее дерево должно быть чистым.
- Native `topic` остаётся **shadow-only** и не имеет authority.

## 2. Зачем нужен A6

A5 показал `topic=implantation` на пяти implant-кейсах. Этого недостаточно, чтобы считать ось качественной: выборка узкая и почти однотематическая.

A6 сначала замораживает независимую матрицу по **всем девяти** темам demo-пакета и по неоднозначным вопросам. Вопросы и ожидаемые темы фиксируются **до live-прогона**, чтобы Исполнитель не мог подобрать их под фактические ответы LLM.

На этом checkpoint мы создаём **только spec**. Runner, runtime, prompt, тесты и live-вызовы не меняются и не запускаются.

```text
client MD frontmatter topics
          ↓
frozen A6 matrix (этот checkpoint)
          ↓ следующий отдельный checkpoint
real existing plan_turn() → audit report

routing/evidence/composer/UI ← без изменений
```

## 3. Название и результат задачи

**A6 Spec — frozen native-topic quality matrix.**

Создать один файл:

`evals/v5/demo/topic_shadow_matrix.json`

Результат этого checkpoint:

- 33 заранее заданных fresh-session вопроса;
- 27 однозначных кейсов: по 3 на каждую тему;
- 6 неоднозначных кейсов с `expected_topic: null`;
- ожидания опираются на `topic` в frontmatter клиентских MD, а не на текущий вывод LLM;
- нет observed/current результатов, confidence thresholds и разрешения на authority.

## 4. Семантика будущего прогона — зафиксировать в spec

Spec должен явно содержать верхнеуровневые поля:

```json
{
  "schema_version": 1,
  "suite_id": "a6_topic_shadow_quality_matrix",
  "client_id": "demo",
  "execution_mode": "planner_direct_live",
  "fresh_session_per_case": true,
  "authority": "shadow_only",
  "taxonomy_source": "clients/{client_id}/md/*.md frontmatter.topic",
  "expected_taxonomy_ordered": [
    "clinic",
    "doctors",
    "extraction",
    "implantation",
    "orthodontics",
    "periodontology",
    "prosthetics",
    "treatment",
    "whitening"
  ],
  "scoring_contract": {},
  "cases": []
}
```

`execution_mode: planner_direct_live` означает для следующего checkpoint:

- вызывать реальный существующий `plan_turn()`;
- использовать тот же production prompt, тот же LLM-call и реальную taxonomy demo;
- один вызов на один кейс;
- без mock/stub и без полного `/ask` pipeline;
- не оценивать route, evidence, текст ответа, UI или marketing;
- contacts/ingress boundaries не должны исключать темы из выборки, потому что измеряется именно planner axis;
- адаптер и downstream уже покрыты A4/A5 unit + A5 live firewall и не становятся предметом A6 spec.

## 5. Scoring contract

В `scoring_contract` зафиксировать ровно такую семантику:

```json
{
  "scored_field": "turn_plan.topic",
  "confidence_field": "turn_plan.topic_confidence",
  "match_rule": "exact_normalized_or_null",
  "one_live_call_per_case": true,
  "retry_failed_case": false,
  "confidence_is_descriptive_only": true,
  "confidence_pass_threshold": null,
  "required_metrics": [
    "overall_exact_match",
    "per_topic_exact_match",
    "ambiguous_null_exact_match",
    "confusion_matrix",
    "planner_unavailable_count",
    "invalid_or_out_of_taxonomy_count",
    "confidence_by_correctness_descriptive"
  ],
  "authority_decision_allowed": false
}
```

Правила:

- `expected_topic` сравнивается с нормализованным `TurnPlan.topic` точным равенством;
- для ambiguous-кейсов правильное значение — только `null`;
- любое значение вне frozen taxonomy считается ошибкой, а не новым классом;
- `plan_turn() -> None`/exception/time-out учитывается как `planner_unavailable`, не как topic mismatch и не скрывается;
- self-reported confidence только записывается; A6 не называет её калиброванной и не вводит порог;
- отсутствие retry запрещает выбирать лучший ответ из нескольких запусков;
- даже 33/33 не дают `topic` authority автоматически.

## 6. Case schema

Каждый элемент `cases` содержит **ровно**:

```json
{
  "id": "topic_a6_...",
  "case_kind": "grounded_single_topic | ambiguous_null",
  "question": "...",
  "expected_topic": "topic-or-null",
  "source_doc_id": "doc-id-or-null",
  "rationale": "короткое объяснение ожидания"
}
```

Не добавлять в строки:

- `observed_topic`, `current`, `actual`, `pass`;
- expected route/service/aspect/doc answer;
- confidence expectation или threshold;
- альтернативный список допустимых тем;
- regex/keyword gates;
- тексты ожидаемых ответов бота.

## 7. Frozen matrix — переписать в spec без изменения смысла

Порядок кейсов обязателен.

### 7.1 `clinic` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_01_clinic_payment` | `Какие способы оплаты есть в клинике?` | `clinic` | `clinic__info__payment_terms` |
| `topic_a6_02_clinic_warranty` | `Какая гарантия действует в клинике?` | `clinic` | `clinic__info__warranty` |
| `topic_a6_03_clinic_consultation` | `Как проходит консультация в клинике?` | `clinic` | `clinic__info__consultation` |

### 7.2 `doctors` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_04_doctors_overview` | `Какие врачи работают в клинике?` | `doctors` | `doctors__doctor__overview` |
| `topic_a6_05_doctors_named` | `Расскажите о докторе Волкове` | `doctors` | `doctors__doctor__volkov` |
| `topic_a6_06_doctors_implants` | `Кто из врачей занимается имплантацией?` | `doctors` | `doctors__doctor__overview` |

Кейс 06 намеренно содержит слово про имплантацию, но спрашивает **кто из врачей**. Ожидание `doctors` взято из doctor overview aliases, а не из текущего LLM.

### 7.3 `extraction` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_07_extraction_process` | `Как проходит удаление зуба?` | `extraction` | `extraction__service__tooth_extraction` |
| `topic_a6_08_extraction_pain` | `Больно ли удалять зуб?` | `extraction` | `extraction__service__tooth_extraction` |
| `topic_a6_09_extraction_aftercare` | `Что делать после удаления зуба?` | `extraction` | `extraction__service__tooth_extraction` |

### 7.4 `implantation` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_10_implantation_survival` | `Какая приживаемость имплантов?` | `implantation` | `implantation__faq__osseointegration` |
| `topic_a6_11_implantation_comparison` | `All-on-4 или All-on-6 — чем отличаются?` | `implantation` | `comparison__all_on_4_vs_all_on_6` |
| `topic_a6_12_implantation_pain` | `Больно ли устанавливать имплант?` | `implantation` | `implantation__faq__pain` |

### 7.5 `orthodontics` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_13_orthodontics_overview` | `Что такое элайнеры?` | `orthodontics` | `orthodontics__service__aligners` |
| `topic_a6_14_orthodontics_indications` | `Какие проблемы исправляют элайнеры?` | `orthodontics` | `orthodontics__service__aligners` |
| `topic_a6_15_orthodontics_process` | `Как проходит лечение на элайнерах?` | `orthodontics` | `orthodontics__service__aligners` |

### 7.6 `periodontology` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_16_periodontology_overview` | `Что такое пародонтит?` | `periodontology` | `periodontology__service__periodontitis` |
| `topic_a6_17_periodontology_gums` | `Почему кровоточат дёсны?` | `periodontology` | `periodontology__service__periodontitis` |
| `topic_a6_18_periodontology_save_teeth` | `Можно ли сохранить шатающиеся зубы?` | `periodontology` | `periodontology__service__periodontitis` |

### 7.7 `prosthetics` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_19_prosthetics_veneers` | `Что такое виниры?` | `prosthetics` | `prosthetics__service__veneers` |
| `topic_a6_20_prosthetics_removable` | `Какие бывают съёмные протезы?` | `prosthetics` | `prosthetics__service__removable_dentures` |
| `topic_a6_21_prosthetics_zirconia` | `Что такое циркониевая коронка?` | `prosthetics` | `prosthetics__service__zirconia_crowns` |

### 7.8 `treatment` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_22_treatment_caries` | `Как лечат кариес?` | `treatment` | `treatment__service__caries` |
| `topic_a6_23_treatment_pulpitis` | `Что такое пульпит?` | `treatment` | `treatment__service__pulpitis` |
| `topic_a6_24_treatment_overview` | `Как проходит лечение зубов?` | `treatment` | `treatment__service__teeth_treatment` |

### 7.9 `whitening` — 3

| id | question | expected_topic | source_doc_id |
|---|---|---|---|
| `topic_a6_25_whitening_overview` | `Что такое профессиональное отбеливание зубов?` | `whitening` | `whitening__service__teeth_whitening` |
| `topic_a6_26_whitening_cleaning` | `Нужна ли чистка перед отбеливанием?` | `whitening` | `whitening__service__teeth_whitening` |
| `topic_a6_27_whitening_safety` | `Безопасно ли отбеливание для эмали?` | `whitening` | `whitening__service__teeth_whitening` |

### 7.10 Ambiguous fresh-session → `null` — 6

| id | question | expected_topic | source_doc_id | rationale |
|---|---|---|---|---|
| `topic_a6_28_null_general_price` | `Сколько стоит лечение?` | `null` | `null` | Не названа услуга или предметная область. |
| `topic_a6_29_null_choice` | `Что лучше выбрать?` | `null` | `null` | Нет вариантов и нет предыдущего контекста. |
| `topic_a6_30_null_booking` | `Хочу записаться` | `null` | `null` | Намерение есть, предметная область не названа. |
| `topic_a6_31_null_pain` | `Мне больно` | `null` | `null` | Не указано, где и с какой услугой связан вопрос. |
| `topic_a6_32_null_more` | `Расскажите подробнее` | `null` | `null` | Fresh session, отсутствует объект follow-up. |
| `topic_a6_33_null_options` | `Какие у вас есть варианты?` | `null` | `null` | Не указано, варианты чего нужны. |

Для всех 27 grounded-кейсов `case_kind = "grounded_single_topic"`.
Для кейсов 28–33 `case_kind = "ambiguous_null"`.

`rationale` для grounded-кейсов должен кратко говорить: ожидаемая тема совпадает с frontmatter указанного source doc. Не копировать текст документа целиком.

## 8. Источники истины

Перед записью spec Исполнитель обязан read-only проверить:

- `load_client_topic_taxonomy("demo")` возвращает ровно frozen список из 9 тем;
- каждый `source_doc_id` существует в `clients/demo/md/*.md`;
- frontmatter `topic` каждого source doc совпадает с `expected_topic`;
- ambiguous-кейсы не получают искусственный source doc.

Запрещено использовать как источник expected:

- вывод A5 live;
- текущий ответ `plan_turn()`;
- legacy `DecisionFrame.service_topic`;
- filename/doc_id inference вместо frontmatter;
- собственное предположение Исполнителя, если оно расходится с таблицей TASK.

Если таблица TASK противоречит frontmatter — **СТОП**, spec не исправлять самостоятельно, эскалировать Архитектору с `file:line`.

## 9. Затрагиваемые файлы — строгий allowlist

Исполнитель может создать **только**:

- `evals/v5/demo/topic_shadow_matrix.json`.

Исполнитель не меняет:

- `TASK.md`;
- `core/**`, `contracts/**`, `orchestration/**`;
- `tests/**`;
- `evals/v5/run_demo_eval.py`, `smoke_case_runner.py` и другие runners;
- client MD/config/pricebook/policies;
- `preservation.json`, smoke/risk/golden/emotion;
- architecture/audit docs.

Любой другой diff → ❌ и СТОП.

## 10. Protected contracts

Не менять:

- `evals/v5/demo/preservation.json`;
- A0 hash `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`;
- вопросы, порядок, expected topics и source doc ids из раздела 7 этого TASK;
- A5 runtime/tests.

После spec review и отдельного commit новый `topic_shadow_matrix.json` также становится protected. Runner следующего checkpoint не сможет менять его ради зелёного результата.

## 11. Явно НЕ делать

- Не запускать LLM/live eval на spec checkpoint.
- Не узнавать observed topic до freeze/commit spec.
- Не добавлять runner/harness/validator/test.
- Не менять planner prompt или sanitization.
- Не давать topic влияние на route/evidence/composer/UI/policy.
- Не добавлять retry, majority vote или выбор лучшего run.
- Не вводить confidence threshold.
- Не подменять ambiguous `null` наиболее вероятной темой.
- Не ослаблять матрицу, если будущий live окажется красным.
- Не создавать commit/branch/stash без команды владельца.

## 12. Проверки spec checkpoint

Выполнить:

```powershell
python -m json.tool evals/v5/demo/topic_shadow_matrix.json > $null
git diff --check
git status --short
git diff -- evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Дополнительно read-only проверить и показать в отчёте:

- case count = 33;
- unique ids = 33;
- grounded count = 27;
- ambiguous count = 6;
- по каждой из 9 тем grounded count = 3;
- expected topics входят в frozen taxonomy или равны `null`;
- source doc/frontmatter match = 27/27;
- unknown keys по case schema отсутствуют;
- live/LLM calls = 0.

Нельзя создавать отдельный validation script на этом checkpoint. Проверку допускается выполнить одноразовой read-only командой в терминале.

## 13. Стоп-условия

СТОП и эскалация, если:

- рабочее дерево до начала не чистое;
- нужен файл вне allowlist;
- taxonomy demo не равна frozen списку из 9 тем;
- source doc отсутствует или его frontmatter topic не совпадает;
- вопрос/expected кажется спорным;
- хочется сначала вызвать LLM, а потом записать expected;
- хочется добавить альтернативные допустимые темы;
- для проверки spec требуется менять runner/runtime/tests;
- preservation hash изменился;
- появился посторонний diff.

Формат эскалации:

```text
СТОП: требуется решение Архитектора
Факт:
Файл/строка:
Почему TASK нельзя выполнить дословно:
Варианты без самостоятельного выбора:
```

## 14. Контрольные точки

### Checkpoint 1 — Spec authoring

Исполнитель:

1. Проверяет clean baseline и hash.
2. Создаёт только `topic_shadow_matrix.json`.
3. Не запускает live/LLM.
4. Показывает полный spec diff, counts и source/frontmatter verification.
5. Делает СТОП без commit.

### Checkpoint 2 — Spec review

Checker независимо проверяет:

- diff только одного allowlist-файла;
- matrix дословно соответствует TASK;
- expected взяты из source frontmatter;
- ambiguous действительно fresh/no-context;
- нет observed/current/resnapshot полей;
- scoring contract не даёт authority и не калибрует confidence;
- live не запускался;
- preservation hash прежний.

Вердикт: `✅ / ❌ / ❓`.

### Checkpoint 3 — Freeze commit

Только после `✅` владелец отдельно разрешает commit одного spec-файла. После commit — чистое дерево и СТОП.

Harness/live/audit для A6 будут отдельным следующим `TASK.md`. Этот spec checkpoint их не начинает.

## 15. Формат отчёта Исполнителя

1. `git status --short` до начала.
2. Полный changed-files.
3. JSON parse result.
4. Counts: total/unique/grounded/ambiguous/per-topic.
5. Таблица `case id → expected topic → source doc → actual frontmatter topic`.
6. Подтверждение `live_calls=0`.
7. `git diff --check`.
8. Preservation hash.
9. Skipped/not run.
10. Явный СТОП без commit.

## 16. Критерий приёмки A6 Spec

A6 Spec принят, когда один новый JSON-файл честно и заранее фиксирует 33 вопроса по всем 9 темам и ambiguous-null группе, каждое grounded expectation подтверждено client frontmatter, никаких observed результатов ещё нет, runtime/harness/tests не менялись, live не запускался, frozen preservation hash сохранён.

Это **не** решение дать `topic` власть. Это измерительная линейка, которую нельзя переписать после того, как мы увидим результат.
