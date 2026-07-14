# TASK — A9 Native Raw Contract / Prompt Spec

Один активный `TASK.md` на один checkpoint. Цель — до native implementation заморозить точную форму будущего planner JSON, exact legacy projection, parser-state expectations и semantic requirements будущего prompt.

Checkpoint docs/unit-fixture only. Production code, действующий `_SYSTEM`, raw builder, runtime и product behavior не меняются. Live/LLM запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `28a8b24 feat: add A9 patient scope container metadata`;
- `origin/codex/stage-a` на том же commit;
- рабочее дерево до governance diff чистое;
- approved design: `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` (`16ced47`);
- container metadata contract завершён: governance `375ac13`, implementation `28a8b24`;
- первый A9 raw immutable и не перезапускается без отдельного разрешения;
- product firewall сохранён, patient-scope authority запрещена.

## 2. Deliverables и allowlist

После отдельного governance commit разрешено менять только:

1. создать `docs/PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md`;
2. создать `tests/fixtures/patient_scope_native_contract_a9_v2.json`;
3. создать `tests/test_patient_scope_native_contract_spec.py`;
4. обновить `docs/README.md` — только добавить новый spec в канонический список A9;
5. после independent spec review `✅` обновить `docs/STRANGLER_ROADMAP.md`:
   - отметить `[x] Native raw contract и prompt spec`;
   - назвать последним завершённым этот checkpoint;
   - назвать следующим `A9 Native Extraction Implementation`;
   - сохранить A9 parent `[ ]`, shadow-only и authority forbidden.

`TASK.md` после governance commit не менять. Любой другой tracked/untracked file → `❌` и СТОП.

## 3. Frozen raw contract

Spec обязан зафиксировать flat planner object с прежними legacy fields и ровно одним новым top-level shadow sibling `patient_scope`.

`patient_scope` — object ровно с четырьмя обязательными keys:

- `extent`: `unknown | one_tooth | few_teeth | full_arch`;
- `jaw`: `unknown | upper | lower | both`;
- `stage`: `unknown | extraction_context | implant_placed`;
- `modifiers`: list, допустимое значение элемента только `reported_bone_deficit`.

`unknown`/`[]` означают явное незнание. `null` не означает all-unknown и является invalid container.

`patient_situation` остаётся отдельным legacy product field. Одновременное присутствие scalar и nested output не означает merge/reconciliation и не создаёт второй LLM-call.

## 4. Exact legacy projection contract

Frozen fixtures обязаны доказать будущей implementation:

1. Из original parsed dict удаляется только top-level key `patient_scope`.
2. Все legacy values сохраняются без нормализации новым A9 seam.
3. Любой второй unknown top-level key остаётся в projected dict и поэтому остаётся fatal для `TurnPlan(extra="forbid")`.
4. Invalid nested scope не влияет на legacy eligibility.
5. Invalid legacy field не уничтожает independently valid native scope.
6. Original input после shadow/legacy branches остаётся deep-equal исходному.
7. `patient_scope` не добавляется в `TurnPlan`, product ctx/dump или resolver input.

Fixture хранит **synthetic governed planner object** и expected projected legacy object явно. Это schema fixture без пользовательского текста/PII и не копия live raw. Spec-test может вычислять только exact one-key projection для проверки самосогласованности fixture; production helper на этом checkpoint не создаётся.

## 5. Source precedence и parser-state fixtures

Schema version: `a9.patient_scope_native_contract.v2`.

Exact container metadata table:

| Raw state | Container meta | Child metas/source |
|---|---|---|
| sibling absent | `defaulted`, error `None`, provenance `turn_plan.schema_default` | текущий scalar bridge без изменений |
| present object, только allowed keys | `valid`, error `None`, provenance `turn_plan.raw.patient_scope` | только native parser, без scalar backfill |
| present `null`/wrong type | `invalid`, `patient_scope_invalid_type`, provenance `turn_plan.raw.patient_scope` | все четыре child metas `defaulted`, safe values; bridge не маскирует failure |
| object с unknown nested extra | `invalid`, `patient_scope_extra_field`, provenance `turn_plan.raw.patient_scope` | known members parse independently; extra name/value не попадают в output metadata |
| present object с missing/invalid member | container остаётся `valid`, error `None` | member остаётся missing/invalid; no scalar backfill |

Confidence container всегда `0.0`.

