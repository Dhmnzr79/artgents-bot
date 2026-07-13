# TASK — A6 Audit: зафиксировать неполный topic quality sample

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** после независимого raw review.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — frozen A6 matrix, принятый harness и единственный raw run.

---

## 1. Зафиксированная точка старта

- A5 native topic shadow: `8662300`.
- Frozen A6 matrix: `cd562fe`.
- A6 harness: `952c50a`.
- A6 live governance: `307390d`.
- Matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Raw artifact: `eval_topic_shadow_a6_last.txt` (UTF-16, gitignored).
- Raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Attempts: `1`.
- Independent checker verdict: `❓ — технически неполный quality sample`.

Рабочее дерево tracked должно быть чистым. Raw не удалять, не переименовывать и не перезаписывать.

## 2. Задача

Создать один read-only audit-документ:

- `docs/TOPIC_SHADOW_AUDIT_A6.md`.

Документ должен честно зафиксировать:

- целостность единственного run;
- 26 scoreable exact matches;
- 7 `planner_unavailable`;
- отсутствие topic mismatches среди доступных планов;
- невозможность оценить doctors целиком и часть extraction/ambiguous;
- корневую техническую причину `aspects=[] → TurnPlan validation failure → plan_turn None`;
- отсутствие оснований для confidence calibration и topic authority;
- следующий архитектурный вопрос: field-level outcome/validation без изменения legacy product ownership.

На этом этапе нельзя менять код, тесты, spec, harness или запускать LLM.

## 3. Затрагиваемые файлы — строгий allowlist

Исполнитель может создать только:

- `docs/TOPIC_SHADOW_AUDIT_A6.md`.

Исполнитель не меняет:

- `TASK.md`;
- `docs/ARCH_TARGET_DESIGN.md`;
- `evals/v5/demo/topic_shadow_matrix.json`;
- `evals/v5/demo/preservation.json`;
- `evals/v5/run_topic_shadow_eval.py`;
- `tests/test_topic_shadow_eval_contract.py`;
- `core/**`, `contracts/**`, `orchestration/**`;
- client content/config;
- raw artifact.

Любой другой diff → ❌ и СТОП.

## 4. Источники истины

Audit строится только из:

1. `eval_topic_shadow_a6_last.txt` с frozen SHA256.
2. `evals/v5/demo/topic_shadow_matrix.json` с frozen git-blob hash.
3. `evals/v5/run_topic_shadow_eval.py` commit `952c50a` — только для описания semantics.
4. `contracts/turn_plan.py` — только для ссылки на `aspects: Field(min_length=1)`.
5. Независимого raw-review, но все его числа нужно повторно сверить с raw.

Запрещено:

- запускать planner/LLM снова;
- использовать новый sample;
- додумывать raw topic до Pydantic rejection;
- считать `observed_topic=null` у unavailable фактическим LLM topic;
- трактовать unavailable как mismatch или correct-null;
- выводить причинность, которой raw не доказывает.

## 5. Обязательная структура audit-документа

### 5.1 Заголовок и статус

```text
# Native topic quality audit — A6
Статус: ❓ технически неполный quality sample
Authority: запрещена
```

Сразу объяснить: run целый и честный, но не является полноценной оценкой всех 33 кейсов из-за семи unavailable планов.

### 5.2 Provenance

Таблица:

- commits A5/spec/harness/live governance;
- matrix path/hash;
- raw path/SHA256/encoding/size;
- attempts=1;
- 33 `A6_CASE`, один `A6_SUMMARY`, `A6_EXIT_CODE=1`;
- дата/временное окно только как наблюдаемый факт raw, без домыслов.

### 5.3 Методика

Кратко и точно:

- direct production `plan_turn(question, None, "demo")`;
- frozen order;
- один call/case, без retry;
- exact normalized topic/null;
- confidence descriptive only;
- denominator frozen=33;
- downstream `/ask`, routing, evidence, composer и UI не измерялись;
- audit не оценивает качество ответов бота.

### 5.4 Integrity

Зафиксировать:

- indices 1..33 и frozen order;
- attempts=1;
- raw hash совпал;
- нет второго summary/index=1/retry artifact;
- protected hashes и tracked tree не изменились.

### 5.5 Главная сводка — разделить coverage и correctness

Нельзя писать только «accuracy 78.8%» без объяснения.

Обязательные показатели:

