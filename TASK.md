# TASK — A9 Native Extraction Implementation

Один активный `TASK.md` на один checkpoint. Реализовать approved/frozen A9 native patient-scope extraction в существующем едином planner call: compact prompt contract, exact one-key legacy projection и independent field parser с scalar bridge fallback только при absent sibling.

Checkpoint code/unit-only, shadow-only. Live/LLM, product authority и downstream wiring запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `7425c77 test: freeze A9 native raw contract spec`;
- `origin/codex/stage-a` на том же commit;
- рабочее дерево до governance diff чистое;
- approved design: `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` (`16ced47`);
- frozen v2 spec: `docs/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md`;
- frozen machine fixture: `tests/fixtures/patient_scope_native_contract_a9_v2.json`;
- container metadata contract завершён (`28a8b24`);
- product firewall сохранён, patient-scope authority запрещена;
- первый A9 raw immutable и не перезапускается.

## 2. Completion-budget decision до code

Default planner model: `qwen3.6-flash`. Локального model tokenizer в repository/runtime environment нет; exact token count не заявляется и live-подбор запрещён.

Representative capacity evidence из frozen fixture:

- representative full object без sibling: `465 UTF-8 bytes`;
- с native sibling: `585 UTF-8 bytes`;
- additive delta: `120 bytes`;
- sample содержит все legacy fields и все 9 allowed aspects, но не объявляется общим worst-case;
- synthetic service ID: 36 bytes, current demo maximum: 29;
- synthetic brand group: 21 bytes, current demo maximum: 6;
- synthetic brand: 26 bytes, current demo maximum: 13;
- synthetic topic: 34 bytes, current demo maximum: 14;
- native values — bounded enums/one-item modifier list.

Отдельный derived compact current-demo reference, построенный из самых длинных **фактических** legacy/native enum и config values, занимает `530 UTF-8 bytes`. Он учитывает `existing_implant_prosthetic_stage`, `jaw=unknown`, все aspects и текущие longest demo catalog/topic/brand values. Это current-config reference, не bound на whitespace, произвольные будущие client strings или tokenizer output.

Решение checkpoint: изменить private planner ceiling с `300` на `700 max_completion_tokens`.

Обоснование policy:

- cap `300` нельзя честно доказать достаточным без tokenizer;
- frozen representative sample занимает 585 bytes, derived current-demo compact reference — 530 bytes;
- `700` даёт консервативный capacity margin над обоими compact byte measurements, но **не является universal token/whitespace guarantee**;
- prompt требует compact JSON и exact fields;
- это ceiling, не второй call, не retry и не разрешение на free text;
- arbitrary future client strings не bounded контрактом: unit guard обязан остановить drift current demo maxima за frozen synthetic catalog-field lengths, после чего нужен новый budget review;
- tokenizer-exact tokens не известны; byte measurements не переименовываются в tokens.

Canonical planner assumption/guard: для Qwen planner call thinking отключается явно через `extra_body={"enable_thinking": false}` независимо от global `QWEN_ENABLE_THINKING`. Для non-Qwen override Qwen-specific `extra_body` не передаётся. Unit tests обязаны проверить оба kwargs paths.

Не менять model, temperature или timeout. Не поднимать cap выше `700` в этом checkpoint.

## 3. Deliverables и allowlist

После отдельного governance commit разрешено менять только:

### Production

1. `core/turn_frame_from_raw.py`
2. `core/turn_planner_llm.py`

### Tests

3. `tests/test_turn_frame_from_raw.py`
4. `tests/test_turn_planner_llm.py`
5. `tests/test_patient_scope_native_contract_spec.py`

В spec-test разрешено только заменить финальный pre-implementation gate на post-implementation binding. Hardcoded manifests, declarative expectations, fixture paths, `465/585/120` evidence и frozen semantics не менять/не ослаблять.

### Roadmap после checker ✅

6. `docs/STRANGLER_ROADMAP.md` — только после independent code review `✅`:
   - отметить `[x] Native extraction implementation`;
   - назвать последним завершённым этот checkpoint;
   - назвать следующим `A9 Native Shadow Wiring / Firewall Proof`;
   - сохранить A9 parent `[ ]`, shadow-only и authority forbidden.

