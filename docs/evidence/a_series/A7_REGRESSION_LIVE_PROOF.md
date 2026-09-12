# A7 Regression / Live Proof

**Статус:** готово для независимого doc↔raw review
**Ветка:** `codex/stage-a`
**Проверяемый HEAD:** `05c8110 test: replay A6 partial paths through product fallback`
**Дата run:** 2026-07-13
**Authority:** не передавалась; topic quality в этом checkpoint не измерялась

---

## 1. Что проверялось

Checkpoint разделён на два независимых доказательства:

1. Seven-path unit replay: семь frozen A6 `aspects=[]` путей проходят через реальный `run_resolver_turn`; partial frame остаётся telemetry, product использует прежний fallback.
2. Live product regression: существующие frozen `preservation` и `smoke` suites запущены по одному разу после A7 Shadow Wiring.

Новый topic quality harness не запускался. A6 raw не перезаписывался.

## 2. Unit replay

Governance: `f5b4079`. Test commit: `05c8110`.

Тест читает questions/topics непосредственно из `evals/v5/demo/topic_shadow_matrix.json` для семи ids:

- `topic_a6_04_doctors_overview`
- `topic_a6_05_doctors_named`
- `topic_a6_06_doctors_implants`
- `topic_a6_09_extraction_aftercare`
- `topic_a6_28_null_general_price`
- `topic_a6_30_null_booking`
- `topic_a6_31_null_pain`

Для каждого пути доказано:

- `plan_turn_attempt` вызван один раз;
- legacy wrapper и publish не вызываются;
- `resolve_with_fallback` вызван один раз;
- `turn_planner_used=false`, `resolver_used=true`;
- ctx сохраняет `partial`, expected topic/null и `aspects_empty`;
- outcome равен fallback `DecisionFrame`, а не shadow topic.

Независимый Cursor checker: `✅`. Полный gate: **227 passed, 0 failed, 0 skipped**.

## 3. Live методика

Preflight:

- clean tree;
- HEAD = `05c8110`;
- matrix/preservation и старые raw hashes совпали;
- новые A7 raw отсутствовали;
- `E2E_USE_TEST_CLIENT=1`;
- существующий `evals/v5/run_demo_eval.py` без изменений.

Разрешённый порядок выполнен:

1. preservation — один attempt, без retry;
2. smoke — один attempt, без retry.

Между runs код, tests, specs и harness не менялись. Selective rerun не выполнялся.

## 4. Raw integrity

| Raw | Attempts | Size | Lines | SHA256 | Exit ref |
|---|---:|---:|---:|---|---|
| `eval_a7_regression_preservation_last.txt` | 1 | 235684 bytes | 251 | `65E4046DDE4683CE8C6CCC92D89E8C1D7DD11B4FE03E5AC5EA702BCA8F506573` | L251: `A7_PRESERVATION_EXIT_CODE=1` |
| `eval_a7_regression_smoke_last.txt` | 1 | 756214 bytes | 686 | `34D0FDB8FAA4315BAB9CAA28867ED90EBFEC9CC767C1238E8ABA96A2D84C562E` | L686: `A7_SMOKE_EXIT_CODE=0` |

Raw-файлы gitignored, не staged и не входят в commit.

## 5. Preservation result

Итог: **passed=3, failed=3, errors=0, skipped=0, total=6**, exit 1. Summary: raw L244.

| Case | Result | Evidence |
|---|---|---|
| `preservation_01_contacts_address` | PASS | raw L237 |
| `preservation_02_osseointegration` | FAIL | raw L238: прежний missing `26 лет` target-red |
| `preservation_03_all_on_4_vs_all_on_6` | FAIL | raw L239: прежний composer/evidence target-red |
| `preservation_04_classic_one_tooth_price` | PASS | raw L240 |
| `preservation_05_all_on_4_jaw_price` | FAIL | raw L241: прежний `price_quick_reply_count got=0 want=2` target-red |
| `preservation_06_marketing_optional_overlay` | PASS | raw L242 |

