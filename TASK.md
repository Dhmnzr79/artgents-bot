# TASK — A7 Topic re-audit: PlannerAttempt shadow quality

Один активный `TASK.md` на один checkpoint. Подготовлен после принятого A7 Regression / Live Proof `9dda450`.

Правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`. Архитектурные источники: `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`, `docs/TOPIC_SHADOW_AUDIT_A6.md`, `docs/A7_REGRESSION_LIVE_PROOF.md`.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- A7 Shadow wiring: `620657d`.
- A7 Regression proof: `9dda450`.
- A6 frozen runner: `evals/v5/run_topic_shadow_eval.py`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Topic matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A7 regression raw hashes:
  - preservation `65E4046DDE4683CE8C6CCC92D89E8C1D7DD11B4FE03E5AC5EA702BCA8F506573`;
  - smoke `34D0FDB8FAA4315BAB9CAA28867ED90EBFEC9CC767C1238E8ABA96A2D84C562E`.

## 2. Цель

Повторить frozen 33-case topic matrix **один раз**, но измерить field-level shadow из `PlannerAttempt`:

```text
one plan_turn_attempt(question, None, "demo")
        ├─ shadow_frame.topic
        ├─ shadow_frame.field_meta.topic
        ├─ shadow_status
        └─ legacy_plan availability (descriptive only)
```

Главный вопрос re-audit:

> Стали ли topic-поля scoreable в тех случаях, где strict legacy TurnPlan раньше целиком исчезал из-за unrelated `aspects=[]`?

Это measurement-only checkpoint. Routing/evidence/composer/UI/authority не меняются.

## 3. Frozen ground truth

Не создавать новый spec и не менять:

- `evals/v5/demo/topic_shadow_matrix.json`;
- `evals/v5/demo/preservation.json`;
- client frontmatter/content.

Expected topic, questions, order, taxonomy и source-doc validation берутся из frozen A6 matrix. `shadow_frame.topic` является field-level представлением того же raw planner topic, поэтому ground truth применим; меняется только способность наблюдать поле при strict legacy failure.

## 4. Неподвижные инварианты

1. Ровно один `plan_turn_attempt()` на case, 33 calls total.
2. Нет `plan_turn()`, второго LLM, retry, selective rerun или classifier.
3. Один fresh call на каждый case в frozen order.
4. Old A6 runner/tests/spec/raw не меняются.
5. New runner не импортирует app/resolver/orchestration/HTTP/UI.
6. Product runtime не запускается.
7. Confidence descriptive only; threshold отсутствует.
8. `authority_decision_allowed=false` независимо от результата.
9. Exception/raw/question/answer/history не попадают в `A7_CASE` output.
10. Ошибка одного case учитывается в denominator 33; run продолжается без retry.
11. Config/hash/taxonomy/source error останавливает до LLM calls с exit 2.
12. Любой FAIL/ERROR после measurement даёт exit 1; только 33 PASS дают exit 0.

## 5. Строгий allowlist harness checkpoint

Разрешены только новые файлы:

1. `evals/v5/run_topic_shadow_attempt_eval.py`
2. `tests/test_topic_shadow_attempt_eval_contract.py`

Любой modified tracked file → ❌ и СТОП.

Особенно запрещено менять production, contracts, orchestration, old A6 harness/tests, frozen specs, TASK после governance commit, docs/audits, raw.

## 6. Reuse boundary

Новый runner может импортировать read-only helpers из `evals.v5.run_topic_shadow_eval`:

- frozen paths/hashes/taxonomy;
- `HarnessConfigError`;
- `load_and_validate_spec()`;
- normalization/confidence helpers или `build_summary()` при сохранении семантики.

Запрещено monkeypatch/менять A6 module state в production run. New summary обязан явно идентифицироваться как A7 attempt re-audit, даже если переиспользует A6 aggregation.

## 7. Case result contract

Каждая строка начинается `A7_CASE ` и содержит **ровно**:

```text
index
case_id
case_kind
expected_topic
observed_topic
topic_confidence
topic_field_status
topic_field_error
shadow_status
legacy_plan_available
status
reason
```

Никаких raw payload/question/exception fields.

## 8. Classification

### Attempt unavailable

| condition | status | reason |
|---|---|---|
| call raises | ERROR | `planner_exception` |
| `shadow_status=not_available` / no attempt shadow | ERROR | `planner_unavailable` |
| `shadow_status=degraded` | ERROR | `shadow_degraded` |

Exception text не выводится.

### Topic field

| FieldMeta status | semantics |
|---|---|
| `valid` | observed topic должен быть в taxonomy; confidence 0..1; exact comparison |
| `missing` | observed=None, confidence=0.0; scoreable null |
| `invalid` | ERROR `invalid_or_out_of_taxonomy`; stable `topic_field_error` разрешён |
| `defaulted` | ERROR `invalid_shadow_metadata` |

Дополнительные inconsistent frame/meta значения → ERROR `invalid_shadow_metadata`.

Exact observed==expected → PASS `exact_match`; валидное неравенство → FAIL `topic_mismatch`.

`partial` сам по себе **не ошибка**: если topic FieldMeta valid/missing, поле scoreable.

## 9. Summary contract

Одна строка `A7_SUMMARY ` после 33 cases. Обязательные поля:

- `measurement_id="a7_topic_shadow_attempt_reaudit"`;
- existing A6 exact-match/per-topic/ambiguous/confusion/confidence metrics;
- `total=33`, `passed`, `failed`, `errors`, `skipped=0`;
- `scoreable_count = passed + failed`;
- `shadow_status_counts` для `ok|partial|not_available|degraded`;
- `topic_field_status_counts` для `valid|missing|invalid|defaulted|unavailable`;
- `legacy_plan_available_count`;
- `planner_unavailable_count`;
- `invalid_or_out_of_taxonomy_count`;
- `authority_decision_allowed=false`.

Confusion sum = 33. Unavailable/degraded идут в technical unavailable column; invalid metadata — invalid column.

## 10. Exit/CLI

- no args only;
- unknown arg → stderr stable config error, exit 2, calls=0;
- preflight error → exit 2, calls=0;
- 33 PASS → exit 0;
- любой FAIL/ERROR → exit 1.

## 11. Обязательные unit tests

1. Old A6 harness/spec hashes unchanged.
2. Production default symbol = `plan_turn_attempt`, не wrapper.
3. Fake attempt called 33 times in frozen order.
4. Exactly one call per case; no retry.
5. A6 worked example `topic=doctors, aspects=[]`, partial + legacy None → scoreable PASS.
6. Missing topic + confidence 0 → scoreable null.
7. Partial topic mismatch → FAIL, не ERROR.
8. Invalid topic metadata → ERROR.
9. not_available/degraded/exception различимы.
10. valid shadow + legacy None scoreable; legacy availability descriptive.
11. Summary denominator/confusion/status counts exact.
12. Output case keys ровно 12; no leaks.
13. Config/hash/taxonomy/source failure до calls.
14. Unknown CLI arg exit 2 до calls.
15. No app/resolver/orchestration/http imports.
16. No skip/xfail/assert True/conditional PASS.
17. Negative tests возвращают конкретные reason strings.

## 12. Harness commands

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q tests/test_topic_shadow_attempt_eval_contract.py
.venv\codex312\Scripts\python.exe -m pytest -q tests/test_topic_shadow_eval_contract.py
.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_planner_attempt_contract.py
.venv\codex312\Scripts\python.exe -m py_compile evals/v5/run_topic_shadow_attempt_eval.py
.venv\codex312\Scripts\python.exe evals/v5/run_topic_shadow_attempt_eval.py --unexpected-argument
git diff --check
git status --short
git diff -- evals/v5/run_topic_shadow_eval.py tests/test_topic_shadow_eval_contract.py `
  evals/v5/demo/topic_shadow_matrix.json evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Live/LLM не запускать до checker `✅` и отдельного harness commit/push.