| metric | value | допустимая интерпретация |
|---|---:|---|
| frozen total | 33 | полный denominator |
| scoreable plans | 26 | coverage 26/33 = 78.79% |
| unavailable | 7 | не получили валидный TurnPlan |
| exact among scoreable | 26/26 | на доступной части mismatch не найден |
| topic mismatch | 0 | не доказывает качество unavailable кейсов |
| invalid/out-of-taxonomy | 0 | sanitizer/contract не выдали invalid result |
| skipped | 0 | кейсы не исключались |

Допустимо показать frozen overall `26/33`, но назвать его **exact coverage over frozen denominator**, а не чистой classifier accuracy: семь строк не были классифицированы harness как валидный plan.

### 5.6 Per-topic coverage table

Таблица для всех девяти тем и отдельной ambiguous-null группы:

- expected total;
- scoreable;
- exact;
- unavailable;
- coverage rate;
- exact rate among scoreable (`n/a`, если scoreable=0).

Фактические значения:

| group | total | scoreable | exact | unavailable |
|---|---:|---:|---:|---:|
| clinic | 3 | 3 | 3 | 0 |
| doctors | 3 | 0 | 0 | 3 |
| extraction | 3 | 2 | 2 | 1 |
| implantation | 3 | 3 | 3 | 0 |
| orthodontics | 3 | 3 | 3 | 0 |
| periodontology | 3 | 3 | 3 | 0 |
| prosthetics | 3 | 3 | 3 | 0 |
| treatment | 3 | 3 | 3 | 0 |
| whitening | 3 | 3 | 3 | 0 |
| ambiguous null | 6 | 3 | 3 | 3 |

Для doctors exact rate among scoreable = `n/a`, не `0%` и не `100%`.

### 5.7 Seven unavailable cases

Таблица всех семи:

- index;
- case id;
- expected topic;
- harness status/reason;
- validation error field;
- raw line reference(s).

Список:

- 04 `topic_a6_04_doctors_overview`;
- 05 `topic_a6_05_doctors_named`;
- 06 `topic_a6_06_doctors_implants`;
- 09 `topic_a6_09_extraction_aftercare`;
- 28 `topic_a6_28_null_general_price`;
- 30 `topic_a6_30_null_booking`;
- 31 `topic_a6_31_null_pain`.

Для всех причина должна быть описана одинаково:

```text
LLM payload был отклонён TurnPlan validation из-за aspects=[];
plan_turn вернул None;
harness корректно записал planner_unavailable.
```

Но обязательно добавить ограничение доказательства:

```text
Raw не сохраняет валидированное значение topic из отклонённого payload,
поэтому нельзя утверждать, был topic в этих семи ответах правильным,
неправильным или null.
```

Не вставлять exception traceback целиком. Достаточно стабильного сообщения `aspects: List should have at least 1 item` и raw line refs.

### 5.8 Confusion matrix — только ненулевые cells

Перечислить фактические cells:

- clinic→clinic=3;
- doctors→planner_unavailable=3;
- extraction→extraction=2;
- extraction→planner_unavailable=1;
- implantation→implantation=3;
- orthodontics→orthodontics=3;
- periodontology→periodontology=3;
- prosthetics→prosthetics=3;
- treatment→treatment=3;
- whitening→whitening=3;
- null→null=3;
- null→planner_unavailable=3.

Сумма=33. Unavailable не превращать в observed null.

### 5.9 Confidence — descriptive only

Зафиксировать:

- correct bucket: count=26, min=0.0, max=1.0, mean=0.8692;
- incorrect: empty;
- invalid: empty;
- три genuine null exact-match входят в correct с confidence=0.0;
- unavailable не имеют confidence.

Явно написать:

- self-reported confidence не калибрована;
- из n=26 нельзя выбирать threshold;
- mean не является вероятностью правильности;
- confidence не разрешает authority.

### 5.10 Что доказано / не доказано

**Доказано:**

- harness и raw integrity;
- 26 scoreable topic values exact на frozen expectations;
- zero observed mismatches на scoreable subset;
- семь all-or-nothing plan rejections связаны с `aspects=[]` validation;
- topic всё ещё не влияет на product routing.

**Не доказано:**

- качество topic на doctors;
- качество topic на четырёх остальных unavailable cases;
- 100% accuracy на 33;
- calibration;
- качество product answers/evidence/UI;
- готовность к authority.

### 5.11 Архитектурный вывод

Сформулировать без реализации:

