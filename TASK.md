# TASK — Marketing-facing A-series strangler roadmap

Один активный `TASK.md` на один checkpoint. Создать понятный владельцу/маркетологу канонический roadmap архитектурной миграции A1–A9 с чекбоксами, фактическим статусом и объяснением влияния каждого этапа на ответы бота.

Checkpoint только документационный. Код, tests/evals/harness, prompt, runtime, raw и live/LLM не меняются и не запускаются.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `16ced47 docs: design A9 native patient scope extraction`;
- `origin/codex/stage-a` на том же commit;
- рабочее дерево до governance diff чистое;
- A9 product authority запрещена;
- первый A9 raw immutable, rerun запрещён без отдельного разрешения.

Проблема, которую исправляет checkpoint:

- `docs/ARCH_TARGET_DESIGN.md` остановился на строке «A5 следующий»;
- `docs/FULLCONTEXT_ROADMAP.md` — широкий продуктовый roadmap этапов 1–8, а не A-series strangler migration;
- единого актуального документа A1–A9 нет;
- фактический статус сейчас приходится восстанавливать из git history, TASK и audit-docs.

## 2. Deliverables и allowlist

После отдельного governance commit разрешено изменить только:

1. создать `docs/STRANGLER_ROADMAP.md`;
2. обновить `docs/README.md` — добавить новый документ в канон;
3. обновить только раздел `## Текущий strangler-checkpoint` в `docs/ARCH_TARGET_DESIGN.md` — убрать stale «A5 следующий», дать короткую актуальную сводку и ссылку на новый roadmap.

`TASK.md` после governance commit не менять.

Любой другой tracked/untracked file → `❌` и СТОП.

## 3. Для кого и каким языком

Главный читатель — владелец продукта/маркетолог, который отвечает за:

- логику ответов;
- продажи и конверсию;
- точность цен/фактов;
- понятность диалога;
- отсутствие медицинских выдумок;
- момент, когда новое понимание можно безопасно включать в product.

Roadmap должен объяснять технические термины простыми словами. Допустимо оставить имена `TurnFrame`, shadow и authority, но рядом дать короткое человеческое определение.

Не перегружать читателя file:line, внутренними class/function names или полными test matrices. Для доказательств дать компактные ссылки на source docs/commits.

## 4. Семантика чекбоксов

Roadmap обязан начать с legend:

- `[x]` — checkpoint реально выполнен, reviewed и committed;
- `[ ]` — checkpoint ещё не завершён;
- завершённый measurement/audit может быть `[x]`, даже если он честно показал красное качество;
- `[x]` не означает product authority или включение функции для пациента;
- product authority отмечается отдельно: `shadow-only`, `forbidden`, `allowed/active`;
- родитель A9 остаётся `[ ]`, пока его оставшиеся subcheckpoints не завершены или owner не закроет stage отдельным решением.

Нельзя ставить `[x]` по намерению, частичному diff или непроверенному live. Отдельно названный design-checkpoint получает `[x]` после review+commit, но не закрывает parent stage и не превращается в implementation/product checkbox.

## 5. Обязательная структура roadmap

### 5.1 Сначала — короткая панель статуса

В начале документа показать:

```text
Текущий этап: A9 Native Patient-scope Extraction
Последний завершённый checkpoint: A9 Native Extraction Design (16ced47)
Следующий checkpoint: A9 Native Container Metadata Contract
Product behavior: current legacy path unchanged
Patient-scope authority: forbidden
Live permission: required separately
```

Формулировки можно улучшить, смысл менять нельзя.

### 5.2 Два разных roadmap

Явно объяснить:

- `FULLCONTEXT_ROADMAP.md` — широкий продуктовый план развития бота;
- `STRANGLER_ROADMAP.md` — пошаговая замена внутреннего «мозга» A1–A9;
- A-series формируется evidence-driven после audit, но каждый checkpoint фиксируется TASK и checker-review **до** реализации;
- A1–A9 не были одним заранее frozen master-plan с первого дня;
- будущий A10 не придумывать до отдельного архитектурного решения.

### 5.3 A1–A9

Для каждого A-пункта обязательны:

1. checkbox и статус;
2. «Что сделали» — 1–3 простых предложения;
3. «Как это сказалось на работе бота»;
4. «Что видит пациент»;
5. authority/product status;
6. evidence link/commit.

Не писать, что shadow-only изменение улучшило реальный ответ, если product продолжал читать legacy path.

## 6. Frozen статус A1–A9

