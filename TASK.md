# TASK — S4 Offline KB Source-Index Builder

**Ветка:** `codex/stage-a`

**Baseline:** `8e60f07 feat: validate external schema refs S3`

**Серия / checkpoint:** `S4` — детерминированная сборка exact `kb:` refs из явно
переданной target KB-папки.

**Режим:** offline foundation only. Никаких `clients/**`, current/legacy loaders,
ответов, routes/UI, live/LLM или product authority.

## Цель

S3 умеет сравнить marketing refs с явно переданным in-memory external index, но пока
никто не строит KB-часть этого индекса. S4 добавляет один узкий filesystem boundary:

```python
def build_response_schema_kb_refs(md_root: Path) -> tuple[SourceRef, ...]: ...
```

Функция читает только явно переданную папку target KB, находит Markdown-файлы и
явные chunk anchors в заголовках, затем возвращает точные ссылки
`kb:<relative/doc.md>#<chunk_id>` в стабильном порядке.

S4 намеренно не строит doctor index: target doctor catalog/schema ещё не
материализованы нормативно. Их нельзя угадывать по текущим demo-файлам.

## Почему scope минимален

Архитектура уже задаёт `kb:<doc>#<chunk>` и требует точного существования doc/chunk.
Значит KB index можно построить без selection, content rendering и product logic.

Legacy не является compatibility contract: S4 не импортирует и не оборачивает
`core/md_chunks.py`, current client discovery, aliases, implicit `overview/korotko`
fallback или текущий frontmatter. Реальные `clients/demo` не мигрируются и не
используются в тестах. Старые пути позже можно удалить после доказанной замены.

## Затрагиваемые файлы

- `TASK.md`;
- `core/response_schema_kb_index.py` (new);
- `tests/test_response_schema_kb_index.py` (new);
- `docs/STRANGLER_ROADMAP.md` — после реализации добавить честный pending S4 `[ ]`;
  менять на `[x]` только после completion checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**` и любые реальные client packs;
- frozen S1/S2/S3 contracts, loaders и tests;
- current/legacy MD loaders, retrieval, aliases, topic/aspect inference и caches;
- doctor models/catalog/parser/index, doctor active/service eligibility и facts;
- parsing/rendering текста chunks, frontmatter semantics и content normalization;
- соединение KB refs и doctor refs в `ResponseSchemaExternalIndex`;
- S2 pack loader wiring и автоматическое client/pack discovery;
- marketing selector, cadence, session, routes/API/UI, prompts и answers;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Вход и discovery contract

- вход должен быть именно `pathlib.Path`; string и path-like coercion запрещены;
- `md_root` должен существовать и быть директорией;
- root считается явно выбранным и доверенным вызывающей стороной; функция сама не
  ищет client ID, environment или fallback;
- рекурсивно рассматриваются только обычные файлы с case-sensitive suffix `.md`;
- относительный doc path строится через `relative_to(md_root).as_posix()`;
- порядок файлов — лексикографический по этому POSIX relative path;
- остальные файлы игнорируются; пустая папка корректно возвращает пустой tuple;
- каждый выбранный файл читается как strict UTF-8, без fallback encoding.

S4 не сохраняет индекс на диск и не вводит manifest/registry.

## Chunk-anchor contract

Target KB chunk существует только при явном ATX-заголовке уровня 2 или 3:

```markdown
### Читаемое название {#approved_chunk}
```

Правила:

- heading должен начинаться с `## ` или `### ` без indentation;
- anchor должен завершать heading, кроме trailing spaces/tabs;
- `chunk_id` соответствует `[A-Za-z0-9][A-Za-z0-9._-]*`;
- ID и doc path сохраняются exact и сравниваются case-sensitive;
- fenced-code subset точный: opener начинается строго в column 0 с трёх или более
  одинаковых backticks либо tildes; остаток opener line считается info string и не
  разбирается. Closer начинается строго в column 0, использует тот же символ не меньшее
  число раз и после него допускает только spaces/tabs. Mismatched символ, более короткая
  последовательность и indented line не закрывают fence. Незакрытый fence действует до
  EOF. Все headings между opener и действительным closer игнорируются;
- H1/H4+, HTML anchors, auto-slugs, frontmatter IDs и headings без explicit anchor
  не создают ref;
- valid terminal anchor распознаётся только на H2/H3 line, которая начинается exact
  `## ` или `### `, имеет непустое читаемое название, затем хотя бы один ASCII space,
  ровно один suffix `{#<chunk_id>}` и только spaces/tabs после него;
- H2/H3 heading без substring `{#` считается heading без anchor и игнорируется;
- если H2/H3 heading содержит `{#`, но не соответствует valid terminal форме, это
  `chunk_anchor_invalid`. Сюда входят missing `}`, empty/invalid ID, отсутствие space
  перед `{#`, текст после `}`, несколько `{#...}` и пустое читаемое название;
- одинаковый `chunk_id` дважды в одном doc — ошибка, даже при разных heading levels;
- heading H2/H3 с конструкцией `{#...}` в конце, но невалидным/пустым ID — ошибка, а
  не молчаливое исчезновение ref;