Frozen spec doc/JSON, v1 matrix/harness/raw/audit и любой другой tracked/untracked file менять запрещено.

## 4. Native parser contract

`core/turn_frame_from_raw.py`:

1. Проверять **presence**, а не truthiness:
   - key `patient_scope` absent → существующий scalar bridge byte/semantics unchanged;
   - key present → только native container, scalar не backfill’ит ни одного member.
2. Не мутировать raw.
3. Container:
   - object только с allowed keys → `valid/None`;
   - `null`/wrong type → `invalid/patient_scope_invalid_type`, safe frame, четыре child metas `defaulted`;
   - unknown extra → `invalid/patient_scope_extra_field`, known members parse independently;
   - object с missing/invalid member → container остаётся `valid`.
4. Container provenance `turn_plan.raw.patient_scope`, confidence `0.0`.
5. Member provenance `turn_plan.raw.patient_scope.<field>`, включая missing/invalid; invalid-container default children используют `turn_plan.schema_default`.
6. Scalar bridge provenance `turn_plan.patient_situation.*` и current values/statuses не менять.

Known members:

- allowed value и explicit `unknown`/`[]` → `valid`;
- missing → safe value + `missing`;
- wrong type → safe value + matching `*_invalid_type`;
- outside allowlist → safe value + matching `*_not_allowed`;
- modifiers non-list или любой non-string item → whole field `[]/invalid/patient_modifiers_invalid_type`;
- modifiers с unsupported string, включая mixed valid+unsupported → whole field `[]/invalid/patient_modifier_not_allowed`;
- duplicate allowed modifiers → current model canonical unique sorted list;
- invalid одного member сохраняет valid neighbors.

Raw value/unknown extra name/value не включать в error, provenance или logs.

## 5. Exact legacy projection

В `core/turn_planner_llm.py` добавить один pure private helper, который:

```python
return {key: value for key, value in raw.items() if key != "patient_scope"}
```

Только этот projected dict передаётся в current `_validate_plan()`.

Обязательно:

- original parsed `obj` остаётся неизменным и идёт в shadow builder;
- удаляется только exact top-level `patient_scope`;
- любой другой extra сохраняется и остаётся fatal;
- invalid native не меняет valid legacy plan;
- invalid legacy не уничтожает independently valid native frame;
- `_sanitize_topic_fields`, catalog/brand guards, protocol guard, follow-up enrichment, logging и fail-open не изменяются;
- `plan_turn()` возвращает только `legacy_plan` как раньше;
- `patient_scope` не попадает в `TurnPlan`, product ctx/dump, resolver/composer.

## 6. Prompt implementation

Добавить отдельную private константу `_PATIENT_SCOPE_PROMPT` и включить её в существующий `_SYSTEM`.

Scope block обязан кратко требовать:

1. compact `patient_scope` object ровно с keys `extent`, `jaw`, `stage`, `modifiers`;
2. exact enum/list values из frozen contract;
3. только explicit facts текущего сообщения;
4. absent fact → `unknown`/`[]`, no guess;
5. history помогает referent, но не переносит old scope без current mention;
6. legacy `patient_situation` возвращается отдельно;
7. no service/protocol/price unit/document/evidence/diagnosis selection;
8. urgency/pain outside scope;
9. reported bone context не clinical confirmation;
10. no extra scope fields.

Scope block не содержит:

- frozen case IDs;
- exhaustive phrase list;
- All-on-4/All-on-6 или другие service mappings;
- retry/second call/classifier;
- instruction влиять на answer/routing/price/UI.

Существующие legacy prompt rules не переписывать, кроме добавления sibling в exact field list и подключения scope block.

## 7. Test binding к frozen fixture

### `tests/test_turn_frame_from_raw.py`

- загрузить frozen v2 fixture;
- прогнать exact 18 parser cases через production builder;
- прогнать 4 precedence cases;
- проверить values, container/member status/error/provenance, recursive partial signal, raw immutability и отсутствие extra leak;
- сохранить все существующие scalar bridge tests unchanged.

### `tests/test_turn_planner_llm.py`

