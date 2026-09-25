# D2 — сверка состава и сохранений

Дата: 2026-09-25. Статус: зафиксированный результат read-only аудита, не разрешение переносить изменения.
Документ перенесён из подготовительного отчёта в постоянный репозиторий по решению владельца. Факты ниже относятся к указанному baseline и проверкам аудита; документальная фиксация не является повторным запуском тестов или новым опросом GitHub.
Активная база: `C:\Cursor Projects\artgents-bot-active`, ветка `codex/d2-stage1-contract`, HEAD `e261383515d94e7d925acc705d8a6731aa704e48`.
Git top level совпадает с папкой. `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`. Tracked clean, staging пуст, untracked `data/`.

## 1. Сохранность — что проверено в аудите 2026-09-25

- GitHub read-only `ls-remote`: текущая ветка = `e261383`, старая D2 = `b8b28d3`, main = `141ce91`.
- Backup root: `C:\Users\denis\artgents-backups\20260925-134401`.
- `main-checkout`: для всех 36 файлов diff `38fdeb3..b8b28d3` и 7 отдельных untracked документов/скриптов проверены существование, SHA256 против manifest и совпадение с исходной папкой. 43 из 43, расхождений нет.
- `d2-stage-checkout`: проверены 40 файлов, присутствующих в diff `38fdeb3..7b8554f`. Все проверенные backup-файлы совпадают со своими manifest. 32 совпадают с текущим stage-worktree; 8 менялись после backup. Последний изменяющий их коммит — `7b8554f`, он входит в active/GitHub.
- Эти восемь: `clients/demo/target_response/service_catalog.json`, `contracts/response_plan.py`, `core/response_plan_materialization.py`, `docs/tasks/DEMO_D2_TARGET_CONTRACT.md`, `tests/test_d2_demo_snapshot.py`, `tests/test_d2_r1_contract.py`, `tests/test_d2_stage3_prices_scope.py`, `tests/test_d2_stage4_mixed_response.py`.
- `.env` существует в old, active и main-backup; все три побайтово совпадают. Значения не выводились и не копировались в отчёт.
- Старый `core/response_plan_resolver.py` остаётся modified в Git, но diff без различий окончаний строк пуст. Не исправлялся и не stage.
- Архив 15 сентября уже инвентаризирован в предыдущем аудите; все старые черновики из него не объявляются построчно интегрированными.

Это проверка выбранных значимых файлов, а не повторное хеширование всех 152 тысяч файлов backup. Свежие рабочие `data/`, SQLite и logs изменяются при запуске и не объявляются полностью покрытыми старой резервной копией. Эта задача их не пишет и не удаляет. Сборка с GitHub не восстанавливает автоматически ignored настройки, БД, окружение или журналы.

## 2. История двух линий и подтверждённые пробелы

После общего `38fdeb3` работа разошлась:
- старая линия: `b8b28d3` — сохранённый прежний WIP (36 файлов), не предок active;
- этапная линия: `906a539` (документы) → `21051f7` (контракт) →
  `63d980f` (память) → `7297cd7` (цены) → `9ec81e4` (mixed plan) →
  `7b8554f` (новое exact-service правило и demo offer) →
  `94b4596` (постоянная папка) → `e261383` (launcher).

Active содержит вторую линию. Это не объединение всех решений старого WIP.
Наличие старых файлов само по себе не доказывает их вызов из активного пути.
Смена аккаунта не установлена как причина ошибок runtime.

Аудит выявил несколько независимых проблем, а не единственную ошибку папки:
- blocking gate в `core/d2_content_realization.py` отбрасывает prose с
  деньгами/ссылками; наружу причина обобщается в `d2_invalid_turn`;
- этап 1 уже допускает часть неполных refs, но остаются случаи existing ref
  без service/topic и корректного по форме, но несуществующего ref;
- exact-service цена может построиться, а active service не попасть в
  сохранённое состояние для следующего вопроса;
