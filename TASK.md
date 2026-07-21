# TASK — S5 Minimal Doctor Data Contract

**Ветка:** `codex/stage-a`

**Baseline:** `8891797 feat: build offline KB source index S4`

**Серия / checkpoint:** `S5` — строгие модели и локальные валидаторы минимального
target doctor catalog без loader, client migration или подключения к ответам.

**Режим:** offline contract only. Никаких `clients/**`, current doctor runtime,
routes/UI, live/LLM или product authority.

## Решение владельца продукта

Для врача нужны только:

- имя и стабильный технический ID;
- должность;
- стаж в полных годах;
- привязка к услугам, которые врач оказывает;
- ссылка на общий продающий текст профиля в MD.

Не нужны и запрещены в target contract: `active`, образование, сертификаты, фото,
расписание/слоты, синхронизация с календарём/CRM, отдельные карточки, рейтинги и
самостоятельное назначение врача ботом. Если врач присутствует в каталоге, он доступен
для информационного ответа; организационные вопросы решает администратор.

## Evidence из текущего локального контура

Read-only аудит перед TASK обнаружил 17 doctor profiles и 3 overview MD в локальных
packs. Общая полезная семантика уже существует: name, position, experience_years,
service links и продающий MD-текст; все текущие service links существуют в
соответствующих service catalogs. Current runtime также умеет отвечать на service/team
doctor queries.

S5 не копирует legacy parser/routing. Аудит нужен, чтобы не изобретать уже решённые
поля. Расхождения legacy (`cta_key`/`cta_text`, aliases, permissive fallbacks,
отсутствующий `active`) не становятся target contract.

## Цель

Добавить отдельный новый модуль:

```python
class TargetDoctor(BaseModel): ...
class TargetDoctorCatalog(BaseModel): ...
```

S5 формализует только wire shape и локальные законы одного doctor catalog. Он не читает
MD/JSON/YAML, не проверяет существование service/profile refs и не строит
`doctor:<doctor_id>` index. Эти cross-file проверки требуют следующего отдельного
integrity/loader checkpoint.

## Затрагиваемые файлы

- `TASK.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — зафиксировать минимальный doctor layer,
  query expectations и убрать устаревшее требование doctor `active`;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — синхронизировать ownership doctor layer;
- `contracts/doctor_schema.py` (new);
- `tests/test_doctor_schema_contract.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая doctor MD и service catalogs;
- `doctors_lookup.py`, current loaders, retrieval, routing/orchestration и caches;
- frozen S1–S4 contracts/loaders/index builders/tests;
- изменение `ResponseSchemaBundle` и S2 target-pack layout;
- чтение/парсинг frontmatter или MD content;
- existence validation для `service_ids` и `profile_ref`;
- doctor index builder и соединение с `ResponseSchemaExternalIndex`;
- recommendation/ranking/selection, prompts, answers, CTA, UI/cards и session;
- booking, administrator hand-off, schedule/calendar/CRM integration;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## Нормативный wire contract

Новый `contracts/doctor_schema.py` определяет:

```python
class TargetDoctor(TargetDoctorSchemaModel):
    name: NonBlankStr
    position: NonBlankStr
    experience_years: StrictInt  # >= 0
    service_ids: list[NonBlankStr]
    profile_ref: DoctorProfileRef

class TargetDoctorCatalog(TargetDoctorSchemaModel):
    doctors: dict[DoctorId, TargetDoctor]
```

`doctor_id` является ключом mapping, а не дублирующим полем записи. `DoctorId`:

- exact ASCII lower-case identifier `[a-z0-9][a-z0-9_-]*`;
- не trim/lower/slugify;
- current-style ID `doctors__doctor__volkov` допустим, но не предписан;
- пробел, `:`, `.`, `/`, uppercase и пустое значение запрещены.

`TargetDoctor`:

- `extra="forbid"`;
- все пять полей обязательны, defaults отсутствуют;
- `name` и `position` — exact non-blank strings без normalization;
- `experience_years` — strict integer `>= 0`; bool/float/string запрещены;
- `service_ids` — обязательный непустой list exact non-blank IDs, без duplicates;
  порядок сохраняется, регистр не нормализуется;
- `profile_ref` — frozen S1 `SourceRef` с обязательным prefix `kb:` и document suffix
  `.md`; это ссылка на один exact MD chunk с общим продающим текстом, а не копия текста;
