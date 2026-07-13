# TASK — A9 Patient-scope One-run Live Proof

Владелец явно разрешил **ровно один** A9 live proof без retry. Этот checkpoint выполняет один полный запуск frozen harness, сохраняет неизменённый raw и останавливается для независимого review.

Запрещено подгонять spec/harness/runtime, повторять красные cases, создавать второй raw или выбирать «лучший» результат.

Источники: `evals/v5/demo/patient_scope_shadow_matrix.json`, `evals/v5/run_patient_scope_shadow_eval.py`, `docs/PATIENT_SCOPE_DESIGN_A9.md`, `3f11857`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `3f11857 test: add A9 patient scope quality harness`;
- clean tracked tree до governance diff;
- owner authorization: one run, no retry.

Frozen:

```text
patient-scope matrix = d459073bbf8767f7ff590ece2958f7aa8cb18b25
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

Expected harness structure:

```text
34 A9_SCOPE_CASE
10 A9_SCOPE_TURN
5 A9_SCOPE_BOUNDARY
1 A9_SCOPE_SUMMARY
30 endpoint requests
```

Four deterministic field-isolation cases are intentionally target-red on current implementation. Therefore exit 1 is expected and is not permission to edit/retry.

## 2. Allowed state changes

Tracked files: **none** during live proof.

One gitignored raw artifact only:

```text
eval_patient_scope_a9_last.txt
```

Запрещены `_retry`, `_2`, `_fixed`, `_best`, per-case files и любые другие `eval_patient_scope_a9*.txt`.

## 3. Pre-run gate — all must pass before live

1. `git status --short` empty.
2. HEAD = отдельный governance-коммит этого TASK; его parent = `3f11857`.
3. Matrix/protected hashes exact.
4. A7 raw SHA256 exact.
5. No `eval_patient_scope_a9*.txt` exists.
6. New contract suite = 32 passed, 0 skipped.
7. `py_compile` runner/test OK.
8. CLI unknown arg = exit 2 and creates no raw.
9. Runner/spec/runtime diff empty.
10. PowerShell version recorded; capture uses .NET `StreamWriter` with explicit UTF-8 without BOM (not version-dependent `Tee-Object` defaults).

Если любой gate fail → live не запускать, `❓`/СТОП.

## 4. Exact one-run command

Запуск выполняется только из repository root, только один раз:

```powershell
$raw = 'eval_patient_scope_a9_last.txt'
$env:E2E_USE_TEST_CLIENT = '1'
$env:TURN_PLANNER_ON = '1'
$env:CLIENT_ID = 'demo'
$env:PYTHONIOENCODING = 'utf-8'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$writer = New-Object System.IO.StreamWriter($raw, $false, $utf8NoBom)
$writer.AutoFlush = $true
$exitState = [pscustomobject]@{ Code = $null }

try {
  & {
    & .\.venv\codex312\Scripts\python.exe evals/v5/run_patient_scope_shadow_eval.py
    $exitState.Code = $LASTEXITCODE
  } 2>&1 | ForEach-Object {
    $line = [string]$_
    $writer.WriteLine($line)
    Write-Output $line
  }

  if ($null -eq $exitState.Code) {
    throw 'A9 runner exit code was not captured'
  }
  $a9Exit = [int]$exitState.Code
  $writer.WriteLine("A9_SCOPE_EXIT_CODE=$a9Exit")
}
finally {
  $writer.Dispose()
}

