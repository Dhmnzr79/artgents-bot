# TASK — A9 Design: unknown-safe composable patient scope

Один активный `TASK.md` на один checkpoint. A9 начинается с **design-only** аудита. Код, тесты, prompt, runtime и live на этом checkpoint запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/ARCH_TARGET_DESIGN.md` — target TurnFrame, field-level validation и boundaries;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch и product firewall;
- `docs/TOPIC_SHADOW_REAUDIT_A7.md` — accepted field-level measurement pattern;
- текущий код `patient_situation` — только evidence о legacy/current state, не target по умолчанию.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- HEAD: `38d29f3 feat: add A8 planner field shadow validation`.
- A8 governance: `3a3b445`.
- A7 final audit: `596e809`.
- A7 raw SHA256: `EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA`.
- Topic matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- До design diff рабочее дерево чистое.

## 2. Вопрос A9

Нужно спроектировать, как новый `TurnFrame` будет выражать **масштаб и явно сообщённые обстоятельства ситуации пациента**, не пытаясь перечислить все фразы и не превращая одно поле в скрытый диагноз/маршрут.

Простой смысл:

> Что известно о масштабе ситуации: один зуб, несколько, вся дуга/челюсть, какая челюсть, какой этап — и что остаётся неизвестным?

Design обязан ответить:

1. Остаётся ли `patient_scope` одним scalar или становится компактным composable contract.
2. Какие измерения действительно относятся к scope, а какие должны жить отдельно.
3. Как представляется `unknown` по каждому измерению.
4. Как безопасно использовать уже существующий raw `patient_situation`, не копируя его строку в другую семантику.
5. Как в будущем измерить полноту/точность до передачи authority.

## 3. Почему нельзя сразу писать mapping

Current legacy смешивает в одном `PatientScope` разные типы понятий:

- масштаб: `one_tooth`, `few_teeth`, `full_jaw`;
- анатомию: `upper_jaw`;
- этап: `prosthetic_stage`;
- модификатор/состояние: `adjunct`, `urgent`;
- отсутствие конкретики: `generic`, `unknown`.

Одновременно `PatientSituationResult` уже отдельно хранит:

- `problem`;
- `extent`;
- `jaw`;
- `modifiers`;
- coarse `patient_scope`.

Есть минимум два дублирующих mapping:

- `core/patient_situation.py::_scope_for_kind`;
- `core/patient_situation_session.py::_PLANNER_SCOPE_BY_KIND`.

А `core/turn_frame_adapter.py` сейчас копирует `TurnPlan.patient_situation` прямо в `TurnFrame.patient_scope`, хотя `PatientSituationKind` и `PatientScope` — разные словари.

Поэтому прямой перенос текущего enum в shadow закрепит legacy-смешение вместо упрощения архитектуры.

## 4. Цель design checkpoint

Создать один новый документ:

- `docs/PATIENT_SCOPE_DESIGN_A9.md`

Документ должен:

1. Зафиксировать current data flow и все sources/consumers.
2. Провести evidence-based inventory существующих значений и вопросов.
3. Разделить независимые измерения.
4. Сравнить архитектурные варианты.
5. Выбрать один минимальный target contract с точной семантикой.
6. Определить unknown/failure/provenance policy.
7. Разбить будущую реализацию на маленькие checkpoints.

Это design, а не скрытая implementation spec: имена могут быть уточнены документом, но выбранный target должен быть однозначен и проверяем.

## 5. Read-only code alignment

Документ обязан сверить с file:line:

### Contracts

- `contracts/turn_plan.py` — raw `patient_situation: PatientSituationKind | None`;
- `contracts/patient_situation.py` — `PatientSituationKind`, `PatientScope`, `PatientSituationResult`, cues/profile fields;
- `contracts/turn_frame.py` — current `patient_scope: str | None` и единый `FieldMeta` на ось.

### Producers / mappings

- `core/patient_situation.py`:
  - rule/regex cues;
  - `_scope_for_kind`;
  - `_profile_for` (`problem/extent/jaw/modifiers`);
  - optional semantic LLM enrichment;
  - `unknown` behavior;
- `core/patient_situation_session.py`:
  - `_PLANNER_SCOPE_BY_KIND`;
  - `_PLANNER_EXTENT_BY_SCOPE`;
  - session carry/age guard;
- `core/turn_frame_adapter.py` — current semantic mismatch;
- `core/turn_frame_from_raw.py` — `patient_scope` пока `a7.not_migrated`;
- `core/turn_planner_llm.py` — один raw planner call и strict legacy branch.

### Product consumers

- `core/patient_situation_routing.py` — price unit/group bias;
- `core/patient_playbook.py` и `orchestration/patient_playbook_flow.py`;
- `orchestration/composer_flow.py`;
- metadata/session consumers.

Документ не должен путать current product usage legacy `patient_scope` с будущим TurnFrame authority.

## 6. Evidence inventory

Без live и без новых expectations документ должен собрать read-only inventory:

1. Полную таблицу всех `PatientSituationKind`.
2. Текущий mapping каждого kind → coarse scope.
3. Возможные `problem/extent/jaw/modifiers`, которые фактически создаёт код.
4. Где один kind теряет информацию или смешивает измерения.
5. Где два mapping расходятся или рискуют разойтись.
6. Не менее 15 существующих вопросов из repository tests/evals/client aliases, с source file:line.
7. Отдельно минимум:
   - один зуб;
   - несколько зубов;
   - вся челюсть/дуга;
   - верхняя челюсть;
   - нижняя челюсть;
   - существующие импланты / протезный этап;
   - удаление перед имплантацией;
   - костный дефицит как **явно сообщённый** modifier, не диагноз;
   - срочная жалоба;
   - общий интерес без масштаба;
   - короткий/непонятный вопрос;
   - составной случай (например extent + jaw + modifier).

Inventory — не frozen eval и не claim о качестве. Он показывает coverage/gaps текущей модели до target decision.

## 7. Обязательные semantic boundaries

### 7.1 Не диагноз

Scope описывает только явно сообщённые/надёжно структурированные признаки. Он не выводит:

- диагноз;
- состояние кости без явного сообщения;
- показания/противопоказания;
- подходящий протокол;
- All-on-4/All-on-6;
- необходимость операции;
- срочность лечения как медицинское заключение.

Фраза пациента «врач сказал, что мало кости» может дать explicit modifier; обычный вопрос об имплантации — нет.

### 7.2 Не service routing

Ни одно scope-значение не означает конкретный `service_id`:

```text
full_jaw != all_on_4
upper jaw != zygomatic implant
one tooth != classic implant automatically
```

Future price boundary может использовать только масштаб/единицу (`one_tooth` vs `jaw`) через отдельный authority gate, но A9 Design этого не включает.

### 7.3 Orthogonal dimensions

Документ обязан явно разобрать как минимум:

- extent/quantity;
- jaw/anatomy;
- treatment stage;
- explicit modifiers;
- urgency/medical boundary;
- unknown/insufficient information.

Он должен определить, какие из них входят в target patient scope, какие являются другими TurnFrame/policy axes, а какие остаются legacy до отдельной задачи.

Нельзя оставить один enum, где `full_jaw`, `upper_jaw`, `urgent` и `prosthetic_stage` считаются взаимоисключающими значениями одной природы, без явного обоснования.

## 8. Unknown-first contract

Target design обязан считать неполноту нормальным состоянием:

- unknown разрешён по каждому независимому измерению;
- unknown не превращается в ближайшее известное значение;
- отсутствующий jaw не означает both/upper/lower;
- отсутствующий extent не означает generic/full jaw;
- один известный признак сохраняется, даже если другой неизвестен/invalid;
- invalid одного subfield не уничтожает остальные;
- raw неизвестное значение не логируется и не попадает в telemetry;
- default/missing/invalid различимы через field-level metadata;
- `unknown` сам по себе не даёт product route и не заставляет задавать вопрос.

Clarification в будущем допустим только по безопасным вопросам, на которые пациент может ответить сам. Medical clarification запрещён.

## 9. Source / confidence / session policy

Документ обязан определить:

1. Какой source of truth допустим для каждого target subfield:
   - raw planner field;
   - deterministic mapping известного kind;
   - explicit session carry;
   - legacy detector только для comparison telemetry.
2. Как хранится provenance/confidence на уровне независимых значений.
3. Как не выдавать deterministic mapping за распознавание исходной фразы.
4. Как session carry отличается от текущего turn observation.
5. Как age guard/смена темы обнуляют carried scope.
6. Почему нельзя запускать второй patient-situation LLM как постоянный target path.

Один пользовательский ход в target не должен получать два конкурирующих semantic LLM source of truth.

## 10. Варианты, которые нужно сравнить

Документ обязан рассмотреть минимум четыре варианта:

### A. Оставить scalar `PatientScope`

Плюсы: минимальный diff. Минусы: смешение измерений, потеря составных случаев.

### B. Компактный nested/composable `patient_scope`

Несколько независимых полей в одном логическом scope-contract, с unknown по subfield.

### C. Несколько новых top-level TurnFrame axes

Например extent/jaw/stage/modifiers отдельно. Оценить риск роста сущностей и metadata.

### D. Переиспользовать current `PatientSituationResult`/parallel detector как authority

Оценить дублирование regex + отдельный LLM + product coupling.

Для каждого: выразительность, backward compatibility, field-level errors, session semantics, telemetry, стоимость/latency, путь удаления legacy.

Документ выбирает **один** target и объясняет, почему он минимален. Нельзя выбрать «все варианты понемногу».

## 11. Required target contract output

В design должен быть точный псевдоконтракт выбранного варианта:

- имена полей;
- типы;
- allowed values или источник client configuration;
- defaults/unknown;
- invariants;
- metadata granularity;
- stable field errors;
- serialization/privacy boundary;
- один worked example составного случая;
- один worked example частично неизвестного случая;
- один worked example invalid unrelated subfield при сохранении остальных.

Если target меняет `TurnFrame.patient_scope` type, документ обязан дать backward-compatible migration plan и не разрешать немедленное runtime wiring.

## 12. Product firewall

A9 design не разрешает:

- подключать target scope к price/evidence/composer/UI;
- менять current `PatientSituationResult` consumers;
- менять medzone/booking/contacts;
- удалять regex/legacy detector;
- менять planner prompt;
- добавлять второй LLM;
- менять session carry;
- чинить preservation 02/03/05;
- передавать authority.

Design должен перечислить будущие AST/source firewall checks.

## 13. Future migration checkpoints

Документ обязан разбить будущую работу минимум так:

1. **A9 Design** — этот документ.
2. **A9 Contract** — models/FieldMeta only, no runtime.
3. **A9 Raw extraction** — один raw planner payload → partial scope shadow; strict legacy unchanged.
4. **A9 Shadow wiring** — telemetry only; product firewall.
5. **A9 Frozen quality matrix** — expected до live; single-turn + multi-turn/session cases.
6. **A9 One-run live/audit** — coverage/correctness/unknown rate; no retry.
7. **Authority decision** — отдельный checkpoint только при достаточных доказательствах.

Документ может уточнить разбиение, но не объединять contract/runtime/live/authority в один diff.

## 14. Design allowlist

После governance commit разрешён **ровно один новый файл**:

- `docs/PATIENT_SCOPE_DESIGN_A9.md`

Запрещено менять:

- `TASK.md`;
- `docs/ARCH_TARGET_DESIGN.md`;
- contracts/core/orchestration/tests/evals;
- client content/config/pricebook;
- A6/A7/A8 artifacts;
- Cursor rules/checklists.

Любой другой tracked/untracked candidate → ❌ и СТОП.

## 15. Design review commands

Live/LLM/pytest не запускать. Код не меняется.

```powershell
git status --short
git diff --check
git diff --name-only
git diff -- contracts core orchestration tests evals clients
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Checker обязан самостоятельно сверить все code claims и file:line references.

## 16. Стоп-условия

СТОП и эскалация, если design:

- требует code/test/runtime diff;
- предлагает hardcoded phrase catalog как target;
- пытается перечислить «все ситуации» без unknown;
- связывает scope с конкретным лечением/service id;
- превращает urgency/bone state в диагноз;
- использует parallel detector/второй LLM без плана удаления;
- не может развести scalar legacy значения по независимым измерениям;
- скрывает потери mapping;
- требует product authority до quality matrix/live audit;
- противоречит meta-goal «меньше сущностей».

## 17. Definition of Done

A9 Design завершён, когда:

1. Создан только `docs/PATIENT_SCOPE_DESIGN_A9.md`.
2. Current code/data flow и дубли mappings подтверждены file:line.
3. Evidence inventory grounded в repository sources.
4. Независимые измерения и unknown policy однозначны.
5. Выбран один минимальный target contract.
6. Scope не является диагнозом, service route или price decision.
7. Product firewall и future checkpoints определены.
8. Frozen hashes/raw неизменны.
9. Independent Cursor checker дал `✅`.
10. Создан отдельный doc commit и push только в `codex/stage-a`.

После этого — СТОП. Contract/implementation/live/authority не начинать без нового `TASK.md`.
