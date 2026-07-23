# TASK — S61 correction (target-only ingress, CTA, session, strategy)

**Baseline:** `codex/stage-a` / `8d7463f` · **OFFLINE ONLY · NO LIVE**

## Owner decision

Fix four S61 runtime gaps before any live test. No new architecture, no Verifier semantics change, no authority flip.

**Owner post-code ratification (CTA):** принята clamp-семантика как намеренное изменение контракта:

`effective_include_cta = client_cta_capability AND spec.allow_cta`

Остальные spec permissions остаются fail-closed (`spec_package_permission_forbidden`).

## Governance / checker process (honest record)

| Checkpoint | Verdict | Note |
|---|---|---|
| PRE-CODE checker | **❓ escalation** (not ✅) | CTA boundary + missing acceptance criteria + duplicate scope |
| Implementation | started **before** PRE-CODE gate closed | Commits `4ed1e16`, `7e13fa6` on `codex/stage-a` |
| Owner CTA ratification | **post-code** | Только CTA clamp; остальное — по критериям ниже |
| Final acceptance | **depends on COMPLETION checker** | Independent read-only review on diff `8d7463f…HEAD` |

PRE-CODE **не** считается ✅. Цепочка: PRE-CODE escalation → owner CTA ratification → governance correction → COMPLETION verdict.

## Gaps to fix

1. **Target-only precedence** — flag ON must not hit legacy knowledge short-circuits in pre-resolver (price/consult ref, chunks, promo, continuation, duplicate replay).
2. **CTA permissions** — remove global `include_cta=False`; effective CTA = client capability ∧ spec.allow_cta at spec-bound boundary.
3. **Session frequency** — persist actually selected fact/amplifier/consultation IDs after materialized response.
4. **Strategy context** — remove hardcoded `implantology/full_arch`; derive family from service catalog only; extent only if explicitly authored.

Plus: HTTP integration tests for `/ask` and `/ask/stream`.

## Критерии приёмки (A–E)

### A. Target-only precedence

- [ ] `TARGET_FULLCONTEXT_DEV=0`: legacy pre-resolver и post-resolver path **byte/behavior compatible** (no regression in targeted legacy tests).
- [ ] `TARGET_FULLCONTEXT_DEV=1`: разрешены только common upstream guards (client, reset, rate, noise, ingress hard-stop, lead flows без RAG/chunks).
- [ ] Flag ON: **не вызываются** legacy knowledge short-circuits:
  - price widget ref (`orchestrate_price_widget_ref`);
  - consult symptom ref;
  - `get_chunk_by_ref`;
  - promo overview;
  - current_doc continuation;
  - short-contextual chunk;
  - duplicate replay (`duplicate_short_circuit`).
- [ ] Flag ON: target follow-up ref click (`{ ref, q: "" }`) → target navigation bridge из session follow-ups, **не** legacy chunk resolver; unknown ref → controlled target clarify.
- [ ] Flag ON: **нет** parallel target+legacy и **нет** fallback на legacy после выбора target.

### B. CTA clamp (owner-ratified contract change)

- [ ] Runtime передаёт `include_cta = client_cta_capability` (из client pack / `marketing.cta_contexts`), **не** global True/False.
- [ ] Spec-bound boundary: `effective_include_cta = include_cta AND spec.allow_cta` — **без** `spec_package_permission_forbidden` для cta widen.
- [ ] **Остальные** spec permissions (marketing_facts, consultation_close, terminal payload) остаются fail-closed.
- [ ] `spec.allow_cta=false` → `selected_cta_key is None`, verified response **без CTA**, **без exception**.
- [ ] Normal service/price commercial response с `allow_cta=true` → authored CTA может присутствовать в widget payload.
- [ ] Protected S34 test change **только** для cta: widen-forbid case заменён на clamp test; marketing/consultation widen tests **не ослаблены**.

### C. Session frequency (selected IDs)

