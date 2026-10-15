# Документация нынешнего бота

Для владельца достаточно первых двух документов. Остальное — рабочая справка
для разработчиков, Codex и Cursor. Старые планы не задают нынешнюю архитектуру.

Сверка 2026-10-15: demo развёрнут на VPS (`e93cb12`), PR #27–29 merged.
Следующий отдельный этап — НикаДент, сначала read-only аудит его pack.
Начало нового чата: AGENTS → Current Status → текущая очередь → архитектура
и CLIENT_PACK_AUTHORING. Не продолжать старую очистку или demo-контент автоматически.

## Основное

1. [Как ведёт себя бот](BOT_BEHAVIOR.md) — обычный разговор, цены, контакты и запись.
2. [Состояние и остатки](tasks/DEMO_D2_CURRENT_STATUS.md) — что на VPS, что в PR,
   проверенные результаты и ещё открытые задачи.
3. [Запуск и выкладка](WORKFLOW_GIT.md) — локальный виджет, Git и рабочая папка.

## Для разработчиков и агентов

- [AGENTS](../AGENTS.md) и [Checker](WORKFLOW_CHECKER.md) — процесс исполнения.
- [Архитектура](CURRENT_ARCHITECTURE.md), [конфигурация](FLAGS_AND_STATUS.md),
  [маршрутизация](ROUTING_MAP.md), [release-тесты](TEST_SUITE_ARCHITECTURE.md).
- [Текущая очередь](tasks/DEMO_D2_DELIVERY_ROADMAP.md) — только верхняя текущая очередь;
  [карточка закрытия §64](tasks/DEMO_D2_INTERFACE_TASK.md#64-release-handoff--2026-10-15);
  [назначение текущих task документов](tasks/README.md).
- [Execution Lock](tasks/DEMO_D2_EXECUTION_LOCK.md),
  [Target Contract §3](tasks/DEMO_D2_TARGET_CONTRACT.md),
  [Product Decisions](tasks/DEMO_D2_PRODUCT_DECISIONS.md) — сохраняемые protections
  и ответственность. Позднейшие явные решения владельца заменяют противоречащие
  старые записи; весь исторический текст не является действующей инструкцией.
- [Client pack authoring](CLIENT_PACK_AUTHORING.md) — данные клиента.
  НикаДент не аттестован; техническая чистка demo KB и экономия tokens отложены.

## История — не использовать для новых задач

[АРХИВ](archive/README.md): прежние architecture/config/status,19 old plans/audits,
one-call/patient-scope/hybrid и инциденты. Материалы сохранены для provenance,
не для восстановления отменённых контрактов или запуска старых тестов в release.
[Historical references](HISTORICAL_READERS.md) показывают оставшиеся связи
старых test/eval fixtures с документами. Эти материалы не включаются в release
по умолчанию. Некоторые historical probe readers ещё держат старые пути; такие документы
помечаются историческими. Остальные планы/аудиты и SIM/REC evidence ещё
классифицируются: не считать весь корпус уже очищенным.

Secret scan, deployment/security/PostgreSQL contracts и tenant/lead/privacy
защиты действуют. Архивирование не отменяет их. Этап архивирования не переносил
клиентскую базу; последующая редактура demo-контента уже входит в релиз.

Старые50 task cards/prompts и полные прежние Interface/Roadmap теперь в архиве.
На прежних current-путях оставлены текущая очередь и карточка закрытия этапа.

Июльский backlog TECH_DEBT архивирован; [нынешние остатки](TECH_DEBT.md) — указатель на текущую очередь.