## 13. Harness review/commit

Checker начинает с test diff, проверяет functional negative cases и source firewall, сам запускает §12. При `✅` — отдельный commit двух новых файлов + push `codex/stage-a`.

## 14. Live preflight

Перед единственным run:

- clean tree;
- harness commit = HEAD;
- unit commands зелёные;
- frozen hashes/raw hashes совпадают;
- `eval_topic_shadow_a7_last.txt` и любые `eval_topic_shadow_a7_*` отсутствуют;
- `PYTHONIOENCODING=utf-8` для корректной Windows console serialization.

## 15. Единственный live run

```text
python evals/v5/run_topic_shadow_attempt_eval.py
```

Полный stdout/stderr + `A7_EXIT_CODE` сохранить в `eval_topic_shadow_a7_last.txt`.

Ровно один attempt. Retry/selective rerun запрещены независимо от результата.

## 16. Live interpretation

Run технически полный, если:

- 33 `A7_CASE` + 1 `A7_SUMMARY` + exit;
- indices/order exact;
- totals/confusion=33;
- skipped=0;
- raw целый и hash зафиксирован.

Quality sample:

- `errors=0` → все 33 scoreable;
- `errors>0` → технически неполный quality sample, но raw остаётся единственным честным результатом;
- FAIL — честный mismatch, не technical error;
- сравнить отдельно coverage (`scoreable/33`) и correctness (`PASS/scoreable`).

Никаких автоматических authority conclusions.

## 17. Audit doc

После run разрешён только новый:

- `docs/TOPIC_SHADOW_REAUDIT_A7.md`

Он содержит raw integrity, independent metrics, A6↔A7 coverage/correctness comparison, per-topic, ambiguous, statuses, legacy availability, confidence descriptive, errors/mismatches, line refs, console/logging limitations, доказано/не доказано. Затем independent Cursor doc↔raw review, отдельный docs commit/push.

## 18. Стоп-условия

СТОП, если нужен production/spec/old harness diff; второй call/retry; observed expectations после live; raw уже существует; run прерван; или partial предлагается подключить к product.

## 19. Definition of Done

A7 Topic re-audit завершён, когда новый attempt-aware harness принят checker, один 33-case live run сохранён без retry, audit честно разделяет coverage/correctness и сравнивает A6 с A7 без authority claims, checker принял doc↔raw, commits/push выполнены только в `codex/stage-a`.
