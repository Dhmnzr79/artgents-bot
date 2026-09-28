# D2-LEAD-INTERRUPT — вопрос во время записи

Дата: 2026-09-28. Статус: **проект карточки, только документальный checkpoint**.
Владелец попросил сначала оформить отдельную карточку заявки. Решение о
видимом поведении кнопки «Ответить» и GO на runtime-код фиксируются отдельно;
REC-4-P2 не начинается. Astra выполнила read-only архитектурный разбор.

## Baseline и preflight

- Единственная рабочая папка/Git root: `C:\Cursor Projects\artgents-bot-active`;
  ветка `codex/d2-stage1-contract`.
- HEAD и локальный `origin/codex/d2-stage1-contract`:
  `b39ed36cdbc57f608da1c199cf45ce938e70b6dc` — принятый Checker/Cursor
  и сохранённый указатель текущего состояния.
- `origin/main` и merge-base:
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До этой карточки tracked diff/staging пусты. Чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` не трогать; БД и сырые пациентские
  сообщения не входят в checkpoint.
- Ни этот документ, ни прежний Cursor PASS не разрешают live/provider/SMTP,
  запуск бота, merge/deploy или перенос старого runtime.

## Подтверждённая находка

Локальный виджет 2026-09-28: при сборе имени пользователь задал отдельный
ценовой вопрос. Trace `40820dcb` показал «Ответить» и «Продолжить запись»;
`96b02f07` принял текущий `lead:pending:answer`, удалил сохранённый вопрос и
снова запросил имя; provider attempts 0. В `core/d2_lead_bridge.py` это прямо
записано как временное поведение CP5-LEAD. Старый lead-flow имеет похожий
answer→resume, но он не является разрешённым fallback для D2.

Действующий D2 обрабатывает активную заявку до provider. Просто пропустить
клик в обычный путь нельзя: UI-клик имеет пустой `q`, а сохранённый вопрос
лежит у отдельного lead owner. `lead:resume` в D2 пока не подключён; один лишь
показ такой кнопки не восстановит запись.

## Цель и решение владельца

Цель: после «Ответить» действительно ответить на **сохранённый вопрос**, не
потерять имя/телефон и тот шаг, на котором остановилась запись. При
«Продолжить запись» вернуться именно к прежнему шагу; отмена очищает данные.

Рекомендация Astra: показать содержательный ответ и typed кнопку «Продолжить
запись»; её клик восстанавливает прежний шаг name/phone. Альтернатива — после
ответа сразу повторить вопрос соответствующего слота. **Выбор владельца ещё
ожидается.** До его фиксации и отдельного GO реализация не разрешена.

Не добавлять новый parser, второй LLM, semantic regex, реконструкцию вопроса
по фразам, fallback на старый runtime или второго владельца lead/ordinary
state. Действуют D2-022/031/036, A12/B11/C05–C07 и Execution Lock §4.

## Границы будущей реализации — после GO

1. При проверенном текущем UI `lead:pending:answer` взять pending question
   только из tenant-bound lead session. Нельзя брать текст из label кнопки,
   пустого `q`, ordinary memory или другого tenant. UI `ref` и revision сначала
   сверяются с последним сохранённым ответом.
2. Очистить вопрос существующей
   `prepare_lead_pending_provider_question(profile_name=...)` **до** provider
   input и ordinary history. Если содержательного вопроса не осталось, не
   вызывать модель и не стирать pending/слот. Полный opt-in локальный журнал
   может хранить исходный тестовый ввод с ПД; в commit он не попадает.
3. Провести очищенный вопрос через существующие D2 provider, parser,
   materializer и каталог текущего tenant. Цена/материал/политика отвечаются
   обычным владельцем фактов. Ответ по вопросу не должен запускать новую
   заявку, отправлять контакт или показывать коммерческую CTA во время паузы.
4. Сохранить финальный ответ, UI и ordinary state одним D2 completion, затем
   обеспечить согласованный переход существующего lead owner в `paused` с
   прежним шагом и сохранёнными слотами. Выбранный способ перехода должен
   выдержать ошибку до commit, replay того же request_id и сбой после commit;
   две SQLite state-области не объявляются атомарными без доказанного механизма.
5. Подключить текущий typed `lead:resume` к D2 pre-provider bridge. Он
   возвращает к name/phone без provider и без повторного lead effect. Cancel
   очищает PII и pending. Если во время паузы приходит ещё один текстовый
   вопрос, он не принимается за имя/телефон и не прячет выход к записи.
6. Нельзя скрыть пригодный ответ из-за optional semantic claim по D2-097;
   строгие tenant, UI, privacy и lead/effect границы остаются.

## Точный write allowlist этого документального checkpoint

```text
docs/tasks/DEMO_D2_LEAD_INTERRUPT_TASK.md
docs/tasks/DEMO_D2_CURRENT_STATUS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Для реализации после решения владельца нужен новый preflight и **отдельный
точный code/test allowlist**. Предварительно читать `core/d2_dialogue.py`,
`core/d2_lead_bridge.py`, `core/d2_http_adapter.py`, `session.py`,
`core/lead_provider_input_privacy.py`, D2 UI projection и адресные lead/HTTP
тесты. Этот перечень мест чтения не является разрешением их менять.

## Приёмка будущей реализации и ворота

**ACCEPTANCE:** A12/B11/C05–C07, price/content через настоящий `/ask` и
`/ask/stream`; не полный REC-5. **D2 ROUTE:** один проверенный lead click →
очищенный pending вопрос → обычный D2 ответ → frozen UI/state/replay →
проверенное возобновление заявки. **LEGACY IMPACT:** старый normal runtime
не подключается. **OWNER DECISION:** pending по видимому поведению и отдельному
GO. **FUTURE SCOPE:** REC-4-P2, REC-5, отдельные live проверки с бюджетом.

Offline fake-provider проверки: name и phone; цена и материал; JSON/SSE;
очистка имени/телефона в provider input, истории и D2 store; только ПД →
fail-closed; current/foreign/stale/forged click; continue/cancel; повтор
request_id и другой payload с тем же ID; provider/commit/final-frame failure;
один lead effect, без автозаявки; содержательный текст и кнопка resume в одном
сохранённом ответе. Рабочие БД/логи не использовать: временные tenant/DB/log,
блокировка сети, полный журнал выключен до imports. Сравнить старые падения с
чистым baseline; тесты не ослаблять. После implementation — независимый Checker
и отдельный Cursor review до разрешённого commit/push.

Для **этого документального checkpoint** достаточно проверить ссылки,
соответствие текущему baseline/allowlist и `git diff --check`; pytest не нужен.
Ledger Draft до независимого Checker, затем Cursor review. После PASS документы
не дописывать; exact staging, commit/push только по отдельному разрешению.