- развёрнутые пакеты условий и неразличимые названия цен ухудшают ответы;
  Markdown-якоря в кнопках и вводная обзора требуют отдельной проверки;
- старые тесты, контракт и Ledger не полностью синхронизированы.
  Нельзя считать это ни доказательством потери всех правок, ни готовностью демо.

Минимальная диагностика покажет фактический шаг и исход; сама она эти
дефекты не исправляет. Восстанавливаются необходимые результаты, а не
целиком старая реализация.

### Что сохраняем в active без отката

| Результат работы | Источник | Обязательство восстановления |
|---|---|---|
| Один D2-вход JSON/SSE, недостижимость legacy normal runtime | CP6/CP7, включая `298f094` | Не возвращать старый finalizer ради его логов |
| FullContext и один production parser | `38fdeb3`, `21051f7` | Доработать допуск optional provenance, не строить второй parser |
| Typed memory/UI, bounded prose history, offer references | `63d980f` | Сохранить механизм; исправить разрывы сохранения/следующего хода |
| Цена и scope | `7297cd7`, изменённое владельцем правило `7b8554f` | Exact service: свои active/published offers, volume/brand filters, numeric ascending, без лимита и зависимости от directions |
| Общий обзор направления | прежний direction contract | Сохранить authored набор до 3, вводный текст и кнопки; не смешивать с exact-service правилом |
| Mixed response и contacts/policy до freeze | `9ec81e4` | Один финальный план, renderer/UI; не возвращать append после freeze |
| Demo удаление 5 000 / 8 000 и complex offer | `7b8554f` | Сохранить числа, «от», единицы и demo-only ownership |
| Одна активная папка и guarded launcher | `94b4596`, `e261383` | Не переносить рабочую папку снова |
| Lead/privacy, effect/replay/tenant boundaries | существующий D2 и сохранённый lead owner | Не ослаблять ради пригодной prose или успешного теста |

Наличие механизма не означает PASS всех сценариев. Аудит: 147 passed / 11 failed
из 158 выбранных тестов, с отдельным повтором browser-test после первоначального
таймаута. Это не полный CI и не новый прогон документального checkpoint.
Запускался старый interpreter Python 3.12.14 / pytest 9.1.1 против active-кода,
а не идентичное active-окружение. Provider/live calls: 0.

Известные ограничения сравнения:
- 3 source-UI теста сохраняли старое authored ожидание; падали и на `38fdeb3`;
- 5 commercial/directory тестов в active останавливались на patient_text,
  а на `38fdeb3` также падали, но раньше в materializer; одинаковую причину не заявляем;
- 1 stage2 history fixture с 1200 одинаковыми символами уходил в spam_closed,
  воспроизводилось на `9ec81e4`;
- 2 stage3 теста на active останавливались на situation_state и
  treatment_same_requires_subject; на `9ec81e4` были более ранние fixture/contract
  ошибки. Это не доказательство эквивалентности дефектов двух сборок.

Перечень — исторический baseline evidence, не разрешение игнорировать
падения или менять ожидания ради зелёных тестов. Новые карточки должны
сопоставлять конкретные сценарии и зафиксированное окружение.

## 3. Полный реестр 36 файлов старого checkpoint

Источник каждой строки: diff `38fdeb3..b8b28d3` в старом репозитории. Наличие в backup проверено для каждой строки. Категории ниже — решения, предлагаемые для карточек, не уже выполненный перенос.

