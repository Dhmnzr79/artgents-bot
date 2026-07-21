# TASK — S6 Doctor Cross-Reference Integrity

**Ветка:** `codex/stage-a`

**Baseline:** `e73f44c feat: add minimal doctor schema S5`

**Серия / checkpoint:** `S6` — pure in-memory проверка doctor→service/profile refs и
детерминированная сборка `doctor:<doctor_id>` refs.

**Режим:** offline contract validation only. Никаких loaders, `clients/**`, текущего
doctor runtime, routes/UI, live/LLM или product authority.

## Решение владельца продукта

- service link означает простую связь врача с услугой; отдельных ролей, фаз комплексной
  услуги и ранжирования нет;
- при любом показе врача в будущем ответе используются имя, должность и стаж, даже если
  пациент не спросил о стаже отдельно; MD добавляет продающий профиль;
- один semantic `service_id` должен связывать цепочку «описание услуги → цена → кто
  делает», включая короткие follow-up «сколько стоит?» и «а кто делает?»;
- это target behavior, но S6 не подключает его к ответам и не меняет authority.

## Цель

S5 проверяет локальную форму doctor catalog, но намеренно не знает, существуют ли
указанные услуги и MD-профили. S6 добавляет один pure boundary:

```python
class DoctorCatalogExternalIndex(BaseModel):
    service_ids: tuple[NonBlankStr, ...]
    kb_refs: tuple[DoctorProfileRef, ...]

def validate_doctor_catalog_external_refs(
    catalog: TargetDoctorCatalog,
    index: DoctorCatalogExternalIndex,
) -> None: ...

def build_doctor_source_refs(
    catalog: TargetDoctorCatalog,
) -> tuple[SourceRef, ...]: ...
```

Validator доказывает, что каждая простая doctor→service связь и каждый `profile_ref`
имеют exact target. Builder превращает ключи каталога в стабильный sorted набор
`doctor:<doctor_id>`, который будущий loader сможет передать frozen S3 external index.

## Почему scope минимален

Здесь не нужен filesystem или parser: S1/S4/S5 уже задали типы service/KB/doctor refs.
Pure comparison закрывает следующий contract boundary без client migration и без
решения, как runtime формирует текст ответа.

Demo materialization идёт отдельным следующим checkpoint после S6. Предварительно
зафиксирован минимальный план: сохранить текущих шесть врачей; добавить whitening
Фёдоровой, sinus lift Волкову и Орлову, zygomatic/pterygoid Волкову; КТ оставить
clinic-level diagnostic service без doctor link; убрать производные числа и `99,8%`
из doctor overview. S6 эти данные не меняет и не тестирует.

## Затрагиваемые файлы

- `TASK.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — записать simple service-link,
  experience-by-default и shared service-context laws;
- `contracts/doctor_schema_refs.py` (new);
- `tests/test_doctor_schema_refs.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, doctor MD и service catalogs;
- `doctors_lookup.py`, current loaders, retrieval, routing/orchestration и caches;
- frozen S1–S5 contracts/loaders/index builders/tests;
- изменение `ResponseSchemaBundle`, S2 loader или S3 external index;
- filesystem discovery, JSON/YAML/frontmatter/MD parsing;
- doctor selection/ranking, role/phase metadata и complex-service semantics;
- query recognition, follow-up resolution, session writes, price routing и rendering;
- prompts, answers, CTA, UI/cards, booking, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## External index contract

`DoctorCatalogExternalIndex`:

- Pydantic v2, `extra="forbid"`, `frozen=True`, `strict=True`;
- принимает только tuple, не конвертирует list/set/string;
- `service_ids` содержит exact non-blank IDs;
- `kb_refs` содержит только valid S5 `DoctorProfileRef` (`kb:...md#...`);
- каждый tuple unique; порядок входа и case сохраняются, normalization нет;
- пустые tuples допустимы.

Индекс не хранит doctor refs, source text, prices, availability, client ID или paths.
Лишние доступные service/profile refs допустимы.

## Validation law

S6 обходит всех doctors и все authored `service_ids`:

- service ID должен exact и case-sensitive присутствовать в `index.service_ids`;
- `profile_ref` должен exact присутствовать в `index.kb_refs`;
- все missing service IDs и profile refs агрегируются после полного scan;
- duplicate missing refs между врачами появляются в error один раз;
- порядок doctors/service lists не меняется;
- наличие связи означает только возможность показать врача по услуге, без roles,
  priority, ranking, schedule или обещания записи.

`DoctorCatalogExternalRefError` наследует `ValueError` и содержит:

- `code == "doctor_catalog_external_refs_missing"`;
- `missing_service_ids: tuple[str, ...]`;
- `missing_profile_refs: tuple[str, ...]`;
- оба tuple unique и lexicographically sorted.

Ошибка поднимается один раз. При отсутствии missing refs функция возвращает строго
`None`, ничего не фильтрует и не мутирует.

## Doctor source-ref builder

`build_doctor_source_refs(catalog)`:

- создаёт ровно один `doctor:<doctor_id>` для каждого mapping key;
- валидирует каждый результат frozen S1 `SourceRef`;
- возвращает tuple, lexicographically sorted по полному ref;
- empty catalog → `()`;
- не проверяет external integrity автоматически и не строит S3 index wrapper;
- не нормализует ID, не читает profile text и не сохраняет результат.

Невалидный constructed ref невозможен после S5 `DoctorId`; отдельный fallback/error
не вводится. Тест должен доказать реальное использование S1 adapter через introspection
и valid exact output, а не monkeypatch implementation internals.

## Обязательные invariants

1. Новый модуль импортирует только Pydantic и frozen S1/S5 types.
2. Нет filesystem, environment, network, logging, cache, client resolution или globals
   с накопленным state.
3. Нет `active`, roles, phases, specialty inference, ranking или availability.
4. Validator/builder не мутируют catalog/index и не меняют authored order.
5. Два последовательных вызова с разными indexes независимы.
6. S6 не подключается к S2/S3/S4 loader/index или product path.
7. Shared service context и experience-by-default записаны только как future runtime
   law; A9 patient scope не получает authority.

## Protected tests / честность

- новый `tests/test_doctor_schema_refs.py` использует только synthetic S5 payloads;
- `clients/**` не читается и не копируется;
- frozen tests и production modules не меняются;
- запрещены skip/xfail, условные PASS, runtime mocks и snapshot legacy output.

## Минимальные acceptance tests

1. Полный exact index валидирует catalog и возвращает `None`.
2. Missing services и profiles из нескольких doctors собираются одной error с exact
   code и sorted unique tuples.
3. Case mismatch считается missing; extras index refs допустимы.
4. Empty catalog/index допустимы.
5. Index отвергает list/set/string, extras, blank/duplicate services, wrong-prefix,
   non-`.md` и malformed profile refs; config strict/frozen/forbid проверен.
6. Два вызова с разными indexes не делят state.
7. До/после validation `model_dump()` catalog/index идентичны, mapping/list/index order
   и case сохранены.
8. Builder возвращает sorted exact `doctor:` refs, empty tuple для empty catalog и
   каждый ref отдельно проходит frozen S1 `TypeAdapter(SourceRef)`.
9. Catalog insertion order намеренно противоположен expected builder sort.
10. Source/AST audit подтверждает отсутствие IO/current doctor/client/runtime/session/A9
    imports, writes, cache и side effects.

## Verification

До кода:

1. независимый read-only checker читает TASK, architecture diff, frozen S1/S3/S5,
   checklist и guardrails;
2. checker подтверждает simple-link semantics, deterministic aggregate error,
   experience/shared-context laws без runtime authority и минимальность;
3. при `❌`/`❓` governance исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_refs.py -q`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_contract.py tests/test_response_schema_refs.py -q`;
3. `git diff --check`, `git status --short`, diff только по allowlist;
4. независимый read-only checker сначала читает tests, затем implementation/roadmap и
   сам запускает те же команды;
5. live/LLM, current doctor tests и полный pytest не запускаются: consumers не меняются.

## Definition of Done

- doctor→service/profile refs имеют одну pure deterministic integrity boundary;
- exact `doctor:<id>` refs строятся из S5 catalog без filesystem и legacy coupling;
- simple link, experience-by-default и shared service-context laws записаны без
  product activation;
- `clients/**`, current doctor runtime, answers, routes, UI, session и authority не
  изменились;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
