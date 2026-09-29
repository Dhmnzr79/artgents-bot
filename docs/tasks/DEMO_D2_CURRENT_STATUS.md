# D2 — текущее состояние и куда смотреть

Снимок на 2026-09-29 для `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`. Последний принятый Checker/Cursor и отправленный
runtime checkpoint: **REC-4-P2
`f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`**; карточка — `abcb8ee`,
предыдущий runtime checkpoint — D2-LEAD-INTERRUPT `71d7467`.
GitHub branch проверена read-only `ls-remote` 2026-09-29 и совпадает с HEAD;
main и merge-base — `141ce91fb1731cd990fcf8391550150016c73e7f`.
Текущая документальная работа — [D2-AUDIT-PLAN](DEMO_D2_AUDIT_FOLLOWUP_TASK.md):
сверка после аудита и проект дальнейшего порядка, **без GO на runtime**.
Это локальный демо-бот; production-развёртывания и пользователей нет. Перед
работой сверяйте текущие Git HEAD, origin и status: этот файл — указатель на
момент записи, не замена preflight.

## Порядок работы с документами

1. [AGENTS.md](../../AGENTS.md) и [Execution Lock](DEMO_D2_EXECUTION_LOCK.md)
   задают процесс и запреты.
2. [Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) задаёт порядок этапов.
3. Карточка текущего checkpoint задаёт baseline, точный allowlist и приёмку.
4. [Target Contract](DEMO_D2_TARGET_CONTRACT.md),
   [Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md) и
   [Acceptance](DEMO_D2_ACCEPTANCE.md) задают согласованное поведение.
5. [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md) хранит доказательства по времени и SHA.
   Его прежние `Draft` и «текущий» описывают состояние **на дату строки**;
   их не следует принимать за текущий Git-status.

## Ближайшая последовательность

| Шаг | Состояние на этом снимке | Где детали |
|---|---|---|
| D2-DOC-CLICK | Checker и Cursor PASS, commit/push `e246f1e`; исправлены передача выбранного раздела модели и omitted mode ordinary prose. Качество реальной генерации отдельно не доказано | [Карточка](DEMO_D2_DOCUMENT_CLICK_TASK.md) |
| Вопрос при активной записи | Реализация прошла Checker/Cursor, сохранена и отправлена в `71d7467`; ответ, resume/cancel и replay проверены offline, живое качество генерации отдельно не доказано | [Карточка lead-прерывания](DEMO_D2_LEAD_INTERRUPT_TASK.md) |
| REC-4-P2 | Checker/Cursor PASS, commit/push `f4a08ea`. `classic`: обе detail-кнопки при полных данных всех показанных offers; клики читают captured набор, прямой вопрос доступен без кнопки. Это ограниченный A16/B19, не весь REC-5 | [Карточка цен](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md) |
| D2-AUDIT-PLAN | Разрешены сверка документов и проект плана. Карточка фиксирует находки и вопросы; изменения бота не начаты | [Текущая карточка](DEMO_D2_AUDIT_FOLLOWUP_TASK.md) |
| Исправления после аудита | Предложены малые checkpoint: задача volume-кнопки, контакты, полнота контекста, независимые части. Порядок и кодовые карточки ещё требуют принятия; цитаты владельца не равны GO | [Проект в Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) |
| REC-5 | Общая приёмка открыта. Существующие PASS её не закрывают; ни один новый live call не разрешён | [Acceptance](DEMO_D2_ACCEPTANCE.md) |

## Что важно не потерять при продолжении

- Cursor P2: 20 passed / 1 browser deselected; browser отдельно 1 passed;
  широкий адресный набор 118 passed / 1 deselected. Четыре назначенных файла:
  65 passed / 15 известных baseline failed. Это сведения из переданного
  отчёта review, не новый прогон. Старые падения не скрыты и не исправлены
  документальным checkpoint.
- В поздних widget-логах обнаружены потеря price task после «Один зуб» и
  телефон вместо адреса в mixed вопросе. Остальные риски и уровень evidence —
  AF-01–10 текущей карточки. Технический PASS не гарантирует качество понимания.
- `authored` removal, широкий redesign памяти/envelope, MD-only и два model
  calls — не принятый план реализации. Новые правила оформления, рекламы,
  повторных кнопок, missing-data copy и CTA администратора тоже только кандидаты.
- Прежние Draft в P2-карточке, Ledger и «впереди» в dated Product Decisions
  описывают их baseline. Read-only ревью P2, включая поздний browser PASS,
  не переписывает прошлые evidence строки задним числом.
- Foreign маркетинговая памятка расходится с D2-100/D2-102; до отдельной сверки
  не использовать её как спецификацию. Действуют Contract/Decisions/Acceptance.
- Старые runtime-файлы не удалялись. Наличие файла не доказывает его вызов;
  полная проверка недостижимости остаётся C08 в REC-5.

Для нового чата передать этот путь, фактический HEAD и текущую карточку,
затем повторить preflight. Лучше переходить после Checker/Cursor и отдельно
разрешённых commit/push документального checkpoint. Новый чат не означает
новую ветку или разрешение на реализацию.

Старый `C:\Cursor Projects\artgents-bot` и worktree 27e1 — сохранённая
история, не активная папка. Чужие локальные `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не входят в текущую задачу.