- A6 обнаружил coupling: scoreability native topic зависит от валидности unrelated legacy field `aspects`;
- all-or-nothing `TurnPlan` мешает field-level наблюдаемости;
- простое ослабление `aspects min_length` или prompt-hardcode `overview` **не рекомендуется**, потому что может перевести текущие fail-open кейсы на planner-owned product path и изменить ответы;
- повтор A6 без архитектурного изменения не закрывает пробел и запрещён текущим one-run contract.

### 5.12 Рекомендация следующего этапа

Рекомендовать отдельный **A7 contract/design checkpoint**:

```text
Field-level planner outcome / field_errors, shadow-only:
валидный topic может быть наблюдаем независимо от ошибки aspects,
но legacy TurnPlan eligibility и текущий product fail-open сохраняются.
```

Обязательные границы рекомендации:

- один существующий LLM-call;
- без нового topic classifier;
- без разрешения topic authority;
- без автоматического `aspects=["overview"]`;
- без изменения `turn_plan_to_decision_frame`, route/evidence/composer/UI;
- current seven product paths остаются прежними;
- новый A6 rerun возможен только после отдельного spec/review решения и с сохранением первого raw.

Не проектировать полный A7 API в audit-документе и не писать код.

## 6. Raw line references

Все ключевые факты должны иметь ссылки вида:

```text
raw L<line>
```

Минимум:

- первые/последние `A6_CASE`;
- `A6_SUMMARY`;
- `A6_EXIT_CODE`;
- каждый из семи validation errors и соответствующий `A6_CASE`;
- при необходимости planner log, подтверждающий один call.

Line numbers считать по фактическому UTF-16 raw через read-only `Get-Content`. Hash raw должен остаться прежним после нумерации.

## 7. Явно НЕ делать

- Не запускать live/LLM повторно.
- Не создавать второй raw.
- Не менять/нормализовать encoding raw.
- Не менять frozen spec/harness.
- Не исправлять `aspects=[]`.
- Не ослаблять `TurnPlan`/`TurnFrame`.
- Не менять prompt.
- Не объявлять 26/26 итогом всей матрицы.
- Не считать unavailable mismatch или null-match.
- Не давать topic authority.
- Не создавать commit без команды владельца.

## 8. Проверки

```powershell
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a6_last.txt
git diff --check
git status --short
git diff -- evals/v5/demo/topic_shadow_matrix.json evals/v5/demo/preservation.json evals/v5/run_topic_shadow_eval.py tests/test_topic_shadow_eval_contract.py
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Read-only проверить:

- все числа audit совпадают с raw;
- line refs ведут на заявленные события;
- availability и correctness не смешаны;
- запрещённые claims отсутствуют;
- изменён только audit-doc;
- raw SHA256 прежний.

Unit/live тесты не запускать: код не меняется, повторный LLM запрещён.

## 9. Стоп-условия

СТОП, если:

- raw hash не совпал;
- нужен файл вне allowlist;
- числа raw расходятся с TASK;
- невозможно подтвердить line refs;
- хочется повторить run;
- для вывода нужно предположить topic отклонённого payload;
- появился tracked diff вне audit-doc;
- matrix/preservation hashes изменились.

## 10. Контрольные точки

### Checkpoint 1 — Audit authoring

Исполнитель создаёт только audit-doc, проводит read-only сверку и делает СТОП без commit.

### Checkpoint 2 — Audit review

Checker независимо проверяет doc↔raw, line refs, coverage/correctness semantics, запрещённые claims и границы A7 recommendation.

Вердикт: `✅ / ❌ / ❓`.

### Checkpoint 3 — Audit commit

Только после `✅` владелец разрешает commit одного audit-doc.

## 11. Формат отчёта Исполнителя

1. Changed-files.
2. Raw SHA256 до/после.
3. Разделы audit-документа.
4. Таблица line refs семи unavailable.
5. Coverage/correctness/per-topic/confusion verification.
6. Запрещённые claims scan.
7. Git/protected hashes.
8. Skipped/not run.
9. СТОП без commit.

## 12. Критерий приёмки A6 Audit

Audit принят, когда один новый документ byte-verifiably опирается на первый raw, отделяет 26/33 coverage от 26/26 correctness среди scoreable планов, не присваивает значения семи unavailable topic, фиксирует `aspects=[]` coupling без ремонта legacy, запрещает authority и формулирует A7 только как отдельный shadow-only field-level contract/design checkpoint.