- `active`, aliases, education, certificates, photo, schedule, slots, card/UI fields,
  rating, priority, CTA и любые extras отвергаются.

`TargetDoctorCatalog`:

- `extra="forbid"`;
- содержит только mapping `doctors`;
- пустой mapping допустим;
- порядок mapping и всех authored lists сохраняется;
- одинаковые doctor IDs не могут существовать после mapping parse; duplicate raw
  JSON/YAML keys остаются ответственностью будущего strict loader.

## Product expectations, но не S5 authority

Будущая runtime-задача должна поддержать без отдельной doctor-card системы:

- «кто делает импланты» → врачи, связанные с соответствующими service IDs;
- «кто крутой специалист по винирам» → подходящие по service IDs врачи и только их
  утверждённый MD-профиль; без выдуманного рейтинга «лучший»;
- «какие у вас врачи, какой опыт» → имя, должность, стаж и краткая продающая информация
  из MD;
- если врачей несколько, показать релевантных специалистов, а выбор/запись оставить
  администратору;
- никаких данных о расписании и обещаний доступности.

S5 только сохраняет эти требования в architecture docs. Он не реализует query
recognition, filtering, rendering или UI.

## Обязательные invariants

1. Новый contract импортирует только Pydantic и frozen types из
   `contracts.response_schema`; не изменяет их.
2. Нет filesystem, environment, network, logging, cache, client resolution или globals
   с накопленным state.
3. Нет legacy adapters/fallbacks и dual-read ради текущего локального demo.
4. Модели не содержат свободный дублирующий selling text: owner текста — exact MD ref.
5. Наличие doctor record означает только возможность показать утверждённую информацию,
   не доступность для записи и не медицинскую/коммерческую рекомендацию.
6. S5 не подключается к S2/S3/S4 или product path и не объявляет schema активной.
7. A9 patient scope не является входом и не получает authority.

## Protected tests / честность

- новый `tests/test_doctor_schema_contract.py` использует только synthetic payloads;
- `clients/**` не читается и не копируется;
- frozen tests и production modules не меняются;
- запрещены skip/xfail, условные PASS, runtime mocks и snapshot legacy output.

## Минимальные acceptance tests

Compact test module доказывает:

1. exact valid catalog со всеми пятью doctor fields проходит и сохраняет mapping/list
   order, case и strings без normalization;
2. пустой doctors mapping допустим;
3. отсутствие каждого обязательного поля отвергается;
4. blank name/position/service ID и empty/duplicate `service_ids` отвергаются;
5. `experience_years` принимает `0` и положительный strict int, отвергает negative,
   bool, float и string;
6. valid/invalid DoctorId boundaries проверены, включая current-style double underscore;
7. `profile_ref` принимает exact `kb:path/profile.md#chunk`, отвергает `fact:`,
   `doctor:`, non-`.md`, malformed KB ref и не нормализует case;
8. parameterized forbidden extras явно покрывают `active`, education, photo, schedule,
   card/UI, rating/priority и CTA;
9. models не мутируют input и два последовательных catalog validations не делят state;
10. schema introspection подтверждает ровно разрешённые поля и отсутствие defaults;
11. source/AST audit подтверждает отсутствие IO/current doctor/client/runtime/session/A9
    imports, loaders, writes, cache и side effects.

## Verification

До кода:

1. независимый read-only checker читает TASK, обе architecture-doc правки, S1
   `NonBlankStr`/`SourceRef`, current doctor audit evidence, checklist и guardrails;
2. checker подтверждает соответствие решению владельца, минимальность, отсутствие
   `active`/schedule/cards и отсутствие runtime authority;
3. при `❌`/`❓` governance исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_contract.py -q`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_refs.py tests/test_response_schema_kb_index.py -q --basetemp=.pytest_cache/s5-regression-basetemp`;
3. `git diff --check`, `git status --short`, diff только по allowlist;
4. независимый read-only checker сначала читает tests, затем contract/roadmap diff и
   сам запускает те же команды;
5. live/LLM, current doctor tests и полный pytest не запускаются: consumers не меняются.

## Definition of Done

- минимальные doctor data fields выражены строгими offline models/validators;
- `active`, образование, фото, schedule и special cards отсутствуют и запрещены;
- selling profile остаётся source-owned MD ref, без дублирования текста;
- `clients/**`, current doctor runtime, answers, routes, UI, session и authority не
  изменились;
- roadmap отмечает S5 как offline contract foundation, не schema activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
