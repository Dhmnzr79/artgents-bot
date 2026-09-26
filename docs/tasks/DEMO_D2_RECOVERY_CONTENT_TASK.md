# D2-REC-2 — пригодный ответ и необязательные ссылки

Дата: 2026-09-26. Статус реализации: **Draft; ожидаются Checker и Cursor**.
Карточка была отдельно одобрена Checker и Cursor, сохранена в `ce47c16`,
после чего владелец дал GO на реализацию REC-2. Live, merge и deploy не
разрешены. Ниже §1–8 сохраняют утверждённый план и исторический prompt
проверки карточки; факты текущего implementation diff добавлены в §9.

## 1. Результат простыми словами

Если модель дала пригодный ответ по FullContext клиники, ошибка в необязательной
ссылке на материал не должна превращать его в `d2_invalid_turn`.
Наличие суммы или ссылки в живом тексте также не повод вырезать ответ или
заменять его цитатой. Это действующее решение D2-092, не новое обещание
правильности всех высказываний модели.

Примеры ниже синтетические, это не медицинские рекомендации и не live evidence:

- «Я боюсь боли» → непустой ответ модели; документ указан с ошибкой.
  Сохранить живой текст, но не показывать кнопки/видео от непроверенного документа.
- Та же проза содержит «стоимость от 5 000 ₽». Сама сумма не удаляет prose.
  Если есть отдельный проверенный ценовой блок, его данные не меняются;
  потенциальное противоречие — ранее принятый риск демо, не подтверждённая цена.
- Правильный документ выбран без `service_id` и `topic_id` → не требовать
  выдумать услугу только ради публикации ответа. Source UI проходит отдельную
  проверку текущей клиники; новая услуга в память автоматически не назначается.
- «Сколько стоит удаление и больно ли это?» → проверенные предложения удаления
  и пригодная информационная часть сохраняются в одном frozen plan.

REC-2 не исправляет все ошибки диалога: память — REC-3, оформление цен/кнопок —
REC-4, полная приёмка и отдельно разрешённая реальная модель — REC-5.

## 2. Baseline, границы записи и сохранённая работа

