# Architecture Convergence — канон (2026-07-24)

**Статус:** docs sync @ AC3 complete (`aa8e6dd`) + A9R governance.
**Baseline:** `codex/stage-a` @ `b35ed1c` (AC3 complete). **W1b WIP:** припаркован, см. ниже.

## Что завершено

- Target FullContext product path (S69/S70): `/ask` → planner shadow → target runtime → cached FullContext → Composer → Verifier → widget.
- Offline target data: `service_catalog`, `pricebook`, `clinic_strategy`, `marketing.yaml`, doctors (S1–S27).
- A9 shadow infra; **product authority forbidden**.
- **AC1 ✅** — `EffectiveScope` + typed `UiScopeAction` + session `patient_facts`.
- **AC2 ✅** — offline `run_target_scope_aware_selection` (applicability + S15 + S23/S24).
- **AC3 ✅** — scope-aware price runtime + `ResponseStage` + scope/stage UI (`aa8e6dd`).

## Что не завершено (blockers для «образцовой» клиники)

| Gap | Следствие |
|-----|-----------|
| ~~AC1 scope discarded before dispatch~~ | **Fixed @ AC3 `aa8e6dd`** |
| ~~W1 `family_price_overview` in product path~~ | **Replaced @ AC3** |
| ~~Нет scope button emitter~~ | **Fixed @ AC3** |
| ~~`ResponseStage` не в коде~~ | **Fixed @ AC3** |
| A9 free-text scope | **A9R governance** — authority still forbidden |
| Marketing runtime stub | partial paths still stubbed |
| **FULLCONTEXT_PRESENTATION_PARITY** | Phase 2 @ `7c716df` — partial: presentation decision, cadence, bone_graft; gaps H–N remain |
| **FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE** | gaps H–N: Composer source sidecar, contact PRIMARY_EVIDENCE, channel mutex, situation priority/HTTP tests, `time`/`result_reliability`, fallback phone — governance @ `7c716df`; partial implementation @ `84b2741`–`029c38b` |
| **FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE** | widget runtime seams A–F: provisional marketing gate vs final spec, typed contacts, verifier observability, widget-faithful test matrix — governance @ `81cf09c8`; implementation **STOP** |
| PRICE_SERVICE verification matrix | not fully proven end-to-end |

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

**AC1 product (runtime @ AC3):**

1. explicit current `UiScopeAction`
2. explicit current `UiStageAction`
3. fresh session `patient_facts` (same topic, within turn-age threshold)
4. all-unknown

**Future (A9R3 — docs only until owner GO):** confident current-turn `TurnFrame.patient_scope` projection slots between (2) and (3). See `docs/A9R_GOVERNANCE.md`. Correction replaces stale session; uncertain/conflicting extraction must not overwrite session.

Scope **не выбирает** лечение, протокол или `service_id`. Product code **не читает** `TurnFrame.patient_scope` until A9R3.

## W1b WIP (parked)

Незавершённый W1b **не в рабочем дереве**. Snapshot:

- Path: [`artifacts/w1b_wip_checkpoint_2026-07-24/`](artifacts/w1b_wip_checkpoint_2026-07-24/MANIFEST.txt)
- Checksums: `checksums.sha256`
- Restore: `RESTORE.md` (owner approval)

**Вердикт аудита:** KEEP ref contract + two-phase dispatch; REWORK groups as extent overlay + selection gate; DROP parallel applicability authority.

## Checkpoints (порядок)

1. ~~W1b park + docs sync~~ (2026-07-24)
2. ~~**AC1**~~ (`72681cc`)
3. ~~**AC2**~~ (`5a3a2f8`)
4. ~~**AC3**~~ (`aa8e6dd`)
5. **A9R** — governance re-audit + frozen matrix (`TASK.md`) → A9R1 offline → A9R2 live → A9R3 authority
6. **FULLCONTEXT_PRESENTATION_PARITY** — Phase 2 partial @ `7c716df`
7. **FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE** — dialogue/presentation closure (governance @ `7c716df`) → implementation after owner GO
8. Post-A9 widget E2E
9. Provider prompt caching

См. также: [`A9R_GOVERNANCE.md`](A9R_GOVERNANCE.md), [`ARCH_TARGET_DESIGN.md`](ARCH_TARGET_DESIGN.md), [`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md), [`PATIENT_SCOPE_DESIGN_A9.md`](PATIENT_SCOPE_DESIGN_A9.md).
