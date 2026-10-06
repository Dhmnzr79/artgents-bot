# D2 S2-C7 — задание Terra: реальные источники для изолированного D2

Дата: 2026-09-18. Статус: готово; текущий архитектурный Checker PASS получен.
Запуск — по поручению владельца. Реализация и её Checker ещё не выполнены.
Прочитать DEMO_D2_S2_C7_ARCHITECTURE_GATE.md целиком; он определяет exact scope.
Предыдущие редакции C7 и их PASS не действуют. S2 не завершён; S3 не начинать.

## 1. Preflight до правок

Прочитать AGENTS.md, docs/WORKFLOW_CHECKER.md, D2 PRODUCT_DECISIONS D2-076–084,
TARGET_CONTRACT и ACCEPTANCE B13–B17. Не повторять общий аудит.
Проверить/сообщить repo/Git root C:\Cursor Projects\artgents-bot,
branch codex/demo-d2-service-volume, HEAD/baseline
36a57e22dc44c8bbc8c6b19d994fabc0292e2113; local origin/main/merge-base
141ce91fb1731cd990fcf8391550150016c73e7f, status/untracked/staging.
При несовпадении остановиться, не reset/stash/checkout. Без fetch/worktree.

Ожидаемый task-owned WIP:
- docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md (tracked, принятые уточнения);
- docs/tasks/DEMO_D2_TARGET_CONTRACT.md (tracked);
- docs/tasks/DEMO_D2_ACCEPTANCE.md (tracked);
- docs/tasks/DEMO_D2_S2_C7_ARCHITECTURE_GATE.md (untracked);
- этот task (untracked).

Foreign WIP не изменять/не stage:
- docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md
- docs/audits/DEMO_D2_LATENCY_BASELINE.json
- docs/audits/DEMO_D2_LATENCY_BASELINE.md
- docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md
- scripts/measure_d2_latency_baseline.py

## 2. Порядок одного checkpoint

1. Captured-text seam существующего strict schema loader; immutable tenant snapshot,
   read set/hash/path containment/stable capture; модельные catalogs через from_bundle.
2. Полные Markdown материалы и структурные разделы, точные source/UI связи;
   model view и materialization sources из одних captured данных.
3. Чистая проекция опубликованных TargetOffer terms для D2. Убрать только в D2
   completeness-фильтр; legacy helper и non-D2 поведение не менять. Все условия
   должны доходить до frozen row/text без выдумок. Rename D2 no-candidate reason.
4. Additive content_section_refs внутри RequestUnderstandingRequest; секции в
   authority и provenance в frozen blocks/parts. Существующий D1R parser, один
   D2 resolver. Читается любой выбранный раздел, не только korotko. Это точная
   authored проверка C7; не объявлять свободную прозу модели/T3 реализованными.
5. Binding реальных источников, две стандартные price failure authorities и
   разрешённая price CTA из схемы. При недоступной цене CTA не очищается целиком.
   Отсутствие данных/неподготовленный обзор не маскировать фальшивым успешным ответом.
6. Заполнить все 14 строк матрицы gate реальными pytest node IDs и результатами
   до Checker. Затем один связный offline regression ниже.
7. Один independent read-only Checker; после REJECT — findings/focused recheck.
   После implementation PASS — точный commit/push. S3 не начинать.

## 3. Exact write allowlist

```text
contracts/d2_tenant_snapshot.py
contracts/request_understanding.py
contracts/response_plan_materialization.py
contracts/response_plan.py
core/d2_tenant_snapshot.py
core/d2_snapshot_sources.py
core/d2_published_offer_terms.py
core/response_schema_loader.py
core/response_plan_materialization.py
tests/test_response_schema_loader.py
tests/test_request_understanding_schema_offline.py
tests/test_d2_single_request.py
tests/test_d2_multi_request.py
tests/test_d2_price_modes.py
tests/test_d2_part_failure.py
tests/test_d2_tenant_snapshot.py
tests/test_d2_snapshot_sources.py
tests/test_d2_demo_snapshot.py
docs/tasks/DEMO_D2_S2_C7_TERRA_TASK.md
```

