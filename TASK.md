# TASK — A1: минимальный канонический TurnFrame (shadow-only)

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Проектная опора — `docs/ARCH_TARGET_DESIGN.md` v4.

---

## Решение владельца по A0

A0 завершён как **честная фиксация baseline и целевого продуктового контракта**, а не как требование сначала отремонтировать удаляемую legacy-маршрутизацию.

Зафиксировано:

- harness: commit `a0e6926`;
- frozen spec: `evals/v5/demo/preservation.json`, commit `e852f4b`;
- frozen hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`;
- текущий live baseline: `preservation = 3/6`, `smoke = 24/24`;
- зелёные сейчас: cases `01`, `04`, `06` — это нижняя граница, их нельзя регрессировать;
- красные сейчас: cases `02`, `03`, `05` — это известный долг, который должна закрыть новая архитектура, а не отдельный ремонт legacy перед удалением.

`preservation.json` остаётся read-only. Цель миграции — получить `6/6` новой архитектурой. Нельзя менять frozen-spec, чтобы сделать старый baseline зелёным.

## Задача

**Название:** A1 — минимальный канонический контракт `TurnFrame` и чистый legacy-adapter.

**Размер:** МАЛЕНЬКАЯ. Только контракт, чистое преобразование и unit-тесты. **Никакого runtime wiring и изменения ответов.**

**Цель:** создать первый кирпич нового backbone — один типизированный контракт хода, в который на следующем этапе можно будет переводить понимание запроса. В A1 он строится только явным вызовом чистого adapter в unit-тестах и пока не участвует в `/ask` или `/ask/stream`.

Это не новый router, classifier или LLM-вызов. Adapter только переносит уже имеющиеся значения из текущих `TurnPlan` / `DecisionFrame`; если значения нет, он честно оставляет `unknown`/`None` и фиксирует provenance. Запрещено угадывать недостающее regex-правилами.

## Минимальный контракт

Новый `TurnFrame` должен содержать:

- `intent` — текущее намерение/route intent;
- `topic` — строковый client-configurable topic или `None`; не создавать глобальный тематический enum;
- `aspects` — непустой список аспектов;
- `primary_aspect` — обязан входить в `aspects`;
- `emotion` — минимальная ось `none | fear | doubt`, без policy и без изменения тона;
- `specificity` — `unknown | general | specific`;
- `patient_scope` — строковое значение или `None`, без нового классификатора;
- `service_id` — строка или `None`;
- `follow_up` — явный bool;
- `followup_of` — строка или `None`;
- `needs_clarification` — bool;
- `field_meta` — confidence + provenance по смысловым полям.

Для `field_meta` достаточно маленького общего типа:

- `confidence`: число `0..1`;
- `provenance`: непустая строка;
- никаких отдельных классов metadata под каждое поле.

Модель должна запрещать неизвестные поля (`extra="forbid"`). Не добавлять `ResponseSpec`, evidence assembly, verifier или marketing в эту задачу.

## Правила adapter

Чистая функция adapter:

- не вызывает LLM, resolver, файловую базу, PriceBook или network;
- не читает/не пишет session/context globals;
- не меняет входные `TurnPlan` / `DecisionFrame`;
- переносит только явно доступные значения;
- `primary_aspect` берёт из явно переданного значения; если оно не передано — первый элемент уже существующего `aspects` без тематического угадывания;
- неизвестный `topic` остаётся `None`, а не выводится из текста вопроса, aspect или regex;
- отсутствие `emotion` даёт `none` с provenance `default`;
- `follow_up` определяется только наличием `followup_of`, без анализа текста;
- отсутствующие оси получают confidence `0.0` и честный provenance вроде `missing_legacy_axis`;
- не содержит специальных веток для приживаемости, All-on-4/All-on-6, цены, боли или других тем.

## Затрагиваемые файлы (allowlist)

Исполнитель может менять **только**:

- `contracts/turn_frame.py` — новый контракт;
- `core/turn_frame_adapter.py` — чистое преобразование legacy → `TurnFrame`;
- `tests/test_turn_frame_contract.py` — unit-контракт модели и adapter;
- `contracts/__init__.py` — только экспорт новых общих типов, если экспорт действительно нужен.

`TASK.md`, архитектурные документы, rules и checklist Исполнитель не меняет.

## Явно НЕ делать

- Не чинить cases `02`, `03`, `05` в текущем runtime.
- Не подключать `TurnFrame` к `/ask`, `/ask/stream`, planner, resolver, composer или orchestration.
- Не менять `TurnPlan`, `DecisionFrame` и их существующую семантику.
- Не добавлять новый LLM prompt/call, classifier, router, handler или тематическую таблицу.
- Не добавлять regex/keyword inference для заполнения `topic`, `emotion`, `patient_scope` или `specificity`.
- Не менять `evals/v5/demo/preservation.json`, harness и существующие suite/tests.
- Не переносить emotion-WIP из ветки `wip/emotion-pilot`.
- Не добавлять marketing, promo, medzone enforcement, evidence selection или UI-логику.
- Не создавать commit/ветку/stash без явной команды владельца.

## Обязательные unit-тесты

1. Валидный полный `TurnFrame` создаётся.
2. Неизвестное поле отклоняется.
3. Confidence вне диапазона `0..1` отклоняется.
4. Пустой provenance отклоняется.
5. Пустой `aspects` отклоняется.
6. `primary_aspect`, которого нет в `aspects`, отклоняется.
7. Adapter переносит явные `intent`, `aspects`, `service_id`, `followup_of`, `needs_clarification`.
8. Adapter не выдумывает `topic`, если legacy-вход его не содержит.
9. Adapter корректно выставляет `follow_up` только из `followup_of`.
10. Default emotion равен `none` и помечен provenance `default`.
11. В adapter нет тематических исключений; тесты не должны быть написаны только под шесть preservation-вопросов.
12. Входные legacy-модели после adapter не мутированы.

## Стоп-условия

Исполнитель обязан остановиться и выдать `СТОП: требуется решение владельца/Архитектора`, если:

- для реализации требуется файл вне allowlist;
- требуется изменить текущий runtime или существующие контракты;
- невозможно заполнить поле без нового угадывания/классификации;
- возникает желание добавить enum конкретных стоматологических тем;
- нужно выбрать новую продуктовую семантику, которой нет в этом TASK;
- существующие тесты требуют изменения;
- adapter начинает принимать текст вопроса ради тематического inference;
- есть незакоммиченный diff, не относящийся к A1.

Формат остановки:

```text
СТОП: требуется решение владельца/Архитектора
Что обнаружено:
Какие есть варианты:
Риск каждого варианта:
Какие файлы потребуются:
```

## Контрольная точка

Одна реализационная контрольная точка:

1. Реализовать только allowlist.
2. Показать diff тестов первым.
3. Запустить проверки ниже.
4. СТОП → checker → Архитектор.

Не подключать контракт к runtime автоматически после зелёного unit-прогона. Runtime shadow wiring будет отдельной задачей A2 с отдельным allowlist.

## Команды проверки

```powershell
python -m pytest -q tests/test_turn_frame_contract.py
python -m pytest -q tests/test_turn_planner_llm.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
git diff --check
git status --short
```

Live eval в A1 не нужен, потому что runtime намеренно не меняется. Если Cursor утверждает, что A1 изменила live-поведение, это ошибка границ задачи.

## Критерии приёмки

- [ ] Изменены только allowlist-файлы.
- [ ] `TurnFrame` содержит минимальные целевые оси и запрещает extra fields.
- [ ] `topic` остаётся строковым/client-configurable, без стоматологического enum в core.
- [ ] Инвариант `primary_aspect ∈ aspects` проверяется моделью.
- [ ] Есть единый маленький тип confidence/provenance, без размножения сущностей.
- [ ] Adapter является чистой функцией и не угадывает недостающие значения.
- [ ] Нет тематических веток и новых маршрутов.
- [ ] Existing planner tests не изменены и остаются зелёными.
- [ ] Frozen A0 spec/hash не изменены.
- [ ] Checker подтвердил отсутствие runtime wiring и подгонки тестов.

## Готово, когда

A1 готова после принятого checker-review. Следующий шаг — отдельный A2: подключить построение `TurnFrame` в shadow-observability без влияния на ответ. Автоматически к A2 не переходить.