- Папка и Git top level: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`, продолжение существующей D2-задачи.
- Baseline подготовки карточки: `f4bae9b0b292026733854ae1d8fd34e608f953d5`
  (`feat(d2): add safe REC-1 diagnostics`). Документальный checkpoint и точный
  implementation baseline: `ce47c16f564498165c1d00b2d0efd997dcbb9c22`.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- После commit REC-1 tracked clean, staging пуст. Foreign/untracked: `data/`.
  `data/demo/d2_dialogue.sqlite` не часть задачи. Старые папки/worktrees,
  `.env`, `.venv`, tenant packs, SQLite, пользовательские логи не менять.
- REC-1 сохранён после независимых Checker и Cursor отчётов, включая
  late-clock дополнение. Это история предыдущего checkpoint, не verdict
  этой карточки и не доказательство готовности REC-2.

Исторический documentation-only allowlist подготовки:

```text
docs/tasks/DEMO_D2_RECOVERY_CONTENT_TASK.md     # новый, читать явно даже untracked
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md          # текущий статус и ссылка REC-2
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md        # новая Draft/evidence строка
```

Review карточки и отдельный GO получены. Реализация стартовала ровно с
`ce47c16`; разрешённые файлы перечислены в §5. Произвольный descendant не
считается разрешённым baseline.

## 3. Источники и подтверждённые места проблемы

Приоритет: AGENTS → Execution Lock → Delivery Roadmap → Target Contract §5–7,
Product Decisions D2-092/094/095 → Acceptance C01–C04/C09 и A03/A05/A06.
[Inventory](DEMO_D2_RECONCILIATION_INVENTORY.md) — историческое evidence;
`b8b28d3` не переносить целиком и не использовать как baseline.

Read-only осмотр на f4bae9b подтвердил:

1. `core/one_call_envelope_protocol.py::_normalize_production_payload` уже
   сбрасывает malformed `content_ref` при непустой prose, вместе с section/fallback.
   Это рабочая часть, не писать её заново. Независимо повреждённые
   section/fallback поля всё ещё доходят до строгих валидаторов.
2. `core/d2_content_realization.py` в обоих путях model prose использует
   `_MONEY`/`_LINK` как блокирующие проверки: unavailable либо authored fallback.
   Это противоречит позднейшему D2-092.
3. `core/response_plan_materialization.py::_d2_information_blocks` считает
   отсутствующий документ/раздел unavailable, даже при пригодной prose.
   `_d2_content_scope` может бросить `d2_content_scope_required`, когда
   существующий материал имеет allowed services, а модель не назвала service/topic.
4. Выбор `source_content_ref` сейчас опирается на исходный ref и успешный
   outcome. После допуска prose без provenance этого недостаточно: публикация
   текста не должна автоматически разрешать UI от исходной непроверенной ссылки.
5. `core/d2_dialogue.py` проверяет наличие information blocks перед commit;
   последствия отказа материализации превращаются в публичный `d2_invalid_turn`.
   Нельзя просто снять финальную проверку и объявить пустой ответ успешным.
6. Старые `test_d2_prose_violation.py` и часть recovery/content expectations
   требуют удалять money/link prose. Их нужно выровнять по D2-092 с сохранением
   отрицательных проверок ownership/пустого ответа, не ради зелёного pytest.
   REC-1 diagnostic test на money gate также потребует явного пересмотра ожидания.

Это осмотр кода, не новый воспроизведённый live-инцидент и не свежий pytest baseline.

## 4. Один механизм, без нового runtime

**ACCEPTANCE:** C01 (необязательное provenance), C02 (независимые части), C03
(неблокирующий review), регрессии C04/C05/C08/C09/C10/A12;
затронутые диалоги A03/A05/A06 и информационная часть A04/B15.
Не объявлять целиком закрытой A04: отдельные гарантийные code-owned факты не
создавать в этой задаче.

**D2 ROUTE:** существующие `/ask` и `/ask/stream` → один production parser →
тот же common turn/materializer → один frozen plan → существующие renderer/store.
**LEGACY IMPACT:** не добавлять legacy imports, semantic selectors или fallback.
**OWNER DECISION:** D2-092 уже утверждает публикацию prose; новый GO нужен на
эту реализацию, не на повторное обсуждение принятого правила.
**FUTURE SCOPE:** REC-3–5, новые commercial facts, смена формата UI, корреляция
логов между попытками, админка, raw transcripts — вне карточки.

### 4.1 Что считается пригодным

Структурно допустимая content-часть в разбираемом существующим parser envelope,
с непустым строковым content_text в действующих ограничениях длины и без
нарушения строгих границ. Это не новый семантический классификатор полезности.
Не извлекать текст regex из malformed/truncated JSON, не подменять обязательные
route/kind/IDs, не создавать второй parser или repair-вызов модели.
`other`, ADMIN, CLARIFY, active lead и terminal не переклассифицировать по prose.
Область нового допуска — `model_prose`, включая уже существующий default этого
режима при его пропуске. Явный `authored` не превращать в model prose:
его источники и точные цитаты сохраняют действующие проверки. Изменение такого
поведения требует отдельного обоснования и согласования, не следует из REC-2.

### 4.2 Текст и provenance — разные основания

| Вход content/model_prose | Текст | Provenance и source UI |
|---|---|---|
| Ref отсутствует/null, текст пригоден | Публиковать | Без выдуманного источника и source-owned UI |
| Неправильная форма optional ref/section/fallback | Сохранить | Невалидное provenance не является разрешением UI; нормализация только этих optional полей |
| Ref корректен по форме, отсутствует в текущем snapshot | Сохранить | Без чтения файлов по нему, без похожего источника и UI |
| Ref/sections существуют и разрешены текущему tenant; service/topic null | Сохранить | Проверить source ownership/совместимость, не угадывать услугу; допустимый source UI по действующим правилам |
| Локальный source не совместим с явно заданным валидным service/topic | Не подменять prose или typed IDs | Не использовать несовместимый источник для цитат/UI |
| Доказанный чужой source owner, forged/stale/foreign UI action | Не маскировать как успех | Строгий отказ по существующей защите |
| Пустой/нестроковый/слишком длинный текст или неразбираемый envelope | Не создавать успешный живой ответ | Существующий валидный authored/recovery путь только там, где он уже допустим; иначе ошибка/gap |

Отсутствие filename в текущем snapshot само по себе не доказывает другой tenant.
Не загружать чужие tenant packs, чтобы это выяснить. Но настоящий чужой authority
с source_client_id != текущему client, недоступный typed ID и неавторизованный
UI action не превращаются в «просто missing ref». У существующего валидатора
может быть одно имя ошибки на разные причины: проверять фактическое основание.

Нормализация модельных optional полей не применяется к входному HTTP ref или
проверенному сервером selected_ui_ref. Уже выбранный follow-up сохраняет
server-owned привязку, даже если модель не повторила её в ответе.
При unverified provenance все связанные поля итоговой части/блока/UI должны
быть согласованы до freeze; нельзя очистить ref только в одном представлении.
Конкретную гранулярность очистки повреждённых sections/fallback фиксировать
в тестах, не ослабляя допуск источника. Спорное изменение видимого UI — стоп.

### 4.3 Деньги, ссылки и диагностика

- У пригодной prose money/link больше не вызывает unavailable/recovered,
  authored substitution, обрезку, второй вызов или новый strict gate.
- Существующие механические детекторы могут служить только неблокирующей
  диагностике. Не добавлять семантические regex/фразы, не расширять их для
  классификации темы или проверки медицинской/коммерческой истинности.
- Наличие суммы/ссылки — сигнал для review, не доказанная галлюцинация.
  Полнота обнаружения смысловых ошибок не обещается.
- Review event с закрытым кодом и attempt_trace_id через REC-1 no-context logger.
  Без prose/PII/raw exception/IDs, без новых DB/wire полей. Observer failure
  не влияет на публикацию. `answered` не получает failure_reason; review
  не записывать как replacement_reason и не выдавать за failed transport.
- Code-owned цены, политики, контакты, единицы и условия остаются прежними,
  собираются до freeze. Проза с суммой не становится проверенным прайсом.
- Сохранённый текст content-блока равен принятому prose с существующей обработкой
  внешних пробелов; внутренние фразы не вырезаются. JSON/SSE отдают тот же
  сохранённый результат. Widget сохраняет прежний безопасный Markdown renderer:
  escaping HTML и отсутствие исполнения URI; это не GO делать ссылки активными.
  Текущий formatter отображает Markdown-ссылку как label — в REC-2 его не менять.

## 5. Write allowlist реализации — GO получен

```text
core/one_call_envelope_protocol.py             # существующая optional normalization
contracts/request_understanding.py            # только согласованные optional validators
core/d2_content_realization.py                 # publication vs nonblocking observation
core/response_plan_materialization.py          # verified provenance, scope, frozen blocks/UI
core/d2_dialogue.py                            # передача review в observer/существующий content gate
core/d2_diagnostics.py                         # закрытое неблокирующее review event
tests/test_request_understanding_schema_offline.py
tests/test_d2_r1_contract.py
tests/test_d2_prose_realization.py
tests/test_d2_prose_violation.py
tests/test_d2_recovery_scenarios.py
tests/test_d2_content_scenarios.py
tests/test_d2_content_source_ui.py
tests/test_d2_independent_request_parts.py      # разделить missing и настоящий foreign
tests/test_d2_diagnostics.py
tests/test_d2_rec2_content_http.py              # новый assembled HTTP evidence
docs/tasks/DEMO_D2_RECOVERY_CONTENT_TASK.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Наличие файла не обязывает менять его. Не расширять контракт/schema ради новых
полей, не менять ordinary state/session delta и не трогать price selectors.
В core/d2_dialogue.py запрещено исправлять REC-3 память под видом content gate.
Read-only: contracts/response_plan.py, app/HTTP adapter/provider/prompt,
store/schema, resolver/renderer,
tenant loader/data, lead/privacy owners, widget JS/harness, launcher, окружение.
Любая необходимая запись вне перечня или изменение этих границ — стоп/вопрос.

