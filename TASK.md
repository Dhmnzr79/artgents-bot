# TASK — A5: planner заполняет native topic (shadow-only)

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — `docs/ARCH_TARGET_DESIGN.md` v4 и `docs/TURN_FRAME_SHADOW_AUDIT_A3.md`.

---

## Зафиксированная точка старта

- A0 frozen spec hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A1 TurnFrame: `0761213`.
- A2 shadow observability: `3746d77`.
- A3 audit: `0cb8ca3`.
- A4 client topic taxonomy + contract: `2757cae`.
- До A5 `TurnPlan.topic` optional, но текущий planner prompt его не запрашивает.
- Рабочее дерево перед A5 должно быть чистым.

## Задача

**Название:** A5 — текущий turn planner возвращает `topic/topic_confidence` из разрешённой taxonomy клиента; downstream остаётся legacy.

**Размер:** МАЛЕНЬКАЯ/СРЕДНЯЯ. Один существующий LLM prompt, field-level validation, unit-тесты и live proof. Новых LLM-вызовов нет.

**Цель:** заполнить native `TurnPlan.topic` на реальных planner-success ходах и увидеть его в A2 `TurnFrame` shadow. Поле не получает authority и не влияет на текущий `DecisionFrame`, routing, evidence, AnswerPlan, composer, UI или policy.

```text
client MD frontmatter topics
          ↓ allowed taxonomy in existing planner prompt
same planner call → TurnPlan.topic/topic_confidence
          ↓
TurnFrame shadow only

legacy DecisionFrame/routing/evidence ← без изменений
```

## Prompt contract

Изменить только существующий turn-planner prompt:

- добавить ровно два поля JSON: `topic`, `topic_confidence`;
- `topic` — одно значение из списка разрешённых topics текущего client pack или `null`;
- topic означает широкую предметную область вопроса, не aspect, subtopic, service id и не doc id;
- `topic_confidence` — число `0..1`; при `topic=null` обязано быть `0.0`;
- если вопрос неоднозначен — `topic=null`, confidence `0.0`; не угадывать;
- список разрешённых topics передаётся динамически из `load_client_topic_taxonomy(client_id)` в user content;
- не хардкодить темы в `_SYSTEM` или production-коде;
- не добавлять новый prompt/call/classifier.

Старые поля и инструкции `route/aspects/service_id/followup_of/needs_clarify/patient_situation/brand_filter` не переписывать и не ослаблять. Допускаются только минимальные изменения списка полей и инструкция про topic.

## Field-level validation

Native topic пока необязателен и shadow-only. Ошибка только в topic-полях **не должна делать весь TurnPlan fail-open**, если остальные старые поля валидны.

Перед/внутри `_validate_plan()`:

- использовать allowed taxonomy текущего client pack;
- valid topic нормализовать и сохранить;
- unknown topic → `topic=None`, `topic_confidence=0.0`;
- non-string topic → `None/0.0`;
- invalid/non-numeric/bool/out-of-range confidence → сохранить valid topic с confidence `0.0` либо обнулить оба поля; выбрать одно правило и зафиксировать тестом;
- confidence без topic → `0.0`;
- не мутировать исходный raw dict;
- записать структурированный telemetry event/log `turn_plan_topic_sanitized` со стабильным машинным reason;
- не писать raw topic value, вопрос, ответ или exception message в sanitization event;
- ошибки старых обязательных полей продолжают работать по прежним правилам и могут отклонить весь plan.

Допустимые стабильные reasons должны быть ограничены маленьким набором, например:

- `topic_not_allowed`;
- `topic_invalid_type`;
- `topic_confidence_invalid`;
- `topic_confidence_without_topic`.

Не добавлять общий `field_errors`-каркас в A5 — это будет отдельная задача. Здесь только локальная безопасная обработка двух новых shadow-полей.

## Runtime firewall

Обязательные инварианты:

- `turn_plan_to_decision_frame()` продолжает вычислять legacy `service_topic` только прежним способом из `service_id`;
- `DecisionFrame.service_topic/confidence.topic` не читают `TurnPlan.topic/topic_confidence`;
- `_resolve_service_id`, AnswerPlan, evidence, composer и routing не читают native topic;
- единственный downstream-потребитель native topic — существующий `core/turn_frame_adapter.py` → A2 shadow;
- return/output planner по старым полям остаётся прежним;
- `publish_turn_plan()` может хранить новые поля внутри уже существующего `turn_plan.model_dump()`, но не создавать новые управляющие ctx-флаги;
- структурированный `turn_planner_llm` log должен включить topic/confidence для аудита.

## Затрагиваемые файлы (allowlist)

Исполнитель может менять **только**:

- `core/turn_planner_llm.py` — taxonomy in prompt, topic validation/sanitization, audit log fields;
- `tests/test_turn_planner_llm.py` — prompt/validation/backward compatibility/firewall tests;
- `tests/test_turn_frame_shadow.py` — только доказательство, что valid native topic появляется в shadow с provenance `turn_plan.topic`;
- `eval_turn_topic_a5_preservation_last.txt` — raw live artifact, gitignored;
- `eval_turn_topic_a5_smoke_last.txt` — raw live artifact, gitignored.

`TASK.md`, architecture, contracts, taxonomy loader, adapter, orchestration, eval spec/harness, client content/config и продуктовые tests Исполнитель не меняет.

## Явно НЕ делать

