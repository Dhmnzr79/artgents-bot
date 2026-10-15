# Действующие документы задачи

Не читать весь каталог или архив как очередь работ. Текущий вход —
[docs/README](../README.md), для владельца — [поведение бота](../BOT_BEHAVIOR.md).

- [Current Status](DEMO_D2_CURRENT_STATUS.md): локальные/deployed различия и реальные результаты.
- [Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md): закрытие demo; следующим отдельным этапом — НикаДент.
- [Interface Task](DEMO_D2_INTERFACE_TASK.md): текущая карточка §64; §§60–63 — исторические receipts.
- [Execution Lock](DEMO_D2_EXECUTION_LOCK.md), [AGENTS](../../AGENTS.md),
  [Checker](../WORKFLOW_CHECKER.md): процесс и protections.
- [Target Contract§3](DEMO_D2_TARGET_CONTRACT.md), [Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md),
  [Owner Decisions](DEMO_D2_OWNER_DECISIONS.md), [Acceptance](DEMO_D2_ACCEPTANCE.md):
  согласованные роли/границы; позднейшие ownerdecisions заменяют старые противоречия.
- [Checkpoint Ledger](DEMO_D2_CHECKPOINT_LEDGER.md): исторические доказательства, не свежий Git/status и не разрешение.
- [KB Editor Agent](DEMO_KB_EDITOR_AGENT.md) / [KB Cleanup](DEMO_KB_EDITOR_CLEANUP.md): отложенная техническая работа с demo KB, не автоматическая следующая задача.

На 2026-10-15 demo работает на VPS (`e93cb12`, PR #29 merged).
Перед работой с НикаДент — сначала read-only инвентаризация и отдельный scope;
не переносить demo-данные и не менять развёрнутый demo попутно.

50 старых карточек/дублирующих prompts — [task history](../archive/README.md).
Полные прежние Interface/Roadmap — там же, для provenance и sectionlinks.
Архивирование не доказывает выполненностьSIM/REC и не отменяет agreedguards.
Новые runtime работы или восстановление старых tests по архиву не начинать.
