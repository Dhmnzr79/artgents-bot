# D2 S2-C6 — независимый отказ ценовой части

Статус: готово к исполнению Terra после переключения владельцем модели.
Подготовка задания не начинает реализацию. Это продолжение S2, не S3.

## 1. Обязательный preflight

Прочитать `AGENTS.md`, `docs/WORKFLOW_CHECKER.md` и выполнить preflight до правок.
Рабочая папка и Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Implementation baseline: `391c5ad4fe8c8789c5dfbef4f7dff2dfa6b114b8`.
Локальный `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Это продолжение текущей ветки; новую ветку/worktree не создавать.
Несовпадение folder/branch/HEAD — остановка с сообщением о фактическом состоянии.

Foreign WIP, не редактировать и не stage:

- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.md`;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md`;
- `scripts/measure_d2_latency_baseline.py`.

Два собственных C6 untracked-документа: это задание и
`docs/tasks/DEMO_D2_S2_C6_ARCHITECTURE_GATE.md`. Gate читать без изменений,
но включить вместе с заданием в будущий проверенный C6 commit (stage-only exception).

## 2. Основание и цель

Прочитать C6 gate целиком; он задаёт архитектуру реализации. Дополнительно:
`DEMO_D2_TARGET_CONTRACT.md` §§5–7, `DEMO_D2_ACCEPTANCE.md` C02/C04/C09 и
ограничения существующего S3 gate. Принятые правила не пересогласовывать.
Текущее задание уточняет порядок работы и Git; семантику C6 gate не меняет.
Старые C4/C5 требования выбросить исключение при пустом ценовом наборе меняются
только в явно определённой C6 границе результата, а не в правилах выбора цены.

Пользовательский сценарий: «Цена виниров и больно ли лечиться?».
Если безопасно подготовить цену нельзя, сохранить отдельный утверждённый блок
об отказе цены и независимый проверенный content. Показать оба в исходном порядке.
Не превращать отсутствие ценовых данных в утверждение «услуга не оказывается».

## 3. Реализация

1. Единственный смысловой вход — уже разобранный D1R `RequestUnderstanding.requests`.
   До локального отказа проверить все part refs/tenant/snapshot, включая поздние
   content parts. Не добавлять semantic parser, regex/dictionaries или LLM retry.
2. Сохранить C4 strict applicability, ranking/cap, единицы и запрет арифметики.
   Только ожидаемые `d2_no_complete_price_candidates` и
   `d2_no_scope_price_candidates` могут дать unavailable price part. Другие
   исключения, ownership/schema/unknown refs и ошибки программы остаются fatal.
3. Развить C5 parts статусами answered/unavailable и typed reason. Заморозить
   отдельные tenant-owned failure blocks с request_id/message_id/reason/text.
   Коды и сообщения берутся из проверенной authority, без fallback-строки в коде.
   Missing authority — явная ошибка; наличие authority не меняет выбор цен.
4. Итог complete/degraded/failed вычисляет код по всем parts. Frozen validation
   отвергает противоречия status/block/aggregate и потерянные/дублированные части.
   Unavailable price не имеет price rows, selected/finalized offers или choices.
   `no_public_price` остаётся нормальным answered результатом.
5. Перенести typed failure blocks через существующие внутренние plan/ComposerResult
   структуры без фиктивного patient_text/visible_price_block. Второй смысловой
   envelope или Composer вызов запрещён.
6. Renderer выводит по одному связанному блоку на part в исходном порядке. Он
   не ловит ошибки и не читает данные клиники заново.
7. Наличие price request подавляет обычные source follow-up/video даже при отказе
   цены. `is_price_answer` по-прежнему означает фактически видимую цену. В degraded
   разрешена лишь существующая допустимая независимая CTA; при failed весь UI пуст.
8. C5 scope определяется всеми проверенными parts; отказ цены не назначает фокус
   выжившей услуге. Situation остаётся turn-local, delta keep. Сессии не писать.

Пока реализовать только существующие ANSWER price/content формы с максимум одной
price part. Не добавлять частичные отказы content, политики, акции, T3 свободную
прозу, новый RAG, provider, prompt, clinic adapter или runtime wiring.

## 4. Exact write allowlist

```text
contracts/response_plan.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
tests/test_d2_part_failure.py                         NEW
tests/test_d2_price_modes.py
tests/test_d2_single_request.py
tests/test_d2_price_scope_selection.py
tests/test_d2_independent_request_parts.py
docs/tasks/DEMO_D2_S2_C6_TERRA_TASK.md
```

Четыре существующих test files менять только для перехода указанных двух отказов
от exception assertions к проверкам unavailable/degraded/failed и отсутствия
небезопасных цен. Сохранить fatal проверки без authority. Успешные C1–C5 сценарии
и strict applicability не ослаблять. Gate имеет только stage-only разрешение.
Все прочие файлы read-only, включая D1R, UI projection, session, HTTP/SSE,
widget, lead/privacy, clinic data и legacy runtime.

## 5. Матрица проверки до Checker

Новый файл тестов покрывает все девять групп C6 gate. До передачи Checker выдать
короткую таблицу «группа → реальные pytest node IDs → что проверяется».
Количество passed само по себе не доказывает покрытие. Не объявлять сценарий
проверенным, если в fixture нет нужных данных (например, UI обоих источников).

- Неполные условия цены + здоровый content; прямой и обратный порядок.
- Strict known scope без подходящих offers + content другой услуги.
- Одиночный отказ: failed/пустой UI; no_public_price: answered/complete.
- Успешные одиночные/смешанные parts и content-only UI первого источника.
- Degraded price request: нет follow-up/video/choices, корректная CTA и пустые price IDs.
- Fatal чужие/неизвестные refs, mismatch, missing/foreign authority, неожиданная
  ошибка программы; особенно чужой content после недоступной цены.
- Невалидный frozen linkage/aggregate, mutation snapshots после freeze, C5 mixed focus.
- Sentinels на запрещённые semantic/Composer entry points и сетевой транспорт.

Positive inputs: raw JSON → настоящий D1R parser → resolver → frozen plan →
renderer/UI projection. Positive fixtures должны пройти model validation;
`model_copy(update=...)` без последующей validation для них запрещён.
При проверке ошибок программы допустима адресная инъекция exception; не подменять
resolver/renderer в успешных пользовательских сценариях.

Во время реализации запускать только затронутые nodes. Когда матрица полностью
готова, один обязательный C1–C6 regression:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_single_request.py tests/test_d2_content_source_ui.py tests/test_d2_price_modes.py tests/test_d2_multi_request.py tests/test_d2_treatment_situation.py tests/test_d2_price_scope_selection.py tests/test_d2_volume_choices.py tests/test_d2_independent_request_parts.py tests/test_d2_part_failure.py
```