Roadmap обязан использовать эту фактическую карту.

### `[x] A1 — минимальный TurnFrame`

- Governance `631abc1`, implementation baseline `0761213`.
- Создан будущий единый semantic frame и legacy adapter.
- Не подключён к product decisions.
- Маркетинговый эффект: прямого изменения ответов нет; появился фундамент, чтобы позднее убрать разрозненные классификаторы.

### `[x] A2 — TurnFrame shadow observability`

- Governance `5e8b63c`, runtime shadow `3746d77`.
- Frame начал строиться параллельно и логироваться.
- Product продолжил отвечать по legacy.
- Эффект: можно измерять новое понимание без риска для пациентов.

### `[x] A3 — первый shadow audit`

- Governance `0486e87`, audit commit `0cb8ca3` / `docs/TURN_FRAME_SHADOW_AUDIT_A3.md`.
- Audit: planner-success coverage `5/5`, topic missing `4/5`; authority не готова.
- Эффект: не улучшение ответов, а честное обнаружение пробела topic.

### `[x] A4 — client-configurable topic taxonomy`

- Governance `de66ebc`, implementation `2757cae`.
- Allowed topics перенесены в client content/frontmatter; optional native topic contract подготовлен.
- Runtime product ownership не переключён.
- Эффект: темы можно определять из конфигурации клиента, не зашивая их в код, но пациент ещё не видит новый путь.

### `[x] A5 — native topic в shadow`

- Governance `cfc438b`, implementation `8662300`.
- Existing planner начал возвращать/валидировать native topic; downstream остался legacy.
- Эффект: бот научился параллельно формировать более чистую тему для измерения; ответы пациенту не переключены.

### `[x] A6 — frozen topic quality measurement`

- Matrix/harness/live/audit завершены через `3f205f4` … `4a6c867`.
- Первый sample технически неполный: `26/33` scoreable, семь потеряны из-за unrelated strict `aspects=[]`.
- Checkpoint выполнен, quality green не объявлен.
- Эффект: выяснили, почему topic-наблюдение — даже отдельно валидное поле — могло пропасть целиком из-за unrelated `aspects=[]`; качество topic в семи unavailable cases A6 не измерено, product не переключали.

### `[x] A7 — field-level planner outcome и topic re-audit`

- Design `7f9cfe4`, contract/split/wiring/regression/re-audit завершены; final audit `596e809`.
- Один raw JSON разделён на partial shadow frame и strict legacy product branch.
- Re-audit: topic scoreability `33/33` на frozen sample; это measurement result, не authority.
- Эффект: ошибка одного поля больше не скрывает остальные понятные части; реальные ответы сохраняют прежний безопасный fallback.

### `[x] A8 — service/follow-up/clarification shadow validation`

- Governance `3a3b445`, implementation `38d29f3`.
- Добавлена независимая shadow-валидация `service_id`, follow-up и clarification.
- Prompt/product routing не менялись.
- Эффект: диагностика стала точнее; пациентские ответы/цены/UI не изменились.

### `[ ] A9 — composable patient scope`

Родитель остаётся открытым. Обязательные subcheckboxes:

- `[x]` original patient-scope design (`9ee8c34`);
- `[x]` nested contract (`2a34b6c`);
- `[x]` scalar bridge (`0cc9042`);
- `[x]` shadow wiring/firewall proof (`33966e4`);
- `[x]` frozen matrix (`15d2ae7`);
- `[x]` harness (`3f11857`);
- `[x]` one-run audit (`10b4739`);
- `[x]` native extraction design (`16ced47`);
- `[ ]` native container metadata contract;
- `[ ]` native raw contract/prompt spec;
- `[ ]` native extraction implementation;
- `[ ]` native wiring/firewall proof;
- `[ ]` manual-contact `not_applicable` taxonomy;
- `[ ]` frozen matrix/harness v2 review;
- `[ ]` one-run live re-audit — только после отдельного owner permission;
- `[ ]` authority decision;
- `[ ]` legacy retirement — только после принятой authority architecture.

Обязательная честная сводка A9:

- infrastructure integrity accepted;
- first live-positive exact = `0` по extent/jaw/stage/modifiers;
- composite exact `0/9`;
- product firewall preserved;
- patient-scope authority forbidden;
- реальные ответы не оценивались этим scope harness и продолжали использовать legacy path.

