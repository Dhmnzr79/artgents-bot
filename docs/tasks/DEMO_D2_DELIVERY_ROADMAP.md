# Текущая дорожная карта demo-бота

## Текущая очередь — НикаДент, owner GO 2026-10-15

Техническое подключение после read-only аудита: работоспособность на текущих
данных, настоящая SMTP-доставка заявок, локальное переключение demo/nikadent,
сборка/выкладка и embed-код для nikadent41.ru. Клиент вставляет код самостоятельно;
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
