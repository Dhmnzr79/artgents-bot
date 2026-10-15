# Текущая дорожная карта demo-бота

## Текущая очередь

Owner 2026-10-15: закрыть документы и проверки завершённого demo-этапа,
сохранить commit/push; далее отдельным этапом подключать НикаДент.
Текущая работа — **documentation only**, без runtime, client pack или VPS-правок.
Карточка закрытия — [Interface §64](DEMO_D2_INTERFACE_TASK.md#64-release-handoff--2026-10-15).
Фактический релиз, проверки и ограничения — [Current Status](DEMO_D2_CURRENT_STATUS.md).

## Завершённый demo-этап

- Очистка основных входов документации и миграция актуальных guards выполнены
  в своих зафиксированных границах; receipts §§60–63 сохранены в Interface Task.
- Demo-контент, основной источник follow-up, карточки цен, галерея результатов,
  CTA и текущая типографика входят в merged PR #27–29.
- На VPS — `e93cb12`, Inter 400–600; CI, 878 Linux publish tests, PostgreSQL,
  Secret scan, Docker smoke и deploy успешны. Публичные health/assets проверены.
- Старые JSON-envelope, doctor_catalog и model ordinary price_detail не возвращены.
  Полный historical suite и SIM/REC acceptance не объявляются закрытыми.

## Следующий отдельный этап: НикаДент

1. В новом чате проверить Git preflight и прочитать Current Status,
   [архитектуру](../CURRENT_ARCHITECTURE.md),
   [правила client pack](../CLIENT_PACK_AUTHORING.md) и Target Contract §3.
2. Сначала read-only определить состояние `clients/nikadent`: контент, прайс,
   канонические контакты, policy/text_ref, widget integration, заявки и доставка.
   Существующая папка не означает готовый или уже подключённый tenant.
3. Представить конкретные пробелы и минимальный план подключения. Этот список
   не разрешает новые поля/слои/сценарии, изменение demo или автоматический deploy.
4. После отдельного scope — реализовать и проверить tenant isolation, price/UI,
   lead/privacy и доставку заявок конкретного клиента. Demo-заглушка не является
   подтверждением реальной доставки. Вручную не копировать чужие контакты/кейсы.

## Отложенное, не автоматическая очередь

- Техническая чистка demo KB и сокращение full-context tokens.
- Оставшаяся классификация historical tests/docs: сохранить полезные invariants,
  убрать доказанные дубли/отменённые assertions, не удалять тест только из-за FAIL.
- Постоянный gate и сверка SIM/REC evidence. Temporary demo gate остаётся
  помеченным временным; security/PostgreSQL/Docker/deploy защиты сохраняются.
- Каталог врачей в UI, отзывы и обобщение gallery data на новых клиентов.
  Нынешняя галерея реализована только для demo, не является общим tenant-каталогом.

## Границы

Сохраняются DeepSeek prose/META, native show_price + second response, quota 30/400,
tenant/privacy/medical/price/UI/transport guards и Target Contract §3.
Новые архитектурные механизмы требуют отдельного согласования; совет Astra
не является owner GO. Historical документы и прежние STOP/GO не разрешают работу.

Preflight, точный allowlist, proportional checks, independent Checker и exact staging
обязательны. Полный CI set — перед merge; merge/deploy требуют явной authority.
Живые provider calls требуют разрешения и бюджета. Docs-only commit/push
не обновляет VPS. История — [архив Roadmap](../archive/checkpoints/DEMO_D2_DELIVERY_ROADMAP.md).
