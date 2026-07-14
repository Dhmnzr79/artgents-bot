# TASK — A9 Native Shadow Wiring / Firewall Proof

Один активный `TASK.md` на один checkpoint. Доказать на реальных локальных runtime-швах, что уже реализованный native `patient_scope` проходит из единого planner payload в существующий shadow/telemetry channel, но не становится входом product path.

Checkpoint test/runtime-proof-only, shadow-only. Production code, live/LLM, product authority и downstream wiring запрещены.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `302a05e feat: implement A9 native patient scope extraction`;
- до governance-редактирования working tree был clean; текущий разрешённый diff — только `TASK.md`; HEAD совпадает с `origin/codex/stage-a`;
- governance предыдущего checkpoint: `e46a428 docs: define A9 native extraction implementation`;
- native raw/prompt fixture: `tests/fixtures/patient_scope_native_contract_a9_v2.json`;
- generic shadow recorder: `core/turn_frame_shadow.py`;
- planner runtime seam: `core/turn_planner_llm.py::plan_turn_attempt`;
- product seam: `orchestration/resolver_turn.py::run_resolver_turn`;
- observability seam: `core/metadata_first_observability.py` + `orchestration/finalize_turn.py`;
- первый A9 raw immutable и не перезапускается;
- live-positive exact первого raw остаётся `0` по `extent/jaw/stage/modifiers`, composite `0/9`;
- product firewall сохранён, patient-scope authority запрещена.

Контекст продукта: бот работает только как local demo, production-клиентов нет. Этот checkpoint не сохраняет legacy ради действующих пользователей и не улучшает legacy-ответы. Legacy branch используется только как временный контрольный контур, чтобы доказать отсутствие скрытой authority у native shadow.

## 2. Архитектурное решение до test code

Production wiring уже generic и достаточен:

```text
plan_turn_attempt(original planner object)
  ├─ shadow_frame <- original object including patient_scope
  └─ legacy_plan  <- exact object without only patient_scope

run_resolver_turn
  ├─ record_planner_attempt_shadow(attempt) -> request.ctx / telemetry
  └─ product decision <- attempt.legacy_plan or existing resolver fallback
```

Поэтому новый runtime adapter, flag, serializer, route или product consumer не добавляется. Checkpoint закрывается только executable proof в существующих test modules. Если доказательство требует production change — СТОП и новое governance-решение; silently расширять allowlist запрещено.

Это proof data-flow isolation, а не утверждение о качестве текста legacy-ответов. Price/evidence/composer/UI не нужно прогонять через старый widget: отсутствие native input доказывается A/B runtime signature + source/AST firewall + нулевым production diff.

## 3. Deliverables и allowlist

### Governance

1. `TASK.md`

До governance checker `✅` разрешён только этот файл. После `✅` — отдельный governance commit/push.

### Tests после governance commit

2. `tests/test_turn_frame_shadow.py`
3. `tests/test_metadata_first_observability.py`

Production files менять запрещено. Новый fixture создавать запрещено: использовать frozen v2 JSON только как read-only evidence либо компактные synthetic payloads, прямо связанные с его enums/semantics.

### Roadmap только после final checker `✅`

4. `docs/STRANGLER_ROADMAP.md`

После code/runtime checker `✅`:

- закрыть только `Native shadow wiring/firewall proof`;
- оставить A9 parent `[ ]`, authority `Forbidden`;
- назвать следующим checkpoint `A9 Manual-contact not_applicable Taxonomy`;
- исправить вводную формулировку roadmap: бот — local demo без production-клиентов; legacy временно служит измерительным/контрольным контуром, а не защищаемым продуктом;
- кратко объяснить владельцу: native карточка наблюдаема технически, но ещё не управляет ответом.

Любой другой файл — STOP.

## 4. Primary runtime proof

В `tests/test_turn_frame_shadow.py` добавить integration tests через production functions. В primary tests запрещено мокать:

- `plan_turn_attempt`;
- `build_turn_frame_from_raw`;
- `record_planner_attempt_shadow`;
- `run_resolver_turn`;
- `turn_plan_to_decision_frame`;
- `publish_turn_plan`.

Разрешено мокать только внешний chat completion, catalog/config loaders, event/usage side effects и controlled existing resolver fallback. Один synthetic planner response = один planner call; retry/second call запрещены.

