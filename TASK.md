# TASK — A7 Regression / Live Proof

Один активный `TASK.md` на один checkpoint. Подготовлен Архитектором после принятого A7 Shadow Wiring `620657d`.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`. Архитектурная опора: `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- A7 Planner split: `a6318a8`.
- A7 Shadow wiring: `620657d`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Topic matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A5 post-hardening preservation raw SHA256: `BDDDA1E686214C33B4C2563A0271FF01F381C18DC89C67911AAB449D892A3290`.
- A5 post-hardening smoke raw SHA256: `57F36CE829F7CC54842EB109DC928D63B7EE3534CC29ACCB08DE917F5A2ABEBA`.
- Рабочее дерево до реализации чистое после отдельного governance-коммита этого файла.

## 2. Цель

Доказать две разные вещи и не смешивать их:

1. **Детерминированно:** семь A6 `aspects=[]` путей сохраняют прежний product fail-open, а partial frame остаётся только telemetry.
2. **Одним live proof:** после runtime wiring не изменились frozen smoke/preservation результаты.

Этот checkpoint не измеряет заново качество topic всей матрицы — это отдельный A7 Topic re-audit.

## 3. Почему без нового live harness

- Семь A6 case ids уже заморожены в `evals/v5/demo/topic_shadow_matrix.json`.
- Product acceptance уже заморожен в `smoke.json` и `preservation.json`.
- Новый harness/spec создал бы второй источник ожиданий и лишние LLM-вызовы.
- Seven-path proof делается интеграционным test-client тестом с deterministic `PlannerAttempt`; smoke/preservation проверяются существующим runner без semantic changes.

## 4. Неподвижные инварианты

1. Production-код не меняется.
2. Frozen specs/harness не меняются.
3. A6 raw и A5 raw не перезаписываются.
4. Seven-path тест не вызывает LLM/network и не мокает проверяемый `run_resolver_turn`.
5. Для каждого из семи кейсов `plan_turn_attempt` вызывается ровно один раз, `resolve_with_fallback` — ровно один раз.
6. Partial topic/null остаётся в ctx, но product outcome берётся только из fallback `DecisionFrame`.
7. Нет retry/resnapshot/подмены ожидаемого текущим output.
8. Live: ровно один smoke run и один preservation run; failed case не перезапускать отдельно.
9. Live raw сохраняется под новыми именами и не коммитится.
10. Красный frozen preservation baseline не «чинить» и не считать новой регрессией, если вектор остался прежним.

## 5. Seven frozen paths

Из `topic_shadow_matrix.json` использовать только:

| id | expected topic |
|---|---|
| `topic_a6_04_doctors_overview` | `doctors` |
| `topic_a6_05_doctors_named` | `doctors` |
| `topic_a6_06_doctors_implants` | `doctors` |
| `topic_a6_09_extraction_aftercare` | `extraction` |
| `topic_a6_28_null_general_price` | `null` |
| `topic_a6_30_null_booking` | `null` |
| `topic_a6_31_null_pain` | `null` |

Test обязан читать questions/topics из frozen JSON, а не дублировать их вручную.

Для replay:

```text
raw aspects=[]
legacy_plan=None
shadow_status=partial
fallback decision = отдельный product sentinel
```

Проверить для каждого case:

- один attempt call с exact question/client;
- один resolver fallback;
- `turn_planner_used=false`, `resolver_used=true`;
- ctx `turn_frame_shadow_status=partial`;
- ctx topic равен expected topic или `None`;
- aspects error = `aspects_empty`;
- product decision/intent/service topic/scope не берутся из shadow topic;
- no publish/legacy wrapper call;
- recorder return не участвует в outcome.

## 6. Строгий allowlist до live

Разрешён только:

1. `tests/test_turn_frame_shadow.py` — один параметризованный seven-path regression test и узкие helpers.

Любой другой diff → ❌ и СТОП.

Особенно запрещено менять production, existing assertions, TASK после governance commit, specs/harness, client content, pricebook, marketing.

## 7. Unit checkpoint

Команды исполнителя и checker:

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_shadow.py `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_from_raw.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_contract.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py

git diff --check
git diff --name-only
git diff -- production protected paths
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Live/LLM на unit checkpoint не запускать. После checker `✅` — отдельный test commit.

## 8. Live preflight

Перед первым live call:

- clean tree;
- test commit является HEAD;
- unit suites зелёные;
- frozen hashes совпадают;
- старые raw hashes совпадают;
- новые файлы отсутствуют:
  - `eval_a7_regression_preservation_last.txt`
  - `eval_a7_regression_smoke_last.txt`

Если любой gate не пройден → live не запускать.

## 9. Единственные разрешённые live runs

Порядок:

1. preservation — один run;
2. smoke — один run.

Оба через существующий `evals/v5/run_demo_eval.py`, `E2E_USE_TEST_CLIENT=1`, вывод целиком сохранить в новые raw-файлы вместе с exit code.

Запрещено:

- retry;
- selective case rerun;
- исправлять код/spec между runs;
- перезаписывать raw;
- запускать A6 topic harness.

## 10. Frozen live acceptance

### Preservation

Ожидается прежний frozen baseline, не 6/6:

| case | expected |
|---|---|
| 01 contacts | PASS |
| 02 osseointegration | FAIL: прежний answer/evidence target-red |
| 03 comparison | FAIL: прежний evidence target-red |
| 04 classic price | PASS |
| 05 All-on-4 price | FAIL: прежний quick-reply target-red |
| 06 marketing absence | PASS |

Итого: `passed=3, failed=3, errors=0, skipped=0`, exit 1.

Если кейс меняет статус или появляется новый reason/error → ❌ regression investigation, без retry.

### Smoke

Ожидается: `24/24 PASS`, `errors=0`, `skipped=0`, exit 0.

Любой FAIL/ERROR → ❌ regression investigation, без retry.

## 11. Live audit document

После единственных runs разрешено создать только:

- `docs/A7_REGRESSION_LIVE_PROOF.md`

Документ обязан содержать:

- commit/branch/environment;
- raw filenames, sizes, SHA256, attempts=1;
- exact preservation per-case vector и reasons;
- smoke summary;
- сравнение с A5 baseline: unchanged/changed;
- errors/skipped/timeouts/logging errors;
- frozen hashes после run;
- честное разделение unit replay и live proof;
- утверждение, что topic quality/authority не оценивались;
- line refs в raw;
- следующий шаг только A7 Topic re-audit.

Нельзя включать raw, question/history/answer dumps в git.

## 12. Review/commit sequence

1. Governance commit TASK — до работы.
2. Seven-path test implementation.
3. Cursor checker unit review.
4. При `✅`: отдельный test commit + push `codex/stage-a`.
5. Live preflight и два единственных runs.
6. Audit doc, independent checker doc↔raw review.
7. При `✅`: отдельный docs commit + push `codex/stage-a`.

## 13. Стоп-условия

СТОП, если:

- нужен production/spec/harness diff;
- seven-path replay требует тематического production workaround;
- unit test вызывает реальный LLM;
- live output отличается от frozen vector;
- один из raw-файлов уже существует;
- run прерван или неполон;
- кажется нужным retry;
- требуется менять acceptance после просмотра live.

## 14. Definition of Done

A7 Regression / Live Proof завершён, когда семь frozen fail-open paths детерминированно доказывают telemetry-only wiring, checker принял unit test, один preservation и один smoke live run воспроизводят frozen product baseline, два новых raw сохранены без перезаписи, audit точно отражает raw, checker принял audit, commits/push сделаны только в `codex/stage-a`.
