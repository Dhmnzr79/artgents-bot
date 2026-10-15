# D2 demo — текущее состояние

Срез 2026-10-15. Начинать новый чат с этого документа и
[текущей очереди](DEMO_D2_DELIVERY_ROADMAP.md), а не с исторических task cards.

## Что работает на VPS

- Demo доступен на [demo.bot.artgents.ru](https://demo.bot.artgents.ru).
- Развёрнутый commit: `e93cb121e8ea45c31dc45b435720a556fda8033d`.
  [PR #29](https://github.com/Dhmnzr79/artgents-bot/pull/29) merged;
  [CI](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38568028019),
  [Publish image](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38568028002)
  и [Deploy production](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38568539796)
  завершились успешно. Это подтверждение выкладки demo, не аттестация реальных
  production-пользовательских диалогов или НикаДент.
- После деплоя `/health/live` и `/health/ready` вернули 200/ok=true;
  публичные `widget.css`, `widget.js`, `cases.js` совпали с релизом.
  Живые запросы к модели агентом для этой проверки не выполнялись.
- Предыдущие [PR #27](https://github.com/Dhmnzr79/artgents-bot/pull/27) и
  [PR #28](https://github.com/Dhmnzr79/artgents-bot/pull/28) тоже merged и входят
  в этот релиз. Их нельзя читать как открытые draft-задачи.

## Нынешнее поведение и данные

- Согласованная конфигурация production: `DEFAULT_LLM_MODEL=deepseek-flash`,
  `CHAT_BASE_URL=https://api.deepseek.com`, ключ в `CHAT_API_KEY`.
  Чистый env имеет Qwen default; автоматического fallback после ошибки DeepSeek нет.
- Обычный ответ — свободный текст с optional `<D2_META>` для источников/действий.
  Цена — native `show_price`, кодовая карточка и второй ответ той же модели.
  Карточка зависит от вызова tool; полезная prose без него сохраняется.
- Full context получает MD выбранного клиента, завершённую историю, опубликованную
  карточку и канонические контакты из `clinic_policies.yaml -> contact`.
  Первый заявленный документ в `sources` задаёт follow-up после успешной проверки;
  неверный основной не заменяется следующим. Остальные — дополнительные факты.
  При клике сервер сохраняет выбранную задачу. Лимит продолжений — два слота.
- Situation intake выключен; tenant, lead/privacy, revision, commit/replay и
  транспортные защиты сохранены. Demo-заявка учебная. Лимиты demo — 30 вызовов
  модели на сессию и 400 в сутки; второй ценовой вызов тоже считается.
- Интерфейс: локальный Inter 400–600, letter-spacing 0. Названия услуг,
  числовые цены и заголовки карточек имеют вес 600 на десктопе и мобильных.
  Размеры отличаются по существующим desktop/touch CSS-правилам.
- Кейсы All-on-4 и циркониевых коронок открываются из меню, после услуги и по
  authored ссылке общего документа `clients/demo/md/clinic__info__results.md`.
  Фото лежат в `static/clients/demo/cases/`, каталог, связи с услугами и отдельные
  описания «До»/«После» — в `static/widget/cases.js`. Модель этот JS не читает.
- Галерея локальная: фото переключаются кнопками, кейсы — стрелками/свайпом
  с анимацией 220 мс и учётом reduced motion. Повторный запрос может снова открыть
  галерею, если модель выбрала документ результатов и сервер выдал его ссылку.
  Уже просмотренные кейсы не предлагаются повторно в обычных service follow-up.
- «Я хочу так же» под кейсами использует опубликованную серверную CTA, когда она
  есть. Иначе, включая стартовое меню, отправляет обычное «Хочу записаться на
  консультацию»: форма зависит от модельного `start_booking`, не открывается
  принудительно. Перезапуск активной/приостановленной заявки ограничен прежними guards.
- Редактура demo-контента и пользовательские UI-правки включены в релиз.
  Техническая оптимизация базы/full-context tokens не объявляется выполненной.

## Что проверено и какие есть ограничения

- Последний Linux publish gate: **878 passed**; Secret scan, PostgreSQL
  qualification, Docker build/smoke/publish и deploy зелёные.
- Независимый Checker и локальные браузерные проверки подтвердили изменения
  кейсов/CTA и typography на desktop, 390 px, 360 px и landscape touch.
  Это offline Chromium evidence, не физическая проверка всех Android/iOS.
- Локальный Windows union в предыдущем релизе: 836 passed, 37 failed, 5 skipped.
  Все 37 failing node IDs воспроизвелись на чистом baseline `3404c2f`:
  Bash startup и права доступа G7/G8. Linux publish выполнил эти проверки успешно;
  assertions/guards не отключались. Конкуренция с локальным ботом за rotating log
  устранялась отдельным `BOT_LOG_DIR` для тестов, без runtime-правки.
- PR/Publish используют `tests/release/offline.txt` и `tests/release/policy.txt`;
  results-document regression включён в shared gate. Gate всё ещё temporary demo:
  это не PASS всех historical tests и не закрытие всей SIM/REC acceptance.

## Передача следующему чату

- Owner завершил настройку demo и планирует далее подключать НикаДент, а не
  продолжать правки demo-контента. Работа с НикаДент ещё не начата/не аттестована.
  Папка `clients/nikadent` существует; её наличие не доказывает готовность клиента.
- Сначала read-only инвентаризация pack, контактов, прайса, политик, лид-доставки,
  widget integration и tenant boundaries. Затем отдельный согласованный scope.
  Demo на VPS не менять как побочный эффект подключения другого клиента.
- Рабочая папка: `C:\Cursor Projects\artgents-bot-active`.
  Закрывающая docs-only ветка — `codex/release-handoff-docs`, baseline `e93cb12`.
  Перед новой задачей проверить фактические Git branch/status и свежий `origin/main`;
  push документации не означает merge или изменение развёрнутого бота.
- Посторонний WIP: `otzyv-1.jpg`, `otzyv-2.jpg`, `otzyv-3.jpg` в корне.
  Они не подключены как отзывы и не опубликованы. Сохранить до отдельного решения.
  Прежние 14 MD были EOL-копиями и сохранены в ignored backup; не считать их
  нынешним незакоммиченным контентом. Игнорируемые эксперименты, logs, `.env` и БД
  не включать в релиз.

Исторические receipts: [Interface §§60–63](DEMO_D2_INTERFACE_TASK.md),
[состояние до закрытия](https://github.com/Dhmnzr79/artgents-bot/blob/e93cb121e8ea45c31dc45b435720a556fda8033d/docs/tasks/DEMO_D2_CURRENT_STATUS.md),
[архив](../archive/README.md). Они не задают новую очередь работ.
Роли и protections: [архитектура](../CURRENT_ARCHITECTURE.md),
[Target Contract §3](DEMO_D2_TARGET_CONTRACT.md), [AGENTS](../../AGENTS.md).