- Не менять `contracts/turn_plan.py`, `core/topic_taxonomy.py`, `core/turn_frame_adapter.py` и A2 recorder.
- Не использовать native topic в `turn_plan_to_decision_frame()`.
- Не менять routing/evidence/composer/AnswerPlan/UI/policy.
- Не добавлять новый LLM call, feature flag, topic router или regex inference.
- Не создавать hardcoded mapping service→topic или список тем.
- Не выводить topic из filename/doc_id/service id после LLM; allowed list только валидирует output.
- Не чинить preservation `02/03/05` через downstream topic.
- Не менять frozen spec, harness или expected результаты.
- Не resnapshot'ить ответы.
- Не добавлять skip/xfail/условный PASS.
- Не выбирать лучший из нескольких live-прогонов и не скрывать предыдущие.
- Не создавать commit/ветку/stash без явной команды владельца.

## Обязательные unit-тесты

1. Existing planner user content содержит динамический список topics клиента.
2. `_SYSTEM` не содержит hardcoded topic names.
3. Mock LLM valid topic/confidence проходит в TurnPlan.
4. Topic другого client pack / unknown topic безопасно обнуляется без потери валидных legacy-полей.
5. Non-string topic безопасно обнуляется.
6. Invalid confidence обрабатывается выбранным field-level правилом без fail-open всего plan.
7. Confidence без topic становится `0.0`.
8. Sanitization не мутирует raw dict.
9. Sanitization event имеет только стабильный reason и не содержит raw/question/exception.
10. Старый LLM payload без новых полей остаётся валиден.
11. Unknown `service_id` и другие старые ошибки всё ещё отклоняют plan.
12. `turn_plan_to_decision_frame()` игнорирует native topic даже при высокой confidence.
13. Shadow snapshot использует native topic и provenance `turn_plan.topic`.
14. Native topic не меняет intent/aspects/service/follow-up.
15. Нет импортов/чтения native topic в routing/evidence/composer/AnswerPlan.
16. Frozen A0 hash неизменен.

## Live proof

После зелёных unit-тестов выполнить один полный прогон каждой suite и сохранить сырой вывод:

```powershell
$env:E2E_USE_TEST_CLIENT="1"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
python evals/v5/run_demo_eval.py --client demo --suite preservation 2>&1 | Tee-Object -FilePath eval_turn_topic_a5_preservation_last.txt
$preservationExit = $LASTEXITCODE
"EVAL_EXIT_CODE=$preservationExit" | Tee-Object -FilePath eval_turn_topic_a5_preservation_last.txt -Append

python evals/v5/run_demo_eval.py --client demo --suite smoke 2>&1 | Tee-Object -FilePath eval_turn_topic_a5_smoke_last.txt
$smokeExit = $LASTEXITCODE
"EVAL_EXIT_CODE=$smokeExit" | Tee-Object -FilePath eval_turn_topic_a5_smoke_last.txt -Append

Get-FileHash -Algorithm SHA256 eval_turn_topic_a5_preservation_last.txt
Get-FileHash -Algorithm SHA256 eval_turn_topic_a5_smoke_last.txt
```

Не перезапускать отдельные кейсы ради результата. Технический повтор полного run сохранять отдельным именем и сообщать все попытки.

Live acceptance:

- smoke: `24/24`, errors=0, skipped=0;
- preservation: existing green cases `01/04/06` остаются PASS; cases `02/03/05` могут оставаться target-red или улучшиться естественно, spec не менять;
- errors/timeouts/skipped отсутствуют;
- contacts остаётся boundary/not_applicable для TurnFrame;
- planner-success preservation cases `02–06`: shadow status `ok`;
- native topic для implant-вопросов `02–06` ожидается `implantation` с provenance `turn_plan.topic` и confidence из planner;
- `turn_complete` legacy `service_topic`, decision и product route не должны быть переписаны native topic;
- raw hashes и exit codes показать checker.

Если хотя бы один старый green case регрессировал либо smoke не `24/24` — ❌, не менять spec и не объявлять это вариативностью без эскалации.

## Команды unit/regression проверки

```powershell
python -m pytest -q tests/test_turn_planner_llm.py tests/test_turn_frame_shadow.py
python -m pytest -q tests/test_turn_frame_contract.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
git diff --check
git status --short
git hash-object evals/v5/demo/preservation.json
```

## Стоп-условия

СТОП и эскалация, если:

- требуется файл вне allowlist;
- native topic нужно читать downstream для получения желаемого ответа;
- изменение prompt регрессирует legacy route/aspects/service или старые green cases;
- invalid topic валит весь otherwise-valid plan;
- taxonomy пуста/не загружается;
- LLM систематически возвращает темы вне allowed list;
- live run имеет timeout/error/skipped;
- smoke не 24/24;
- frozen hash изменился;
- есть посторонний diff.

## Контрольная точка и приёмка

1. Реализация + unit/regression commands.
2. Один preservation + один smoke live run.
3. Показать diff тестов первым, changed-files, raw hashes и покейсный topic/provenance.
4. СТОП → checker → Архитектор.

A5 принят, когда topic честно заполняется из client taxonomy в shadow, битое optional поле не ломает legacy plan, downstream firewall доказан, smoke остаётся `24/24`, старые preservation green не регрессируют и frozen hash сохранён.

После A5 автоматически не давать topic authority и не чинить evidence. Следующий шаг определяется отдельным аудитом качества topic на более широкой тематической матрице.
