# TASK — A7 Contract: partial-capable TurnFrame и PlannerAttempt

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** после принятого A7 Design.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Архитектурная опора — `docs/ARCH_TARGET_DESIGN.md`, `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` и текущий код.

---

## 1. Зафиксированная точка старта

- A7 Design governance: `f2bceab`.
- A7 Design: `7f9cfe4`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Перед началом tracked working tree должен быть чистым.

Принятый design фиксирует один будущий planner attempt с двумя ветками:

```text
один raw JSON
  ├─ field-level builder → partial TurnFrame shadow
  └─ strict TurnPlan validation → current product path
```

Этот TASK реализует **только модели данных и их совместимость с существующим legacy→TurnFrame adapter**. Он не получает raw JSON и не подключает dual-branch к runtime.

## 2. Цель checkpoint

Создать честный контракт, в котором:

1. `FieldMeta` явно хранит `status` и стабильный `error`.
2. `TurnFrame` может представить частичный результат:
   - `aspects=[]` допустим;
   - `primary_aspect=None` допустим;
   - заданный `primary_aspect` обязан входить в `aspects`.
3. Новый `PlannerAttempt` различает:
   - `ok`;
   - `partial`;
   - `not_available`;
   - `degraded`.
4. Строгий legacy `TurnPlan` не меняется.
5. Существующий adapter продолжает строить те же semantic values, но заполняет новые metadata честно.
6. Никакой runtime wiring, planner split или product authority в этом checkpoint нет.

## 3. Не цель

На этом этапе **не** делать:

- извлечение partial frame из raw LLM JSON;
- `plan_turn_attempt()`;
- изменение `plan_turn()`;
- изменение prompt или LLM response handling;
- wiring в `resolver_turn.py` / `turn_frame_shadow.py`;
- новый статус в runtime ctx;
- использование partial frame для route/decision/evidence/composer/policy/UI;
- live/LLM/eval прогоны;
- новый A6 raw;
- исправление семи A6 unavailable-кейсов;
- перенос product ownership со strict `TurnPlan`.

## 4. Строгий allowlist

Исполнитель может изменить только:

1. `contracts/turn_frame.py`
2. `contracts/planner_attempt.py` — новый файл
3. `contracts/__init__.py`
4. `core/turn_frame_adapter.py`
5. `tests/test_turn_frame_contract.py`
6. `tests/test_planner_attempt_contract.py` — новый файл

Любой другой diff → ❌ и СТОП.

Особенно запрещено менять:

- `contracts/turn_plan.py`;
- `core/turn_planner_llm.py`;
- `core/turn_frame_shadow.py`;
- `orchestration/**`;
- `llm.py`, `app.py`;
- `TASK.md` и архитектурные документы;
- frozen eval specs/harness;
- продуктовые тесты вне allowlist;
- client content / pricebook / marketing.

`core/turn_frame_adapter.py` в allowlist только для совместимости с обязательными `FieldMeta.status/error`. Его сигнатура, источники semantic values и отсутствие thematic inference должны сохраниться.

## 5. Контракт FieldMeta

### 5.1 Типы

В `contracts/turn_frame.py` добавить публичные aliases:

```python
FieldStatus = Literal["valid", "defaulted", "missing", "invalid"]

FieldErrorReason = Literal[
    "aspects_empty",
    "aspects_invalid_type",
    "aspect_not_allowed",
    "primary_aspect_unavailable",
    "topic_not_allowed",
    "topic_invalid_type",
    "topic_confidence_invalid",
    "route_invalid",
]
```

`FieldMeta`:

```python
confidence: float  # required, 0..1
provenance: str    # required, non-empty
status: FieldStatus  # required; без неявного default
error: FieldErrorReason | None = None
```

### 5.2 Инвариант status/error

- `status="invalid"` требует `error is not None`.
- Любой `status != "invalid"` требует `error is None`.
- Неизвестный status/error и extra fields отклоняются.
- Не использовать raw exception text или raw user/LLM value как error.