- exact projection helper: пять frozen projection cases, input immutable;
- native sibling + valid legacy → valid legacy plan;
- second unknown top extra остаётся fatal;
- invalid native + valid legacy → legacy plan valid, shadow partial;
- invalid legacy + valid native → legacy none, native neighbors preserved;
- one call/no retry;
- Qwen call явно использует `extra_body.enable_thinking=false`; non-Qwen call не получает Qwen-specific body;
- `_PATIENT_SCOPE_PROMPT` содержит required semantics и не содержит forbidden scope mappings;
- captured call использует `max_completion_tokens=700`;
- current demo catalog/topic/brand maxima не превышают frozen synthetic sample lengths;
- independently derived compact current-demo longest-values object воспроизводимо равен `530 bytes`; это capacity evidence, не tokenizer/whitespace guarantee;
- product wrapper/published `TurnPlan` не содержит `patient_scope`.

### `tests/test_patient_scope_native_contract_spec.py`

Только заменить gate «implementation ещё отсутствует» на binding:

- `_SYSTEM` включает scope block;
- exact projection seam присутствует;
- native builder читает sibling по presence;
- frozen fixture/manifests/evidence остаются неизменны.

## 8. Product firewall / non-goals

Запрещено:

- менять contracts/value/error allowlists;
- менять resolver/composer/routing/app/response metadata wiring;
- передавать native scope в product decisions;
- добавлять session carry/merge, question/history parser, detector или scalar reconciliation;
- добавлять second call/retry/fallback classifier;
- менять logging payload или логировать raw scope;
- менять frozen spec JSON/doc, v1 matrix/harness/raw/audit;
- запускать live/LLM;
- менять authority;
- закрывать wiring/firewall, harness v2, live, authority или A9 parent checkbox.

## 9. Targeted tests

Primary implementation slice:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_turn_frame_from_raw.py tests/test_turn_planner_llm.py tests/test_patient_scope_native_contract_spec.py -q
```

Related shadow/product regressions:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_turn_planner_wiring.py tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py -q
```

Full suite не обязателен при зелёных targeted slices и пустом downstream diff. Если targeted regression показывает широкий риск — СТОП и новая оценка scope.

## 10. Static checks

```powershell
git diff --check
git diff --name-only
git diff -- contracts orchestration app.py
rg -n "patient_scope" core/turn_planner_llm.py core/turn_frame_from_raw.py
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object tests/fixtures/patient_scope_native_contract_a9_v2.json
```

Protected baselines:

- first A9 raw SHA256: `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`;
- v1 matrix git blob: `d459073bbf8767f7ff590ece2958f7aa8cb18b25`;
- v2 fixture git blob: `c7458e4481489895320ea3de1dec1a81b8da5f50`.

## 11. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет TASK и budget decision до code. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — implementation

Изменить только allowlist production/tests. Выполнить targeted tests/static checks. Roadmap не менять, commit не делать.

### Checkpoint 3 — independent code/runtime review

Checker сверяет diff с frozen fixture, test evidence, budget guard, one-call invariant, exact projection, privacy и product firewall.

### Checkpoint 4 — completion

Только после checker `✅` обновить один roadmap checkbox/status, повторить static checks, затем один implementation commit и push в `codex/stage-a`.

## 12. Definition of Done

1. Все 18 parser + 4 precedence + 5 projection cases проходят production binding.
2. Absent использует unchanged bridge; любой present container полностью владеет native scope.
3. Exact one-key projection сохраняет strict legacy extras/eligibility.
4. Prompt реализует frozen current-turn/unknown-safe semantics без product mappings.
5. Один planner call, no retry; cap ровно `700`, Qwen thinking explicitly off, current-demo drift/reference guards зелёные без universal sufficiency claim.
6. Legacy `TurnPlan`/product path не содержит `patient_scope`.
7. Оба targeted pytest slices зелёные; full suite обоснованно не запускался.
8. Production diff только в двух allowlist modules; downstream contracts/wiring untouched.
9. Frozen v1/v2 artifacts и raw hashes неизменны; live/LLM не запускались.
10. Independent checker дал `✅` до roadmap update/commit.
11. Roadmap закрывает только native extraction implementation; A9 parent открыт, authority forbidden.

После completion commit — СТОП. `A9 Native Shadow Wiring / Firewall Proof` начинается только с нового TASK и governance review.