## 6. Доказательства и порядок реализации после GO

1. Зафиксировать на точном baseline результаты назначенных ниже existing tests
   в active .venv. Новые кейсы сначала должны воспроизводить реальные отказы.
   Не запускать live ради подтверждения code-level ветки.
2. Проверить production parser матрицей optional provenance: отсутствует/null,
   bad path/type, valid-but-missing document, malformed/missing section и fallback,
   valid ref при null service/topic. Отдельно обязательные поля и limits остаются strict.
3. Публикация prose с money/HTTP-ссылкой/Markdown/URI без fallback и с authored
   fallback сохраняет текст; безопасный review event не меняет answered/status.
   Пустой ответ отдельно, никакого «всегда вернуть 200».
4. Не смешивать missing и foreign: действительный чужой authority/UI остаётся
   отрицательным кейсом. Fixture с missing.md не выдавать за foreign ownership.
   Именно такой fixture сейчас используется в test_d2_independent_request_parts.py
   в test_foreign_content_source_fails_closed_without_neighbor_substitution;
   разделить отсутствие источника и доказанного чужого владельца, не удалять
   отрицательную проверку tenant boundary из test_d2_content_source_ui.py.
5. Новый HTTP-файл: JSON и SSE → raw fake envelope → реальный parser/snapshot/
   materializer/store. Для каждого семейства проверить answer, frozen content/ref/UI,
   status частей, persisted completion, state и число вызовов, не только HTTP 200.
