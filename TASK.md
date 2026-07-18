# TASK — S3 External Source-Reference Integrity

**Ветка:** `codex/stage-a`

**Baseline:** `dbf9c37 chore: clean S2 file endings`

**Серия / checkpoint:** `S3` — offline-проверка внешних `kb:`/`doctor:` ссылок target
marketing policy по явно переданному in-memory индексу.

**Режим:** pure contract validation only. Никаких filesystem loaders, `clients/**`,
live/LLM, selectors, session, routes/UI или product authority.

## Цель

Закрыть оставшуюся после S1/S2 границу ссылочной целостности: S1 уже проверяет wire
syntax и локальные `fact:` refs, а S2 строго собирает bundle, но `kb:`/`doctor:` refs
намеренно не проверяет без соответствующих source indexes.

S3 добавляет:

- строгий in-memory index доступных KB chunk refs и doctor refs;
- чистую детерминированную функцию, которая проверяет все внешние refs в уже валидном
  `ResponseSchemaBundle`;
- одну typed aggregate error со всеми отсутствующими refs в стабильном порядке.

S3 не строит индекс из файлов и не меняет loader S2. Он только формализует следующий
contract boundary: future index builder сможет передать найденные refs, не меняя закон
проверки.

## Почему scope минимален

Target marketing policy нормативно использует `kb:<doc>#<chunk>` и
`doctor:<doctor_id>`. Придумывать сейчас doctor schema, KB parser или client discovery
рано. Но сравнение уже валидных точных refs с явным набором доступных refs не требует
ни product logic, ни медицинских решений, ни client migration.

Индекс in-memory и не является новым persisted target-файлом. Это предотвращает
появление неутверждённого manifest/wrapper и сохраняет ownership у KB/doctor layers.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/response_schema_refs.py` (new);
- `tests/test_response_schema_refs.py` (new);
- `docs/STRANGLER_ROADMAP.md` — после реализации добавить честный pending-статус S3
  `[ ]` для completion review; менять на `[x]` только после checker `✅`. A9
  status/raw/frozen/live не менять.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**` и любое чтение реальных client packs;
- frozen S1: `contracts/response_schema.py`, `tests/test_response_schema_contract.py`;
- frozen S2: `core/response_schema_loader.py`, `tests/test_response_schema_loader.py`;
- все current loaders/runtime, `contracts/__init__.py`, config/flags/environment;
- KB/md parsing, heading/chunk discovery, frontmatter и content normalization;
- doctor model/index construction, active/service eligibility и source text;
- service/option `content_ref`, commercial fact `detail_ref` и CTA-key existence: их
  wire/index contracts ещё не материализованы и не должны угадываться в S3;
- `fact:` existence — остаётся единственной ответственностью S1 aggregate bundle;
- selection/applicability/strategy/marketing selector, cadence, rendering и UI;
- session state, cache/global registry и cross-client lookup;
- routes/API/app/orchestration/resolver/composer, prompts и answers;
- protected acceptance/golden/eval fixtures и весь A9 design/raw/harness/evidence;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Нормативный in-memory contract

Новый модуль определяет:

```python
class ResponseSchemaExternalIndex(BaseModel):
    kb_refs: tuple[SourceRef, ...]
    doctor_refs: tuple[SourceRef, ...]

def validate_response_schema_external_refs(
    bundle: ResponseSchemaBundle,
    index: ResponseSchemaExternalIndex,
) -> None: ...
```

`ResponseSchemaExternalIndex`:

- Pydantic v2, `extra="forbid"`, `frozen=True`, strict input;
- принимает только tuple, не конвертирует list/set/string скрыто;
- `kb_refs` содержит полные exact wire refs только вида `kb:<doc>#<chunk>`;
- `doctor_refs` содержит полные exact wire refs только вида `doctor:<doctor_id>`;
- использует frozen S1 `SourceRef` syntax validation, затем проверяет правильный prefix;
- refs внутри каждого tuple уникальны; порядок входа сохраняется, сортировки/normalization
  index model не делает;
- пустые tuples допустимы.

Индекс не хранит fact refs, source text, active/eligibility, client ID или paths. Лишний
доступный ref, который bundle не использует, допустим.

## Проверяемые refs

S3 обходит только `marketing.scenario_rules[*].ordered_amplifier_refs`, потому что:

- `initial_commercial_blocks[*].ordered_fact_refs` по S1 допускают только `fact:`;
- structured external refs в target schema сейчас нормативно существуют только в
  scenario amplifier pools;
- plain `content_ref`/`detail_ref` имеют другие wire contracts и protected от
  расширения scope.