| № | Файл | Разница и предлагаемая судьба |
|---|---|---|
| 1 | `app.py` | Trace/outcome/error/SSE hooks. Адаптировать только безопасное журналирование; не переносить новый public wire и raw body |
| 2 | `clients/demo/target_response/d2_direction_prices.json` | Нейтральная вводная имплантации. Отдельная разрешённая точечная правка текста позднее; цены/order не переносить целиком |
| 3 | `contracts/d2_dialogue.py` | Старые selected_content_ref/selected_section_ref. В active другой typed selected_ui_ref; не добавлять параллельные поля |
| 4 | `core/d2_contacts_cta.py` | Общий contacts → адрес+телефон. Зафиксировать отдельный owner choice перед изменением видимого состава |
| 5 | `core/d2_content_realization.py` | Неблокирующая публикация prose/review flags. Нужный результат по D2-092; адаптировать без ослабления tenant/privacy |
| 6 | `core/d2_dialogue.py` | Смешаны диагностика, selected sections, review, regex контактов, post-freeze append. Разобрать по механизмам; целиком не переносить |
| 7 | `core/d2_full_audit.py` | Полные transcripts. Сохранить исторический файл; не включать raw-режим автоматически. Безопасный observer сделать отдельно |
| 8 | `core/d2_http_adapter.py` | Классификация ошибок меняет exceptions/rollback paths. Не переносить поведение целиком; диагностировать без смены исходного исключения |
| 9 | `core/d2_live_provider.py` | Prompt/contact/section improvements плюс raw audit. Selected UI частично заменён stage2; проверить смысл в единственном prompt. Для первого checkpoint только timing/hooks без текстов |
| 10 | `core/d2_outcome.py` | Error classes, closed codes/site. Идеи безопасных кодов пригодны; новый exception/wire contract не переносить |
| 11 | `core/d2_snapshot_sources.py` | Удаление Markdown-якорей из button label. В active отсутствует; восстановить при UI-проверке, не менять ref |
| 12 | `core/response_plan_materialization.py` | Optional provenance normalization и clinic scope. В active stage1 только часть допусков. Адаптировать по текущему контракту и ownership |
| 13 | `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md` | Исторические evidence. Не копировать PASS; добавить новые проверенные строки без переписывания истории |
| 14 | `docs/tasks/DEMO_D2_EXECUTION_LOCK.md` | Исторические правила. Действующий lock active имеет приоритет; не заменять старой редакцией |
| 15 | `docs/tasks/DEMO_D2_TARGET_CONTRACT.md` | Исторические уточнения. Сверять с текущими D2-092–096 и exact-service правилом; не откатывать |
| 16 | `static/widget/api.js` | Другой done/outcome contract. Не переносить в diagnostic-only checkpoint; текущий wire оставить |
| 17 | `tests/js/d2_r4_api.mjs` | Тесты старого outcome wire. Историческое evidence, не требование внедрить этот wire |
| 18 | `tests/js/d2_widget_harness.mjs` | Парная правка старого wire. Сохранить текущий stage4 harness, позже добавить нужные сценарии под текущий protocol |
| 19 | `tests/test_d2_commercial_scenarios.py` | Direct price без topic. Частично покрыт новым R1/extraction; оставить покрытие разных услуг и проверить commercial continuation |
| 20 | `tests/test_d2_content_scenarios.py` | Ожидания live prose. Сверить с D2-092/B15, сохранить source/UI assertions |
| 21 | `tests/test_d2_content_source_ui.py` | Authored → prose expectations. Исправлять только с привязкой к текущему контракту, не ради green |
| 22 | `tests/test_d2_continuation_scenarios.py` | Проверка нейтральной вводной. Полезна для будущей правки текста; не заменяет stage2 history/TTL tests |
| 23 | `tests/test_d2_directory_ui_scenarios.py` | Valid prose fixtures, contacts matrix и regex-dependent location test. Regex-test не переносить как требование; остальные разделить по назначению |
| 24 | `tests/test_d2_full_audit.py` | Проверки raw audit/credential redaction. Не доказывают PII safety. Новые диагностические тесты должны запрещать raw/PII |
| 25 | `tests/test_d2_http_contract.py` | Старые error/wire expectations. Сохранить нынешние endpoint/replay/mixed проверки; диагностический слой тестировать отдельно |
| 26 | `tests/test_d2_independent_request_parts.py` | Live prose и части ответа. Сверить с stage4 partial failure, не ослаблять completeness/ownership |
| 27 | `tests/test_d2_live_provider_offline.py` | Prompt/selected sections. Адаптировать к единственному current selected_ui_ref, без реального provider |
| 28 | `tests/test_d2_part_failure.py` | Prose expectations. Сохранить независимость частей, корректные answered/unavailable/deferred |
| 29 | `tests/test_d2_price_deferral.py` | Prose expectations. Сохранить first price / explicit deferral последующих |
| 30 | `tests/test_d2_prose_realization.py` | Prose expectations/linkage. Совместить с текущим frozen plan, не удалять проверки связи |
| 31 | `tests/test_d2_prose_violation.py` | Non-blocking review вместо удаления денег/ссылок. Требуемое новое правило; отдельный контрактный checkpoint C03 |
| 32 | `tests/test_d2_r3_free_dialogue.py` | Missing/optional source, scope, selected section. Добавить недостающее без старого post-freeze механизма |
| 33 | `tests/test_d2_r4_outcomes.py` | Outcome/store/transport wire. Использовать как список failure cases, не как разрешение старого protocol |
| 34 | `tests/test_d2_recovery_scenarios.py` | Keep prose при bad ref/money + review event. Нужные требования C02/C03; перенести доказательство в новый механизм |
| 35 | `tests/test_d2_single_request.py` | Prose expectations. Перепроверить current parser/general information |
| 36 | `tests/test_d2_snapshot_sources.py` | Button heading expectations. Проверить label cleanup при неизменных action/source IDs |

