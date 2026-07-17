# TASK — Fix Situation Intake Target Contract

**Ветка:** `codex/stage-a`

**Baseline:** `4cae480 fix: harden lead cancellation and date handoff`

**Режим:** documentation-only product contract. Runtime не меняется.

## Цель

Зафиксировать согласованный будущий контракт кнопки «Рассказать о ситуации» без
латания legacy FullContext:

1. `situation_intake` — отдельный intake state до FullContext/retrieval/composer.
2. Введённый текст — user-authored lead note, а не вопрос к базе.
3. Любое осмысленное стоматологическое описание внутри intake — ситуация, страх, боль,
   цена, жалоба или прошлый опыт — сохраняется с заявкой → имя → телефон, без
   content-ответа и без повторной медицинской маршрутизации.
4. Phone-only hard-stop действует на обычном входе в диалог до intake. Явно выбранный
   `situation_intake` является конверсионным lead-capture шагом и не обрывается по теме
   введённого стоматологического текста.
5. Вне intake обычный страх будущего лечения остаётся маркетинговым вопросом.
6. Минимальный deterministic anti-spam: length, empty/short, link-only, obvious garbage,
   общий rate limit и один retry; без LLM spam analysis.
7. Выход до note — «Назад к диалогу»; после note — обычная текстовая отмена lead-flow.
   Заметную кнопку выхода на первом экране имени не добавлять без отдельного решения.

## Allowlist

- `TASK.md`;
- `docs/MARKETING_QUESTION_FOUNDATION.md`;
- `docs/MARKETING_QUESTION_TECH.md`;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md`;
- `.cursor/rules/00-guardrails.mdc`.

## Protected / вне scope

- весь code/runtime, tests, evals, prompts, configs и client data;
- реализация `situation_intake`;
- CTA-context/schema и delivery CRM/email/n8n;
- first-screen lead exit UI;
- A9 design/raw/harness/evidence;
- live/LLM, authority, merge и `main`.

## Verification

1. Все четыре канона одинаково различают обычный ingress hard-stop и явно выбранный
   conversion intake, принимающий любое стоматологическое описание.
2. Нигде нет заявления, что target уже реализован.
3. Изменения только внутри allowlist.
4. `git diff --check` и локальные Markdown links проходят.
5. Независимый checker `✅` до commit/push.

`pytest` не запускать: исполняемое поведение не меняется.

## Definition of Done

- правила сохранены в существующих канонах без нового постоянного документа;
- future schema governance получает однозначный `situation_intake` contract;
- code/runtime/A9 не затронуты;
- commit/push только в `origin/codex/stage-a`, дерево чистое.
