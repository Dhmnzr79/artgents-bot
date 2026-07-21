# TASK — S18 Target Service Consultation Value Contract

**Ветка:** `codex/stage-a`

**Baseline:** `e03fb73 docs: audit target marketing migration S17`

**Серия / checkpoint:** `S18` — минимальный offline contract для одной необязательной
подводки к консультации в source Markdown услуги.

**Режим:** governance + isolated models/parser/validators + synthetic unit tests +
architecture docs only. Никаких demo content changes, session/runtime wiring, ответов,
routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец зафиксировал минимальную продуктовую схему:

1. содержательная MD-база услуг должна быть естественно более продающей и описывать
   реальные особенности клиники, а не оставаться медицинской энциклопедией;
2. отдельная сложная карточка `service_accents`, priority facts и редактируемые лимиты
   не нужны;
3. у нужного service Markdown допускается только одно специальное необязательное поле
   `consultation_value` в YAML frontmatter того же файла;
4. это source-owned смысл пользы консультации, а не готовая реплика и не CTA-кнопка;
5. composer в будущем может свободно связать слова, но не менять смысл/силу source;
6. автоматическая подводка используется только в заключении подходящего
   содержательного service-ответа;
7. она автоматически показывается максимум один раз на exact Markdown document в
   пределах `client_id + session_id`, независимо от числа H3/chunks/follow-up clicks;
8. прямой вопрос о консультации может быть отвечен повторно как content question;
9. частотность является universal runtime law и не редактируется в каждом client pack.

Demo не имеет live-клиентов. S18 не строит compatibility adapter и не подключает
contract к текущему или будущему product path.

## Архитектурное решение

### Source ownership

`consultation_value` хранится в YAML frontmatter **того же** Markdown, на который
target service/option ссылается через `content_ref`:

```md
---
doc_id: implantation__service__example
doc_type: service
topic: implantation
subtopic: example
consultation_value: >
  Врач оценивает исходные данные и определяет, подходит ли пациенту этот метод.
---

## Пример услуги
```

Отдельный YAML/JSON с копией текста, H3 `#consultation-value`, `service_accents`,
готовые CTA/реплики и per-service cadence settings запрещены.

### FullContext boundary

- Основное тело всех разрешённых MD может оставаться cached FullContext background.
- Frontmatter не входит в общий текст FullContext.
- `consultation_value` разрешается только прямым exact lookup после выбора
  service/option `content_ref`; это не vector/semantic retrieval и не поиск чанка.
- В будущий answer material поле передаётся с ролью `consultation_close`; значения
  других документов не передаются как selectable consultation material.
- S18 только материализует offline source contract и не меняет существующий
  `core/knowledge_base.py` или composer.

### Universal cadence law

Будущий session state хранит exact document refs, реально использованные как
автоматическая подводка, под именем `shown_consultation_value_refs`.

1. Автопоказ разрешён только при exact selected `content_ref` и существующем значении.
2. Один document ref автоматически используется максимум один раз в текущем
   `client_id + session_id`.
3. Ref отмечается только после фактического включения подводки в ответ.
4. Переход по другому H3/chunk/follow-up того же документа не сбрасывает suppression.
5. Новый session/reset очищает suppression; TTL не вводится.
6. Прямой вопрос о консультации обходит только repeat suppression и остаётся обязан
   соблюдать source fidelity и все safety boundaries.
7. Manual-contact, spam/off-topic, pure clarify, active lead-flow и явный отказ от
   консультации/контакта не получают автоматическую подводку.
8. `consultation_value` — текстовый selling accent, не новая CTA и не secondary UI.
   Будущий composer/selector обязан уважать уже согласованный общий marketing limit и
   не складывать поверх него лишний продающий блок.

S18 не реализует session state, selection, placement или cadence runtime. Эти правила
фиксируются как acceptance для отдельного будущего authority/runtime checkpoint.

## Цель

Создать узкий offline contract, который:

1. описывает одну immutable запись source metadata: exact relative `content_ref` и
   nonblank `consultation_value`;
2. детерминированно читает только explicit Markdown root;
3. находит optional `consultation_value` только в YAML frontmatter;
4. fail-closed отклоняет malformed frontmatter и неверный тип/пустое значение;
5. fail-closed отклоняет поле у документа, чей `doc_type` не `service`;
6. возвращает записи в стабильном lexical order, без cache, writes и client resolution;
7. отдельно валидирует, что каждый найденный `content_ref` действительно принадлежит
   хотя бы одному target service или option `content_ref` из переданного каталога;
