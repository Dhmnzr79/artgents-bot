# Текущая дорожная карта demo-бота

## Текущая очередь — ограничения реальных клиентов, owner GO 2026-10-16

Interface§82: лимиты частоты/посетителя/модели/ввода и3заявки/час, tenant
настройки, durable counters и сохранение контактов/записи после AI-квоты.
Это protection feature; semantic/price/lead/privacy owners сохраняются.
Ветка onboarding, база7c7ca52; публикация остаётся на паузе. Model/SMTP0.

## Текущая очередь — первая чистка клиентской базы, owner GO 2026-10-15

Interface §71: четыре аннотированных пункта аудита — старые MD-поля/alias comments,
точные повторы названия в алиасах, CTA-словарь НикаДент, готовность шаблона.
Существующая onboarding ветка/PR31, база8364092. Сохранить прозу/якоря/активные
метаданные, цену/контакты/lead/privacy owners и тексты прежних CTA-вариантов.
Остальные найденные файлы не удалять. Проверить validators + D2/consent offline
и независимый Checker. Provider/SMTP0; merge/deploy не входят.

## Текущая очередь — чистка старых стилей, owner GO 2026-10-15

Interface §69: после аудита удалить подтверждённые старые стили и неиспользуемые
поля цветов общего виджета demo/НикаДент. База5a9f0ba, та же onboarding ветка/PR31.
Сохранить активные динамические video-aspect классы и текущую палитру/внешний вид;
проверить актуальные UI paths offline и independent Checker. Локальное фото и
foreign3otzyv не входят в коммит. Model/SMTP0, без merge/deploy.

## Текущая очередь — launcher concept1, owner GO 2026-10-15

Interface §68: первый вариант из widget-concepts.html владельца, белая капсула,
аватар/зелёная точка, синяя стрелка, anchored expansion10s. Продолжение локального
НикаДент, baseline50d61af, та же ветка/PR31. Заменить прежнюю отдельную подсказку
одной поверхностью, повтор анимации из тестовой панели, mobile/reduced-motion,
offline DOM checks и Checker. Это presentation feature; demo и D2 paths прежние.
Model/SMTP calls0, merge/deploy не входят.

## Текущая очередь — согласие перед заявкой, owner GO 2026-10-15

Interface §67, продолжение локального подключения НикаДент, baseline2beb02b,
та же ветка/PR31. Пустой чекбокс до имени/телефона, две ссылки владельца,
компактный inline-блок в диалоге. Демо сохраняет stub без согласия. Сервер
проверяет явное подтверждение, сохраняет дату/версию без контактов; при отказе
можно выйти из записи и задавать вопросы. Закрыть обход через прямой /lead.
Новые model/SMTP calls0, merge/deploy не входят. Tests + Checker + инструкция.
Это lead/privacy bug fix/feature, не architecture simplification.

## Текущая очередь — меню по страницам, owner GO 2026-10-15

Продолжение локального подключения НикаДент: Interface §66, baseline8161637
в прежней ветке/PR #31. Владелец разрешил приветствие + три вопроса для выбранных
страниц и общее меню для остальных; акция одна на весь сайт. Настройка только
в widget_config.json клиента, выбор по pathname без передачи URL модели.
Добавить локальный выбор страницы, targeted offline/browser checks, Checker,
инструкцию редактирования. Это presentation feature/integration, не semantic
architecture simplification. Tenant/price/lead/privacy ownership сохраняются.
Model/SMTP calls0; merge/deploy/установка на сайт не входят в этот этап.

## Текущая очередь — НикаДент, owner GO 2026-10-15

Последнее уточнение владельца в этом же чате: **пока тестируем только локально**.
Merge PR #31 / VPS deploy не выполнялись; не продолжать выкладку без нового GO.
Локально проверены собственные контакты/врачи, настоящая доставка заявки
(получение подтверждено владельцем), demo_stub и отсутствие resend при replay.
После локальной проверки owner позже предоставит обновлённый контент.

