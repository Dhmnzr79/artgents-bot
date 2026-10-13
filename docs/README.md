# Документация — актуальный вход

Срез 2026-10-13: работающий D2 demo на VPS; чистка docs/tests идёт отдельной
веткой `codex/docs-tests-cleanup`. Исторические планы не разрешают возвращать
удалённые механизмы и не являются состоянием нынешнего бота.

## Читать сначала

1. [Текущее состояние](tasks/DEMO_D2_CURRENT_STATUS.md) — release, модель,
   выполненные fixes, реальные границы evidence и локальные отличия.
2. [Текущая очередь](tasks/DEMO_D2_DELIVERY_ROADMAP.md) — верхний раздел
   «Текущая очередь — owner GO 2026-10-13» заменяет нижние исторические next steps.
3. [Карточка чистки §60](tasks/DEMO_D2_INTERFACE_TASK.md#60-cleanup-checkpoint--2026-10-13)
   — allowlist, инвентаризация, что сохраняем/мигрируем/архивируем.
4. [Git и локальный запуск](WORKFLOW_GIT.md), [Checker](WORKFLOW_CHECKER.md).

## Принятые решения и ограничения

[Product Decisions](tasks/DEMO_D2_PRODUCT_DECISIONS.md) и
[Target Contract §3](tasks/DEMO_D2_TARGET_CONTRACT.md) сохраняют agreed responsibility
boundaries. Позднейшие явные owner decisions (обычная prose, native price tool,
дополнительный provider response, DeepSeek) заменяют противоречащие старые записи.
[Interface](tasks/DEMO_D2_INTERFACE_TASK.md) хранит receipts этих изменений;
не считать весь его исторический текст текущей инструкцией.

## Исторические материалы — пока перенос не завершён

`CURRENT_ARCHITECTURE.md` сам помечен как stale pre-S69 snapshot и **не описывает
нынешний runtime**. A1–A9/S*/prepared-hybrid/sales-one-plus plans, audit evidence,
старые experiment/card sections — история либо будущие предложения, не текущая
очередь. Они ещё не все перенесены физически в архив: это открытая работа §60.
Действующие инварианты и полезные tests нужно выделить перед переносом/удалением.

Отдельно сохраняются deployment/security/PG contracts, client authoring инструкции
и настоящие tenant/lead/privacy protections. Они не отменяются из-за возраста.
Новая короткая current architecture и сверенный permanent test index ещё в работе;
не выдавать этот исправленный вход за завершённую чистку всего корпуса.