6. Диалоги: ordinary content → показанный authorized follow-up (если доступен)
   → следующий ответ; degraded provenance не рождает action. Checked price +
   prose + policy/contact остаются одним mixed plan. В следующем ходе состояние
   читается из предыдущего store, не подставляется тестом; известный REC-3 gap
   не объявлять исправленным и не обходить ручной записью active_service.
7. Replay JSON↔SSE после reopen store и изменения temporary tenant возвращает
   frozen результат без нового provider/effect. Проверить sink failure и traces
   разных попыток/tenant; review не требует повторной модели на replay.
8. У существующего REC-1 теста `test_existing_content_gate_is_diagnosed_not_repaired`
   money-пример намеренно перестаёт падать по D2-092: новое ожидание — сохранённый
   prose + review, а диагностирование реального отказа оставить отдельным кейсом.
   Для каждого изменённого старого ожидания записать «до → после → пункт договора».
   Запрещены skip/xfail, удаление неудобных ownership assertions и helpers,
   которые вызывают тот же selector для вычисления ожидаемого результата.

Минимальные наборы по шагам, не весь CI на каждую правку:

- Parser: test_request_understanding_schema_offline.py, test_d2_r1_contract.py.
- Publication/materialization: test_d2_prose_realization.py,
  test_d2_prose_violation.py, test_d2_recovery_scenarios.py,
  test_d2_content_scenarios.py, test_d2_content_source_ui.py,
  test_d2_independent_request_parts.py.
- Собранный checkpoint: новый test_d2_rec2_content_http.py плюс
  test_d2_diagnostics.py, test_d2_http_contract.py, test_d2_http_scenarios.py,
  test_d2_stage4_mixed_response.py, test_d2_no_legacy_path.py,
  test_d2_lead_scenarios.py, test_d2_widget_replay.py,
  test_d2_multi_request.py, test_d2_r3_free_dialogue.py.

Все файлы выше находятся в tests/. Existing файлы последней группы кроме
diagnostics read-only. Widget harness доказывает прежнюю безопасную доставку,
не новую разметку. Если нужен новый JS security-case — сначала согласовать
точный test-only allowlist; не править browser код молча.

Interpreter: `C:\Cursor Projects\artgents-bot-active\.venv\Scripts\python.exe`.
Команда каждого выбранного набора: `python -B -m pytest -q -p no:cacheprovider
--basetemp <unique OS temp>/pytest <exact test paths> --tb=short`.
PYTHON_DOTENV_DISABLED=1; CHAT_API_KEY=offline-placeholder; BOT_PG_DSN пуст;
APP_ENV=local; PYTHONDONTWRITEBYTECODE=1; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1;
BOT_LOG_DIR в том же unique temp. Сеть/provider/SMTP заблокированы fixtures;
temporary tenant copy и SQLite. Browser — temporary profile/fake transport,
динамический localhost-порт, не 9001. Пакеты не устанавливать/не обновлять.

