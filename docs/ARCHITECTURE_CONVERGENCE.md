# Architecture Convergence — канон (2026-07-24)

**Статус:** docs-only checkpoint после Architecture Convergence Audit.  
**Baseline:** `codex/stage-a` @ `eedbd66`. **W1b WIP:** припаркован, см. ниже.

## Что завершено

- Target FullContext product path (S69/S70): `/ask` → planner shadow → target runtime → cached FullContext → Composer → Verifier → widget.
- Offline target data: `service_catalog`, `pricebook`, `clinic_strategy`, `marketing.yaml`, doctors (S1–S27).
- A9 shadow infra; **product authority forbidden**.

## Что не завершено (blockers для «образцовой» клиники)

| Gap | Следствие |
|-----|-----------|
| Нет `EffectiveScope` в runtime | scope не переносится между ходами |
| UI click → label → planner | extent угадывается повторно |
| `service_catalog.selection` не в product path | applicability обходится ad-hoc (W1b groups) |
| `clinic_strategy` extent rules не wired | приоритет без фильтра |
| Session без `patient_facts` | повтор situation menu |
| Marketing runtime stub | `marketing_scenarios=()`, no initial block |
| PRICE_SERVICE verification matrix | не доказана |

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

(`ResponseStage` enum — post-AC1 checkpoint; not in AC1 scope.)

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
| Situation nav buttons | extent-keyed overlay (evolution of W1b) |
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

1. ~~W1b park + docs sync~~ (этот checkpoint)  
2. **AC1** — `EffectiveScope` + typed `UiScopeAction` + session `patient_facts` (`TASK.md`)
3. Service selection + strategy + pricebook wiring
4. Response stages + marketing runtime
5. A9 v2 live re-audit (owner approval)  
6. Full HTTP/widget matrix → live E2E  
7. Provider prompt caching  

См. также: [`ARCH_TARGET_DESIGN.md`](ARCH_TARGET_DESIGN.md), [`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md), [`PATIENT_SCOPE_DESIGN_A9.md`](PATIENT_SCOPE_DESIGN_A9.md).