Known-member fixtures обязаны покрыть:

- allowed value и explicit `unknown`/`[]` → `valid`;
- missing member → safe value + `missing`;
- wrong type → safe value + соответствующий `*_invalid_type`;
- scalar outside allowlist → safe value + соответствующий `*_not_allowed`;
- modifiers non-list/non-string item → `patient_modifiers_invalid_type`;
- modifiers unsupported string → `patient_modifier_not_allowed`;
- mixed valid+invalid modifiers → всё поле `invalid`, value `[]`; partial filtering запрещён;
- modifiers duplicate allowed value → canonical unique sorted list;
- invalid одного member не стирает valid neighbors.

Для present native container confidence всегда `0.0`, provenance контейнера `turn_plan.raw.patient_scope`, provenance members `turn_plan.raw.patient_scope.<field>`. Для absent сохраняются current scalar bridge values/provenance и `container=defaulted/turn_plan.schema_default`.

Любой native container/member `missing` или `invalid` ожидает `shadow_status=partial`, не `degraded`. Product authority из fixture/spec запрещена.

### 5.1 Hardcoded required-case manifest

Spec-test хранит этот manifest в test code независимо от JSON и требует exact ordered ID sets.

`projection_cases` — ровно 5:

1. `projection_valid_native_valid_legacy`
2. `projection_native_plus_unknown_top_level`
3. `projection_invalid_native_valid_legacy`
4. `projection_valid_native_invalid_legacy`
5. `projection_input_immutability`

`precedence_cases` — ровно 4:

1. `precedence_absent_uses_bridge`
2. `precedence_present_object_uses_native`
3. `precedence_present_invalid_container_no_bridge`
4. `precedence_present_invalid_member_no_backfill`

`parser_cases` — ровно 18:

1. `container_valid_object`
2. `container_null_invalid_type`
3. `container_non_object_invalid_type`
4. `container_extra_field_preserves_neighbors`
5. `members_valid_composite`
6. `members_explicit_unknown_empty`
7. `members_all_missing`
8. `extent_invalid_type`
9. `extent_not_allowed`
10. `jaw_invalid_type`
11. `jaw_not_allowed`
12. `stage_invalid_type`
13. `stage_not_allowed`
14. `modifiers_invalid_type_non_list`
15. `modifiers_invalid_type_item`
16. `modifier_not_allowed`
17. `modifiers_duplicate_canonical`
18. `invalid_member_preserves_neighbors`

`prompt_examples` — ровно 5 abstract meaning IDs, без user utterances:

1. `meaning_one_tooth`
2. `meaning_full_upper_reported_bone`
3. `meaning_implant_placed`
4. `meaning_informational_no_patient_facts`
5. `meaning_vague_followup_no_current_scope`

## 6. Prompt semantic contract

На этом checkpoint `_SYSTEM` не меняется. Fixture/spec замораживает смысл, а не дословную русскую формулировку будущего prompt:

1. Всегда вернуть object с четырьмя keys.
2. Извлекать только явно сообщённые признаки текущего сообщения.
3. Не сообщено → `unknown`/`[]`, не угадывать.
4. History может разрешать referent, но не переносит старое scope-value без explicit current mention.
5. `patient_situation` возвращается отдельно по legacy enum.
6. Scope не выбирает service/protocol/price unit/document/evidence/diagnosis.
7. Urgency и pain не входят в scope.
8. `reported_bone_deficit` — сообщённый контекст, не клиническое подтверждение.
9. Только JSON, без extra fields.

Минимальные semantic fixtures хранятся как abstract meaning IDs, не как тексты пациентов:

- один отсутствующий зуб;
- вся верхняя челюсть + сообщённая нехватка кости;
- имплант уже установлен;
- informational question без patient facts;
- vague follow-up «а сколько стоит?» при старом session extent → all unknown/empty.

Запрещены frozen live case IDs, exhaustive phrase classifier и All-on-4/All-on-6/service mappings.

## 7. Static completion-budget evidence

Fixture содержит один **representative upper-size schema sample**: все legacy fields заполнены, перечислены все allowed aspects и выбраны длинные native enum values. Это не общий worst-case: catalog-derived strings зависят от клиента и не имеют length bound в `TurnPlan`.

Spec-test фиксирует compact JSON UTF-8 byte/character size и отдельно delta, добавленную sibling `patient_scope`, сравнением с тем же synthetic object без sibling.