Техническое подключение после read-only аудита: работоспособность на текущих
данных, настоящая SMTP-доставка заявок, локальное переключение demo/nikadent,
изначально также сборка/выкладка и embed-код для nikadent41.ru (теперь отложены).
Клиент вставляет код самостоятельно;
админку сайта агент не открывает. Контент, суммы прайса и реальный аватар отложены.
Это **bug fix / integration**, не архитектурное упрощение. Карточка: Interface §65.
Текущие роли Target Contract §3, tenant/lead/privacy/price/UI/replay сохраняются.
Demo остаётся demo_stub. Очереди, автоматического resend/fallback, новых model
calls и semantic решений не добавляем. Live cap: 20 model calls, 1 test email.
Handoff-документация прочитана из fc84066 (PR #30 открыт); task branch создана
от свежего origin/main e93cb12, без merge отдельного docs PR.
Следующие старые очереди — контекст истории, не дополнительные задачи этапа.

## Текущая очередь — owner GO 2026-10-13: документация и тесты

Этот раздел — единственная очередь нынешней чистки. Прежние аудиты, предложения
и STOP/GO не дают разрешения на реализацию и не возвращают удалённые механизмы.
Полная прежняя дорожная карта сохранена в
[архиве](../archive/checkpoints/DEMO_D2_DELIVERY_ROADMAP.md).
Состояние — [Current Status](DEMO_D2_CURRENT_STATUS.md),
ближайший checkpoint — [Interface §63](DEMO_D2_INTERFACE_TASK.md#63-primary-document-owns-follow-up--owner-go-2026-10-14).
Owner GO 2026-10-14: основной документ задаёт follow-up; дополнительные источники
не подмешивают и не обнуляют ссылки. Это узкий bug fix поверх текущего UI WIP.

## Уже выполнено

- Контактный regression и мигрированные situation/quota/policy/text проверки
  включены в release gate; privacy/tenant/lead/replay guards сохранены.
- Удалены18 доказанных obsolete cases (15в§60.4 и3в§60.10). Shared selections для PR/Publish
  сохраняют все49 прежних файлов; добавлен selection contract.
- Последний точный publish offline selection:821PASS5platformSKIP,50файлов.
  GitHubCIf8c1700: все5jobs SUCCESS. Security/PostgreSQL/Docker защиты не ослаблены.
- Созданы owner behavior/current status/architecture/test index.
  19 прежних rootпланов и50 historical cards архивированы вместе с полными
  Interface/Roadmap. Четыре старых reference-bound источника помечены историческими;
  прежнийJulyTECH_DEBT сохранён отдельно, current debt pointer обновлён.
  Это не завершение всех historical docs/tests или whole-bot acceptance.

## Что делать дальше

1. OwnerGO§62: instruction for relevant document sections (#korotko for general
   questions, matched sections for direct questions/followups), essential conditions
   preserved. Existing prompt only, no follow-up mechanism changes; tests/Checker.
2. Продолжить классификацию оставшихся docs/evidence/probe bindings. Действующие
   tenant/privacy/medical/price/UI/transport/deploy protections сохранять.
   Исторические планы и эксперименты убрать из текущего чтения.
3. Закончить useful test inventory: сохранить ещё не покрытые invariants,
   мигрировать полезные guards, удалить доказанные дубли и cancelled-contract-only
   assertions. Не оживлять suites ради старого имени и не удалять из-за FAIL.
   Failure сравнивать с чистым baseline. Не восстанавливать JSON-envelope,
   doctor_catalog, model ordinary price_detail или старую semantic route.
4. Сверить SIM/REC evidence: выполнено/заменено/отменено/отложено только по
   доказательствам. Архивирование не закрывает незавершённую приёмку; offline
   fixtures не сертифицируют livemodelquality. Temporary gate coverage review открыт.
5. После coherent checkpoints — отдельная demo KB cleanup/экономия fullcontext.
   Далее совместная выкладка по отдельному разрешению. Текущий VPS не менять
   в docs/tests чистке; push draftPR сам по себе его не обновляет.

## Границы

Текущая задача сохраняет runtime mechanics, client KB, модель,30/400 лимиты
и владения. OwnerGO§61 разрешает только tuning существующего prompt. Strict/classifier/Qwen fallback не возвращать. Live/provider calls,
merge/deploy и разрушительная чистка требуют явной authority и нужного бюджета.
Текущий agreed model path:DeepSeek prose/META + nativeprice + secondresponse.
Основная ответственность — TargetContract§3 и позднейшие явные решения владельца.
Архитектурный вопрос обсуждать с Astra; её совет не меняет продуктовые правила.

На каждом coherent checkpoint: заранее preflight/allowlist, сохранить foreignWIP,
proportionalofflinechecks/independentChecker, exactstage/diffcheck/commit/pushreport.
Cursor и widget проверки нужны на согласованных рубежах; docs-only перенос не
требует новой liveприёмки. Полный актуальный CIset — перед merge.

Optional карточки врачей/до-после — будущая идея; текущая чистка их не реализует.