Исторические результаты REC-1: полный прогон Cursor 65/1 (v19 expectation),
последующее diagnostics 32 passed, focused clock 6 passed. Это не REC-2 baseline
и не полный CI. Старый аудит 147/11 был на другом окружении. Нужны новые точные
результаты до/после на одних условиях; причины старых failures не скрывать.

## 7. Риски, решения владельца и стоп-условия

Принятые правила не пересогласовывать: неточность prose — демо-риск D2-092;
code-owned факты и tenant/lead/privacy остаются строгими; один parser/вызов/plan.
GO на реализацию после review карточки получен. Следующие ворота — независимый
Checker, Cursor и согласование закрытия diff; live отдельно.

Остановиться и задать конкретный вопрос, если безопасная реализация требует:
нового visible правила или отказа; ослабления ownership/lead/privacy; нового
wire/state/schema или модели; удаления/активации ссылок в widget; изменения
memory/price/commercial logic; записи вне allowlist. Архитектурный разбор Astra
помогает выявить конфликт, но не заменяет согласование владельца.

Сам факт пригодной prose не доказывает медицинскую или коммерческую точность.
Нет гарантии, что исчезнут все d2_invalid_turn: malformed обязательный контракт,
пустой ответ и нарушения границ не маскируются успехом. No-live evidence не
доказывает качество настоящей модели и всей демо-сессии.

## 8. Evidence подготовки и строгий Cursor prompt

На документальном шаге: проверены preflight, фактические места кода и правила
договора; код/данные/окружение не менялись, тесты не запускались, provider/live/SMTP 0.
Независимый review этой карточки ожидается; verdict только отдельным отчётом,
без заранее поставленного PASS внутри проверяемого diff.

```text
Проверь read-only только карточку REC-2 и её включение в действующий roadmap.
Repo C:\Cursor Projects\artgents-bot-active, branch codex/d2-stage1-contract.
HEAD/baseline f4bae9b0b292026733854ae1d8fd34e608f953d5.
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Сначала AGENTS.md, WORKFLOW_CHECKER, Execution Lock, Roadmap, Target Contract,
Acceptance, Product Decisions D2-092–096, Ledger; затем эту карточку.
Текущий allowlist только DEMO_D2_RECOVERY_CONTENT_TASK.md (новый, открыть явно),
DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_CHECKPOINT_LEDGER.md в docs/tasks/.
Staging должен быть пуст; tracked runtime соответствует HEAD. data/ — foreign WIP.
Read-only code inspection разрешён, тесты и code edits на этом шаге запрещены.
Проверь, что это один existing parser/materializer/plan, не новый fallback;
пригодная prose и авторизация source UI разделены; null/malformed/missing refs
не смешаны с доказанным foreign ownership или пользовательским typed action.
Проверь сохранение цены/policy/contact, frozen replay, privacy/lead и no-legacy.
Money/link review не должен стать semantic sanitizer, новым gate или raw логом.
Проверь точность будущего allowlist и запрет незаметно выполнить REC-3/4.
Проверки должны проходить реальные JSON/SSE/parser/store и следующий ход,
сохранять негативные сценарии и честно переопределять старые ожидания по D2-092.
Не выдавай historical 65/1,32,6 за свежий прогон REC-2. Не требуй новых live calls.
Дай отдельный PASS/REJECT именно карточки, находки severity/file/line/evidence
и минимальное исправление. Не записывай verdict внутрь diff.
Без edits/tests/staging/commit/push/install/live/merge/deploy.
PASS карточки не разрешает реализацию: требуется отдельный GO владельца.
```

## 9. Реализация на `ce47c16`: Draft evidence, не verdict

Владелец дал GO после отдельных Checker/Cursor PASS карточки. Runtime diff
ограничен одним существующим parser/materializer/frozen plan: optional поля
`content_ref`/sections/fallback у непустой `model_prose` очищаются как одна
группа при неверной форме; отсутствующий в snapshot или локально несовместимый
источник не скрывает prose, но не получает source ref/UI. Доказанный чужой
владелец источника, неизвестная typed service, пустая prose и явный `authored`
остаются строгими. У подтверждённого источника без service/topic сохраняются
source ref и разрешённые UI, но не создаётся service focus. Money/link — два
закрытых review-сигнала REC-1, а не ответный gate или проверенная цена.