Исходный C1–C5 результат на 391c5ad: 228 passed по предыдущему отчёту, не новый
запуск. Известны deprecation warnings и неблокирующий WinError 32 при ротации
занятого logs/app.jsonl. Логи не редактировать/очищать. Новый failure сравнить
с baseline без переключения грязного checkout и без нового worktree.

## 6. Checker, эскалация и завершение

Один независимый read-only Checker на завершённый C6 diff + полную матрицу.
После REJECT исправить конкретные причины, повторить targeted проверки и focused
recheck. Общий набор повторять только если последующие существенные изменения
требуют повторной regression проверки; не запускать после каждого нового теста.
Полный CI, HTTP/browser/live тесты не запускать.

После двух содержательных неудачных попыток одного участка передать Sol точные
вход/ожидание/diff/ошибку; не повторять незавершённую работу бесконечно. При
архитектурном конфликте, втором parser, broad catch, выходе за allowlist или
необходимости ослабить C4 — остановить этот участок и дать Astra два варианта.

После Checker PASS: stage точные изменённые пути allowlist плюс неизменённый C6
gate; проверить staged names/stat/full diff и `git diff --cached --check`.
Commit: `feat(d2): preserve independent answers on price failure`.
Push: `origin codex/demo-d2-service-volume`. Не создавать другой PR, merge/deploy,
worktree, reset/clean/stash, не удалять временные папки. Provider/SMTP calls = 0.

Финальный отчёт: сценарий и его границы, branch/commit/push, changed paths,
матрица и tests, Checker, warnings/failures, calls, staging и оставшийся foreign
WIP. C6 не подключён к работающему боту и не означает завершение S2. S3 не начинать.