Маркетинговое объяснение: цель A9 — понимать независимо «один/несколько/вся челюсть», верх/низ, этап лечения и явно сообщённую нехватку кости, не превращая это в диагноз или автоматический выбор лечения. Пока это не включено в реальные ответы.

## 7. Следующий checkpoint

Roadmap обязан выделить отдельный блок:

```text
Следующий: A9 Native Container Metadata Contract
```

Простое объяснение:

- бот должен различать «поле отсутствует», «значение неизвестно», «модель вернула неверный формат»;
- ошибка формата patient scope не должна ломать другие понятные поля и product answer;
- это contract/unit-test checkpoint, без prompt/runtime/live и без изменения ответов пациенту.

Не разрешать implementation этим roadmap.

## 8. Правило поддержки чекбоксов

Roadmap должен содержать maintenance policy:

1. Новый checkbox добавляется в governance TASK до работы.
2. `[x]` ставится только в completion commit checkpoint после checker `✅`.
3. Если checkpoint завершил измерение с красным результатом, checkbox ставится, а quality/result пишется рядом честно.
4. Design checkbox не закрывает implementation checkbox.
5. Live checkbox не закрывается без immutable raw, audit и owner permission.
6. Authority checkbox обновляется только отдельным product decision.
7. `ARCH_TARGET_DESIGN.md` не дублирует подробный список, а ссылается на этот roadmap, чтобы снова не устареть.

## 9. README и ARCH sync

### `docs/README.md`

В таблицу «Канон runtime» добавить:

```text
STRANGLER_ROADMAP.md | канонический статус архитектурной миграции A1–A9, чекбоксы и влияние на продукт
```

Не удалять `FULLCONTEXT_ROADMAP.md`; объяснить различие назначением строк.

### `docs/ARCH_TARGET_DESIGN.md`

Заменить только stale section `## Текущий strangler-checkpoint` на краткую сводку:

- canonical live status → `docs/STRANGLER_ROADMAP.md`;
- A1–A8 completed as migration checkpoints;
- A9 active, latest completed `16ced47`;
- native positive quality not ready;
- product firewall preserved, authority forbidden;
- следующий checkpoint — native container metadata contract.

Не переписывать target architecture или «Кучу A/B» в этом checkpoint.

## 10. Protected scope

Запрещено менять:

- code/contracts/tests/evals/clients/config;
- `docs/FULLCONTEXT_ROADMAP.md`;
- A1–A9 design/audit documents;
- raw artifacts;
- hashes/metrics/commits под красивую историю;
- product authority statements.

Нельзя заявлять:

- что A1–A8 уже изменили ответы пациента, если checkpoint был shadow-only;
- что A6 `26/33` или A7 `33/33` означают product accuracy;
- что A9 ready;
- что модель «не поняла» patient scope;
- что A9 harness проверил тексты ответов/цены/UI;
- что A10 уже определён.

## 11. Проверки

Pytest/live/LLM не запускать: diff docs-only.

```powershell
git status --short
git diff --check
git diff --name-only
git diff -- contracts core orchestration tests evals clients
rg -n "A5 следующий" docs/ARCH_TARGET_DESIGN.md
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
```

После authoring `rg "^(### |- )\[[ x]\]" docs/STRANGLER_ROADMAP.md` должен показывать все A1–A9 и A9 subcheckpoints.

## 12. Checkpoints

### Checkpoint 1 — governance review

Checker проверяет TASK до docs authoring. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — roadmap authoring

Изменить только три allowlist docs, выполнить read-only проверки, без commit.

### Checkpoint 3 — independent review

Checker сверяет каждый checkbox/claim с git/docs, понятность для маркетолога, отсутствие ложного product impact и stale A5.

### Checkpoint 4 — docs commit

Только после `✅`: commit/push трёх docs в `codex/stage-a`.

## 13. Definition of Done

1. Создан один канонический A-series roadmap.
2. A1–A9 и A9 subcheckpoints имеют честные checkboxes.
3. Под каждым A-пунктом есть понятное влияние на работу бота и видимое пациенту поведение.
4. Shadow completion не выдан за product activation.
5. A9 red quality/product firewall/authority отражены точно.
6. Следующий checkpoint назван без запуска implementation.
7. README ведёт на roadmap.
8. ARCH больше не говорит «A5 следующий» и ссылается на канон.
9. Protected files/raw/hashes unchanged; pytest/live/LLM не запускались.
10. Independent checker дал `✅` до docs commit.

После docs commit — СТОП. A9 contract/code/live не начинать без нового TASK и checker review.
