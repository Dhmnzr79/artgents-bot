# TASK — A9 Frozen Matrix/Harness v2 Review

Один активный `TASK.md` на один checkpoint. Подготовить и заморозить versioned A9 patient-scope matrix/harness v2 **до** любого нового live/LLM запуска.

Checkpoint eval/contract-only. Он не оценивает новую модель, не меняет ответы бота и не передаёт authority. Первый A9 raw, v1 artifacts и audit остаются неизменными.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline и цель

- branch `codex/stage-a`;
- baseline HEAD `deaa759 test: add A9 manual contact taxonomy`, совпадает с `origin/codex/stage-a`;
- до governance edit рабочее дерево было чистым; текущий разрешённый diff — только `TASK.md`;
- выбранный design: `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`, §9 и §12;
- первый audit: `docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`;
- v1 matrix/harness: `evals/v5/demo/patient_scope_shadow_matrix.json` и `evals/v5/run_patient_scope_shadow_eval.py`;
- принятый pure taxonomy helper: `evals/v5/patient_scope_availability_v2.py`;
- первый A9 raw immutable; live-positive exact остаётся `0` по `extent/jaw/stage/modifiers`, composite `0/9`;
- product firewall сохранён, patient-scope authority `Forbidden`;
- бот локальный demo, production-клиентов нет.

Цель checkpoint: заранее заморозить вопросы, ожидания, versioned artifact names, классификацию наблюдений и честные **live-only** знаменатели будущего one-run re-audit. Не запускать этот re-audit.

## 2. Решение до code

Создать независимые v2 artifacts, не редактируя и не импортируя как mutable config v1 snapshot:

1. `evals/v5/demo/patient_scope_shadow_matrix_v2.json`;
2. `evals/v5/run_patient_scope_shadow_eval_v2.py`;
3. `tests/test_patient_scope_shadow_eval_v2_contract.py`.

V2 harness может быть механически основан на v1 коде, но является отдельным frozen executable snapshot. Это исключает retroactive reinterpretation первого run и не требует risky refactor старого измерителя.

V2 matrix сохраняет те же 10 bridge, 4 field-isolation, 20 single-turn и 5×2 multi-turn expectations. Questions, ordering, evidence refs, current-turn/session laws и 30-call denominator не подгоняются под первый raw или текущий output. Изменяются только version/scoring-contract поля, необходимые v2.

## 3. Frozen names и versions

- matrix: `evals/v5/demo/patient_scope_shadow_matrix_v2.json`;
- harness: `evals/v5/run_patient_scope_shadow_eval_v2.py`;
- contract tests: `tests/test_patient_scope_shadow_eval_v2_contract.py`;
- future raw (не создавать сейчас): `eval_patient_scope_a9_v2_last.txt`;
- future audit (не создавать сейчас): `docs/PATIENT_SCOPE_SHADOW_REAUDIT_A9_V2.md`;
- matrix schema: `a9.patient_scope_shadow_matrix.v2`;
- summary schema: `a9.patient_scope_shadow_summary.v2`;
- output prefixes: `A9_SCOPE_V2_CASE`, `A9_SCOPE_V2_TURN`, `A9_SCOPE_V2_BOUNDARY`, `A9_SCOPE_V2_SUMMARY`.

Harness содержит exact git-blob hash v2 matrix и hashes защищённых upstream fixtures. После completion matrix/harness/test становятся frozen и меняются только отдельным versioned checkpoint.

## 4. Observation priority

V2 harness применяет к каждому successful endpoint response ровно следующий порядок:

```text
request exception                              -> ERROR / transport_error
scoreable shadow frame                         -> semantic comparison
runtime turn_frame_shadow_status=not_available -> ERROR / not_available
runtime turn_frame_shadow_status=degraded      -> ERROR / degraded
exact ingress_manual_contact + allowed shape
  + key turn_frame_shadow absent               -> NOT_APPLICABLE / pre_planner_manual_contact
other missing/malformed frame                  -> ERROR / extraction_error
```

Обязательные свойства:

- scoreable frame имеет приоритет даже при `service_route=ingress_manual_contact`;
- runtime `not_available/degraded` имеет приоритет над manual-contact helper;
- helper вызывается только после successful response и использует production implementation напрямую;
- `not_applicable` — harness observation status, не fake frame и не runtime status;
- taxonomy не расширяется за exact `ingress_manual_contact`;
- generic missing/malformed frame не называется transport error;
- exception не может стать `not_applicable`.

## 5. Result rows и group counts

Case/turn result сохраняет privacy-safe v1 semantic fields, добавляет exact `availability_status` и использует `status` только из:

```text
PASS | FAIL | ERROR | NOT_APPLICABLE
```

`availability_status` имеет одно из шести exact значений:

```text
available | not_available | degraded | not_applicable | transport_error | extraction_error
```

Для deterministic bridge/field rows `availability_status=available`, но они не входят в live `planner_availability`.

Для `NOT_APPLICABLE`:

- `reason=pre_planner_manual_contact`;
- `shadow_status=not_applicable`;
- `availability_status=not_applicable`;
- observed scope/status/errors равны `null`;
- row остаётся в frozen total и endpoint completeness;
- row не является PASS, FAIL или ERROR;
- row не делает `overall_exit_code=1` сам по себе.

Каждый group count имеет exact keys:

```text
total, passed, failed, errors, not_applicable
```

Их сумма обязана совпадать с `total`.

## 6. Honest summary denominators

V1 aggregate `per_axis` смешивал 14 deterministic rows с 30 live turns. V2 обязан явно отделить diagnostic deterministic groups от live quality.

Summary v2 включает:

1. frozen completeness: 34 case rows, 10 turn rows, 5 boundary rows, planned/executed endpoint calls `30`;
2. group counts для bridge, field-isolation, single-turn, multi-turn и boundaries;
3. `planner_availability` **только по 30 live rows** с отдельными exact buckets:
   - `available`;
   - `not_available`;
   - `degraded`;
   - `not_applicable`;
   - `transport_error`;
   - `extraction_error`;
   - deterministic 14 rows сюда не входят;
   - сумма шести buckets всегда равна `executed_live_calls=30`;
4. `live_current_scope` только по 20 single + 10 multi rows:
   - `total=30`;
   - `scoreable` — только rows с валидным scope/status/error observation;
   - `exact_complete` — `PASS` среди scoreable;
   - `not_applicable` отдельно;
5. `live_per_axis` для `extent/jaw/stage/modifiers`:
   - `scoreable`;
   - `all_value_exact` (value + field status + stable error);
   - `positive_expected`;
   - `positive_available`;
   - `positive_exact`;
   - confusion только по scoreable rows;
6. `live_composite`:
   - `total=7` frozen live expected composite rows: 5 single + 2 multi;
   - `scoreable` — только scoreable rows среди этих семи;
   - `exact` — `PASS` среди scoreable live composites;
7. field-status diagnostics могут считаться только по scoreable live rows и должны иметь явно live-названный key;
8. `product_parity_source=existing_regression_suites` и `authority_decision_allowed=false`.

Positive definition frozen:

- scalar axis: expected value не `unknown`;
- modifiers: expected list непустой.

Metric definitions frozen:

- `positive_available` = positive-expected rows, которые scoreable;
- `positive_exact` = positive-expected scoreable rows с exact value + field status + stable error;
- `all_value_exact` = любые scoreable rows с exact value + field status + stable error;
- confusion включает только scoreable rows и сравнивает frozen expected value с observed value;
- `live_composite.scoreable/exact` никогда не включает deterministic rows или non-scoreable live rows.

Composite definition frozen: минимум две known/non-empty expected axes.

Historical v1 `composite 0/9` остаётся immutable audit fact: там были смешаны 7 live и 2 deterministic field-isolation rows. V2 не публикует all-row composite diagnostic и не переименовывает `0/9` в live metric.

`not_applicable`, runtime unavailable, transport и extraction errors исключаются из scope/exact/positive/composite **scoreable** denominators. Они не исчезают из total/completeness и имеют отдельные counts.

