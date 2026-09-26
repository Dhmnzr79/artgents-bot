# D2-REC-2-CORR — optional topic и документный follow-up

Дата: 2026-09-26. Статус: реализация открыта, review не получен.
Владелец 2026-09-26 отнёс D2-097/098 к исправлению REC-2 и дал GO начать
работу. Это новый ограниченный checkpoint поверх сохранённого REC-2, а не
изменение его исторического Checker/Cursor PASS. D2-099 остаётся REC-4.

## Baseline и preflight

- Единственная рабочая папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`; HEAD и `origin/codex/d2-stage1-contract`:
  `7621441ca84e6bfc39fce79b744b647cc521a8b4` до изменений.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Tracked/staged diff до работы пуст; чужой untracked `data/` не трогать.
  Старые папки/worktree, SQLite, `.env`, журналы с переписками и tenant pack
  вне scope. Git не смог прочесть `.pytest_cache/` и global ignore, поэтому
  полнота untracked-обзора там не подтверждена.
- Baseline узких offline-тестов на HEAD: 2 passed, 18 deselected в
  `tests/test_d2_rec2_content_http.py`. Они доказывают прежнее поведение,
  включая уже отменённое ожидание отказа для unknown optional topic; CTA
  после follow-up они не проверяют.

## Обязательный результат

**ACCEPTANCE:** A03, B12, C01; регрессии C04/C05/C07/C09/C10 и затронутый
multipart без переноса scope между частями. Через реальные offline JSON/SSE
`/ask` и `/ask/stream` проверить одинаковый frozen ответ, source UI, CTA,
память, replay и отсутствие повторного provider/effect. Ни одного runtime PASS
до этих проверок не заявлять.

1. При обычном `ANSWER` с пригодной `model_prose` неизвестный модельный
   `topic_id` (в том числе `pain` при документе о боли) не превращает ход
   в `d2_invalid_turn`. Единый разрешитель по captured tenant snapshot
   отделяет optional topic от provenance и canonical focus **до** session
   binding и materialization. Неизвестное значение становится null и не
   попадает в scope, memory, UI или цену. Canonical topics берутся из
   структурного `topic` документов и утверждённых направлений, не из
   `subtopic`, filename, фраз вопроса или только прайса. Валидный конфликт
   source/scope не авторизует несовместимый UI. Unknown service, authored,
   price и иные обязательные typed границы не смягчать.
2. Показанный документный follow-up связывается сервером с целевым
   документом/разделом из того же tenant snapshot и проверенной frozen UI
   текущей revision. Модельный optional `content_ref` может отсутствовать
   или отличаться, но не переназначает эту связь. Содержательный ответ
   остаётся живой прозой модели; verified provenance, допустимые secondary
   и CTA выбираются из выбранного источника, source CTA выше общей.
   Проверенный чужой owner и forged/stale UI по-прежнему дают строгий отказ.
   Уточнение владельца 2026-09-26 после Cursor REJECT: при проверенном клике
   без нового текста вопроса
   с единственной обычной `model_prose` ошибочные, но существующие в tenant
   модельные `service_id`/`topic_id`, несовместимые с выбранным документом,
   становятся null **до** session binding. Живой текст и серверная связь
   документа/раздела сохраняются; ошибочные поля не попадают в память,
   цену или UI. Допустимая CTA выбранного документа сохраняется. Unknown
   service, обязательные price/lead поля и чужой owner остаются строгими.
   Для ручного ввода это уточнение не действует.
   Для двух независимых content-частей действует D2-072: не приписывать
   весь ответ одному документу и не показывать его secondary/CTA вместо
   общей допустимой CTA. Сохраняемый маркер первого источника отражает
   порядок частей, но не разрешает его UI. Новый refusal для multipart не
   добавлять.
3. Стартовая кнопка, отправляющая только текст без typed ref, остаётся
   обычным вводом. Никаких веток под «боль», семантических regex, второго
   parser/prompt/state, повторного provider-вызова или legacy fallback.

**D2 ROUTE:** существующие `/ask` и `/ask/stream` → один production parser →
однократное разрешение typed claims/выбранного действия → существующий
session binder/materializer/frozen plan → renderer/store/replay.
**LEGACY IMPACT:** старый normal runtime, Composer и semantic selectors не
подключать; внешние JSON/SSE и lead owner не менять.
**OWNER DECISION:** D2-097/098 и место коррекции в REC-2 утверждены владельцем;
после Cursor REJECT он явно согласовал узкое разрешение несовместимых optional
claims на проверенном документном клике и разрешил добавить Product Decisions
в allowlist. Техническая реализация в этих границах не требует повторного GO.
Если появится
новый strict gate, неоднозначное присвоение документа multipart или заметно
иная CTA-политика — остановиться и спросить владельца.
**FUTURE SCOPE:** D2-099, цены/кнопки REC-4, память REC-3, полная REC-5,
live/merge/deploy и старые read-only падения REC-2 не закрываются здесь.

## Точный write allowlist

```text
core/d2_snapshot_sources.py
core/d2_dialogue.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/one_call_prompt_contract.py
tests/test_d2_rec2_content_http.py
tests/test_d2_content_source_ui.py
tests/test_d2_r1_contract.py
docs/tasks/DEMO_D2_REC2_CORRECTION_TASK.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
```

Если необходим иной файл, объяснить до записи или staging. Tenant data, HTTP
adapter, session schema, UI wire, lead/privacy и старые checkout — read-only.

## Проверки и ворота

- Только fake provider, временные БД/логи/tenant fixtures вне checkout;
  сеть и live provider закрыты. Без запуска бота на 9001. Budget live = 0.
- Целевые собранные тесты: неизвестный topic с owned/missing ref и без ref,
  валидный topic, конфликтный source; empty/foreign/stale/forged, unknown
  service, обязательный price topic, authored; click с omitted/другим
  модельным ref → правильные source/UI/CTA и отсутствие auto-lead;
  чистый click с несовместимым известным topic/service → prose, выбранный
  источник/CTA, очищенные claims и прежняя память; совместимый scope
  сохраняется, unknown service остаётся strict, ручной ввод не получает
  click authority;
  multipart, JSON/SSE, state и replay. Не подгонять тесты под реализацию.
- Сравнить новые результаты с baseline и сохранить известные старые REC-2
  падения отдельно от регрессий. Запускать узкий offline набор, не полный CI.
- До commit: Ledger Draft со свидетельствами, независимый Checker PASS и
  отдельный Cursor review этого REC-2 correction diff; затем exact staging,
  staged names/stat/diff/check, commit и push той же ветки. После PASS
  Ledger не редактировать ради hash.
