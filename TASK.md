# TASK — S8 Strict Doctor Catalog Loader

**Ветка:** `codex/stage-a`

**Baseline:** `f791b67 data: harden demo doctor template S7`

**Серия / checkpoint:** `S8` — строгая offline-загрузка минимального target doctor
catalog из одного явно переданного JSON-файла.

**Режим:** filesystem-to-contract foundation only. Никаких `clients/**`, current doctor
runtime, routes/UI, live/LLM или product authority.

## Цель

Добавить один изолированный loader:

```python
def load_doctor_catalog(catalog_path: Path) -> TargetDoctorCatalog: ...
```

Он читает JSON в окончательной wire-форме S5, отклоняет неоднозначный или повреждённый
файл и возвращает проверенный `TargetDoctorCatalog`.

S8 отвечает только на вопрос: «Можно ли безопасно и однозначно прочитать будущий
каталог врачей с диска?». Он не выбирает врача, не читает продающий MD-текст, не
соединяет каталог с услугами/ценами и не влияет на ответы.

## Почему это следующий минимальный scope

S5 зафиксировал поля каталога, S6 — проверки service/profile refs, S7 доказал, что
данные demo можно перенести в эту форму. До материализации demo-файла нужен строгий
disk→S5 boundary, иначе будущий consumer будет вынужден сам разбирать JSON и может
тихо принять duplicate keys, частичные данные или legacy-поля.

S8 намеренно не читает текущий doctor MD frontmatter и не преобразует
`name_full/services` в `name/service_ids`. Это не compatibility adapter старой
архитектуры. Следующий отдельный checkpoint сможет создать один target
`doctor_catalog.json` для demo и проверить его через S4→S6. Ещё более поздний
checkpoint сможет построить read-only service context для цепочки
«описание → цена → врач» по одному exact `service_id`.

## Затрагиваемые файлы