- [ ] IDs берутся из authoritative bound package/plan (`TargetMaterializedSessionSelection`), **не** из Composer prose.
- [ ] После materialized response: session merge = `previous ∪ current`, stable dedupe.
- [ ] Terminal/error **не** добавляют shown IDs и **не** затирают предыдущий focus.
- [ ] Target follow-ups сохраняются в session для ref-nav на следующем click.

### D. Service-derived strategy (no A9 authority)

- [ ] Удалён постоянный `TargetStrategyMatch(family="implantology", extent="full_arch")`.
- [ ] `family` — только из structured service catalog для resolved `service_id`.
- [ ] `extent` — только если в catalog `selection.extent` ровно одно authored value; иначе `None`.
- [ ] `service_id=None` → пустой/безопасный match, **не** fabricated family/extent.
- [ ] A9 `patient_scope` **не** влияет на strategy routing.
- [ ] `veneers`/prosthetics → **не** `implantology/full_arch`; `all_on_4` → `implantology` + authored `full_arch`.

### E. HTTP integration (offline)

- [ ] `/ask`, flag OFF: legacy path; target factories **не** вызываются.
- [ ] `/ask`, flag ON: injected fake boundary/Composer/Verifier; один target response; legacy content routing **не** вызывается.
- [ ] `/ask/stream`, flag ON: batch `ui` + `done`; token streaming не требуется; legacy chunk/composer **не** вызываются.
- [ ] Verifier hard block → controlled target response; legacy **не** вызывается.
- [ ] **NO network** in tests/import; fake/recording backends only.

## Do NOT

- LIVE / LLM / authority / A9
- New Verifier milestone / issue kinds
- Change frozen S47/S50/S53/S55/S58 artifacts
- RAG / per-MD routing / shadow branch
- Enable dev flag in running server

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S61 correction governance |
| `docs/STRANGLER_ROADMAP.md` | correction note |
| `contracts/target_turn_frame_dispatch.py` | session selection sidecar |
| `core/target_spec_offline_response_package.py` | effective_include_cta |
| `core/target_session_selection.py` | **new** extract selection from bound package |
| `core/target_policy_bound_verified_response_pipeline.py` | internal bound+verify helper |
| `core/target_turn_frame_bound_response.py` | attach session sidecar |
| `core/target_runtime_strategy.py` | **new** service-derived strategy match |
| `core/target_runtime_client_context.py` | cta_capability; remove hardcoded strategy |
| `core/target_runtime_turn.py` | dynamic strategy + cta_capability |
| `core/target_runtime_session.py` | merge shown IDs; store follow-ups |
| `core/target_runtime_followup_nav.py` | **new** target ref→q bridge |
| `orchestration/pre_resolver_turn.py` | target_fullcontext_mode skips legacy knowledge |
| `orchestration/target_fullcontext_turn.py` | resolve ref before target turn |
| `app.py` | pass target mode to pre-resolver |
| `tests/test_s61_correction_target_runtime.py` | **new** correction acceptance |
| `tests/test_s61_target_fullcontext_runtime.py` | update for corrections |
| `tests/test_target_spec_offline_response_package.py` | CTA clamp test (contract change) |

## Protected / forbidden

- Frozen eval artifacts unchanged
- Verifier S59 semantics unchanged
- S47/S50/S53/S55/S58 byte-identical

## Targeted pytest

```powershell
$bt = Join-Path $env:TEMP ("s61corr_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_spec_offline_response_package.py `
  tests/test_demo_target_marketing_selection.py `
  tests/test_target_boundary_enforced_fullcontext_response.py `
  tests/test_s59_semantic_verifier_policy.py `
  tests/test_fullcontext_verifier_replay_s54.py `
  -q
```

## Commits

1. Governance: TASK.md, STRANGLER note (`4ed1e16`)
2. Implementation: correction modules + tests (`7e13fa6`)
3. Governance correction: TASK acceptance criteria + honest checker record (this commit)
4. Completion: roadmap note after COMPLETION ✅

Push only to `origin/codex/stage-a`.

## PRE-CODE / COMPLETION checker

- PRE-CODE: **❓ escalation** — see «Governance / checker process» above.
- COMPLETION: required on diff `8d7463f…HEAD`; final acceptance only after COMPLETION ✅.