Write-Output "A9_SCOPE_CAPTURED_EXIT=$a9Exit"
```

Нельзя запускать runner до этой команды или после неё. Нельзя запускать отдельно один case.

Raw создаётся как UTF-8 without BOM одним `StreamWriter`; тот же writer дописывает exit-marker. После запуска raw нельзя переписывать/нормализовать. SHA256 считается по фактическим bytes.

## 5. During run

- attempts=1;
- no retry on timeout/error/red result;
- no interruption unless process irrecoverably hangs beyond configured endpoint timeouts;
- no code/spec/test edits;
- no parallel eval/LLM calls;
- console output не редактируется до raw;
- internal LLM-call count может быть больше 30, потому что измеряется full endpoint pipeline.

## 6. Raw integrity checks — read-only

После единственного run:

1. Record path/size/SHA256; verify UTF-8 without BOM decodes strictly.
2. Exactly one `eval_patient_scope_a9*.txt`.
3. Exactly 34 `A9_SCOPE_CASE` lines.
4. Exactly 10 `A9_SCOPE_TURN` lines.
5. Exactly 5 `A9_SCOPE_BOUNDARY` lines.
6. Exactly 1 `A9_SCOPE_SUMMARY` line.
7. Exactly 1 `A9_SCOPE_EXIT_CODE=` line at end.
8. Case indices 1..34; no duplicate/missing.
9. Scenario/turn order matches frozen matrix.
10. Summary JSON parses.
11. `executed_live_calls=30` and `planned_live_calls=30`.
12. Group totals/sums exact.
13. Exit marker matches summary `overall_exit_code`.

Read-only parser may be inline; do not create helper files.

## 7. Independent metric recalculation

Пересчитать из 34+10+5 result lines, не доверяя summary:

- PASS/FAIL/ERROR separately for bridge, field_isolation, single_turn, multi_turn, boundaries;
- bridge exact count;
- field target-red count;
- planner availability/errors separate from semantic mismatches;
- per-axis scoreable/exact and confusion;
- field status counts;
- composite total/exact;
- five boundary outcomes individually;
- endpoint execution count;
- privacy: no question/raw/answer/history/sid/exception text in result JSONL.

Встроенный summary сравнить с independent calculation. Расхождение → `❌`, no rerun.

## 8. Interpretation

Full quality sample технически пригоден только если:

```text
executed_live_calls = 30
all 44 scope results present
all 5 boundary results present
no transport/config/parser errors
```

Semantic FAIL допустим и является измерением. ERROR/unavailable не превращается в mismatch и не исключается из denominator.

Отдельно сообщить:

- сколько current results scoreable;
- какие axes/cases target-red;
- какие gaps вызваны scalar bridge;
- какие boundary semantics не выполняются;
- что один run не калибрует confidence и не разрешает authority.

## 9. Post-run repository checks

```powershell
git status --short
git diff --check
git diff -- evals/v5/demo/patient_scope_shadow_matrix.json evals/v5/run_patient_scope_shadow_eval.py tests/test_patient_scope_shadow_eval_contract.py
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Tracked tree должен быть clean; raw gitignored и не staged.

## 10. Исполнительский отчёт

Обязателен:

1. pre-run gate;
2. exact command and attempts=1;
3. captured exit;
4. raw path/size/SHA256/encoding;
5. line/order/integrity checks;
6. independent metrics and summary comparison;
7. all semantic/error/boundary failures;
8. privacy result;
9. post-run hashes/git;
10. live/LLM note;
11. no retry/no edits;
12. СТОП для independent raw checker.

## 11. Checker review after run

Checker не запускает runner/live/LLM. Он:

1. independently hashes raw;
2. confirms one artifact/one attempt;
3. parses all result lines;
4. verifies frozen order/counts;
5. independently recalculates metrics;
6. separates FAIL from ERROR;
7. verifies privacy;
8. verifies hashes/clean tree;
9. gives:
   - `✅` if integrity complete and calculations honest;
   - `❓` if sample technically incomplete due unavailable/errors without tampering;
   - `❌` for integrity drift, rerun, edits, mismatch in calculations or privacy leak.

## 12. Definition of Done

1. Governance TASK approved and committed before live.
2. Pre-run gate passed.
3. Exactly one runner execution.
4. Exactly one immutable raw artifact.
5. 34+10+5+1 result structure complete.
6. Independent metrics match summary.
7. No protected/tracked diff.
8. No retry/resnapshot.
9. Checker review completed.
10. Authority decision remains separate.

После raw review — СТОП. Не менять prompt/runtime и не запускать второй sample.