Точное изменение прежних ожиданий по принятому D2-092 и §4:

| Тесты | До → после | Основание |
|---|---|---|
| `test_d2_prose_violation.py`, `test_d2_recovery_scenarios.py`, `test_d2_content_scenarios.py` | money/link выбрасывали или заменяли prose цитатой → непустой исходный prose в ответе, без `failure_reason`; code-owned цена отдельно неизменна | §4.1, §4.3, D2-092 |
| `test_d2_prose_violation.py`, `test_d2_independent_request_parts.py` | `missing.md` считался gap/foreign → пригодный prose без ref, sections и source UI; настоящий `source_client_id` другого tenant проверяется отдельным отрицательным тестом | §4.2, C01/C09 |
| `test_request_understanding_schema_offline.py` | malformed optional sections у `model_prose` отвергали весь envelope → очищается только optional provenance; `authored` и пустой текст остаются strict | §4.1–4.2 |
| `test_d2_content_source_ui.py`, `test_d2_independent_request_parts.py` | старые assertions ожидали текст документа при default `model_prose` → проверяют текст модели, порядок частей и прежние границы UI | §4.1–4.2 |
| `test_d2_diagnostics.py` | money давали `d2_invalid_turn` → HTTP 200 и неблокирующий закрытый review; другие реальные отказные кейсы остаются | §4.3 |

Офлайн-проверки с временными tenant copies/SQLite и отключённой сетью:

- До кода на точном `ce47c16`: восемь назначенных файлов — **83 passed,
  27 failed**, 69.46 с. Это старые ожидания v19/authored и старый HTTP
  fixture, не новый regression baseline после переписывания тестов.
- После основного diff: десять назначенных файлов, включая новый собранный
  HTTP-файл и REC-1 diagnostics — **150 passed, 13 failed**, 93.71 с.
  Тринадцать красных — старые parser/R1 проверки: один v19 вместо v20,
  старый HTTP fixture/маршрут `other` и смежные старые ожидания. После этого
  для одного строгого случая сохранён прежний `d2_content_service_mismatch`
  вместо нового класса ошибки; focused recheck **2 passed**, новый полный
  aggregate после этой точечной правки не заявляется.
- Затронутые сценарии отдельно: `test_d2_rec2_content_http.py`,
  `test_d2_content_source_ui.py`, `test_d2_independent_request_parts.py`,
  `test_d2_prose_violation.py` — **50 passed**; recovery/content — **10 passed**;
  новый money/link review/replay/sink — **3 passed**. Это выборочные прогоны,
  не сумма для общего pass-rate.
- Дополнительный read-only regression set (HTTP, Stage 4, lead, no-legacy,
  widget replay, multi-request, R3, B12), исключая один browser-case:
  **52 passed, 6 failed, 1 deselected**, 103.18 с. Исключённый browser-case
  внутри sandbox дал timeout 75 с, но тот же офлайн case вне sandbox
  **1 passed**, 24.97 с. Никакого live/provider вызова не было.
- Шесть read-only failures не правились: три в `test_d2_multi_request.py`
  ожидают старый authored text вместо default `model_prose`; один в
  `test_d2_r3_free_dialogue.py` требует старый money-gap вместо D2-092;
  его greeting/`other` case всё ещё упирается в content gate; B12 free-CTA
  останавливается на `patient_text_required`. Последние два не исправляются
  под видом REC-2. Для изменения этих тестов нужен отдельный test-only
  allowlist владельца; их падения не объявлены PASS.

Новый HTTP-файл проверяет JSON/SSE и replay в обе стороны, completion/store,
согласованность frozen part/block/UI, mixed price+policy/contact, valid source
без выдуманного focus, пустой/явный authored/неизвестный typed ID, показанный
follow-up и следующий ход. Диагностика проверена с отказавшим sink и replay:
review не содержит prose и не повторяется на replay. `git diff --check`,
allowlist и foreign WIP — обязательны к повторной проверке на review. Текущий
diff не staged, не committed и не pushed; независимый Checker implementation
и Cursor ещё не проводились. Provider/live/SMTP 0; merge/deploy 0.