`error` — маленький frozen allowlist первого A7 slice. Расширение возможно только отдельной архитектурной задачей.

### 5.3 Один source of truth

Не добавлять `field_errors` в `TurnFrame`, `TurnFrameMeta` или `PlannerAttempt`.

Если позже telemetry потребуется flat list ошибок, она должна детерминированно выводиться из `TurnFrameMeta`. В этом checkpoint такой telemetry helper не нужен.

## 6. Partial-capable TurnFrame

Изменить только structural contract:

```python
aspects: list[AspectKind] = Field(default_factory=list)
primary_aspect: AspectKind | None = None
```

Инварианты:

- `aspects=[]` + `primary_aspect=None` → valid model.
- Непустой `aspects` + `primary_aspect=None` → valid partial model.
- Если `primary_aspect is not None`, он обязан входить в `aspects`.
- `aspects=[]` + non-null `primary_aspect` отклоняется тем же общим инвариантом.
- Не расширять `AspectKind`.
- Не менять `RouteIntent`, emotion/specificity или остальные semantic axes.
- `extra="forbid"` сохраняется.

Важно: допустимость partial `TurnFrame` **не** означает допустимость partial `TurnPlan` и не даёт product authority.

## 7. PlannerAttempt contract

Создать `contracts/planner_attempt.py`.

Публичные типы:

```python
ShadowAttemptStatus = Literal["ok", "partial", "not_available", "degraded"]

class PlannerAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_plan: TurnPlan | None
    shadow_frame: TurnFrame | None
    shadow_status: ShadowAttemptStatus
```

Не добавлять raw payload, question, answer, history, exception, retry count, route result или UI state.

### 7.1 Structural status invariants

`PlannerAttempt` обязан валидировать:

#### `ok`

- `legacy_plan is not None`;
- `shadow_frame is not None`;
- в `shadow_frame.field_meta` нет `invalid` или `missing`;
- `defaulted` допустим.

#### `partial`

- `shadow_frame is not None`;
- и выполняется хотя бы одно:
  - `legacy_plan is None`;
  - хотя бы одна ось frame имеет status `invalid` или `missing`.
- `partial` с valid legacy plan и полностью valid/defaulted frame отклоняется: это `ok`.

#### `not_available`

- `legacy_plan is None`;
- `shadow_frame is None`.

#### `degraded`

- `shadow_frame is None`;
- `legacy_plan` может быть `None` или valid `TurnPlan`, потому что shadow builder/serialization может сломаться независимо от strict branch.

Это только contract invariant. В этом checkpoint нет функции, которая классифицирует raw outcome.

## 8. Экспорт контрактов

В `contracts/__init__.py` экспортировать:

- `FieldStatus`;
- `FieldErrorReason`;
- `ShadowAttemptStatus`;
- `PlannerAttempt`;
- существующие `FieldMeta`, `TurnFrameMeta`, `TurnFrame` сохранить.

Не создавать import cycle. `planner_attempt.py` может импортировать `TurnFrame` и `TurnPlan`; `turn_frame.py` не должен импортировать `PlannerAttempt`.

## 9. Совместимость legacy adapter

`core/turn_frame_adapter.py` остаётся чистой функцией:

- принимает только `TurnPlan`, optional `DecisionFrame`, optional explicit `primary_aspect`;
- не читает question/answer/history/raw JSON/taxonomy/client content/session;
- не вызывает LLM/resolver/network;
- не импортирует `PlannerAttempt`;
- не строит partial frame из invalid raw;
- не меняет semantic values и provenance относительно A1–A5.

Обновить только создание `FieldMeta`:

- явно передавать status;
- обычное явно полученное значение → `valid`;
- безопасное системное значение (`emotion="none"`, false follow-up default) → `defaulted`;
- отсутствующая legacy axis → `missing`;
- strict legacy adapter не должен создавать `invalid`, потому что получает уже валидный `TurnPlan`.

Минимальная семантика для существующих путей:

| axis/source | status |
|-------------|--------|
| intent из `DecisionFrame` или `TurnPlan` | `valid` |
| native topic присутствует | `valid` |
| topic из non-unknown `DecisionFrame.service_topic` | `valid` |
| topic отсутствует/unknown | `missing` |
| aspects из strict TurnPlan | `valid` |
| primary aspect из explicit param или aspects[0] | `valid` |
| emotion=`none` из hard default | `defaulted` |
| specificity из query_mode | `valid` |
| specificity=`unknown` без decision | `missing` |
| service_id/patient_scope/followup_of отсутствуют | `missing` |
| follow_up=true из followup_of | `valid` |
| follow_up=false при отсутствующем followup_of | `defaulted` |
| needs_clarification из strict plan boolean | `valid` |

`error=None` для всех metadata legacy adapter.

## 10. Обязательные тесты

Сначала показать diff тестов.

### 10.1 FieldMeta

Проверить:

1. Все четыре status принимаются при корректном error invariant.
2. `status` обязателен — старый constructor без status красный.
3. `invalid` без error отклоняется.
4. `valid/defaulted/missing` с error отклоняются.
5. Unknown status отклоняется.
6. Unknown error отклоняется.
7. Confidence вне 0..1 отклоняется.
8. Пустой provenance отклоняется.
9. Extra field отклоняется.

### 10.2 TurnFrame

Проверить:

1. Existing full frame продолжает создаваться.
2. `aspects=[]`, `primary_aspect=None` создаётся.
3. Non-empty aspects, `primary_aspect=None` создаётся.
4. Non-null primary в aspects создаётся.
5. Non-null primary вне aspects отклоняется.
6. Empty aspects + non-null primary отклоняется.
7. Serialization сохраняет `status` и `error` каждой оси.
8. Unknown top-level/meta field отклоняется.

Старый тест `test_empty_aspects_rejected` не удалять молча: переписать в явный positive partial-contract test и добавить отдельный negative test для non-null primary.

### 10.3 PlannerAttempt

Новый `tests/test_planner_attempt_contract.py` должен проверить:

1. `ok` с valid legacy plan + frame без invalid/missing.
2. `ok` без legacy plan отклоняется.
3. `ok` без frame отклоняется.
4. `ok` с invalid/missing metadata отклоняется.
5. `partial` с legacy None + frame принимается.
6. `partial` с legacy valid + invalid/missing metadata принимается.
7. `partial` с legacy valid + полностью valid/defaulted frame отклоняется.
8. `partial` без frame отклоняется.
9. `not_available` с обоими None принимается.
10. `not_available` с legacy plan или frame отклоняется.
11. `degraded` без frame принимается и с legacy None, и с legacy plan.
12. `degraded` с frame отклоняется.
13. Extra field / unknown status отклоняются.
14. Worked example `topic=doctors`, `aspects=[]`:
    - legacy None;
    - partial;
    - topic meta valid;
    - aspects invalid / `aspects_empty`;
    - primary invalid / `primary_aspect_unavailable`.
15. Model dump не содержит raw/question/answer/history/exception.

### 10.4 Legacy compatibility/firewall

Проверить:

1. `TurnPlan(aspects=[])` по-прежнему отклоняется.
2. Adapter semantic values до/после не изменены.
3. Adapter явно выставляет valid/defaulted/missing и никогда invalid.
4. Adapter signature не получила raw/question/answer/history/client/taxonomy.
5. `PlannerAttempt` не импортируется из runtime modules.
6. `contracts/planner_attempt.py` не импортирует Flask/app/orchestration/LLM/resolver.
7. Не появилось тематических веток для doctors/extraction/A6 case ids.

Source/AST scans допустимы только как дополнительный firewall, не вместо functional tests.

## 11. Запрещённые способы сделать тесты зелёными

Нельзя:

