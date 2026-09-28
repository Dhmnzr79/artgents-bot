# D2 — текущее состояние и куда смотреть

Снимок на 2026-09-28 для `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`. Последний принятый Checker/Cursor и отправленный
checkpoint: **карточка D2-LEAD-INTERRUPT `43c0aba362403ac144e88809e4f8ff5a81e6bc2a`**;
предыдущий runtime checkpoint — D2-DOC-CLICK `e246f1e`.
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
| Вопрос при активной записи | Документальная карточка прошла Checker/Cursor и сохранена в `43c0aba`. Владелец утвердил ответ на сохранённый вопрос, кнопку «Продолжить запись» и отдельный GO на код. Реализация и offline-проверка ведутся от этого SHA; до Checker/Cursor нового checkpoint исправление не объявляется принятым | [Карточка lead-прерывания](DEMO_D2_LEAD_INTERRUPT_TASK.md) |
| REC-4-P2 | Кнопки «Что входит» и «Этапы оплаты» ещё не начаты; требуется отдельный GO и preflight от принятого SHA | [Карточка цен](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md) |
| REC-5 | Общая приёмка D2 впереди | [Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) |

Старый `C:\Cursor Projects\artgents-bot` и worktree 27e1 — сохранённая
история, не активная папка. Чужие локальные `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не входят в текущую задачу.