8. не меняет S1 `TargetService`, target pack loader или runtime.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/service_consultation.py` — new frozen metadata record + pure cross-ref
  validation error/function;
- `core/service_consultation_source.py` — new explicit-root offline frontmatter reader;
- `tests/test_service_consultation_source.py` — new synthetic contract/parser tests;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — same-MD ownership and exact `content_ref` link;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — consultation-close role, global limit and
  universal cadence law;
- `docs/MARKETING_QUESTION_TECH.md` — target integration boundary/status only;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая demo MD, current/target marketing, pricebook, playbook,
  doctors, tone/UI и `target_response/**`;
- перенос или редактирование 24 legacy marketing strings;
- добавление реальных `consultation_value` в demo;
- изменение `contracts/response_schema.py`, frozen S1 models или S2/S3/S4 loaders;
- изменение current FullContext corpus/composer/prompt/cache;
- TurnFrame/ResponseSpec/evidence assembly/session state/selector/cadence implementation;
- ответы, routes, API/app/UI/config, CTA, lead-flow и authority;
- новый route/classifier/retriever/embed/vector/search layer;
- готовые продающие реплики, automatic copy generation и semantic rewriting;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Exact contract

### `ServiceConsultationValue`

Frozen strict model:

- `content_ref`: nonblank exact relative POSIX Markdown path, без absolute path,
  backslash, `.`/`..`, query/fragment и без расширения, отличного от lowercase `.md`;
- `value`: strict string, который после удаления только внешних пробелов/переводов
  строк остаётся непустым; внутренний source text не переписывается;
- extra fields forbidden.

Значение хранится как source text. S18 не пытается оценивать медицинскую истинность,
тон, стиль или формировать из него готовый ответ.

### Offline source reader

`build_service_consultation_values(md_root: Path)`:

- принимает только existing directory `pathlib.Path`;
- рекурсивно читает только lowercase `*.md` в lexical relative-path order;
- читает UTF-8 и никогда не пишет;
- документ без frontmatter или без `consultation_value` игнорируется;
- при наличии поля требует YAML mapping, exact `doc_type: service` и strict string value;
- malformed YAML, duplicate YAML keys, invalid UTF-8 и invalid record получают typed
  fail-closed error с code и exact relative path;
- возвращает immutable tuple `ServiceConsultationValue` в lexical `content_ref` order;
- не импортирует client resolver, current loaders, runtime, session или LLM.

### Pure catalog cross-reference

`validate_service_consultation_refs(records, services)`:

- принимает уже validated records и `dict[str, TargetService]`;
- собирает exact non-null `content_ref` из services и их options;
- один ref может использоваться несколькими service/options;
- все orphan consultation refs возвращаются одним deterministic sorted typed error;
- ничего не фильтрует по `active`, не выбирает услугу и не читает source text;
- не требует, чтобы каждый service имел `consultation_value`.

## Acceptance tests

`tests/test_service_consultation_source.py` обязан доказать:

1. optional same-MD frontmatter field читается из root/nested service docs и возвращается
   в exact lexical order;
2. MD body, H2/H3 и `suggest_h3` не создают consultation values;
3. документы без поля/frontmatter игнорируются;
4. non-service document с полем fail-closed;
5. empty/whitespace/non-string value, malformed YAML и duplicate key fail-closed с
   deterministic code/path/cause; внешние пробелы нормализуются предсказуемо;
6. invalid root/type, invalid UTF-8 и invalid content ref fail-closed;
7. model strict/frozen/extra-forbid и path invariants;
8. stateless repeated calls, nested lexical order и no writes;
9. cross-ref принимает service/option refs, shared refs и optional absence;
10. cross-ref одним sorted error возвращает все orphan refs;
11. module import/AST boundary не содержит client/runtime/session/LLM/network/writes;
12. нет skip/xfail, live/LLM и изменений client data.

Tests не кодируют demo `consultation_value`, готовую формулировку ответа или runtime
cadence implementation.

## Verification

До contract/docs edits:

1. governance TASK коммитится отдельно;
2. independent read-only checker читает TASK, target/current architecture docs,
   service schema, KB index, FullContext assembly, checklist/guardrails;
3. checker подтверждает same-MD/frontmatter ownership, FullContext compatibility,
   once-per-document/session product law, minimality и no-runtime/no-authority boundary;
4. при `❌`/`❓` TASK исправляется и повторно проверяется до implementation.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_service_consultation_source.py -q --basetemp=.pytest_tmp_s18_contract`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_kb_index.py tests/test_response_schema_contract.py -q --basetemp=.pytest_tmp_s18_neighbors`;
3. `git diff --check`, exact allowlist и отсутствие skip/xfail;
4. independent checker повторяет review и команды;
5. no full pytest, no live/LLM.

## Definition of Done

- owner-approved minimal same-MD `consultation_value` law записан без
  `service_accents`/priority/per-client cadence complexity;
- field не попадает в общий FullContext body и не требует отдельного документа;
- deterministic explicit-root source contract и cross-ref independently verified;
- once-per-document-per-session law, direct-question override и safety suppression
  зафиксированы, но не подключены;
- demo/client data, current runtime, target product path, A9 и authority не изменены;
- roadmap S18 независимо проверен;
- governance и completion commits/push только `codex/stage-a`, tree clean/synced.