`overall_exit_code=1`, если есть semantic `FAIL`, `ERROR` observation или boundary `FAIL/ERROR`. Accepted `NOT_APPLICABLE` сам по себе не красит run. Config/spec failure остаётся CLI exit `2`.

## 7. Matrix v2 contract

V2 matrix:

- отличается от v1 только `schema_version`, `purpose` и exact `scoring_contract` v2;
- не добавляет observed/current output, route result, answer, authority decision или case-specific first-run facts;
- не объявляет заранее, какие case IDs станут `not_applicable`: applicability определяется только actual successful response shape и exact service route;
- сохраняет 39 unique ordered IDs и 30 ordered live turns;
- сохраняет все question/expected scope/status/evidence/session-boundary payloads byte-equivalent после удаления трёх разрешённых top-level differences;
- не читает first raw для генерации expectations.

Exact scoring contract обязан зафиксировать:

- per-field normalized semantic match;
- field status/stable error match;
- current frame is current turn only;
- legacy carry scored separately;
- one live call per turn, no retry;
- confidence descriptive only/no threshold;
- manual-contact taxonomy/reason;
- `not_applicable` excluded from scope/exact/positive/composite scoreable denominators but retained in total;
- live-only quality separation;
- authority false and parity source existing regression suites.

Exact `purpose` literal:

```text
Frozen A9 v2 patient-scope shadow expectations with live-only scoring and harness-owned manual-contact applicability.
```

Exact `scoring_contract` manifest (никаких дополнительных/отсутствующих keys):

```json
{
  "scope_match": "per_field_exact_normalized",
  "metadata_match": "per_field_status_and_stable_error",
  "observation_priority": [
    "transport_error",
    "scoreable_shadow",
    "runtime_not_available_or_degraded",
    "pre_planner_manual_contact",
    "extraction_error"
  ],
  "planner_availability_live_only": true,
  "manual_contact_not_applicable": {
    "service_route": "ingress_manual_contact",
    "status": "not_applicable",
    "reason": "pre_planner_manual_contact"
  },
  "not_applicable_retained_in_frozen_total": true,
  "not_applicable_excluded_from_scoreable_denominators": [
    "scope",
    "exact",
    "positive",
    "composite"
  ],
  "live_quality_separate_from_deterministic_fixtures": true,
  "current_frame_is_current_turn_only": true,
  "legacy_session_carry_scored_separately": true,
  "one_live_call_per_live_turn": true,
  "retry_failed_case": false,
  "confidence_is_descriptive_only": true,
  "confidence_pass_threshold": null,
  "authority_decision_allowed": false,
  "product_parity_source": "existing_regression_suites"
}
```

V2 contract test содержит собственные literal `purpose` и `scoring_contract` oracle, не импортирует их из harness и не вычисляет из matrix. Harness содержит отдельный literal manifest. Их равенство проверяется через загруженный frozen JSON, а не сравнением двух импортов одного production constant.

## 7.1 Exact scoreable-frame shape

Frame считается scoreable только если одновременно:

1. `turn_frame_shadow` — dict;
2. `turn_frame_shadow.patient_scope` — dict с exact keys `extent/jaw/stage/modifiers`;
3. каждое scope value принадлежит frozen allowed schema, modifiers — sorted unique allowed list;
4. `turn_frame_shadow.field_meta` — dict;
5. `field_meta.patient_scope` — dict с exact пятью keys: `container`, `extent`, `jaw`, `stage`, `modifiers`;
6. `container` meta — dict и содержит keys `status` и `error` (дополнительные штатные metadata keys разрешены):
   - status только `valid/defaulted/invalid`;
   - error только `null`, `patient_scope_invalid_type` или `patient_scope_extra_field`;
   - invariant `(status == "invalid") == (error is not null)` соблюдён;
