# D2 — этап 4: единый mixed response

Статус: реализация разрешена. База: `7297cd7`
(`feat(d2): materialize scoped ordered prices`). Работа выполняется в
`C:\Users\denis\.codex\worktrees\27e1\artgents-bot` на текущей ветке
`codex/d2-stage1-contract`.

## Проверенная исходная позиция

- `origin/main` и merge-base: `141ce91`.
- Foreign WIP: `data/`, `.pytest_tmp_stage2_debug.sqlite` и
  `.pytest_tmp_stage2_debug2.sqlite`; не менять, не удалять, не stage.
- Staging пуст до этапа. `git diff --check` чист до правок.

## Цель и точная граница

Один `run_d2_dialogue_turn` сохраняет один frozen plan для content + price,
content + exact clinic policy или content + contact. Цена, policy и contact
берутся только из bound tenant snapshot; пригодная FullContext prose остаётся
полностью видимой. JSON `/ask`, SSE `/ask/stream` и реальный widget harness
получают тот же сохранённый result/UI; после freeze нет нового selection,
materialization или renderer pass.

Первой materialize только первая price part; последующие price part остаются
явно deferred. Независимая unavailable price part не стирает доступные content
и contact части. Для policy в mixed plan допустим только exact typed authored
`policy_id`; новая видимая фраза для отсутствующей policy не вводится.

## Точный write allowlist

```text
contracts/response_plan.py
core/d2_dialogue.py
core/d2_snapshot_sources.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/response_ui_projection.py
tests/test_d2_stage4_mixed_response.py
tests/test_d2_http_contract.py
tests/test_d2_http_scenarios.py
tests/test_d2_widget_replay.py
tests/js/d2_widget_harness.mjs
docs/tasks/DEMO_D2_STAGE4_MIXED_RESPONSE_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

`app.py`, `core/d2_http_adapter.py`, `static/widget/api.js`,
`static/widget/widget.js`, tenant data and all legacy modules are read-only
evidence. Нельзя добавлять fallback, второй prompt/parser/state/wire contract,
semantic regex или inference по raw dialogue/label.

Владелец 2026-09-25 явно разрешил это единственное расширение allowlist после
Checker finding: `core/response_plan_resolver.py` должен принять exact contact
и policy blocks до своего единственного final UI pass. Это не разрешает иных
изменений архитектуры или wire.

## Приёмка и доказательство

- Applicable A05, A06, A13, A14; B10, B14, B16; C01–C05, C08–C10.
- Raw fake provider проходит production D1R parser, общий D2 route, tenant
  snapshot, frozen plan/store и реальные JSON/SSE endpoints.
- Проверить content + price + policy, content + unavailable price + contact,
  request-part order/status, frozen source ownership, UI suppression и replay.
- JSON↔SSE parity: answer, UI, actions, revision и request ID равны; replay
  после изменения temporary tenant copy не делает provider call и не меняет
  результат.
- Browser harness использует payload реального endpoint, показывает один
  mixed-answer bubble и сохраняет typed action/retry semantics.
- Tests используют temporary DB, logs и tenant copy с blocked network;
  provider/live/SMTP calls = 0.

## Форма checkpoint

- **D2 ROUTE:** production parser → `run_d2_dialogue_turn` → tenant snapshot
  → frozen plan/store → `/ask` или `/ask/stream` → widget harness.
- **LEGACY IMPACT:** Composer, sales_fast, legacy semantic selectors, legacy
  ordinary memory и fallback не подключаются.
- **OWNER DECISION:** не требуется для exact typed policy composition и
  price partial failure: Target Contract §6–8 уже задаёт поведение. Остановиться
  при необходимости новой policy-gap copy, нового strict gate, terminal-mix,
  tenant/wire change или выхода за allowlist.
- **FUTURE SCOPE:** live provider, полный stage-5 matrix, deploy/merge и
  legacy deletion.
- **Review:** независимый Checker PASS и отдельный Cursor review до commit.