Вектор полностью совпал с frozen A5 post-hardening baseline: `PASS, FAIL, FAIL, PASS, FAIL, PASS`. Новых FAIL/ERROR нет.

## 6. Smoke result

Итог: **passed=24, failed=0, errors=0, skipped=0, total=24**, exit 0. Summary: raw L678.

- Все 24 cases: PASS, raw L653–L676.
- STRONG: 17/17.
- MEDIUM: 7/7.
- Product smoke baseline после wiring не изменился.

## 7. Сравнение с frozen baseline

| Gate | Frozen expectation | A7 result | Verdict |
|---|---|---|---|
| Preservation | 3/6; FAIL 02/03/05 | 3/6; FAIL 02/03/05 с теми же reason-классами | unchanged |
| Smoke | 24/24 | 24/24 | unchanged |
| Eval errors | 0 | 0 | unchanged |
| Skipped | 0 | 0 | unchanged |
| Retry | 0 | 0 | compliant |

Это доказывает отсутствие наблюдаемой product regression в frozen suites. Это не доказывает корректность всех возможных вопросов и не делает TurnFrame authority-ready.

## 8. Console logging limitation

Raw содержит Windows console logging errors при попытке CP1251 sink напечатать символ `₽`:

- preservation: 2 `UnicodeEncodeError` traceback — raw L99 и L167 (logging markers L84/L88/L158);
- smoke: 4 `UnicodeEncodeError` traceback — raw L275, L343, L412 и L481 (logging markers L260/L264/L334/L403/L472).

PowerShell дополнительно оборачивает stderr native process строкой `NativeCommandError`, поэтому число текстовых `--- Logging error ---` markers больше числа самих `UnicodeEncodeError` (3/2 и 5/4).

Ограничение записано честно:

- это ошибки console logging sink, не eval case errors;
- оба runner полностью завершились и напечатали summary/exit;
- `errors=0`, `skipped=0` в обоих suites;
- product status vector совпал;
- retry для получения «красивого» raw не выполнялся;
- код/encoding после просмотра raw не менялись.

Исправление Windows logging encoding не входит в A7 и требует отдельного checkpoint, если владельцу нужна чистая консольная телеметрия.

## 9. Frozen evidence after run

| Artifact | Verified hash |
|---|---|
| A6 raw SHA256 | `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A` |
| Topic matrix git hash | `dc356c9c738fb80a10cf0035508d7e8c8247979d` |
| Preservation git hash | `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5` |
| A5 preservation post-hardening SHA256 | `BDDDA1E686214C33B4C2563A0271FF01F381C18DC89C67911AAB449D892A3290` |
| A5 smoke post-hardening SHA256 | `57F36CE829F7CC54842EB109DC928D63B7EE3534CC29ACCB08DE917F5A2ABEBA` |

Tracked working tree после run оставался clean; единственный новый tracked candidate — этот audit-doc.

## 10. Что доказано

- Семь known `aspects=[]` путей сохраняют legacy fallback в deterministic runtime replay.
- Partial TurnFrame публикуется только в telemetry.
- A7 Shadow Wiring не изменил frozen preservation vector.
- Smoke сохранился 24/24.
- Нет eval errors, skipped cases, retry или resnapshot.

## 11. Что не доказано

- Topic quality на полной 33-case matrix не переизмерялось.
- Confidence не калибрована.
- TurnFrame не готов к product authority.
- Старые preservation target-red 02/03/05 не исправлены и не должны считаться закрытыми.
- Console logging encoding не исправлена.

## 12. Следующий checkpoint

Следующий архитектурный шаг — **A7 Topic re-audit** с отдельным governance, новым attempt-aware quality raw и сохранением первого A6 raw. Этот документ не разрешает запуск re-audit, изменение authority или исправление console encoding.
