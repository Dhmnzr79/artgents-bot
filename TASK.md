# TASK — S2 Offline Target-Pack Loader

**Ветка:** `codex/stage-a`

**Baseline:** `9443716 feat: add target schema contracts S1`

**Серия / checkpoint:** `S2` — строгая offline-загрузка target schema из явного
client-pack path без подключения к ответам бота.

**Режим:** filesystem-to-contract foundation only. Никаких live/LLM, migration
`clients/**`, runtime consumers, selectors, session или product authority.

## Цель

Добавить один изолированный loader, который читает будущий target pack из явно
переданного каталога, разбирает JSON/YAML без тихих fallback и возвращает проверенный
`ResponseSchemaBundle` из S1.

S2 отвечает только на вопрос: «Можно ли однозначно прочитать полный набор target-файлов
и доказать их schema/cross-ref целостность?». Он не отвечает на вопросы «какой pack
активен», «что выбрать пациенту» и «как показать это в ответе».

## Почему это следующий минимальный scope

S1 уже фиксирует модели и in-memory cross-reference validation. Следующий безопасный
шаг — материализовать только границу disk → S1 contract на синтетическом pack. Без этого
client migration преждевременна: ошибки формата, дубли ключей или частично прочитанные
файлы могли бы скрываться за current-runtime fallback.

S2 намеренно не использует `client_id`, глобальный `clients/` root, current loaders,
cache или feature flag. Поэтому новый код нельзя случайно включить в ответы. Интеграция
с client resolution и миграция demo требуют отдельных governance checkpoint-ов.

## Затрагиваемые файлы

- `TASK.md`;
- `core/response_schema_loader.py` (new);
- `tests/test_response_schema_loader.py` (new);
- `docs/STRANGLER_ROADMAP.md` — только краткий статус S2 после независимого completion
  review; A9 status/raw/frozen/live не менять.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая создание target-файлов и migration demo;
- `contracts/response_schema.py` и `tests/test_response_schema_contract.py`: S1 frozen
  baseline; если loader требует изменить contract, остановиться и открыть отдельное
  governance-решение;
- все существующие loaders, включая `core/client_config_loader.py`,
  `core/client_runtime.py`, `core/pricebook_loader.py`, `core/marketing_loader.py`;
- `contracts/__init__.py`, `config.py`, flags, environment и dependency files;
- routes/API/app/orchestration/resolver/composer, prompts, answer/UI/widget code;
- selection/applicability/priority/marketing/CTA logic и rendering source text;
- session state, caches, mtime/watch/reload и global singleton;
- KB chunk parser, doctor index, CTA/tone loader и проверка существования внешних
  `kb:`/`doctor:` refs;
- current-client compatibility, legacy fallback или dual-read/shadow wiring;
- protected acceptance/golden/eval fixtures и весь A9 design/raw/harness/evidence;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Нормативный filesystem contract S2

Loader принимает только явный `pack_root: Path` и читает фиксированную target-layout:

```text
<pack_root>/
  service_catalog.json
  brand_catalog.json
  clinic_strategy.yaml
  marketing.yaml
  pricebook/
    facts.json
    services/
      *.json
```

Формы данных не переопределяются loader-ом:

- `service_catalog.json` — direct mapping `service_id -> TargetService`;
- `brand_catalog.json` — `TargetBrandCatalog` wrapper;
- каждый `pricebook/services/*.json` — один `TargetOffer`; loader сортирует файлы по
  имени для детерминированного порядка, но не выводит `offer_id` из filename;
- `pricebook/facts.json` — direct mapping `fact_id -> TargetCommercialFact`;
- `clinic_strategy.yaml` — `TargetClinicStrategy`;
- `marketing.yaml` — `TargetMarketingPolicy`.

Все пять файлов и каталог `pricebook/services/` обязательны. Пустой services-каталог
допустим на уровне IO; допустимость пустого/неполного bundle решает только S1 contract.
Не-JSON entries в services-каталоге не считаются offers и игнорируются. Loader не ищет
файлы рекурсивно и не читает пути из содержимого source-файлов.

## Loader API и ошибки

Новый public surface внутри модуля:

- `load_response_schema_bundle(pack_root: Path) -> ResponseSchemaBundle`;
- `ResponseSchemaLoadError` с machine-readable `code`, `path: Path` относительно
  `pack_root` и исходной причиной через exception chaining. Для ошибки самого root
  используется `Path(".")`; абсолютный host path в error API не записывается.

`pack_root` обязан быть `pathlib.Path`; строка не нормализуется и не принимается скрыто:
она даёт `pack_root_invalid`, `Path(".")`, chained `TypeError`.
Loader не резолвит client alias/default, не добавляет repo root и не меняет cwd.

Обязательные error codes:

- `pack_root_invalid` — root отсутствует или не является каталогом: cause
  `FileNotFoundError` либо `NotADirectoryError`; non-`Path` даёт `TypeError`;
- `required_path_missing` — обязательный файл/каталог отсутствует или имеет неверный
  filesystem kind: cause `FileNotFoundError`, `IsADirectoryError` для ожидаемого файла
  либо `NotADirectoryError` для ожидаемого каталога;
- `file_read_failed` — UTF-8/read ошибка: cause `UnicodeDecodeError` либо `OSError`;
- `json_invalid` — синтаксическая ошибка с cause `json.JSONDecodeError`;
- `yaml_invalid` — синтаксическая ошибка или запрещённый YAML merge key `<<`, cause
  `yaml.YAMLError` (для merge допустим локальный subclass);
- `duplicate_key` — повтор mapping key на любом уровне JSON/YAML, cause один локальный
  `DuplicateKeyError(ValueError)` для обоих форматов;
- `top_level_type_invalid` — JSON/YAML source не является требуемым mapping, cause
  `TypeError`;
- `schema_invalid` — Pydantic/S1 bundle validation не прошла, cause
  `pydantic.ValidationError`.

Loader не возвращает `None`, default model или частичный bundle при ошибке. Текст ошибки
не является API; тесты проверяют `code`, `path`, тип cause и стабильный S1 error token,
когда применимо.

## Детерминированное чтение

1. Каждый source читается строго как UTF-8.
2. JSON parser отклоняет duplicate object keys на любом уровне до Pydantic.
3. YAML использует изолированный subclass `yaml.SafeLoader` без произвольного object
   construction и отклоняет duplicate mapping keys на любом уровне. Таблица implicit
   resolvers сначала копируется для subclass; `yaml.SafeLoader` и поведение
   `yaml.safe_load` глобально не мутируются.
4. Timestamp resolver удаляется только из изолированной копии: unquoted ISO-looking
   scalar остаётся точной строкой. YAML merge key `<<` полностью запрещён как
   `yaml_invalid`, потому что target layout не требует merge semantics и коллизии после
   merge не должны иметь вторую трактовку.
5. Top-level type проверяется до сборки bundle: все фиксированные sources и каждый offer
   обязаны быть mappings.
6. Offer files читаются в лексикографическом порядке filename; порядок не зависит от OS.
7. После parse loader делает ровно один authoritative
   `ResponseSchemaBundle.model_validate(...)`; отдельной ослабленной cross-ref модели нет.
8. Любая ошибка прекращает загрузку; fallback к current Pricebook/marketing запрещён.

## Client isolation и внешние refs

- Loader читает только фиксированные descendants переданного `pack_root`.
- Symlink policy в S2 не вводится: path передаёт trusted offline caller, а loader не
  получает пути из пользовательского/source content. Security boundary для runtime
  client resolution появится только вместе с таким consumer.
- `kb:` и `doctor:` refs проходят S1 syntax validation, но S2 не проверяет их
  существование: соответствующие target indexes ещё не материализованы.
- `fact:` refs и все service/option/brand/strategy links проверяет S1 aggregate bundle.
- Два последовательных вызова независимы: нет cache/shared state; изменение synthetic
  source между вызовами видно во втором результате.

## Обязательные invariants

1. Новый loader импортирует только stdlib, PyYAML, Pydantic error type и
   `contracts.response_schema`; current loaders/runtime не импортируются.
2. Loader не знает `client_id`, `DEFAULT_CLIENT_ID`, `clients/` и demo.
3. Loader не меняет source values, не trim/normalize ID/text/ref и не выводит ID из
   filename.
