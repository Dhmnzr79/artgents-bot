# TASK — A9 Manual-contact `not_applicable` Taxonomy

Один активный `TASK.md` на один checkpoint. Реализовать отдельную harness-owned pure taxonomy для successful pre-planner `ingress_manual_contact`: отсутствие `TurnFrame` должно классифицироваться как `not_applicable / pre_planner_manual_contact`, а не как transport failure или fake unknown frame.

Checkpoint eval/unit-only, no live. Runtime/product, v1 harness/raw и patient-scope authority не меняются.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `5b004db test: prove A9 native shadow wiring firewall`;
- HEAD совпадает с `origin/codex/stage-a`; working tree до governance edit был clean, текущий разрешённый diff — только `TASK.md`;
- выбранный design: `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`, §9 и §11.3;
- observed audit gap: `docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`, §10–11;
- current v1 harness: `evals/v5/run_patient_scope_shadow_eval.py`;
- current v1 contract tests: `tests/test_patient_scope_shadow_eval_contract.py`;
- первый A9 raw immutable, один attempt, no retry;
- live-positive exact первого raw остаётся `0` по `extent/jaw/stage/modifiers`, composite `0/9`;
- product firewall сохранён, authority запрещена;
- local demo, production-клиентов нет.

Фактический data flow:

```text
pre_resolver_turn
  -> ingress route != normal
  -> service_reply / meta.service_route=ingress_manual_contact
  -> resolver/planner не вызывается
  -> PlannerAttempt и turn_frame_shadow отсутствуют по архитектуре
```

Поэтому отсутствие frame на этом пути — неприменимость измерения, а не semantic unknown и не transport error.

## 2. Решение до code

Создать маленький versioned eval helper, который читает только успешный response dict:

```text
evals/v5/patient_scope_availability_v2.py
```

Он не является новым runtime contract и пока не подключается к full harness. Следующий checkpoint `A9 Frozen Matrix/Harness v2 Review` интегрирует helper в новый versioned harness/spec до live.

Current v1 harness, matrix, raw и summary не переписываются. Runtime не получает fake `turn_frame_shadow_status=not_applicable` и не создаёт all-unknown frame.

## 3. Exact classification contract

Public pure helper:

```python
classify_manual_contact_not_applicable(response: dict[str, Any]) -> tuple[str, str] | None
```

Exact positive result:

```python
("not_applicable", "pre_planner_manual_contact")
```

Helper возвращает positive result только если одновременно:

1. `response` — dict;
2. `response["meta"]` — dict;
3. normalized `meta.service_route` (`strip().lower()`) exact `ingress_manual_contact`;
4. key `meta.metadata_first` либо полностью отсутствует, либо присутствует как dict;
5. если `metadata_first` — dict, exact key `turn_frame_shadow` полностью отсутствует;
6. exact status `meta.metadata_first.turn_frame_shadow_status` не равен normalized `not_available` или `degraded`.

Exact sentinel/shape table:

| Shape | Result helper |
|---|---|
| key `metadata_first` отсутствует | eligible для positive при exact route |
| `metadata_first` present dict, включая `{}` | inspect status/frame keys |
| `metadata_first` present `null`/list/string/любой non-dict | `None` |
| в metadata dict key `turn_frame_shadow` отсутствует | eligible для positive |
| key `turn_frame_shadow` present с любым value: valid/malformed dict, `{}`, `null`, list, scalar | `None` |
| exact status `not_available` или `degraded` | `None` |

Проверяется именно presence key, не truthiness. Empty/malformed present frame не переименовывается в `not_applicable`: caller сохраняет существующий semantic/extraction error path.

Во всех других случаях возвращается `None`; helper не назначает generic error bucket и не заменяет caller ordering.

Priority contract будущего harness v2:

```text
request exception                              -> transport_error
scoreable shadow frame                         -> semantic comparison
runtime status not_available / degraded        -> exact runtime bucket
exact ingress_manual_contact + allowed metadata shape
  + key turn_frame_shadow absent                -> not_applicable / pre_planner_manual_contact
other missing/malformed frame                  -> existing extraction error
```

Transport exception находится выше helper и не может быть превращён в `not_applicable`, потому что successful response отсутствует.

## 4. Narrow scope / anti-expansion

Positive classification запрещена для:

- `ingress_hard_stop_non_target`;
- `ingress_not_offered_policy`;
- `ingress_service_not_offered`;
- `ingress_normal`;
- noise/promo/ref/lead и любых других short-circuit `service_route`, кроме exact `ingress_manual_contact`;
- одного `meta.ingress_route=manual_contact` без exact `meta.service_route`;
- near-match, substring или произвольного route с `manual_contact` внутри;
- response с scoreable shadow frame;
- response с runtime status `not_available` или `degraded`.

Расширение taxonomy требует отдельного inventory/spec checkpoint.

## 5. Privacy / purity

Helper обязан:

- не мутировать input;
- не читать question, answer, history, sid, session, raw payload или exception;
- не возвращать input values;
- возвращать только две stable constants либо `None`;
- не логировать;
- не импортировать Flask, app, session, planner, resolver, contracts или client data;
- не выполнять I/O, network, LLM или environment reads.

Разрешены только стандартные typing/data-shape imports, если нужны.

## 6. Deliverables и allowlist

### Governance

1. `TASK.md`

До governance checker `✅` разрешён только этот файл. После `✅` — отдельный governance commit/push.

### Eval/unit после governance

2. `evals/v5/patient_scope_availability_v2.py` — новый pure helper.
3. `tests/test_patient_scope_not_applicable_taxonomy.py` — новый unit/contract test.

### Roadmap только после final checker `✅`

4. `docs/STRANGLER_ROADMAP.md`

После final `✅`:

- закрыть только `Manual-contact not_applicable taxonomy`;
- оставить A9 parent `[ ]`, authority `Forbidden`;
- назвать следующим `A9 Frozen Matrix/Harness v2 Review`;
- объяснить владельцу: это исправляет только честность будущего измерения, не ответы бота.

Любой другой файл — STOP.

## 7. Required tests

Новый test module обязан проверить production helper напрямую:

1. exact `ingress_manual_contact`, key `metadata_first` отсутствует → positive tuple;
2. exact route, `metadata_first={}` или dict без key `turn_frame_shadow` → positive tuple;
3. present non-dict/null `metadata_first` → `None`;
4. present `turn_frame_shadow` с каждым shape: valid dict, malformed/empty dict, null, list, scalar → `None`;
5. exact nested status path `turn_frame_shadow_status=not_available/degraded` → `None`;
6. route normalization допускает только whitespace/case normalization;
7. parameterized exact non-applicable denylist из §4 → `None`;
8. `meta.ingress_route=manual_contact` без `service_route` → `None`;
9. near-match/substrings → `None`;
10. non-dict response/meta shapes fail closed → `None`;
11. input deep-equal после вызова;
12. question/answer/history/sid/raw/exception secrets не появляются в result/repr;
13. source/AST imports не содержат runtime/product dependencies;
14. production modules не импортируют новый eval helper;
15. v1 harness/matrix/raw hashes unchanged.

Запрещены conditional PASS, skip/xfail, мок helper-а, подмена ожидаемого текущим output и чтение первого raw для генерации expected.

## 8. Protected artifacts / versioning

После governance immutable:

- `TASK.md`;
- `evals/v5/run_patient_scope_shadow_eval.py`;
- `tests/test_patient_scope_shadow_eval_contract.py`;
- `evals/v5/demo/patient_scope_shadow_matrix.json`;
- `eval_patient_scope_a9_last.txt`;
- `docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`;
- native v2 fixture/doc;
- A6/A7/A8 frozen artifacts.

Protected hashes:

- first A9 raw SHA256: `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`;
- v1 matrix git blob: `d459073bbf8767f7ff590ece2958f7aa8cb18b25`;
- native v2 fixture git blob: `c7458e4481489895320ea3de1dec1a81b8da5f50`;
- v1 harness git blob: `2898ff1d56dba3319f4121158ba98e2879cdb579`.

Новый helper использует suffix `v2`, но сам по себе не объявляет full harness v2 frozen/ready и не разрешает live.

## 9. Product firewall / non-goals

Запрещено:

- менять runtime/product code, ingress routing или response payload;
- создавать fake PlannerAttempt/TurnFrame/status для early boundary;
- подключать helper из app/core/orchestration/resolver/session;
- менять v1 harness, matrix, tests, raw, summary или audit;
- интегрировать helper в live harness в этом checkpoint;
- менять denominators/summary schema сейчас;
- расширять `not_applicable` за exact manual-contact route;
- менять native parser/prompt/wiring;
- добавлять LLM call/retry/classifier;
- запускать live/LLM/widget;
- менять authority;
- закрывать matrix/harness v2, live, authority, legacy retirement или A9 parent.

## 10. Targeted tests

Primary taxonomy + frozen v1 regression:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest tests/test_patient_scope_not_applicable_taxonomy.py tests/test_patient_scope_shadow_eval_contract.py -q
```

Full suite не обязателен: два новых isolated eval/unit files, production и v1 artifacts immutable. Если test обнаруживает необходимость runtime/v1 change — СТОП и новая оценка scope.

## 11. Static checks

```powershell
git diff --check
git diff --name-only
git diff -- app.py llm.py resolver.py session.py core contracts orchestration ingress_gate.py
git diff -- evals/v5/run_patient_scope_shadow_eval.py tests/test_patient_scope_shadow_eval_contract.py evals/v5/demo/patient_scope_shadow_matrix.json
rg -n "patient_scope_availability_v2" app.py llm.py resolver.py session.py core contracts orchestration ingress_gate.py
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/run_patient_scope_shadow_eval.py
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object tests/fixtures/patient_scope_native_contract_a9_v2.json
```

Expected implementation diff до roadmap: только два new files. Runtime/product/v1 diff empty.

## 12. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет exact taxonomy, priority, harness-owned ownership, anti-expansion, versioning и test sufficiency до code. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — taxonomy helper/tests

Создать только два allowlist files. Выполнить targeted tests/static checks. Roadmap не менять, commit не делать.

### Checkpoint 3 — independent code review

Checker начинает с test diff, сверяет exact positive/negative cases, purity/privacy, imports, v1 immutability и test evidence.

### Checkpoint 4 — completion

Только после checker `✅` обновить roadmap, повторить static checks, затем один completion commit и push в `codex/stage-a`.

## 13. Definition of Done

1. Governance checker принял helper-only решение до code.
2. Exact successful `ingress_manual_contact` без frame возвращает только `not_applicable / pre_planner_manual_contact`.
3. Scoreable frame и runtime `not_available/degraded` имеют приоритет.
4. Все другие routes/shapes fail closed в `None`; taxonomy не расширена.
5. Helper pure/privacy-safe и не мутирует input.
6. Runtime/product не импортирует helper и не меняется.
7. V1 harness/matrix/tests/raw/summary/audit неизменны и имеют exact hashes.
8. Targeted tests зелёные; full suite обоснованно не запускался.
9. Live/LLM/widget не запускались; authority forbidden.
10. Final checker дал `✅` до roadmap/commit.
11. Roadmap закрывает только taxonomy и называет следующим frozen matrix/harness v2 review.

После completion commit — СТОП. `A9 Frozen Matrix/Harness v2 Review` начинается только с нового TASK и governance review.