Внутри общих файлов разрешены только изменения, перечисленные в gate; отсутствие
изменений legacy доказать существующими regression тестами. Gate и три принятых
документа WIP — read-only/stage-only исключение, не право их переписывать.
Все остальные файлы read-only: clients, prompt/backend, session/lead/privacy,
HTTP/SSE/widget, старые semantic/presentation helpers.

## 4. Тесты и смысл доказательств

Во время разработки — только затронутые nodes. Нельзя переносить _sources fixtures
в production или real-demo интеграционные тесты, подменять builder/resolver/renderer.
Positive input: raw D1R JSON через реальный parser с реальными snapshot catalogs;
source/bundle проходят validation. Negative packs создаются только в pytest tmp_path.

До Checker один run (более широкий, чем прежний data-only проект, потому что
меняется общий D2 материализатор и additive schema; не повторять после каждой правки):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_response_schema_loader.py tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_single_request.py tests/test_d2_multi_request.py tests/test_d2_price_modes.py tests/test_d2_content_source_ui.py tests/test_d2_treatment_situation.py tests/test_d2_price_scope_selection.py tests/test_d2_volume_choices.py tests/test_d2_independent_request_parts.py tests/test_d2_part_failure.py tests/test_d2_tenant_snapshot.py tests/test_d2_snapshot_sources.py tests/test_d2_demo_snapshot.py
```

NEW files создать до запуска. Старые tests, запрещавшие цену лишь из-за unknown
metadata, заменить B13 с положительным ожиданием и отдельным malformed-data
случаем. C6 failure fixtures используют действительно отсутствующие допустимые
offers; не удалять независимые safety/partial/order/freeze assertions.
Тесты legacy completeness не ослаблять. Read-only test failure — stop и анализ
baseline, а не молчаливое расширение allowlist.

Исторический C6 отчёт: 238 passed (не повторный запуск). Известны datetime.utcnow
warnings/WinError32 log rotation; логи не менять. При новом failure проверить
baseline без переключения dirty checkout/worktree. Полный CI/browser/HTTP/live
и замеры скорости не входят в C7. Provider/SMTP/network calls обязаны быть 0.

Матрица отчёта: # gate → actual node IDs → PASS/FAIL → boundary/known gap.
Отдельно указать: B13 покрыт; B15 только data/section/provenance slice; broad
витрина demo unconfigured, T3 prose и B14 first-price deferral ещё не реализованы.
Не называть data-adapter PASS готовностью всего бота или завершением S2.

## 5. Остановка и сдача

Соблюдать stop-conditions gate. При архитектурном конфликте остановить участок
и передать Astra два конкретных варианта. После двух содержательных неудач
реализации передать Sol только воспроизводимый участок, не повторять полный аудит.

После implementation Checker PASS stage точные изменённые allowlist paths и
четыре read-only/stage-only документа (gate, PRODUCT_DECISIONS, TARGET_CONTRACT,
ACCEPTANCE), проверенные Checker вместе с кодом. Не stage foreign WIP.
Проверить staged names/stat/full diff и git diff --cached --check.
Commit: feat(d2): bind real tenant sources to isolated response plans
Push: origin codex/demo-d2-service-volume.
Без merge/deploy/нового PR, cleanup, worktree, reset/stash и provider calls.

Отчёт: branch/commit/push, изменённые файлы, матрица/тесты/Checker, известные
ограничения и baseline failures, calls, staging и оставшийся foreign WIP.
Работающий бот не переключён, S2 не завершён, S3 не начат.

## 6. Проверка задания

2026-09-18: c7_revised_gate_checker, read-only — PASS по gate и task на baseline
36a57e2. Точечное замечание no_public_price/package.label учтено в gate §4.
Матрица выше — будущие проверки, не уже выполненные тесты. Код и данные клиники
при подготовке не менялись; calls = 0, staging пуст, commit/push подготовки нет.

## 7. Матрица реализации C7

2026-09-18, offline, provider/SMTP/network calls: 0. Узлы ниже выполнены на
реальном пакете `clients/demo` либо на временной копии через тот же публичный
loader. Это не запуск production runtime.

| # | Actual test node | Result | Проверенная граница / известный пробел |
|---|---|---|---|
| 1 | `test_d2_demo_snapshot.py::test_real_simple_prices_without_metadata` | PASS | Реальные extraction/whitening/veneers: опубликованная цена `from`, unit и package сохраняются без требования metadata. |
| 2 | `test_d2_demo_snapshot.py::test_real_implant_terms_are_preserved` | PASS | Реальные Classic Impro: сумма, package, includes, исключение и этапы оплаты заморожены. |
| 3 | `test_d2_snapshot_sources.py::test_terms_absence_and_corruption_are_distinct` | PASS | Валидная простая цена проходит без допусловий; повреждённый captured offer — typed failure; legacy unknown evidence D2 не подавляет. |
| 4 | `test_d2_demo_snapshot.py::test_real_content_below_korotko` | PASS | Выбранные anchored sections pain после `korotko` дают точный текст, provenance и source UI. |
| 5 | `test_d2_tenant_snapshot.py::test_material_without_korotko_is_published` | PASS | Нет зависимости от `korotko`; вложенные/ordinal sections, fence/comment, duplicate anchor и пустой документ обработаны структурно. |
| 6 | `test_d2_demo_snapshot.py::test_real_price_and_section_are_ordered` | PASS | Цена и section в обоих порядках; вторичные follow-up/video подавлены ценой, CTA остаётся. |
| 7 | `test_d2_snapshot_sources.py::test_unavailable_price_defaults_keep_content_and_cta` | PASS | Нет активной применимой цены → утверждённый D2-079 текст, без подменной цены, CTA сохраняется. |
| 8 | `test_d2_snapshot_sources.py::test_optional_ui_does_not_block_answer` | PASS | Отсутствующий source UI и неразрешённая source CTA не уничтожают exact content; общая разрешённая CTA не является optional source UI. |
| 9 | `test_d2_tenant_snapshot.py::test_snapshot_capture_identity_and_mutation` | PASS | Изменение набора файлов меняет hash; mid-capture mutation прекращает подготовку; `Path.read_bytes` после capture запрещён sentinel; bundle заново строится только из captured bytes. |
| 10 | `test_d2_snapshot_sources.py::test_tenant_view_and_source_binding` + `test_d2_tenant_snapshot.py::test_snapshot_rejects_path_escape_and_missing_required_pack` | PASS | Проверяются session/tenant, forged view, service/topic scope, невалидный tenant path и required pack; пустая связь услуги не является wildcard. |
| 11 | `test_d2_demo_snapshot.py::test_overview_readiness_is_not_optional_ui` | PASS | Broad overview demo имеет typed `direction_overview_not_configured`; нет выдуманных цен/кнопок. |
| 12 | `test_response_schema_loader.py::test_captured_text_loader_matches_path_loader` | PASS | Path и captured-text loader используют один strict schema contract на валидном pack; captured missing required file и duplicate key остаются ошибками. |
| 13 | `test_request_understanding_schema_offline.py::test_d2_section_refs_use_existing_envelope` | PASS | `content_section_refs` проходит через существующий D1R parser; absent field совместим, неправильная форма/дубликаты отклоняются. |
| 14 | `test_d2_demo_snapshot.py::test_real_path_never_calls_legacy_or_network` | PASS | Реальный D2 path проходит resolver/renderer/UI без Composer, legacy materializer или сети. |

Границы C7: B13 покрыт. B15 покрыт только как data/section/provenance slice;
обычная свободная проза модели и T3 не реализованы. Broad price overview demo
не настроен. B14 first-price deferral не реализован. S2 не завершён и S3 не начат.