Документ обязан:

- отделить статический размер JSON от tokenizer-exact token count;
- не заявлять точный token count без локального tokenizer текущей модели;
- зафиксировать verdict: этот representative byte/delta sample сам по себе **не доказывает** запас внутри `max_completion_tokens=300`;
- потребовать от implementation TASK явного budget decision до code changes: сохранить `300` только с model-tokenizer/static evidence либо обосновать новый консервативный limit;
- не подбирать лимит через live/LLM.

На этом checkpoint runtime token limit не меняется.

## 8. Contract-spec test

`tests/test_patient_scope_native_contract_spec.py` проверяет только frozen spec/fixture:

- exact top-level keys и schema version;
- value allowlists совпадают с `contracts.turn_frame`;
- legacy keys совпадают с `TurnPlan.model_fields`, а `patient_scope` остаётся sibling;
- exact projection cases и preservation unknown extra;
- exact hardcoded ordered manifest: `5 projection + 4 precedence + 18 parser + 5 prompt examples`, без missing/extra/duplicate IDs;
- expected safe values/status/error/provenance проходят текущие value/meta contracts;
- prompt semantic/forbidden requirements и пять examples присутствуют;
- `_SYSTEM` и production source ещё не содержат native `patient_scope` implementation;
- representative completion-size/native-delta measurement воспроизводим и не назван exact token count;
- fixture разрешает только synthetic governed planner objects без пользовательского текста;
- fixture не разрешает authority/live/product usage и не содержит копий live/v1 raw, вопросов/ответов, session IDs, PII или secrets.

Тест не импортирует harness, не ходит в сеть и не вызывает LLM.

## 9. Explicit non-goals / protected scope

Запрещено:

- менять `core/turn_planner_llm.py`, `core/turn_frame_from_raw.py` или любой production code;
- менять `_SYSTEM`, `max_completion_tokens`, model/temperature/timeout;
- реализовывать projection helper, native parser, source precedence или wiring;
- менять `TurnPlan`, planner eligibility, retry/fail-open, resolver/composer/product payload;
- запускать live/LLM;
- менять v1 matrix/harness/raw/audit/design docs;
- копировать live/v1 raw или добавлять вопросы/ответы/session IDs/PII/secrets в fixture; synthetic governed planner objects обязательны и разрешены;
- закрывать native extraction implementation, A9 parent или authority checkbox.

Первый A9 raw SHA256 должен остаться:
`478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`.

A9 v1 matrix git blob должен остаться:
`d459073bbf8767f7ff590ece2958f7aa8cb18b25`.

## 10. Проверки

После authoring:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_patient_scope_native_contract_spec.py -q
git diff --check
git diff --name-only
git diff -- core contracts orchestration app.py
rg -n 'patient_scope' core/turn_planner_llm.py
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
```

Full pytest не запускать: production code не меняется, новый isolated spec-test достаточен.

## 11. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет TASK до spec authoring. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — spec/fixture authoring

Создать только allowlist doc/fixture/test и README entry. Выполнить один isolated pytest и static checks. Roadmap пока не менять, commit не делать.

### Checkpoint 3 — independent spec review

Checker сверяет doc, fixture и test с approved design, проверяет полноту states, отсутствие скрытой implementation, firewall/privacy и честность completion-budget evidence.

### Checkpoint 4 — completion

Только после checker `✅` обновить один roadmap checkbox/status, повторить static checks, затем один spec completion commit и push в `codex/stage-a`.

## 12. Definition of Done

1. Exact raw sibling/value shape frozen в одном canonical spec и versioned fixture.
2. Exact one-key legacy projection и preservation других extras frozen.
3. Container/source precedence и все field parser states имеют expected value/meta/status/error.
4. Prompt semantics заморожены без изменения `_SYSTEM`.
5. Completion-budget decision основан на static evidence без ложного exact token claim.
6. Isolated contract-spec pytest зелёный; full suite обоснованно не запускался.
7. Production diff пуст, live/LLM не запускались.
8. V1 raw/matrix hashes неизменны.
9. Independent checker дал `✅` до roadmap update/commit.
10. Roadmap закрывает только этот subcheckpoint; A9 parent открыт, authority forbidden.

После completion commit — СТОП. `A9 Native Extraction Implementation` начинается только с нового TASK и governance review.