## 4. Семь отдельных untracked артефактов

Все семь сохранены в main-backup и совпадают по SHA256 с текущими файлами. Ни один не объявляется утверждённой реализацией:

- `docs/MARKETING_BOT_SITUATIONS.md` — исторические продуктовые материалы;
- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md` — аудит 17 сентября, объясняет происхождение замены runtime;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json` и `.md` — прежние замеры, не доказательство скорости active;
- `docs/tasks/D2_EXTERNAL_REVIEW_PACKET_TEMPLATE.md` — шаблон review;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md` — исторический проект ворот, не разрешение текущих действий;
- `scripts/measure_d2_latency_baseline.py` — исторический измеритель; не запускался и не переносился.

## 5. Нельзя автоматически переносить

- Raw-question semantic regex для выбора контакта.
- Post-freeze append/re-render.
- Старую альтернативную модель selected-section полей рядом с текущей.
- Новую public outcome/error/done схему только ради журналирования.
- Raw body/provider transcript с редактированием лишь credentials: это не защита PII.
- Исторические статусы PASS как приёмку нынешней сборки.

Это не удаление прежней работы: её исходники и evidence сохраняются, но способ реализации конфликтует с принятыми границами.

## 6. Связь с действующим планом


Единственный источник последовательности — текущий раздел
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md).
Первая [карточка диагностики](DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md) подготовлена
для review, не для автоматического исполнения. Для следующих частей нужны
свои точные baseline/allowlist и согласование. Целые затронутые диалоги
проверяются на каждом шаге, не только в финальной приёмке.

## 7. Остаточные риски и ограничения

- Архивы не заменяют доказательство работающего поведения; branch content не равно union всех старых папок.
- Все исторические черновики архива 15 сентября не разобраны построчно; это явный остаток, а не заявление «ничего невозможно потерять».
- Fresh active venv отличается версиями зависимостей и не содержит pytest. Для будущего gate нужно воспроизводимое тестовое окружение; нельзя молча менять работающую `.venv`.
- Рабочие DB/logs остаются локальными и не включаются в Git. Перед любым будущим действием, способным их изменить или удалить, нужна отдельная проверка/авторизация. Диагностическая реализация не должна мигрировать/пересоздавать их.
- Полный резервный архив заранее не удаляется даже после первого PASS.

Итог исходной сверки: runtime edits 0, branch/staging/commit/push 0, live/provider calls 0. Подготовительные документы теперь закрепляются в active в отдельном documentation-only diff. Исходные архивы и временный полный аудит не удаляются. Независимое review постоянного diff и Cursor review отражаются отдельно в Ledger.