- whitespace/регистр/ID не нормализуются; никаких special aliases для `korotko` или
  `overview` нет.

Результат сортируется лексикографически по полному exact ref и возвращается как tuple.
Каждый построенный элемент валидируется frozen S1 `SourceRef`; неожиданно невалидный
ref является typed build error, а не пропускается.

## Error contract

`ResponseSchemaKbIndexError` наследует `Exception` и содержит:

- `code: str`;
- `path: Path`, всегда относительно `md_root`; для invalid root — `Path(".")`;
- стабильные codes: `md_root_invalid`, `file_read_failed`, `chunk_anchor_invalid`,
  `chunk_anchor_duplicate`, `source_ref_invalid`.

Каждая ошибка оборачивает точную исходную причину через `raise ... from ...`:

- non-`Path` → `TypeError`;
- missing root → `FileNotFoundError`;
- file-as-root → `NotADirectoryError`;
- UTF-8/IO read failure → исходный `UnicodeDecodeError`/`OSError`;
- invalid/duplicate anchor → `ValueError`;
- invalid constructed S1 ref → Pydantic `ValidationError`.

Для каждого file-level error `path` — exact POSIX-compatible relative `Path` выбранного
файла. При нескольких проблемных файлах fail-first остаётся детерминированным благодаря
сортировке discovery. Текст ошибки не является API и не содержит KB content.

## Обязательные invariants

1. Новый модуль импортирует только stdlib, Pydantic `TypeAdapter`/`ValidationError` и
   frozen S1 `SourceRef`.
2. Нет YAML/frontmatter/Markdown dependency, environment, network, logging, cache,
   globals с накопленным state или client resolution.
3. Вызовы для разных roots независимы; функция не мутирует вход и ничего не пишет.
4. Ни текст chunk, ни metadata не возвращаются: индекс доказывает только наличие ref.
5. S4 не проверяет approved/active/medical eligibility: это будущий ownership layer.
6. S4 не подключается к S2/S3 или product path и не объявляет schema активной.
7. A9 patient scope не является входом и не получает authority.

## Protected tests / честность

- `tests/test_response_schema_kb_index.py` использует только synthetic `tmp_path`;
- `clients/demo` не читается, не копируется и не упоминается как fixture;
- frozen tests и production modules не меняются;
- запрещены skip/xfail, условные PASS, runtime mocks и snapshot текущего legacy parser.

## Минимальные acceptance tests

Compact test module доказывает:

1. nested synthetic docs дают exact POSIX refs для valid H2/H3 anchors в
   лексикографическом порядке;
2. case, dots, underscores и hyphens в ID сохраняются без normalization;
3. headings без anchor, H1/H4, HTML/auto anchors, non-`.md` и uppercase `.MD` files
   игнорируются;
4. один synthetic doc фиксирует fence subset: backtick/tilde opener и valid closer,
   info string, mismatched symbol, short/indented closer и EOF внутри unclosed fence;
   fenced headings игнорируются, а headings после valid closer видимы;
5. empty root возвращает `()`;
6. string input, missing root и file-as-root дают `md_root_invalid` с `Path(".")`;
7. invalid UTF-8 даёт `file_read_failed`; root/read error tests проверяют exact chained
   `TypeError`, `FileNotFoundError`, `NotADirectoryError` или `UnicodeDecodeError` и для
   file-level error exact relative `path`;
8. `{#}`, `{#bad` без `}`, `{#bad id}`, `{#id} text`, `Title{#id}`, multiple
   `{#one} {#two}` и heading без title дают `chunk_anchor_invalid` с chained
   `ValueError` и exact path;
9. duplicate anchor в одном doc даёт `chunk_anchor_duplicate` с chained `ValueError`
   и exact path; детерминированный file order проверяется двумя bad docs;
10. повторные вызовы и два разных roots не делят state и не создают файлов;
11. real synthetic `.md` path с `#` создаёт constructed ref с лишним `#`: настоящий S1
    `TypeAdapter(SourceRef)` поднимает Pydantic `ValidationError`, а S4 оборачивает его
    как `source_ref_invalid` с exact relative path;
12. source/AST audit подтверждает отсутствие legacy/client/runtime/session/A9 imports,
    writes, cache и side effects.

## Verification

До кода:

1. независимый read-only checker читает TASK, S1 `SourceRef`, S3 external-index
   contract/tests, architecture docs, checklist и guardrails;
2. checker подтверждает минимальность KB-only scope, exact parsing law, отсутствие
   legacy compatibility и doctor-schema invention;
3. при `❌`/`❓` TASK исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_kb_index.py -q --basetemp=.pytest_cache/s4-basetemp`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_refs.py -q`;
3. `git diff --check`, `git status --short`, diff только по allowlist;
4. независимый read-only checker сначала читает tests, затем implementation/roadmap и
   сам запускает те же команды;
5. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- exact KB refs строятся одним строгим offline boundary из explicit target root;
- нет implicit legacy fallback, current client coupling или doctor schema invention;
- S1–S3, `clients/**`, answers, routes, UI, session и authority не изменились;
- roadmap честно отмечает S4 как offline foundation, не schema activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