7. каждый из четырёх axis meta — dict и **содержит keys** `status` и `error` (дополнительные штатные metadata keys разрешены);
8. axis status принадлежит `valid/defaulted/missing/invalid`;
9. axis error равен `null` или одному из exact stable values:
   - `patient_extent_invalid_type`;
   - `patient_extent_not_allowed`;
   - `patient_jaw_invalid_type`;
   - `patient_jaw_not_allowed`;
   - `patient_stage_invalid_type`;
   - `patient_stage_not_allowed`;
   - `patient_modifiers_invalid_type`;
   - `patient_modifier_not_allowed`;
10. для каждого axis invariant `(status == "invalid") == (error is not null)` соблюдён.

Container проверяется только как часть scoreable shape. Semantic comparison, positive/confusion и axis metrics используют только четыре axes; container не является пятой semantic axis и не входит в quality denominators.

Если key `turn_frame_shadow` присутствует, но эта shape-проверка не проходит, observation получает `ERROR / extraction_error`. Это относится и к exact manual-contact route: present malformed/partial frame никогда не становится `not_applicable` и не сравнивается как semantic FAIL.

## 8. Product firewall, privacy и non-goals

Запрещено:

- менять app/core/orchestration/resolver/session/contracts/ingress/product code;
- менять prompt/native parser/wiring;
- подключать patient scope к route, evidence, price, composer, CTA, UI или session state;
- создавать fake PlannerAttempt/TurnFrame/status;
- менять v1 matrix/harness/test/raw/summary/audit;
- читать первый raw для построения v2 expected;
- запускать live/LLM/widget;
- делать retry, второй classifier или case-specific production hack;
- менять authority;
- закрывать A9 parent, live re-audit, authority или legacy retirement.

V2 emitted rows/summary не содержат question, answer, history, sid/session, raw planner payload, exception text/path, full response, recommendation, diagnosis, price/service choice или PII. Harness не логирует response body. Errors используют только stable constants.

## 9. Deliverables / allowlist

### Governance до checker `✅`

1. `TASK.md` — единственный разрешённый diff.

После governance `✅`: отдельный commit/push только `TASK.md`.

### Eval/contract после governance

2. `evals/v5/demo/patient_scope_shadow_matrix_v2.json`;
3. `evals/v5/run_patient_scope_shadow_eval_v2.py`;
4. `tests/test_patient_scope_shadow_eval_v2_contract.py`.

### Roadmap только после final checker `✅`

5. `docs/STRANGLER_ROADMAP.md`.

Любой другой diff — STOP.

## 10. Required contract tests

Новый test module обязан проверять production v2 harness/helper напрямую, без mock helper и без network/LLM:

1. exact v2 matrix hash/schema/shape/order/counts и byte-equivalence case payloads с v1;
2. exact protected v1 harness/matrix/contract/raw hashes unchanged;
3. deterministic bridge + native field isolation дают `14/14 PASS`;
4. dependency-injected perfect fake run делает ровно 30 calls и выдаёт 34+10+5+1 rows;
5. два successful exact manual-contact responses без frame дают `NOT_APPLICABLE`, не ERROR/PASS;
6. perfect fake scoreable rows дают expected live-only totals: `30 total`, `28 scoreable`, `28 exact_complete`, `2 not_applicable`;
   `planner_availability = available 28 / not_applicable 2 / остальные четыре buckets 0`, сумма `30`;
7. positive axis denominators из frozen matrix равны first-audit invariants (`13/9/4/3`) и perfect fake даёт exact по каждому;
8. live composite frozen total `7`, perfect fake scoreable/exact `7/7`; historical all-row `9` не переиспользуется;
9. group-count arithmetic и availability buckets точны;
10. scoreable frame имеет приоритет над manual-contact taxonomy, включая overlap `scoreable frame + manual route + runtime not_available/degraded` → semantic comparison и `availability_status=available`;
11. runtime `not_available/degraded` имеют приоритет над helper и попадают в свои buckets;
12. request exception становится только transport error;
13. other missing/malformed frame становится extraction error;
    exact manual route + present malformed/partial frame также становится extraction error, не NA;