### 4.1 Valid native A/B isolation

Два запуска с одинаковыми legacy keys:

1. control без `patient_scope`;
2. treatment с полностью valid native composite sibling, намеренно отличающимся от legacy scalar `patient_situation`.

Оба проходят через реальный `plan_turn_attempt` внутри `run_resolver_turn`.

Обязательные assertions:

- в treatment `request.ctx.turn_frame_shadow.patient_scope` точно равен native composite;
- все четыре native member meta имеют provenance `turn_plan.raw.patient_scope.<field>`, status `valid`, confidence `0.0`;
- `request.ctx.turn_plan` не содержит `patient_scope`;
- control/treatment product signatures совпадают: `ResolverTurnOutcome.intent`, `decision.model_dump()`, `scope_topic_candidate`, published strict `turn_plan`;
- route/service/topic/aspects/follow-up/clarify не зависят от native sibling;
- fallback не вызывается;
- на каждый запуск ровно один planner completion, retry отсутствует.

### 4.2 Invalid native does not invalidate valid legacy

Synthetic payload содержит valid legacy keys и present native container с одним invalid member и valid соседями.

Обязательные assertions:

- legacy plan остаётся valid и публикуется без `patient_scope`;
- product decision идёт по legacy planner branch, existing fallback не вызывается;
- shadow status `partial`;
- invalid member получает safe value + exact error/provenance;
- valid native neighbors сохраняются в ctx snapshot;
- native values не меняют decision/output signature.

### 4.3 Valid native does not rescue invalid legacy

Synthetic payload содержит independently valid native composite и invalid legacy field (`aspects=[]` или второй top-level extra, как уже frozen contract допускает для proof).

Обязательные assertions:

- `legacy_plan is None`, strict branch не repair'ится;
- native frame и exact member provenance доступны в shadow ctx;
- shadow status `partial`;
- `run_resolver_turn` использует controlled existing resolver fallback;
- fallback decision/product signature не строится из native scope;
- planner completion ровно один, scope retry отсутствует.

## 5. Observability / privacy proof

В `tests/test_metadata_first_observability.py` доказать существующий generic channel для native sibling:

1. Valid composite и его nested `field_meta` без преобразований проходят:
   - `request.ctx`;
   - `metadata_first_turn_details()`;
   - `metadata_first_response_meta()`;
   - `finalize_ask()` только при `E2E_USE_TEST_CLIENT=1`.
2. При отсутствии `E2E_USE_TEST_CLIENT` metadata/shadow не появляется в обычном response payload.
3. Partial native container сохраняет valid neighbors и exact generic errors/status.
4. Extra native key/name/value, question/history, exception text и raw object не сериализуются в ctx/details/response slice.
5. Нельзя логировать пользовательский вопрос, историю, raw scope или exception payload ради proof.

Existing generic recorder/metadata production code менять не требуется и запрещено.

## 6. Static product firewall

Усилить source/AST assertions без изменения production:

1. `run_resolver_turn()` вызывает `plan_turn_attempt` один раз, записывает весь attempt в recorder, но для product использует только `attempt.legacy_plan`.
2. Product modules не читают:
   - `attempt.shadow_frame.patient_scope`;
   - `shadow_frame.patient_scope`;
   - nested `turn_frame_shadow["patient_scope"]`;
   - native member axes через shadow (`extent/jaw/stage/modifiers`).
3. `turn_plan_to_decision_frame()` и `publish_turn_plan()` не читают/публикуют native `patient_scope`.
4. `TurnPlan` contract не содержит `patient_scope`.
5. Imports/constructors `PatientScopeFrame` остаются только в contract/builder/adapter shadow boundary; product routing, resolver, price, evidence, playbook, composer, marketing, booking, contacts, medzone и session mutation не получают этот type.
6. No native scope enum/value mapping добавлен в service-id, price-unit/group или document-id selection.

AST/source proof должен различать новый nested `contracts.turn_frame.PatientScopeFrame` и одноимённый legacy scalar `PatientSituationResult.patient_scope`; запрещено объявлять нарушением существующий legacy scalar только по совпадению строки.

## 7. Frozen/protected artifacts

После governance immutable:

- `TASK.md`;
- `tests/fixtures/patient_scope_native_contract_a9_v2.json`;
- `docs/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md`;
- `evals/v5/demo/patient_scope_shadow_matrix.json`;
- A9 v1 harness/audit;
- `eval_patient_scope_a9_last.txt`;
- A6/A7/A8 frozen artifacts.

Запрещены resnapshot, изменение expected/target, ослабление asserts, skip/xfail, hardcode live case ids и условный PASS.

Protected hashes:

- first A9 raw SHA256: `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`;
- v1 matrix git blob: `d459073bbf8767f7ff590ece2958f7aa8cb18b25`;
- v2 fixture git blob: `c7458e4481489895320ea3de1dec1a81b8da5f50`.

## 8. Product firewall / non-goals

Запрещено:

- менять production code;
- улучшать или сохранять legacy ответы ради production parity;
- подключать native scope к resolver/routing/price/evidence/playbook/composer/marketing/booking/UI/session;
- добавлять native scope в `TurnPlan`, `DecisionFrame`, `AnswerPlan`, `ResponseSpec` или product ctx;
- добавлять flag/default flip, new route, classifier, handler, adapter или serializer;
- добавлять second LLM call, retry, fallback classifier или question/history parser;
- менять scalar bridge/native parser/prompt/completion cap;
- менять logging payload;
- менять manual-contact semantics в этом checkpoint;
- запускать live/LLM/widget;
- менять authority;
- закрывать manual-contact, matrix/harness v2, live, authority, legacy retirement или A9 parent checkbox.

## 9. Targeted tests

Primary wiring/firewall slice:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py -q
```

Related planner/contracts regressions:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_turn_planner_llm.py tests/test_turn_planner_wiring.py tests/test_patient_scope_native_contract_spec.py -q
```

Full suite не обязателен: production diff запрещён, primary integration + related seams достаточны. Если targeted test обнаруживает production gap — СТОП, не чинить вне allowlist.

## 10. Static checks

```powershell
git diff --check
git diff --name-only
git diff -- core contracts orchestration app.py llm.py
rg -n "patient_scope|PatientScopeFrame|shadow_frame" core orchestration contracts app.py llm.py
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object tests/fixtures/patient_scope_native_contract_a9_v2.json
```

Expected implementation diff до roadmap update: только два test files; production diff пустой; protected hashes exact.

## 11. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет TASK, sufficiency test-only решения, A/B signatures, mock boundaries, privacy и firewall до test code. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — test/runtime proof

Изменить только два allowlist test files. Выполнить targeted tests/static checks. Roadmap не менять, commit не делать.

### Checkpoint 3 — independent code/runtime review

Checker начинает с test diff, подтверждает отсутствие hidden mocks/conditional PASS, затем сверяет runtime proof, product isolation, observability, privacy, production-empty diff и test evidence.

### Checkpoint 4 — completion

Только после checker `✅` обновить roadmap checkbox/status и local-demo wording, повторить static checks, затем один completion commit и push в `codex/stage-a`.

## 12. Definition of Done

1. Test-only решение подтверждено checker до реализации; governance commit отдельно зафиксирован.
2. Actual `plan_turn_attempt -> run_resolver_turn -> record_planner_attempt_shadow` материализует valid native composite в ctx с exact nested metadata.
3. A/B с/без native sibling имеет одинаковую product signature и различается только shadow observation.
4. Invalid native не ломает valid legacy; valid native не repair'ит invalid legacy.
5. Existing resolver fallback не получает native scope как input и сохраняет controlled output.
6. Native valid/partial frame проходит generic turn details и E2E-only response metadata; обычный response не содержит shadow.
7. Raw/extra/question/history/exception secrets не сериализуются.
8. AST/source firewall различает native nested и legacy scalar и не находит product consumers native scope.
9. Production diff пустой; изменены только два allowlist test files, затем roadmap.
10. Оба targeted pytest slices зелёные; full suite обоснованно не запускался.
11. Frozen v1/v2 artifacts и первый raw имеют exact hashes; live/LLM/widget не запускались.
12. Independent checker дал final `✅` до roadmap update/commit.
13. Roadmap закрывает только native wiring/firewall proof, корректно описывает local demo, A9 parent открыт, authority forbidden.

После completion commit — СТОП. `A9 Manual-contact not_applicable Taxonomy` начинается только с нового TASK и governance review.
