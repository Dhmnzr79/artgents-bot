# TASK — S19 Demo Implantation Consultation Values

**Ветка:** `codex/stage-a`

**Baseline:** `07613c5 feat: validate service consultation values S18`

**Серия / checkpoint:** `S19` — минимальное demo-наполнение трёх implantation service
Markdown через уже проверенный S18 `consultation_value` contract.

**Режим:** governance + three source-data fields + narrow real-data acceptance tests.
Никаких schema/code/runtime/session/answers/routes/UI/live/LLM или product authority.

## Owner direction

21 июля 2026 владелец разрешил Исполнителю самостоятельно подготовить 2–3 небольшие
продающие подводки только для demo-услуг имплантации. Это тестовое demo-наполнение, а не
универсальные тексты для реальных клиник. Для будущих клиентов содержание отдельно
редактируется и утверждается по их базе.

Владелец не требует наполнять все услуги. S19 выбирает три репрезентативных документа:

- классическая имплантация;
- одномоментная имплантация;
- All-on-4.

## Основание

- S18 зафиксировал optional `consultation_value` в YAML frontmatter того же service MD;
- поле не входит в общий FullContext body и разрешается только exact lookup по
  service/option `content_ref`;
- automatic cadence/placement остаются unwired: максимум один раз на document/session,
  один marketing slot + один amplifier slot, direct question вне automatic slots;
- current demo `marketing.yaml` уже содержит consult-reason semantics для этих трёх
  услуг, а их service MD подтверждают соответствующие diagnostic/selection facts;
- S19 публикует три owner-approved demo source values и не переносит остальные legacy
  marketing strings.

## Exact approved data

В каждый файл добавляется ровно один YAML scalar `consultation_value` после `subtopic` и
до `aliases`. Предпочтительная форма authoring — folded scalar `>-`.

### `implantation__service__classic.md`

```yaml
consultation_value: >-
  На консультации врач оценит состояние кости и соседних зубов, сравнит подходящие системы имплантов и составит поэтапный план восстановления.
```

### `implantation__service__one_stage.md`

```yaml
consultation_value: >-
  На консультации врач проверит, можно ли удалить зуб и установить имплант в один день именно в вашей ситуации.
```

### `implantation__service__all_on_4.md`

```yaml
consultation_value: >-
  На консультации врач оценит КТ и поможет понять, подходит ли протокол All-on-4 или лучше рассмотреть другой вариант восстановления.
```

Эти значения являются source-backed demo meanings. Они не являются обязательным
дословным output: future composer может связать слова свободно, не меняя смысл и силу.

## Цель

1. Добавить exact три поля выше в same-MD frontmatter.
2. Не менять MD body, H2/H3, aliases, `suggest_h3`, CTA или situation metadata.
3. Доказать через real-data test, что S18 reader находит ровно эти три значения.
4. Доказать exact cross-ref к target service catalog для `classic`, `one_stage`,
   `all_on_4`.
5. Доказать, что значения не находятся в MD body и не создают H3/follow-up.
6. Не подключать values к product answer/session/runtime.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/md/implantation__service__classic.md`;
- `clients/demo/md/implantation__service__one_stage.md`;
- `clients/demo/md/implantation__service__all_on_4.md`;
- `tests/test_demo_service_consultation_values.py` — new read-only real-data acceptance;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- любые другие `clients/demo/md/*.md`, включая All-on-6 и advanced protocols;
- body/content/H2/H3/aliases/suggest_h3/CTA/situation changes выбранных трёх MD;
- current `clients/demo/marketing.yaml`, pricebook, playbook, doctors, tone/UI;
- весь `clients/demo/target_response/**`;
- перенос `clinic_proof`, promo, CTA или остальных `consult_reasons`;
- `contracts/**`, `core/**`, orchestration, routes/API/app/UI/config;
- изменение S18 schema/parser/cross-ref;
- session state, cadence, selection, placement, composer prompt и FullContext assembly;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Frozen body preservation

После split outer frontmatter delimiters через `text.split("---", 2)[2]` exact SHA-256
body обязан остаться:

- classic: `cbd72f3339cfb91456a7ef19a5a87ea2b59214f732650253b454ca42658b6cb1`;
- one_stage: `478ecab092824ef29b82433c0ee84a4bb59568a67a69290ddc9f19969bc09800`;
- all_on_4: `efa435bafef8f5400a5b01f93ea5109b3d538ee0f64951d60edeb4107f43ec27`.

Тест не resnapshot-ит эти hashes после реализации. Любое расхождение — stop/review.

## Acceptance tests

`tests/test_demo_service_consultation_values.py` обязан доказать:

1. S18 explicit-root reader на real `clients/demo/md` возвращает ровно три records;
2. exact `content_ref → value` равны approved data выше;
3. каждый документ сохраняет exact `doc_id`, `doc_type: service`, `topic: implantation`,
   subtopic и существующие `suggest_h3`/CTA/situation fields;
4. exact body hashes выше не изменились;
5. `consultation_value` отсутствует в body, а `consultation-value` отсутствует среди
   H2/H3 anchors и `suggest_h3`;
6. target `service_catalog.json` содержит `classic`, `one_stage`, `all_on_4` с exact
   соответствующими `content_ref`;
7. real records проходят S18 `validate_service_consultation_refs` against validated
   target services;
8. остальные demo service MD не получили field;
9. no imports/wiring from product runtime, no writes, skip/xfail, live or LLM.

Test может читать real demo/target data, S18 contract/reader и frozen file metadata. Он
не вызывает ответы, session, resolver, composer или LLM.

## Verification

До client-data/test edits:

1. governance TASK коммитится отдельно;
2. independent checker читает exact TASK, три service MD, legacy consult reasons, S18
   contract/tests, service catalog, architecture docs, checklist/guardrails;
3. checker подтверждает factual support, bounded demo-only scope, exact texts/body
   preservation и no-runtime/no-authority boundary;
4. при `❌`/`❓` TASK исправляется до data implementation.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_service_consultation_values.py -q --basetemp=.pytest_tmp_s19_data`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_service_consultation_source.py tests/test_knowledge_base.py -q --basetemp=.pytest_tmp_s19_neighbors`;
3. `git diff --check`, exact allowlist, exact body hashes и отсутствие skip/xfail;
4. independent checker повторяет review и команды;
5. no full pytest, no live/LLM.

## Definition of Done

- ровно три owner-approved demo consultation values опубликованы в same-MD frontmatter;
- ни одно тело MD/H3/follow-up/CTA не изменено;
- S18 reader/cross-ref проходят real demo data;
- FullContext body не получает consultation values;
- no client-wide rollout, runtime/session/answer/A9/authority changes;
- roadmap S19 independently reviewed;
- governance и completion commits/push только `codex/stage-a`, tree clean/synced.
