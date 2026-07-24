# Architecture Convergence — канон (2026-07-24)

**Статус:** docs-only checkpoint после Architecture Convergence Audit.
**Baseline:** `codex/stage-a` @ `57f9067` (AC2 complete). **W1b WIP:** припаркован, см. ниже.

## Что завершено

- Target FullContext product path (S69/S70): `/ask` → planner shadow → target runtime → cached FullContext → Composer → Verifier → widget.
- Offline target data: `service_catalog`, `pricebook`, `clinic_strategy`, `marketing.yaml`, doctors (S1–S27).
- A9 shadow infra; **product authority forbidden**.
- **AC1 ✅** — `EffectiveScope` + typed `UiScopeAction` + session `patient_facts`.
- **AC2 ✅** — offline `run_target_scope_aware_selection` (applicability + S15 + S23/S24).

## Что не завершено (blockers для «образцовой» клиники)

| Gap | Следствие |
|-----|-----------|
| AC1 scope discarded before dispatch | `target_runtime_turn.py` вычисляет `effective_scope`, но не передаёт в price path |
| W1 `family_price_overview` в product path | selection без `service_catalog.selection`; scope не влияет на цены |
| Нет scope button emitter | `build_ui_scope_ref` только в тестах; виджет не показывает «Один зуб / …» |
| `ResponseStage` не в коде | broad vs scoped ответ не различается детерминированно |
| Marketing runtime stub | `marketing_scenarios=()` на части путей; family overview запрещает CTA |
| PRICE_SERVICE verification matrix | не доказана end-to-end в product path |

## Единый pipeline (target)

```text
message / typed UI action
  → CurrentTurnScope (UiScopeAction + session; A9 future)
  → EffectiveScope
  → catalog.selection ∩ active
  → clinic_strategy
  → pricebook
  → ResponseSpec (+ marketing / follow-up / CTA)
  → Composer + Verifier + widget
```

(`ResponseStage` enum — **AC3**; derived from EffectiveScope + AC2 result, not a second selector.)

## Source owners

| Домен | Owner |
|-------|-------|
| Scope facts | `PatientScopeFrame` + session `patient_facts` |
| UI extent click | typed `UiScopeAction` (canonical extent) |
| Applicability | `service_catalog.selection` |
| Priority | `clinic_strategy.yaml` |
| Price | `pricebook` |
| Marketing text | `facts.json` + KB |
| Marketing policy | `marketing.yaml` |
| Situation nav buttons | extent-keyed client labels + `target:ui_scope/` refs (AC3 emitter) |
| Session | `target_runtime_session` |

## EffectiveScope priority

**AC1 product (runtime):**

1. explicit current `UiScopeAction`
2. fresh session `patient_facts` (same topic)
3. all-unknown

**Future (after A9 authority — docs only, not AC1):** current-turn A9 `patient_scope` may slot between (1) and (2). Free-text correction — after A9 quality proof.

Scope **не выбирает** лечение, протокол или `service_id`. AC1 product code **не читает** `TurnFrame.patient_scope`.

## W1b WIP (parked)

Незавершённый W1b **не в рабочем дереве**. Snapshot:

- Path: [`artifacts/w1b_wip_checkpoint_2026-07-24/`](artifacts/w1b_wip_checkpoint_2026-07-24/MANIFEST.txt)
- Checksums: `checksums.sha256`
- Restore: `RESTORE.md` (owner approval)

**Вердикт аудита:** KEEP ref contract + two-phase dispatch; REWORK groups as extent overlay + selection gate; DROP parallel applicability authority.

## Checkpoints (порядок)

1. ~~W1b park + docs sync~~ (2026-07-24)
2. ~~**AC1** — `EffectiveScope` + typed `UiScopeAction` + session `patient_facts`~~ (`72681cc`)
3. ~~**AC2** — scope-aware selection component (offline, unwired)~~ (`5a3a2f8`)
4. **AC3** — atomic runtime wiring + ResponseStage + scope/follow-up/marketing/CTA (`TASK.md`)
5. A9 v2 live re-audit (owner approval) — free-text scope authority
6. Full HTTP/widget matrix → live E2E
7. Provider prompt caching

См. также: [`ARCH_TARGET_DESIGN.md`](ARCH_TARGET_DESIGN.md), [`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md), [`PATIENT_SCOPE_DESIGN_A9.md`](PATIENT_SCOPE_DESIGN_A9.md).