14. `NOT_APPLICABLE` не красит exit; FAIL/ERROR красит; config failure возвращает `2`;
15. boundary checks продолжают выполняться и влиять на exit;
16. output schema/prefixes frozen и recursive privacy scan зелёный;
17. v2 eval imports отсутствуют в production modules;
18. no skip/xfail/conditional PASS; fake endpoint возвращает только заранее построенные contract observations.
19. test-side purpose/scoring oracle literal и независим от harness constants; matrix case payload byte-equivalence проверяется против protected v1 JSON с удалением только трёх разрешённых top-level fields.

## 10.1 Protected literal hashes

- first A9 raw SHA256: `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`;
- v1 harness git blob: `2898ff1d56dba3319f4121158ba98e2879cdb579`;
- historical v1 contract test git blob: `c2ed5f0655ab8e1dddda1a865ab95c50ffc797b3`;
- v1 matrix git blob: `d459073bbf8767f7ff590ece2958f7aa8cb18b25`;
- native v2 fixture git blob: `c7458e4481489895320ea3de1dec1a81b8da5f50`.

Historical `tests/test_patient_scope_shadow_eval_contract.py` остаётся immutable target-red artifact прежнего implementation gap и не является current regression gate.

## 11. Targeted verification

Primary:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_patient_scope_shadow_eval_v2_contract.py tests/test_patient_scope_not_applicable_taxonomy.py -q
```

Новые v2 contract tests должны также покрыть deterministic native field-isolation path, поэтому старый target-red v1 module не запускается и не фильтруется через `-k` ради зелёного отчёта.

Full suite не обязателен: разрешённый diff isolated eval/spec/test/roadmap, runtime/product immutable. Если новый test обнаруживает необходимость runtime/v1 изменения — STOP и новая оценка scope.

Static checks:

```powershell
git diff --check
git diff --name-only
git diff -- app.py llm.py resolver.py session.py core contracts orchestration ingress_gate.py
git diff -- evals/v5/run_patient_scope_shadow_eval.py tests/test_patient_scope_shadow_eval_contract.py evals/v5/demo/patient_scope_shadow_matrix.json docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md
rg -n "patient_scope_shadow_eval_v2|patient_scope_availability_v2" app.py llm.py resolver.py session.py core contracts orchestration ingress_gate.py
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/run_patient_scope_shadow_eval.py
git hash-object tests/test_patient_scope_shadow_eval_contract.py
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object tests/fixtures/patient_scope_native_contract_a9_v2.json
```

## 12. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет versions/names, exact observation priority, denominators, matrix immutability, privacy, firewall и tests до code. После `✅` — отдельный governance commit/push.

### Checkpoint 2 — matrix/harness/tests

Создать только три allowlist files, выполнить targeted verification/static checks. Roadmap не менять, commit не делать.

### Checkpoint 3 — independent code review

Checker начинает с test diff, независимо пересчитывает live/positive/composite denominators, проверяет priority/error taxonomy/privacy/hashes и evidence tests.

### Checkpoint 4 — completion

Только после final checker `✅` обновить roadmap, повторить static checks, затем один completion commit и push в `codex/stage-a`.

## 13. Definition of Done

1. Governance checker принял design до code.
2. V2 matrix/harness names, schemas и hashes frozen.
3. Все 30 live turns и исходные semantic expectations сохранены без first-run fitting.
4. Manual contact честно `NOT_APPLICABLE`; priority contract доказан.
5. Live-only total/scoreable/exact/positive/composite denominators отделены от deterministic fixtures.
6. Completeness остаётся 30/30, `not_applicable` не исчезает из total.
7. Perfect dependency-injected run доказывает summary arithmetic без network/LLM.
8. Targeted tests и static checks зелёные; full suite обоснованно не запускался.
9. Runtime/product и все v1/first-raw artifacts неизменны exact hashes.
10. Live/LLM/widget не запускались; authority forbidden.
11. Final checker дал `✅` до roadmap/commit.
12. Roadmap закрывает только `A9 Frozen Matrix/Harness v2 Review`, оставляет A9 parent `[ ]` и называет следующим `A9 One-run Live Re-audit — permission required`.

После completion commit — STOP. Любой live re-audit начинается только после отдельного явного разрешения владельца и нового TASK/checker review.