- `TASK.md`;
- `core/doctor_schema_loader.py` (new);
- `tests/test_doctor_schema_loader.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая demo MD, service catalog, pricebook и создание
  `doctor_catalog.json`;
- frozen S1–S7 contracts/loaders/index builders/tests;
- изменение S2 target-pack layout или `ResponseSchemaBundle`;
- current `doctors_lookup.py`, MD/frontmatter parsers, current loaders, retrieval,
  routing/orchestration и caches;
- mapping legacy authoring fields, fallback/dual-read и client discovery;
- service/price/profile existence validation: это делает S6 после явной сборки
  external index;
- doctor filtering/recommendation/ranking, query recognition, follow-up/session logic;
- чтение/рендеринг MD body, prompts, answers, CTA, UI/cards;
- booking, availability, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## Нормативный file contract

Loader принимает только `catalog_path: pathlib.Path` на один обязательный обычный
UTF-8 JSON-файл. Строка и любой другой тип не нормализуются в `Path`.

Top-level JSON — exact S5 wrapper:

```json
{
  "doctors": {
    "doctor_id": {
      "name": "...",
      "position": "...",
      "experience_years": 10,
      "service_ids": ["service_id"],
      "profile_ref": "kb:doctor.md#korotko"
    }
  }
}
```

Loader не добавляет defaults, не trim/lower/slugify значения, не выводит doctor ID из
filename и не принимает transitional/legacy keys. `active`, aliases, education, photo,
schedule, ranking, CTA и любые extras отклоняются frozen S5 contract.

## Loader API и fail-closed ошибки

Public surface нового модуля:

- `load_doctor_catalog(catalog_path: Path) -> TargetDoctorCatalog`;
- `DoctorCatalogLoadError` с полями `code: str`, `path: Path` и исходной причиной через
  exception chaining;
- локальный `DuplicateDoctorCatalogKeyError(ValueError)` для повторных JSON keys.

Обязательные error codes:

- `catalog_path_invalid` — non-`Path`, отсутствующий path, каталог вместо файла или
  иной неверный filesystem kind; cause соответственно `TypeError`,
  `FileNotFoundError` или `IsADirectoryError`/`OSError`;
- `file_read_failed` — UTF-8 decode/read error; cause `UnicodeDecodeError` или
  `OSError`;
- `json_invalid` — синтаксическая ошибка; cause `json.JSONDecodeError`;
- `duplicate_key` — повтор mapping key на любом уровне; cause
  `DuplicateDoctorCatalogKeyError`;
- `top_level_type_invalid` — top-level не mapping; cause `TypeError`;
- `schema_invalid` — S5 validation не прошла; cause `pydantic.ValidationError`.

Закон поля `DoctorCatalogLoadError.path`:

- для non-`Path` значения — `Path(".")`, поскольку допустимого входного пути нет;
- для missing/directory/иного invalid filesystem kind — исходный переданный
  `catalog_path`;
- для `file_read_failed`, `json_invalid`, `duplicate_key`,
  `top_level_type_invalid` и `schema_invalid` — исходный переданный `catalog_path`.

Ошибка никогда не возвращает пустой/default/частичный catalog. Текст exception не
является API; тесты проверяют code/path/cause/chaining.

## Детерминированное чтение и invariants

1. Файл читается строго как UTF-8.
2. JSON duplicate object keys отклоняются на любом уровне до Pydantic.
3. Top-level type проверяется до model validation.
4. Выполняется ровно один authoritative
   `TargetDoctorCatalog.model_validate(parsed_mapping)`; второй ослабленной schema нет.
5. Source values и authored mapping/list order сохраняются без normalization.
6. Loader не проверяет filesystem-существование `profile_ref` и `service_ids`: после
   загрузки это отдельная ответственность frozen S6.
7. Два последовательных вызова независимы; cache/shared mutable state отсутствует.
8. Нет filesystem writes, environment/network, logging side effects или client/global
   resolution.
9. Новый модуль импортирует только stdlib, Pydantic error type и S5 contract.
10. Loader не классифицирует запрос, не выбирает врача и не формирует answer context.
11. S8 не подключается к product path и не меняет A9/product authority.

## Protected tests / честность

- новый `tests/test_doctor_schema_loader.py` использует только synthetic `tmp_path`;
- `clients/**` не читается и не копируется;
- frozen tests не меняются;
- запрещены skip/xfail, conditional PASS, runtime mocks и snapshot legacy output.

## Минимальные acceptance tests

Compact test module доказывает:

1. полный synthetic catalog загружается как `TargetDoctorCatalog`, exact strings,
   mapping/list order и case сохранены;
2. пустой `doctors` mapping допустим;
3. string вместо `Path`, missing path и directory path дают
   `catalog_path_invalid`, exact path/cause/chaining;
4. invalid UTF-8 даёт `file_read_failed`;
5. malformed JSON даёт `json_invalid`;
6. duplicate top-level doctor key и nested doctor-field key дают `duplicate_key` до
   schema validation;
7. top-level list/scalar дают `top_level_type_invalid`;
8. payload transitional формы с `name_full`/`services` вместо
   `name`/`service_ids` даёт `schema_invalid` и не преобразуется loader-ом;
9. owner-rejected extra `active` отдельно даёт `schema_invalid`;
10. missing required field и invalid S5 value отдельно дают `schema_invalid` с
    original `ValidationError` и стабильным S5 error token;
11. filename намеренно не совпадает с doctor ID — ID берётся только из mapping key;
12. повторная загрузка после изменения synthetic source видит новое значение и не
    использует cache;
13. source/AST audit подтверждает отсутствие current doctor/client/runtime/session/A9
    imports, write APIs, environment/network и compatibility mapping; в loader ровно
    один вызов `TargetDoctorCatalog.model_validate(...)`, отсутствуют
    `model_construct`, вторая schema, fallback validation и compatibility converter.

## Verification

До кода:

1. независимый read-only checker читает TASK, S5/S6 contracts/tests, S7 template test,
   checklist и guardrails;
2. checker подтверждает final wire shape, fail-closed boundary, отсутствие legacy
   adapter/runtime/A9 authority и достаточность acceptance laws;
3. при `❌`/`❓` governance исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_loader.py -q --basetemp=.pytest_tmp_s8`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_contract.py tests/test_doctor_schema_refs.py -q --basetemp=.pytest_tmp_s8_regression`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_loader.py -q --basetemp=.pytest_tmp_s8_neighbor`;
4. `git diff --check`, `git status --short`, diff only по allowlist;
5. independent read-only checker сначала читает test diff, затем implementation/roadmap
   diff и сам запускает те же команды;
6. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- explicit-path JSON loader строго собирает frozen S5 catalog;
- duplicate/syntax/type/schema ошибки fail-closed и различимы;
- нет legacy mapping, client discovery, cache или runtime wiring;
- `clients/**`, ответы, routes, UI, session и authority не изменились;
- roadmap отмечает S8 как offline IO foundation, а не doctor/product activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