Для каждого scenario ref:

- `fact:` игнорируется S3 и уже доказан S1;
- `kb:` должен точно и case-sensitive присутствовать в `index.kb_refs`;
- `doctor:` должен точно и case-sensitive присутствовать в `index.doctor_refs`;
- неизвестный prefix невозможен после S1; отдельный fallback/guess запрещён.

Проверяются все authored refs независимо от будущей active/eligibility/cadence: source
integrity не должна зависеть от selector-а.

## Error contract

`ResponseSchemaExternalRefError`:

- наследует `ValueError`;
- `code == "external_refs_missing"`;
- `missing_kb_refs: tuple[str, ...]`;
- `missing_doctor_refs: tuple[str, ...]`;
- оба tuple содержат уникальные exact refs в лексикографическом порядке;
- ошибка поднимается один раз после полного scan, чтобы не скрывать второй класс missing
  refs;
- human-readable `str(error)` не является API и не содержит source text.

Если missing refs нет, функция возвращает строго `None`. Она не возвращает filtered
bundle/report и не мутирует bundle/index.

## Обязательные invariants

1. Новый модуль импортирует только stdlib typing, Pydantic и frozen
   `contracts.response_schema`.
2. Нет filesystem, environment, network, logging, cache, client resolution или globals,
   зависящих от вызовов.
3. Exact ref не trim/lower/resolve; сравнение case-sensitive.
4. Validator не проверяет content, doctor activity/service eligibility или medical facts.
5. Extras в index не влияют на результат и не считаются ошибкой.
6. Один bundle с двумя разными indexes проверяется независимо; state не переносится.
7. Функция не изменяет marketing pools, их порядок или source refs.
8. S3 не подключается к S2 loader или product path и не объявляет schema активной.
9. A9 patient scope не является входом и не получает authority.

## Protected tests / честность

- Новый `tests/test_response_schema_refs.py` использует только synthetic S1 models;
  `clients/demo` не читается и не копируется.
- Frozen S1/S2 tests и все существующие acceptance/evals/golden не меняются.
- Запрещены skip/xfail, условные PASS, runtime mocks и ослабление source-ref syntax.

## Минимальные acceptance tests

Новый compact test module доказывает:

1. bundle с `fact:`, `kb:` и `doctor:` refs проходит при полном exact index и функция
   возвращает `None`;
2. отсутствующие KB и doctor refs собираются одним точным
   `ResponseSchemaExternalRefError`, который является `ValueError`, имеет
   `code == "external_refs_missing"` и два sorted unique tuple;
3. index отклоняет list/set/string вместо tuple, extra fields, duplicate refs, wrong
   prefix и malformed S1 source ref; introspection проверяет `strict=True`,
   `frozen=True`, `extra="forbid"`, присваивание полю запрещено, а созданная model
   сохраняет exact tuple order/case без normalization;
4. empty index допустим для bundle без внешних refs;
5. лишние index refs допустимы;
6. case mismatch считается missing и не нормализуется;
7. `fact:` ref не требуется в external index;
8. два последовательных вызова с разными indexes не делят state;
9. до/после validation bundle/index `model_dump()` идентичны, порядок pools и exact
   index tuple order/case сохранены;
10. external refs проверяются во всех scenario rules, а duplicate missing ref между pools
    появляется в error только один раз;
11. source/AST audit подтверждает отсутствие IO/current loader/client/runtime/session/A9
    imports и side effects.

## Verification

До кода:

1. независимый read-only checker читает этот TASK, frozen S1/S2 contracts/tests,
   `MARKETING_SCENARIO_ARCHITECTURE.md`, `REVIEW_CHECKLIST.md` и guardrails;
2. checker подтверждает минимальность, exact ownership, отсутствие придуманного persisted
   index/runtime authority и достаточность acceptance laws;
3. при `❌`/`❓` TASK исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_refs.py -q`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_loader.py -q --basetemp=.pytest_cache/s3-regression-basetemp`;
3. `git diff --check`, `git status --short`, diff только по allowlist;
4. независимый read-only checker сначала читает новый test diff, затем contract/roadmap
   diff и сам запускает те же команды;
5. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- все structured external marketing refs имеют одну pure integrity boundary;
- missing KB/doctor refs выдаются вместе и детерминированно;
- index остаётся in-memory input, а KB/doctor ownership не дублируется;
- S1/S2, `clients/**`, current loaders, answers, routes, UI, session и authority не
  изменились;
- roadmap отмечает S3 как offline reference foundation, не schema activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
