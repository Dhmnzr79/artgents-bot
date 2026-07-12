# TASK — A4: client topic taxonomy + нативная ось контракта (без runtime wiring)

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Проектная опора — `docs/ARCH_TARGET_DESIGN.md` v4 и `docs/TURN_FRAME_SHADOW_AUDIT_A3.md`.

---

## Зафиксированная точка старта

- A0 frozen spec hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A1 TurnFrame contract: `0761213`.
- A2 shadow observability: `3746d77`.
- A3 audit: `0cb8ca3`.
- A3 вывод: `topic` missing в 4/5 planner-success frame; ни одна ось не готова к authority.
- Рабочее дерево перед A4 должно быть чистым.

## Задача

**Название:** A4 — получить client-configurable taxonomy из существующего MD frontmatter и добавить optional native `topic` в `TurnPlan`/shadow adapter.

**Размер:** МАЛЕНЬКАЯ. Loader + backward-compatible contract + pure adapter + unit-тесты. **LLM prompt и runtime wiring не менять.**

**Цель:** подготовить единственный нативный контракт topic без глобального dental enum и без второго конфигурационного справочника. Источник taxonomy — уже существующее поле `topic` в YAML frontmatter Markdown-документов конкретного client pack.

После A4 текущий planner продолжает возвращать старый JSON без `topic`; значения по умолчанию сохраняют прежнее поведение. Реальное включение `topic` в output текущего planner будет отдельной задачей после review A4, потому что изменение LLM prompt может косвенно менять существующие `route/aspects/service_id`.

## Архитектурное решение

```text
clients/{client}/md/*.md frontmatter.topic
                 │
                 └── client topic taxonomy (read-only, cached)

TurnPlan.topic? + TurnPlan.topic_confidence
                 │
                 └── pure adapter → TurnFrame.topic/field_meta (shadow only)
```

Не создавать `topics.json`, YAML-список, глобальный enum или hardcoded набор стоматологических тем в core.

## Topic taxonomy loader

Новый loader должен:

- читать `topic` из YAML frontmatter `.md` файлов только выбранного client pack;
- использовать `client_md_dir()` / существующее разрешение client pack;
- возвращать детерминированный неизменяемый набор нормализованных topic (`frozenset[str]`);
- нормализовать trim + lowercase;
- игнорировать пустое значение;
- не выводить topic из имени файла, `doc_id`, текста/aliases или service id;
- не читать тело документа для смыслового inference;
- не содержать известных названий тем в production-коде;
- быть cached по resolved client pack;
- не смешивать taxonomy разных клиентов;
- при malformed frontmatter не подменять данные догадкой; ошибка должна быть различима для вызывающего кода/теста, а не превращаться в выдуманный topic.

Допустимо использовать уже установленную библиотеку frontmatter/YAML и существующие path helpers. Не импортировать private helper из content linter только ради переиспользования.

## Расширение TurnPlan

Добавить только два backward-compatible поля:

- `topic: str | None = None`;
- `topic_confidence: float = 0.0`, диапазон `0..1`.

Правила модели:

- `topic` — обычная строка, не `Literal`/enum;
- значение нормализуется trim + lowercase; пустая строка становится `None`;
- если `topic is None`, `topic_confidence` обязан быть `0.0`;
- старый payload без обоих полей валиден и даёт `None/0.0`;
- неизвестные extra fields по-прежнему запрещены;
- модель сама не читает client config и не знает список допустимых тем.

В A4 не менять `_SYSTEM`, `plan_turn()`, `_validate_plan()` или JSON prompt. Валидация LLM topic против client taxonomy относится к следующей wiring-задаче.

## Pure adapter

Обновить существующий `build_turn_frame_from_legacy()` только по правилу приоритета:

1. Если `TurnPlan.topic` заполнен, `TurnFrame.topic` получает его, а metadata:
   - confidence = `TurnPlan.topic_confidence`;
   - provenance = `turn_plan.topic`.
2. Иначе сохраняется текущий fallback из `DecisionFrame.service_topic`.
3. Если оба источника отсутствуют/unknown, остаётся `None` с честной missing/legacy provenance.

Adapter не загружает taxonomy, не валидирует client и не принимает вопрос. На вход ему приходит уже валидированный контракт. Не менять другие оси.

## Затрагиваемые файлы (allowlist)

Исполнитель может менять **только**:

- `core/topic_taxonomy.py` — новый client frontmatter loader;
- `contracts/turn_plan.py` — только optional `topic/topic_confidence` и их локальные инварианты;
- `core/turn_frame_adapter.py` — только приоритет native topic → legacy fallback;
- `tests/test_topic_taxonomy.py` — loader/client isolation/no-hardcode tests;
- `tests/test_turn_frame_contract.py` — native topic/fallback/backward compatibility;
- `tests/test_turn_planner_llm.py` — только доказательство, что старый planner payload без topic остаётся валиден, если существующих тестов недостаточно.

`TASK.md`, архитектурные документы, client content/config, LLM prompt, orchestration, shadow recorder, telemetry, evals и продуктовые тесты Исполнитель не меняет.

## Явно НЕ делать

- Не менять `_SYSTEM`, user prompt, `plan_turn()` и JSON, запрашиваемый у LLM.
- Не добавлять новый LLM-вызов/topic classifier.
- Не подключать topic к `DecisionFrame`, routing, evidence, composer, AnswerPlan, UI или policy.
- Не менять `turn_plan_to_decision_frame()` — legacy runtime topic остаётся прежним.
- Не добавлять topic в request ctx отдельным плоским полем; A2 shadow snapshot достаточно.
- Не создавать новый topic config-файл.
- Не выводить taxonomy из префиксов filename/doc_id/service id.
- Не хардкодить `implantation`, `prosthetics`, `clinic` и другие темы в production loader/contract/adapter.
- Не чинить preservation cases `02/03/05`.
- Не менять frozen spec/harness и существующие expected.
- Не переносить emotion-WIP.
- Не добавлять skip/xfail/условный PASS.
- Не создавать commit/ветку/stash без явной команды владельца.

## Обязательные тесты

1. Loader возвращает темы, фактически существующие во frontmatter demo client pack.
2. Все возвращённые значения нормализованы, непустые и детерминированы.
3. Loader не включает `doc_id`, subtopic или filename prefix как отдельную догадку.
4. Cache привязан к resolved client pack.
5. Production loader не содержит hardcoded известных topic names.
6. Старый `TurnPlan` payload без новых полей остаётся валиден: `topic=None`, confidence `0.0`.
7. Topic trim/lowercase нормализуется.
8. Пустой topic становится `None`.
9. Confidence вне `0..1` отклоняется.
10. `topic=None` с confidence > 0 отклоняется.
11. Adapter предпочитает native `TurnPlan.topic` и переносит точный confidence/provenance.
12. При отсутствии native topic adapter сохраняет текущий `DecisionFrame.service_topic` fallback.
13. Native topic не меняет intent/aspects/service/follow-up и не мутирует inputs.
14. Нет импортов нового loader из orchestration/routing/evidence/composer.
15. Frozen A0 hash не изменён.

Тесты не должны записывать временные client-файлы в репозиторий или менять `clients/demo`. Для проверки malformed/isolation допустим `tmp_path` и monkeypatch path resolver внутри unit loader test.

## Стоп-условия

Исполнитель обязан остановиться и выдать `СТОП: требуется решение владельца/Архитектора`, если:

- требуется файл вне allowlist;
- без изменения LLM prompt невозможно выполнить именно A4 contract/loader scope;
- предлагается второй taxonomy config вместо frontmatter source;
- требуется hardcoded enum/list тем в production;
- любое downstream-поведение начинает читать native topic;
- старые planner payload/tests перестают работать;
- для loader требуется парсить вопрос или содержание body;
- существующие продуктовые тесты требуют изменения;
- frozen hash изменился;
- есть незакоммиченный diff, не относящийся к A4.

Формат остановки:

```text
СТОП: требуется решение владельца/Архитектора
Что обнаружено:
Какие есть варианты:
Риск каждого варианта:
Какие файлы потребуются:
```

## Команды проверки

```powershell
python -m pytest -q tests/test_topic_taxonomy.py tests/test_turn_frame_contract.py tests/test_turn_planner_llm.py
python -m pytest -q tests/test_turn_frame_shadow.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
git diff --check
git status --short
git hash-object evals/v5/demo/preservation.json
```

Live eval в A4 не требуется: LLM prompt и runtime wiring намеренно не меняются. Если live output изменился, это нарушение границ.

## Контрольная точка и критерии приёмки

1. Реализовать только allowlist.
2. Показать diff тестов первым.
3. Запустить все команды проверки.
4. СТОП → checker → Архитектор.

A4 принят, когда taxonomy берётся только из client frontmatter, новые поля полностью backward-compatible, adapter меняет только shadow topic, runtime не импортирует/не читает native topic, все тесты зелёные и frozen hash сохранён.

Следующая задача будет отдельно решать wiring native topic в существующий planner prompt + client validation. Автоматически её не начинать.