- ослаблять или удалять unrelated assertions;
- добавлять skip/xfail/conditional PASS;
- менять `TurnPlan.aspects min_length=1`;
- давать `FieldMeta.status` неявный default ради старых constructors;
- разрешать arbitrary error string;
- хранить error одновременно в двух независимых местах;
- считать missing axis valid;
- маркировать legacy adapter metadata invalid;
- менять semantic output adapter;
- импортировать partial contract в resolver/composer/evidence;
- добавлять runtime flag;
- подгонять branches под семь вопросов A6;
- обновлять frozen spec/hash;
- запускать live несколько раз.

## 12. Acceptance criteria

A7 Contract принимается только если:

- changed files ровно из allowlist;
- `TurnPlan` diff пуст;
- runtime wiring diff пуст;
- `FieldMeta.status` required;
- status/error invariant строгий;
- error — typed allowlist;
- TurnFrame partial-capable;
- primary invariant сохранён;
- PlannerAttempt имеет ровно три поля и четыре статуса;
- status invariants покрыты негативными тестами;
- legacy adapter semantics сохранены;
- partial contract не получает authority;
- все обязательные тесты зелёные без skip;
- frozen hashes совпадают;
- raw не менялся;
- live/LLM не запускались.

## 13. Команды проверки

Исполнитель запускает:

```powershell
python -m pytest -q tests/test_turn_frame_contract.py tests/test_planner_attempt_contract.py
python -m pytest -q tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py
python -m pytest -q tests/test_turn_planner_llm.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
python -m py_compile contracts/turn_frame.py contracts/planner_attempt.py core/turn_frame_adapter.py
git diff --check
git diff -- contracts/turn_plan.py core/turn_planner_llm.py core/turn_frame_shadow.py orchestration
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a6_last.txt
git status --short
```

Нужно явно перечислить:

- passed/failed/skipped;
- warnings и logging errors;
- всё, что не запускалось;
- полный changed-files;
- отсутствие live/LLM;
- hashes.

## 14. Stop conditions

СТОП и эскалация Архитектору, если:

- нужен файл вне allowlist;
- без изменения `TurnPlan` тесты не проходят;
- adapter нельзя мигрировать без смены semantic values;
- `PlannerAttempt` требует runtime import;
- status semantics неоднозначны;
- хочется добавить default для `FieldMeta.status`;
- появляется второй error source;
- product/runtime начинает читать partial frame;
- frozen hash изменился;
- обнаружен unrelated WIP.

При сомнении не расширять scope самостоятельно.

## 15. Checkpoints

### Checkpoint 1 — Implementation

Исполнитель:

1. показывает pre-status;
2. показывает diff тестов первым;
3. реализует только allowlist;
4. запускает команды §13;
5. показывает полный отчёт;
6. не создаёт commit;
7. СТОП.

### Checkpoint 2 — Independent checker

Checker независимо проверяет:

- тесты первыми;
- status/error truthfulness;
- PlannerAttempt invariants;
- TurnPlan unchanged;
- adapter compatibility;
- firewall;
- hashes и skipped/not run;
- вердикт `✅ / ❌ / ❓`.

### Checkpoint 3 — Commit

Только после `✅` владельца:

- stage ровно allowlist-файлы с реальным diff;
- отдельный commit A7 Contract;
- clean tree;
- следующий этап не начинать.

## 16. Формат отчёта Исполнителя

1. Diff тестов — первым.
2. Полный changed-files.
3. Production diff по моделям и adapter.
4. Таблица status/error invariants.
5. Таблица PlannerAttempt status invariants.
6. Доказательство TurnPlan/runtime unchanged.
7. Результаты всех команд §13.
8. Skipped/not run/warnings/logging errors.
9. Frozen hashes и raw SHA256.
10. Нарушения или сомнения `file:line`.
11. Commit не создан.

## 17. Definition of Done

A7 Contract завершён, когда partial-capable `TurnFrame`, обязательный per-field `FieldMeta.status/error` и строгий `PlannerAttempt` существуют как изолированные модели с честными негативными тестами; legacy `TurnPlan` остаётся строгим, legacy adapter сохраняет semantic values и product/runtime ещё не знает о новом attempt envelope.