4. File order влияет только на стабильный порядок `offers`, не на eligibility/priority.
5. Missing/malformed/invalid source всегда fail-closed с typed error; partial/default
   bundle запрещён.
6. Duplicate JSON/YAML keys не могут быть тихо перезаписаны parser-ом.
7. Validation делегируется frozen S1 contract; loader не создаёт второй набор schema
   rules.
8. Никаких filesystem writes, cache, logging side effects, environment reads или network.
9. Model load не классифицирует запрос, не выбирает service/fact/CTA и не рендерит ответ.
10. S2 не объявляет target schema активной и не меняет product authority.

## Protected tests / честность

- Новый `tests/test_response_schema_loader.py` — только synthetic `tmp_path` fixtures;
  он не читает и не копирует `clients/demo`.
- S1 contract/tests и все существующие tests/evals/golden не меняются.
- Запрещены skip/xfail, условные asserts, broad mocks current runtime и подмена target
  под текущий output.
- Допустим monkeypatch только synthetic file content/path behavior, если невозможно
  доказать branch обычным `tmp_path`; предпочтительны реальные temp files.

## Минимальные acceptance tests

Без избыточной матрицы новый test module доказывает:

1. полный synthetic pack загружается в `ResponseSchemaBundle`, source text/refs/IDs
   сохраняются дословно;
2. offer filenames намеренно не совпадают с `offer_id`, а result order следует sorted
   filename — ID из filename не выводится;
3. string вместо `Path`, invalid root и каждый класс missing/wrong-kind required path
   дают точные `code`, relative `Path`, cause type и chaining;
4. malformed JSON и malformed YAML различаются по error code/cause;
5. duplicate keys отклоняются на top-level и nested level отдельно для JSON и YAML;
6. wrong top-level list/scalar отклоняется для fixed source и offer file;
7. invalid nested schema и dangling cross-ref дают `schema_invalid` с исходным
   `ValidationError` и стабильным S1 token;
8. unquoted date-looking scalar в строковом YAML-поле (например strategy rule
   `id: 2026-07-01`) остаётся точной строкой и успешно проходит S1; обычный
   `yaml.safe_load` до и после S2-load по-прежнему превращает такой scalar в `date`, что
   доказывает отсутствие глобальной мутации resolver table;
9. unknown/non-JSON service-directory entry игнорируется, вложенный каталог не
   сканируется;
10. внешние валидные `kb:`/`doctor:` refs не требуют filesystem lookup;
11. повторная загрузка после изменения synthetic source видит новое значение, доказывая
    отсутствие cache/shared state;
12. invalid UTF-8 source даёт `file_read_failed`, точный relative path и chained
    `UnicodeDecodeError`; source/AST audit подтверждает отсутствие current loaders,
    client resolution,
    environment/network/write APIs и product imports.

Отдельный compact case подтверждает, что YAML merge key `<<` отклоняется как
`yaml_invalid` с `yaml.YAMLError`, а не применяется и не классифицируется как обычный
duplicate key.

## Verification

До кода:

1. независимый read-only checker читает этот TASK, S1 contract/tests, оба target
   architecture docs, `REVIEW_CHECKLIST.md` и guardrails;
2. checker подтверждает exact layout, fail-closed boundary, отсутствие скрытого runtime/
   A9 authority и достаточность acceptance laws;
3. при `❌`/`❓` TASK исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_loader.py -q --basetemp=.pytest_cache/s2-loader-basetemp`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py -q`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_pricebook_loader.py tests/test_marketing_loader.py -q --basetemp=.pytest_cache/s2-current-basetemp`
   как узкая current-loader regression;
4. `git diff --check`, `git status --short`, diff только по allowlist;
5. независимый read-only checker сначала читает новый test diff, затем loader/roadmap
   diff и сам запускает те же команды;
6. live/LLM и полный pytest не запускаются: ни один product consumer не меняется.

## Definition of Done

- explicit-path loader строго собирает S1 bundle из target layout;
- duplicate/syntax/shape/schema/cross-ref ошибки fail-closed и различимы;
- synthetic tests доказывают deterministic order, no cache и отсутствие client/runtime
  wiring;
- `clients/**`, existing loaders, ответы, routes, UI, session и authority не изменились;
- roadmap отмечает S2 как offline IO foundation, не как schema activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
